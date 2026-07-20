from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import ComponentType
from world_simulation_engine.model import Character, Location, NarrationBlock, NarrationInsertionProposal, \
    NarrationProposal, SceneCoordinationResult, Simulation, SpeechAnchor, SpeechBlock, World

from .simulator_component import SimulatorComponent


class NarrationActorContext(BaseModel):
    character: Character
    location: Location | None = None


class NarratorContext(BaseModel):
    world: World
    simulation: Simulation
    user_input: str | None = None
    user_character_id: str | None = None
    coordination_result: SceneCoordinationResult
    actors: list[NarrationActorContext] = Field(default_factory=list)
    speech_anchors: list[SpeechAnchor] = Field(default_factory=list)


class Narrator(SimulatorComponent):
    COMPONENT_TYPE = ComponentType.NARRATOR

    async def _build_context(self,
                             *,
                             world_id: str,
                             simulation_id: str,
                             coordination_result: SceneCoordinationResult,
                             user_input: str | None = None,
                             ) -> NarratorContext:
        world = await self._db.world.get_world(world_id)
        if not world:
            raise ValueError(f"World {world_id} not found in database")

        simulation = await self._db.simulation.get_simulation(simulation_id)
        if not simulation:
            raise ValueError(f"Simulation {simulation_id} not found in database")

        user_character = await self._db.character.get_user_character_by_simulation(simulation_id)
        actor_ids = {
            action.actor_id
            for action in coordination_result.accepted_actions
        }
        actor_ids.update(
            action.actor_id
            for action in coordination_result.pending_actions
        )
        if coordination_result.problem:
            actor_ids.update(coordination_result.problem.involved_actor_ids)

        actors = []
        for actor_id in sorted(actor_ids):
            character = await self._db.character.get_character(actor_id)
            if not character:
                continue

            actors.append(
                NarrationActorContext(
                    character=character,
                    location=await self._db.location.get_location_by_character(actor_id),
                )
            )

        actor_names = {
            actor.character.id: actor.character.name
            for actor in actors
        }
        speech_anchors = [
            SpeechAnchor(
                index=len([
                    accepted
                    for accepted in coordination_result.accepted_actions[:action_index]
                    if accepted.action.utterance
                ]),
                character_id=action.actor_id,
                character_name=actor_names.get(action.actor_id),
                text=action.action.utterance,
                action_summary=action.summary,
            )
            for action_index, action in enumerate(coordination_result.accepted_actions)
            if action.action.utterance
        ]

        return NarratorContext(
            world=world,
            simulation=simulation,
            user_input=user_input,
            user_character_id=user_character.id if user_character else None,
            coordination_result=coordination_result,
            actors=actors,
            speech_anchors=speech_anchors,
        )

    async def narrate_turn(self,
                           *,
                           world_id: str,
                           simulation_id: str,
                           coordination_result: SceneCoordinationResult,
                           user_input: str | None = None,
                           ) -> NarrationProposal:
        context = await self._build_context(
            world_id=world_id,
            simulation_id=simulation_id,
            coordination_result=coordination_result,
            user_input=user_input,
        )
        prompt = await self._prepare_prompt(
            simulation_id=simulation_id,
            language=context.world.language,
            prompt_name="narrator",
        )
        llm = await self._prepare_llm_service(simulation_id=simulation_id)

        insertion_proposal = await llm.invoke_structured_with_repair(
            output_model=NarrationInsertionProposal,
            messages=prompt,
            data=context.model_dump(),
            run_name="narrator.narrate_turn",
            repair_instruction=(
                "Return a NarrationInsertionProposal JSON object only. Top-level key: insertions. "
                "Do not include speech blocks. Speech is fixed by speech_anchors and will be composed by code. "
                "Use insertions only for observable non-verbal narration."
            ),
        )

        return self._compose_narration_blocks(
            insertion_proposal=insertion_proposal,
            context=context,
        )

    @classmethod
    def render_text(cls, proposal: NarrationProposal | str | None) -> str:
        if proposal is None:
            return ""

        if isinstance(proposal, str):
            return proposal

        paragraphs = []
        for block in proposal.blocks:
            if isinstance(block, SpeechBlock):
                speaker = block.character_name or block.character_id
                paragraphs.append(f'{speaker}: "{block.text}"')
            else:
                paragraphs.append(block.text)

        return "\n\n".join(paragraphs)

    @classmethod
    def serialize_content(cls, proposal: NarrationProposal | str | None) -> str:
        if proposal is None:
            return ""

        if isinstance(proposal, str):
            return proposal

        return proposal.model_dump_json()

    @classmethod
    def _compose_narration_blocks(cls,
                                  *,
                                  insertion_proposal: NarrationInsertionProposal,
                                  context: NarratorContext,
                                  ) -> NarrationProposal:
        blocks = []
        insertions_by_position: dict[int, list[NarrationBlock]] = {}
        max_position = len(context.speech_anchors)
        for insertion in insertion_proposal.insertions:
            position = min(insertion.position, max_position)
            insertions_by_position.setdefault(position, []).append(
                NarrationBlock(
                    type="narration",
                    text=insertion.text,
                )
            )

        if context.speech_anchors:
            for position, speech_anchor in enumerate(context.speech_anchors):
                blocks.extend(insertions_by_position.pop(position, []))
                blocks.append(
                    SpeechBlock(
                        type="speech",
                        character_id=speech_anchor.character_id,
                        character_name=speech_anchor.character_name,
                        text=speech_anchor.text,
                    )
                )

            blocks.extend(insertions_by_position.pop(max_position, []))
        else:
            blocks = [
                NarrationBlock(
                    type="narration",
                    text=action.summary,
                )
                for action in context.coordination_result.accepted_actions
                if action.summary
            ]
            for insertion_blocks in insertions_by_position.values():
                blocks.extend(insertion_blocks)

        return NarrationProposal(blocks=blocks)
