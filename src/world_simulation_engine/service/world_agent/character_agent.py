from typing import Any, cast
from pydantic import TypeAdapter

from world_simulation_engine.misc.consts import LOGGER
from world_simulation_engine.model import Location, Character, WorldEntry, Task, Item, Equipment, \
    CharacterAgentProfile, CharacterBriefing, PendingGeneratedProposal, CharacterActionOutput
from .world_agent import WorldAgent


class CharacterAgent(WorldAgent[CharacterAgentProfile]):
    async def generate_action(self,
                              character: Character,
                              briefing: CharacterBriefing,
                              current_location: Location,
                              visible_characters: list[Character],
                              tasks: list[Task],
                              world_entries: list[WorldEntry],
                              inventory: list[Item],
                              equipments: list[Equipment],
                              proposals: list[PendingGeneratedProposal],
                              user_input: str | None = None,
                              last_narration: str | None = None,
                              previous_resolver_notes: str | None = None,
                              ):
        LOGGER.info("Generating action for character %s", character.id)

        data = {
            "character": character,
            "briefing": briefing,
            "current_location": current_location,
            "visible_characters": visible_characters,
            "tasks": tasks,
            "world_entries": world_entries,
            "inventory": inventory,
            "equipments": equipments,
            "pending_generated_proposals": proposals,
            "user_input": user_input,
            "last_narration": last_narration,
            "previous_resolver_notes": previous_resolver_notes,
        }
        LOGGER.debug("Base data:\n%s", TypeAdapter(dict[str, Any]).dump_json(data, indent=2).decode())

        messages = self._compose_messages(
            prompts=self.profile.action_prompt,
            data=data,
        )
        LOGGER.debug("Messages:\n%s", "\n".join([f"{m.type}: {m.content}" for m in messages]))

        structured_model = self.model.with_structured_output(CharacterActionOutput)
        return cast(CharacterActionOutput, await structured_model.ainvoke(messages))
