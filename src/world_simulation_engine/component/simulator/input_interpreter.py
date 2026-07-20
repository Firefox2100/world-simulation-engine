from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from world_simulation_engine.misc.enums import ActionType, ComponentType
from world_simulation_engine.model import BackgroundCharacter, Character, Container, Equipment, InventoryEquipment, \
    InventoryStack, Item, ItemStack, Landmark, Location, OOCCommand, Simulation, World, InputInterpretation, \
    ProposedAction, UserActionSequenceItem

from .simulator_component import SimulatorComponent


class InputSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int
    type: Literal["in_world", "ooc"]
    source_text: str
    command_text: str | None = None


class LocatedCharacter(BaseModel):
    character: Character
    location: Location
    position: str | None = None
    landmark: Landmark | None = None


class LocatedBackgroundCharacter(BaseModel):
    character: BackgroundCharacter
    location: Location
    position: str | None = None
    landmark: Landmark | None = None


class LocatedItemStack(BaseModel):
    item: Item
    stack: ItemStack
    location: Location
    position: str | None = None
    owner_id: str | None = None


class LocatedEquipment(BaseModel):
    equipment: Equipment
    location: Location
    position: str | None = None
    owner_id: str | None = None


class LocatedContainer(BaseModel):
    container: Container
    location: Location
    position: str | None = None
    owner_id: str | None = None


class InputInterpreterContext(BaseModel):
    world: World
    simulation: Simulation
    actor: Character
    location: Location

    inventory: list[InventoryStack] = Field(default_factory=list)
    equipment: list[InventoryEquipment] = Field(default_factory=list)

    perceived_characters: list[LocatedCharacter] = Field(default_factory=list)
    perceived_background_characters: list[LocatedBackgroundCharacter] = Field(default_factory=list)
    perceived_items: list[LocatedItemStack] = Field(default_factory=list)
    perceived_equipment: list[LocatedEquipment] = Field(default_factory=list)
    perceived_containers: list[LocatedContainer] = Field(default_factory=list)
    perceived_landmarks: list[Landmark] = Field(default_factory=list)

    input_segments: list[InputSegment] = Field(default_factory=list)
    user_input: str


@dataclass(frozen=True)
class InputMarkup:
    speech: list[str]
    internal_dialog: list[str]


class InputInterpreter(SimulatorComponent):
    COMPONENT_TYPE = ComponentType.INPUT_INTERPRETER

    _OOC_MARKER_PATTERN = re.compile(r"\[/OOC:(.*?)\]", flags=re.DOTALL)
    _SPEECH_SIMILARITY_THRESHOLD = 0.82

    @staticmethod
    def validate_markup(user_input: str) -> InputMarkup:
        speeches = []
        internal_dialog = []
        mode: str | None = None
        emphasis_open = False
        buffer = []
        index = 0

        while index < len(user_input):
            char = user_input[index]
            next_two = user_input[index:index + 2]

            if char == "\\":
                if mode:
                    buffer.append(char)
                if index + 1 < len(user_input):
                    if mode:
                        buffer.append(user_input[index + 1])
                    index += 2
                    continue

            if next_two == "**":
                emphasis_open = not emphasis_open
                if mode:
                    buffer.append(next_two)
                index += 2
                continue

            if char == '"':
                if mode == "internal":
                    raise ValueError("Internal dialog cannot contain speech quotes.")
                if mode == "speech":
                    speeches.append("".join(buffer))
                    buffer = []
                    mode = None
                else:
                    mode = "speech"
                    buffer = []
                index += 1
                continue

            if char == "*":
                if mode == "speech":
                    raise ValueError("Speech cannot contain internal-dialog markers.")
                if mode == "internal":
                    internal_dialog.append("".join(buffer))
                    buffer = []
                    mode = None
                else:
                    mode = "internal"
                    buffer = []
                index += 1
                continue

            if mode:
                buffer.append(char)
            index += 1

        if mode == "speech":
            raise ValueError('Speech quote is not closed with ".')
        if mode == "internal":
            raise ValueError("Internal dialog is not closed with *.")
        if emphasis_open:
            raise ValueError("Emphasis is not closed with **.")

        if any(not speech.strip() for speech in speeches):
            raise ValueError("Speech quotes cannot be empty.")
        if any(not thought.strip() for thought in internal_dialog):
            raise ValueError("Internal dialog markers cannot be empty.")

        return InputMarkup(
            speech=[speech.strip() for speech in speeches],
            internal_dialog=[thought.strip() for thought in internal_dialog],
        )

    @classmethod
    def _split_ooc_markers(cls, user_input: str) -> list[InputSegment]:
        """
        Split raw input into in-world and OOC segments while preserving source order.

        Only exact closed markers of the form [/OOC: ...] are treated as OOC.
        """

        segments: list[InputSegment] = []
        cursor = 0

        for match in cls._OOC_MARKER_PATTERN.finditer(user_input):
            if match.start() > cursor:
                source_text = user_input[cursor:match.start()]
                if source_text.strip():
                    segments.append(
                        InputSegment(
                            index=len(segments) + 1,
                            type="in_world",
                            source_text=source_text,
                        )
                    )

            source_text = match.group(0)
            segments.append(
                InputSegment(
                    index=len(segments) + 1,
                    type="ooc",
                    source_text=source_text,
                    command_text=match.group(1).strip(),
                )
            )
            cursor = match.end()

        if cursor < len(user_input):
            source_text = user_input[cursor:]
            if source_text.strip():
                segments.append(
                    InputSegment(
                        index=len(segments) + 1,
                        type="in_world",
                        source_text=source_text,
                    )
                )

        return segments

    @staticmethod
    def _build_ooc_only_interpretation(segments: list[InputSegment]) -> InputInterpretation:
        return InputInterpretation(
            items=[
                OOCCommand(
                    command_text=segment.command_text or "",
                    normalized_intent=segment.command_text or "",
                    source_text=segment.source_text,
                )
                for segment in segments
                if segment.type == "ooc"
            ],
            unparsed_text=[],
            parser_notes=[
                "Input contained only OOC markers; no in-world action interpretation was needed.",
            ],
        )

    async def _build_context(self,
                             *,
                             world_id: str,
                             simulation_id: str,
                             character_id: str,
                             user_input: str,
                             input_segments: list[InputSegment],
                             ) -> InputInterpreterContext:
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")

        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")

        actor = await self._db.character.get_character(character_id)
        if not actor:
            raise ValueError(f"Character {character_id} not found in database")

        location = await self._db.location.get_location_by_character(character_id)
        if not location:
            raise ValueError(f"Character {character_id} is not in a location")

        inventory = await self._db.item.get_inventory(character_id)
        equipment = await self._db.equipment.get_equipment_inventory(character_id)
        characters = await self._db.get_characters_in_location(location.id)
        background_characters = await self._db.character.get_background_characters_by_location(location.id)
        items = await self._db.item.get_stacks_by_location(location.id)
        location_equipment = await self._db.equipment.get_equipment_by_location(location.id)
        containers = await self._db.container.get_containers_by_location(location.id)
        landmarks = await self._db.location.get_landmarks_by_location(location.id)

        return InputInterpreterContext(
            world=world,
            simulation=simulation,
            actor=actor,
            location=location,
            inventory=inventory,
            equipment=equipment,
            perceived_characters=[
                LocatedCharacter(
                    character=character,
                    location=character_location,
                    position=position,
                    landmark=landmark,
                )
                for character, character_location, position, landmark in characters
                if character.id != character_id
            ],
            perceived_background_characters=[
                LocatedBackgroundCharacter(
                    character=character,
                    location=character_location,
                    position=position,
                    landmark=landmark,
                )
                for character, character_location, position, landmark in background_characters
            ],
            perceived_items=[
                LocatedItemStack(
                    item=item,
                    stack=stack,
                    location=item_location,
                    position=position,
                    owner_id=owner_id,
                )
                for item, stack, item_location, position, owner_id in items
            ],
            perceived_equipment=[
                LocatedEquipment(
                    equipment=entry,
                    location=equipment_location,
                    position=position,
                    owner_id=owner_id,
                )
                for entry, equipment_location, position, owner_id in location_equipment
            ],
            perceived_containers=[
                LocatedContainer(
                    container=container,
                    location=container_location,
                    position=position,
                    owner_id=owner_id,
                )
                for container, container_location, position, owner_id in containers
            ],
            perceived_landmarks=landmarks,
            input_segments=input_segments,
            user_input=user_input,
        )

    async def interpret(self,
                        *,
                        world_id: str,
                        simulation_id: str,
                        character_id: str,
                        user_input: str,
                        ) -> InputInterpretation:
        markup = self.validate_markup(user_input)
        segments = self._split_ooc_markers(user_input)
        has_in_world_text = any(segment.type == "in_world" for segment in segments)

        if not segments:
            return InputInterpretation(
                items=[],
                unparsed_text=[],
                parser_notes=["Raw input contained no non-whitespace text."],
            )

        if not has_in_world_text:
            return self._build_ooc_only_interpretation(segments)

        context = await self._build_context(
            world_id=world_id,
            simulation_id=simulation_id,
            character_id=character_id,
            user_input=user_input,
            input_segments=segments,
        )

        prompt = self._prepare_prompt(
            language=context.world.language,
            prompt_name="input_interpreter",
        )
        llm = await self._prepare_llm_service(simulation_id=simulation_id)

        interpretation = await llm.invoke_structured_with_repair(
            output_model=InputInterpretation,
            messages=prompt,
            data=context.model_dump(),
            repair_instruction=(
                "Return a valid InputInterpretation. Preserve deterministic OOC "
                "segments exactly and keep all items in source order. Any text inside double quotes must be copied "
                "exactly into a speak action utterance."
            ),
            run_name="input_interpreter.interpret",
        )

        self._ensure_no_other_character_control(
            interpretation=interpretation,
            context=context,
        )
        return self._ensure_quoted_speech_actions(
            interpretation=interpretation,
            markup=markup,
        )

    @classmethod
    def _ensure_quoted_speech_actions(cls,
                                      *,
                                      interpretation: InputInterpretation,
                                      markup: InputMarkup,
                                      ) -> InputInterpretation:
        if not markup.speech:
            return interpretation

        updated_items = list(interpretation.items)
        action_items = [
            item
            for item in updated_items
            if item.type == "action"
        ]
        changed = False
        used_action_indices: set[int] = set()

        for speech in markup.speech:
            match_index = cls._matching_speech_action_index(
                speech=speech,
                action_items=action_items,
                used_action_indices=used_action_indices,
            )
            if match_index is None:
                updated_items.append(
                    UserActionSequenceItem(
                        action=ProposedAction(
                            type=ActionType.SPEAK,
                            label="speak_quoted_input",
                            target_ids=[],
                            utterance=speech,
                            intended_duration_seconds=max(1, min(30, len(speech.split()) // 3 + 2)),
                            interruptible=True,
                        ),
                        source_text=f'"{speech}"',
                    )
                )
                changed = True
                continue

            used_action_indices.add(match_index)
            item = action_items[match_index]
            if item.action.utterance != speech:
                item.action = item.action.model_copy(update={"utterance": speech})
                changed = True

        if not changed:
            return interpretation

        return interpretation.model_copy(
            update={
                "items": updated_items,
                "parser_notes": [
                    *interpretation.parser_notes,
                    "Quoted speech was normalized into speak action utterance.",
                ],
            }
        )

    @classmethod
    def _matching_speech_action_index(cls,
                                      *,
                                      speech: str,
                                      action_items: list,
                                      used_action_indices: set[int],
                                      ) -> int | None:
        empty_speech_index = None
        for index, item in enumerate(action_items):
            if index in used_action_indices or item.action.type != ActionType.SPEAK:
                continue
            utterance = (item.action.utterance or "").strip()
            if not utterance:
                if empty_speech_index is None:
                    empty_speech_index = index
                continue
            if utterance == speech:
                return index
            if difflib.SequenceMatcher(None, utterance, speech).ratio() >= cls._SPEECH_SIMILARITY_THRESHOLD:
                return index

        return empty_speech_index

    @staticmethod
    def _ensure_no_other_character_control(
            *,
            interpretation: InputInterpretation,
            context: InputInterpreterContext,
    ):
        other_names = []
        for entry in context.perceived_characters:
            name = entry.character.name.strip()
            if name:
                other_names.append(name)
                other_names.append(name.split()[0])

        action_verbs = (
            "answers",
            "asks",
            "decides",
            "does",
            "goes",
            "moves",
            "says",
            "speaks",
            "takes",
            "tells",
            "walks",
        )
        for item in interpretation.items:
            if item.type != "action":
                continue
            source = item.source_text.strip().lower()
            for name in other_names:
                normalized_name = name.lower()
                if any(source.startswith(f"{normalized_name} {verb}") for verb in action_verbs):
                    raise ValueError(
                        "User input may only describe actions attempted by the user character. "
                        f"Other character action was found in: {item.source_text}"
                    )
