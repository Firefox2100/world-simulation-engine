import asyncio
import json
import operator
from uuid import uuid4
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Annotated, Callable, Awaitable
from langchain_core.runnables import RunnableConfig
from langgraph.constants import START, END
from langgraph.graph.state import StateGraph, CompiledStateGraph
from langgraph.types import Send
from langfuse.langchain import CallbackHandler
from pydantic import BaseModel, Field

from world_simulation_engine.misc.enums import FactionRelationshipEntity
from world_simulation_engine.model import Simulation, SimulationState, LlmConnectionProfile, DirectorOutput, \
    PendingGeneratedProposal, CharacterBriefing, BriefingOutput, CharacterActionOutput, CharacterInventory, \
    ResolverOutput, Faction, FactionRelationship, CommitterFinalOutput, CharacterReactionContext, \
    FailedCharacterRecord
from world_simulation_engine.service import DatabaseService, EmbeddingService, DirectorAgent, WorldGeneratorAgent, \
    MemoryAgent, CharacterAgent, ResolverAgent, CommitterAgent, NarratorAgent
from .world_entry_recaller import WorldEntryRecaller


class ConnectionProfileCache(BaseModel):
    director: LlmConnectionProfile | None = None
    memory: LlmConnectionProfile | None = None
    character: LlmConnectionProfile | None = None
    resolver: LlmConnectionProfile | None = None
    committer: LlmConnectionProfile | None = None
    narrator: LlmConnectionProfile | None = None
    world_generator: LlmConnectionProfile | None = None

    embedding: LlmConnectionProfile | None = None


class TurnGeneratorState(BaseModel):
    run_id: str
    simulation_id: int
    user_input: str | None = None

    simulation: Simulation | None = None
    state: SimulationState | None = None
    connection_profiles: ConnectionProfileCache = Field(default_factory=ConnectionProfileCache)

    director_output: DirectorOutput | None = None
    generated_proposals: list[PendingGeneratedProposal] | None = None
    briefing_output: BriefingOutput | None = None
    character_action_outputs: Annotated[
        list[CharacterActionOutput],
        operator.add,
    ] = Field(default_factory=list)
    character_reaction_outputs: Annotated[
        list[CharacterActionOutput],
        operator.add,
    ] = Field(default_factory=list)
    resolver_output: ResolverOutput | None = None
    reaction_resolver_output: ResolverOutput | None = None
    committer_output: CommitterFinalOutput | None = None
    narration: str | None = None


class CharacterActionState(BaseModel):
    user_input: str | None
    simulation: Simulation | None
    state: SimulationState | None
    connection_profiles: ConnectionProfileCache
    generated_proposals: list[PendingGeneratedProposal] | None = None
    briefing: CharacterBriefing


class CharacterReactionState(BaseModel):
    user_input: str | None
    simulation: Simulation | None
    state: SimulationState | None
    connection_profiles: ConnectionProfileCache
    generated_proposals: list[PendingGeneratedProposal] | None = None
    reaction_context: CharacterReactionContext


@dataclass
class WorkflowRunHandle:
    queue: asyncio.Queue[dict[str, Any]] = field(default_factory=asyncio.Queue)
    done: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task | None = None


class TurnGenerator:
    def __init__(self,
                 database_service: DatabaseService,
                 ):
        self._db = database_service

    @staticmethod
    def _dedupe_relationships(relationships: list[FactionRelationship]) -> list[FactionRelationship]:
        seen = set()
        result = []
        for relationship in relationships:
            key = (
                relationship.from_type,
                relationship.from_id,
                relationship.to_type,
                relationship.to_id,
                relationship.relationship,
                relationship.private,
            )
            if key in seen:
                continue

            seen.add(key)
            result.append(relationship)

        return result

    @staticmethod
    def _faction_ids_from_relationships(relationships: list[FactionRelationship]) -> list[int]:
        faction_ids = set()
        for relationship in relationships:
            if relationship.from_type == FactionRelationshipEntity.FACTION:
                faction_ids.add(relationship.from_id)
            if relationship.to_type == FactionRelationshipEntity.FACTION:
                faction_ids.add(relationship.to_id)

        return list(faction_ids)

    async def _load_faction_context(
        self,
        simulation_id: int,
        character_ids: list[int] | None = None,
        item_ids: list[int] | None = None,
        include_private: bool = False,
    ) -> tuple[list[Faction], list[FactionRelationship]]:
        entity_refs = [
            (FactionRelationshipEntity.CHARACTER, character_id)
            for character_id in (character_ids or [])
        ] + [
            (FactionRelationshipEntity.ITEM, item_id)
            for item_id in (item_ids or [])
        ]
        if not entity_refs:
            return [], []

        privacy_filter = None if include_private else False
        relationships = await self._db.faction_relationship.list(
            entity_refs=entity_refs or None,
            private=privacy_filter,
        )

        faction_ids = self._faction_ids_from_relationships(relationships)
        if faction_ids:
            faction_relationships = await self._db.faction_relationship.list(
                entity_refs=[
                    (FactionRelationshipEntity.FACTION, faction_id)
                    for faction_id in faction_ids
                ],
                private=privacy_filter,
            )
            relationships = self._dedupe_relationships(relationships + faction_relationships)
            faction_ids = self._faction_ids_from_relationships(relationships)

        if not faction_ids:
            return [], relationships

        factions = await self._db.faction.list(
            simulation_id=simulation_id,
            faction_ids=faction_ids,
        )

        return factions, relationships

    async def _load_character_faction_context(
        self,
        simulation_id: int,
        acting_character_id: int,
        visible_character_ids: list[int],
        item_ids: list[int],
    ) -> tuple[list[Faction], list[FactionRelationship]]:
        public_factions, public_relationships = await self._load_faction_context(
            simulation_id=simulation_id,
            character_ids=[acting_character_id] + visible_character_ids,
            item_ids=item_ids,
            include_private=False,
        )
        private_relationships = await self._db.faction_relationship.list(
            entity_refs=[
                (FactionRelationshipEntity.CHARACTER, acting_character_id),
                *[
                    (FactionRelationshipEntity.ITEM, item_id)
                    for item_id in item_ids
                ],
            ],
            private=True,
        )
        relationships = self._dedupe_relationships(public_relationships + private_relationships)
        faction_ids = self._faction_ids_from_relationships(relationships)

        if not faction_ids:
            return [], relationships

        private_factions = await self._db.faction.list(
            simulation_id=simulation_id,
            faction_ids=faction_ids,
        )
        factions_by_id = {faction.id: faction for faction in public_factions + private_factions}

        return list(factions_by_id.values()), relationships

    async def load_simulation(self, state: TurnGeneratorState) -> dict:
        simulation = await self._db.simulation.get(state.simulation_id)
        simulation_state = await self._db.state.get(state.simulation_id)

        if simulation is None or simulation_state is None:
            raise ValueError(f"Simulation {state.simulation_id} not found")

        connection_ids = {
            simulation.agent_preset.director.backend_configuration.connection,
            simulation.agent_preset.memory.backend_configuration.connection,
            simulation.agent_preset.character.backend_configuration.connection,
            simulation.agent_preset.resolver.backend_configuration.connection,
            simulation.agent_preset.committer.backend_configuration.connection,
            simulation.agent_preset.narrator.backend_configuration.connection,
            simulation.agent_preset.world_generator.backend_configuration.connection,
            simulation.embedding_profile.connection,
        }

        connections = {}
        for connection_id in connection_ids:
            if connection_id is None:
                raise ValueError("Not all connections are configured")

            connection = await self._db.connection.llm.get(connection_id)
            if not connection:
                raise ValueError(f"Connection {connection_id} not found")

            connections[connection_id] = connection

        return {
            "simulation": simulation,
            "state": simulation_state,
            "connection_profiles": ConnectionProfileCache(
                director=connections[simulation.agent_preset.director.backend_configuration.connection],
                memory=connections[simulation.agent_preset.memory.backend_configuration.connection],
                character=connections[simulation.agent_preset.character.backend_configuration.connection],
                resolver=connections[simulation.agent_preset.resolver.backend_configuration.connection],
                committer=connections[simulation.agent_preset.committer.backend_configuration.connection],
                narrator=connections[simulation.agent_preset.narrator.backend_configuration.connection],
                world_generator=connections[simulation.agent_preset.world_generator.backend_configuration.connection],
                embedding=connections[simulation.embedding_profile.connection],
            ),
        }

    async def director_planning(self, state: TurnGeneratorState, config: RunnableConfig) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.director is None:
            raise RuntimeError("Director connection profile not loaded")
        director_agent = DirectorAgent(
            profile=state.simulation.agent_preset.director,
            connection=state.connection_profiles.director,
        )

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")
        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )
        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        if state.connection_profiles.world_generator is None:
            raise RuntimeError("World generator connection profile not loaded")
        generator = WorldGeneratorAgent(
            profile=state.simulation.agent_preset.world_generator,
            connection=state.connection_profiles.world_generator,
        )

        present_characters = await self._db.character.list(
            simulation_id=state.simulation_id,
            location=state.state.scene,
        )
        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError("Current location does not exist")
        all_locations = await self._db.location.list(simulation_id=state.simulation_id)
        existing_items = await self._db.item.list(
            simulation_id=state.simulation_id,
            include_character_items=True,
        )
        existing_equipments = await self._db.equipment.list(
            simulation_id=state.simulation_id,
            include_character_equipment=True,
        )
        factions, faction_relationships = await self._load_faction_context(
            simulation_id=state.simulation_id,
            character_ids=[c.id for c in present_characters],
            item_ids=[i.id for i in existing_items],
            include_private=True,
        )
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation_id)
        world_entries = await self._db.entry.list(
            simulation_id=state.simulation_id,
            search_scope=[0] + [c.id for c in present_characters],
        )
        tasks = await self._db.task.list(
            character_ids=[c.id for c in present_characters],
        )

        generator_tools = generator.get_tools(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            present_characters=present_characters,
            existing_locations=all_locations,
            existing_entities=current_location.entities,
            existing_items=existing_items,
            existing_equipments=existing_equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            entity_types=state.simulation.data_preset.entity_types.keys(),
            config=config,
        )

        if state.user_input:
            recalled_entries = await recaller.recall(
                query=state.user_input,
                entries=world_entries,
                language=state.simulation.language,
            )
        elif last_record:
            recalled_entries = await recaller.recall(
                query=last_record.narration,
                entries=world_entries,
                language=state.simulation.language
            )
        else:
            recalled_entries = await recaller.recall(
                query=None,
                entries=world_entries,
                language=state.simulation.language
            )

        output, proposals = await director_agent.plan_turn(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            present_characters=present_characters,
            relevant_tasks=tasks,
            recalled_world_entries=recalled_entries,
            generation_tools=generator_tools,
            existing_items=existing_items,
            existing_equipments=existing_equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            last_narration=last_record.narration if last_record else None,
            previous_resolver_notes="",
            config=config,
        )

        if not state.simulation.act_for_user:
            # Not allowed to activate user character, force disable
            for activation in output.activations:
                character = next((c for c in present_characters if c.id == activation.character_id))

                if character.user_controlled:
                    activation.activate = False
                    activation.priority = 0

        return {
            "director_output": output,
            "generated_proposals": proposals,
        }

    async def memory_briefing(self, state: TurnGeneratorState, config: RunnableConfig) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.memory is None:
            raise RuntimeError("Memory connection profile not loaded")
        memory_agent = MemoryAgent(
            profile=state.simulation.agent_preset.memory,
            connection=state.connection_profiles.memory,
        )

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")
        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )
        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        if state.director_output is None:
            raise RuntimeError("Director output not generated")

        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError("Current location does not exist")
        active_character_ids = [
            a.character_id
            for a in state.director_output.activations
            if a.activate
        ]
        active_characters = []
        if active_character_ids:
            active_characters = await self._db.character.list(
                simulation_id=state.simulation_id,
                character_ids=active_character_ids
            )
        public_factions, public_faction_relationships = await self._load_faction_context(
            simulation_id=state.simulation_id,
            character_ids=active_character_ids,
            include_private=False,
        )
        tasks = []
        if active_characters:
            tasks = await self._db.task.list(
                character_ids=[c.id for c in active_characters],
                private=False,
            )
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation_id)
        world_entries = await self._db.entry.list(
            simulation_id=state.simulation_id,
            search_scope=[0] + [c.id for c in active_characters],
        )
        if state.user_input:
            recalled_entries = await recaller.recall(
                query=state.director_output.scene_focus + " " + state.user_input,
                entries=world_entries,
                language=state.simulation.language,
            )
        elif last_record:
            recalled_entries = await recaller.recall(
                query=state.director_output.scene_focus + " " + last_record.narration,
                entries=world_entries,
                language=state.simulation.language
            )
        else:
            recalled_entries = await recaller.recall(
                query=state.director_output.scene_focus,
                entries=world_entries,
                language=state.simulation.language
            )

        result = await memory_agent.build_briefings(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            characters=active_characters,
            tasks=tasks,
            world_entries=recalled_entries,
            factions=public_factions,
            faction_relationships=public_faction_relationships,
            pending_generated_proposals=state.generated_proposals,
            user_input=state.user_input,
            last_narration=last_record.narration if last_record else None,
            previous_resolver_notes="",
            config=config,
        )

        return {
            "briefing_output": result,
        }

    async def character_action(self, state: CharacterActionState, config: RunnableConfig) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.character is None:
            raise RuntimeError("Memory connection profile not loaded")
        character_agent = CharacterAgent(
            profile=state.simulation.agent_preset.character,
            connection=state.connection_profiles.character,
        )

        character = await self._db.character.get(state.briefing.character_id)
        if not character:
            raise ValueError(f"Character {state.briefing.character_id} not found")
        current_location = await self._db.location.get(character.location)
        if not current_location:
            raise ValueError(f"Current location {character.location} does not exist")
        present_characters = await self._db.character.list(location=character.location)
        present_characters = [c for c in present_characters if c.id != character.id]
        tasks = await self._db.task.list(
            task_ids=state.briefing.relevant_task_ids,
        )
        world_entries = await self._db.entry.list(
            entry_ids=state.briefing.relevant_world_entry_ids,
        )
        items = await self._db.item.list(character_id=character.id)
        equipments = await self._db.equipment.list(character_id=character.id)
        factions, faction_relationships = await self._load_character_faction_context(
            simulation_id=state.simulation.id,
            acting_character_id=character.id,
            visible_character_ids=[c.id for c in present_characters],
            item_ids=[i.id for i in items],
        )
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation.id)

        result = await character_agent.generate_action(
            character=character,
            briefing=state.briefing,
            current_location=current_location,
            visible_characters=present_characters,
            tasks=tasks,
            world_entries=world_entries,
            inventory=items,
            equipments=equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            proposals=state.generated_proposals or [],
            data_preset=state.simulation.data_preset,
            user_input=state.user_input,
            last_narration=last_record.narration if last_record else None,
            previous_resolver_notes="",
            config=config,
        )

        return {
            "character_action_outputs": [result]
        }

    async def character_reaction(self, state: CharacterReactionState, config: RunnableConfig) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")

        if state.connection_profiles.character is None:
            raise RuntimeError("Memory connection profile not loaded")
        character_agent = CharacterAgent(
            profile=state.simulation.agent_preset.character,
            connection=state.connection_profiles.character,
        )

        character = await self._db.character.get(state.reaction_context.character_id)
        if not character:
            raise ValueError(f"Character {state.reaction_context.character_id} not found")
        current_location = await self._db.location.get(character.location)
        if not current_location:
            raise ValueError(f"Current location {character.location} does not exist")
        present_characters = await self._db.character.list(location=character.location)
        present_characters = [c for c in present_characters if c.id != character.id]
        tasks = await self._db.task.list(
            task_ids=state.reaction_context.relevant_task_ids,
        )
        world_entries = await self._db.entry.list(
            entry_ids=state.reaction_context.relevant_world_entry_ids,
        )
        items = await self._db.item.list(character_id=character.id)
        equipments = await self._db.equipment.list(character_id=character.id)
        factions, faction_relationships = await self._load_character_faction_context(
            simulation_id=state.simulation.id,
            acting_character_id=character.id,
            visible_character_ids=[c.id for c in present_characters],
            item_ids=[i.id for i in items],
        )
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation.id)

        result = await character_agent.generate_reaction(
            character=character,
            reaction_context=state.reaction_context,
            current_location=current_location,
            visible_characters=present_characters,
            tasks=tasks,
            world_entries=world_entries,
            inventory=items,
            equipments=equipments,
            factions=factions,
            faction_relationships=faction_relationships,
            proposals=state.generated_proposals or [],
            data_preset=state.simulation.data_preset,
            user_input=state.user_input,
            last_narration=last_record.narration if last_record else None,
            previous_resolver_notes="",
            config=config,
        )

        return {
            "character_reaction_outputs": [result]
        }

    async def resolve_character_actions(self, state: TurnGeneratorState, config: RunnableConfig) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")
        if not state.briefing_output:
            raise RuntimeError("Briefing output is not generated")
        if not state.character_action_outputs:
            raise RuntimeError("Character action outputs is not generated")

        if state.connection_profiles.resolver is None:
            raise RuntimeError("Resolver connection profile not loaded")
        resolver_agent = ResolverAgent(
            profile=state.simulation.agent_preset.resolver,
            connection=state.connection_profiles.resolver,
        )
        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError(f"Current location {state.state.scene} does not exist")
        characters = await self._db.character.list(
            character_ids=[a.character_id for a in state.character_action_outputs]
        )
        inventory = {}
        item_ids = []
        for character in characters:
            items = await self._db.item.list(character_id=character.id)
            equipments = await self._db.equipment.list(character_id=character.id)
            item_ids.extend([item.id for item in items])
            inventory[character.id] = CharacterInventory(
                items=items,
                equipments=equipments,
            )
        factions, faction_relationships = await self._load_faction_context(
            simulation_id=state.simulation.id,
            character_ids=[character.id for character in characters],
            item_ids=item_ids,
            include_private=True,
        )
        world_entry_ids = set()
        for b in state.briefing_output.briefings:
            world_entry_ids |= set(b.relevant_world_entry_ids)
        world_entries = await self._db.entry.list(entry_ids=list(world_entry_ids))
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation.id)

        result = await resolver_agent.resolve_character_actions(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            characters=characters,
            character_actions=state.character_action_outputs,
            proposals=state.generated_proposals or [],
            inventory=inventory,
            world_entries=world_entries,
            factions=factions,
            faction_relationships=faction_relationships,
            last_narration=last_record.narration if last_record else None,
            previous_resolver_notes="",
            config=config,
        )
        return {
            "resolver_output": result,
        }

    async def resolve_character_reactions(self, state: TurnGeneratorState, config: RunnableConfig) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")
        if not state.character_reaction_outputs:
            raise RuntimeError("Character action outputs is not generated")
        if not state.resolver_output:
            raise RuntimeError("Resolver output is not generated")
        if not state.briefing_output:
            raise RuntimeError("Briefing output is not generated")

        if state.connection_profiles.resolver is None:
            raise RuntimeError("Resolver connection profile not loaded")
        resolver_agent = ResolverAgent(
            profile=state.simulation.agent_preset.resolver,
            connection=state.connection_profiles.resolver,
        )
        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError(f"Current location {state.state.scene} does not exist")
        characters = await self._db.character.list(
            character_ids=[a.character_id for a in state.character_action_outputs]
        )
        inventory = {}
        item_ids = []
        for character in characters:
            items = await self._db.item.list(character_id=character.id)
            equipments = await self._db.equipment.list(character_id=character.id)
            item_ids.extend([item.id for item in items])
            inventory[character.id] = CharacterInventory(
                items=items,
                equipments=equipments,
            )
        factions, faction_relationships = await self._load_faction_context(
            simulation_id=state.simulation.id,
            character_ids=[character.id for character in characters],
            item_ids=item_ids,
            include_private=True,
        )
        world_entry_ids = set()
        for b in state.briefing_output.briefings:
            world_entry_ids |= set(b.relevant_world_entry_ids)
        world_entries = await self._db.entry.list(entry_ids=list(world_entry_ids))
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation.id)

        result = await resolver_agent.resolve_character_reactions(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            characters=characters,
            character_reactions=state.character_reaction_outputs,
            previous_resolver_output=state.resolver_output,
            proposals=state.generated_proposals or [],
            inventory=inventory,
            world_entries=world_entries,
            factions=factions,
            faction_relationships=faction_relationships,
            last_narration=last_record.narration if last_record else None,
            previous_resolver_notes="",
            config=config,
        )

        return {
            "reaction_resolver_output": result,
        }

    async def commit_changes(self, state: TurnGeneratorState, config: RunnableConfig) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")
        if state.connection_profiles.committer is None:
            raise RuntimeError("Committer connection profile not loaded")
        if state.resolver_output is None:
            raise RuntimeError("Resolver output is not generated")

        characters = await self._db.character.list(simulation_id=state.simulation_id)
        locations = await self._db.location.list(simulation_id=state.simulation_id)
        tasks = await self._db.task.list(simulation_id=state.simulation_id)
        world_entries = await self._db.entry.list(simulation_id=state.simulation_id)
        factions = await self._db.faction.list(simulation_id=state.simulation_id)
        faction_relationships = await self._db.faction_relationship.list()

        inventory = {}
        world_items = await self._db.item.list(simulation_id=state.simulation_id)
        world_equipments = await self._db.equipment.list(simulation_id=state.simulation_id)
        inventory[0] = CharacterInventory(
            items=world_items,
            equipments=world_equipments,
        )
        for character in characters:
            items = await self._db.item.list(character_id=character.id)
            equipments = await self._db.equipment.list(character_id=character.id)
            inventory[character.id] = CharacterInventory(
                items=items,
                equipments=equipments,
            )

        committer_agent = CommitterAgent(
            profile=state.simulation.agent_preset.committer,
            connection=state.connection_profiles.committer,
            simulation=state.simulation,
            state=state.state,
            characters=characters,
            locations=locations,
            inventory=inventory,
            factions=factions,
            faction_relationships=faction_relationships,
            tasks=tasks,
            world_entries=world_entries,
        )

        result = await committer_agent.commit_changes(
            user_input=state.user_input,
            director_output=state.director_output,
            briefing_output=state.briefing_output,
            character_actions=state.character_action_outputs,
            resolver_output=state.resolver_output,
            pending_generated_proposals=state.generated_proposals,
        )

        return {
            "committer_output": result,
        }

    async def narrate_resolved_turn(self, state: TurnGeneratorState, config: RunnableConfig) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")
        if not state.resolver_output:
            raise RuntimeError("Resolver output is not generated")

        if state.connection_profiles.narrator is None:
            raise RuntimeError("Narrator connection profile not loaded")
        narrator_agent = NarratorAgent(
            profile=state.simulation.agent_preset.narrator,
            connection=state.connection_profiles.narrator,
        )

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")
        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )
        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        final_resolution = state.reaction_resolver_output \
            if state.reaction_resolver_output else state.resolver_output
        character_actions = state.character_reaction_outputs \
            if state.character_reaction_outputs else state.character_action_outputs
        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError(f"Current location {state.state.scene} does not exist")
        characters = await self._db.character.list(character_ids=[a.character_id for a in character_actions])
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation.id)
        world_entries = await self._db.entry.list(
            simulation_id=state.simulation_id,
            search_scope=[0] + [a.character_id for a in character_actions],
            narration_only=True,
        )
        if state.user_input:
            recalled_entries = await recaller.recall(
                query=state.user_input,
                entries=world_entries,
                language=state.simulation.language,
            )
        else:
            recalled_entries = await recaller.recall(
                query="\n".join(state.resolver_output.narrator_context),
                entries=world_entries,
                language=state.simulation.language,
            )

        result = await narrator_agent.narrate_resolved_turn(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            characters=characters,
            resolver_output=final_resolution,
            user_input=state.user_input,
            character_actions=character_actions,
            director_output=state.director_output,
            last_narration=last_record.narration if last_record else None,
            recent_history_summary=state.state.recent_history_summary,
            long_term_history_summary=state.state.long_term_history_summary,
            world_entries_for_narrator=recalled_entries,
            pending_generated_proposals=state.generated_proposals,
            config=config,
        )

        return {
            "narration": result
        }

    async def narrate_wait_for_user(self, state: TurnGeneratorState, config: RunnableConfig) -> dict:
        if state.simulation is None or state.state is None:
            raise RuntimeError("Simulation is not loaded")
        if not state.director_output:
            raise RuntimeError("Director output not generated")

        if state.connection_profiles.narrator is None:
            raise RuntimeError("Narrator connection profile not loaded")
        narrator_agent = NarratorAgent(
            profile=state.simulation.agent_preset.narrator,
            connection=state.connection_profiles.narrator,
        )

        if state.connection_profiles.embedding is None:
            raise RuntimeError("Embedding service connection profile not loaded")
        embedding_service = EmbeddingService(
            profile=state.simulation.embedding_profile,
            connection=state.connection_profiles.embedding,
        )
        recaller = WorldEntryRecaller(
            embedding_service=embedding_service,
        )

        current_location = await self._db.location.get(state.state.scene)
        if not current_location:
            raise ValueError(f"Current location {state.state.scene} does not exist")
        present_characters = await self._db.character.list(
            simulation_id=state.simulation_id,
            location=state.state.scene,
        )
        last_record = await self._db.record.get_last_record(simulation_id=state.simulation.id)
        world_entries = await self._db.entry.list(
            simulation_id=state.simulation_id,
            search_scope=[0] + [c.character_id for c in present_characters],
            narration_only=True,
        )
        if state.user_input:
            recalled_entries = await recaller.recall(
                query=state.user_input,
                entries=world_entries,
                language=state.simulation.language,
            )
        else:
            recalled_entries = await recaller.recall(
                query=state.director_output.scene_focus,
                entries=world_entries,
                language=state.simulation.language,
            )

        result = await narrator_agent.narrate_wait_for_user(
            simulation=state.simulation,
            state=state.state,
            current_location=current_location,
            characters=present_characters,
            director_output=state.director_output,
            user_input=state.user_input,
            last_narration=last_record.narration if last_record else None,
            recent_history_summary=state.state.recent_history_summary,
            long_term_history_summary=state.state.long_term_history_summary,
            world_entries_for_narrator=recalled_entries,
            config=config,
        )

        return {
            "narration": result
        }

    @staticmethod
    def route_after_director(state: TurnGeneratorState):
        if not state.director_output:
            raise RuntimeError("Director output not generated")

        if not state.director_output.wait_for_user:
            return "memory"

        return "narration"

    @staticmethod
    def route_after_briefing(state: TurnGeneratorState):
        if not state.briefing_output:
            raise RuntimeError("Briefing output not generated")

        return [
            Send(
                "character_action",
                CharacterActionState(
                    simulation=state.simulation,
                    state=state.state,
                    connection_profiles=state.connection_profiles,
                    user_input=state.user_input,
                    generated_proposals=state.generated_proposals,
                    briefing=briefing
                ),
            ) for briefing in state.briefing_output.briefings
        ]

    @staticmethod
    def route_after_resolving(state: TurnGeneratorState):
        if not state.resolver_output:
            raise RuntimeError("Resolver output not generated")

        if not state.resolver_output.failed_characters:
            # All action passed, go for committing and narration
            return ["commit_changes", "narrate_resolved_turn"]

        def build_reaction_context(failed_character: FailedCharacterRecord):
            if not state.briefing_output:
                raise RuntimeError("Briefing output not generated")
            if not state.resolver_output:
                raise RuntimeError("Resolver output not generated")

            original_action = next(
                (action for action in state.character_action_outputs
                 if action.character_id == failed_character.character_id)
            )
            original_briefing = next(
                (briefing for briefing in state.briefing_output.briefings
                 if briefing.character_id == failed_character.character_id)
            )

            return CharacterReactionContext(
                character_id=failed_character.character_id,
                character_name=original_action.character_name,
                original_action=original_action,
                failure_record=failed_character,
                fixed_visible_events=[
                    action.visible_result
                    for action in state.resolver_output.resolved_actions
                    if action.final_status in {
                        "succeeded",
                        "partially_succeeded",
                        "delayed",
                    }
                       and action.actor_id != failed_character.character_id
                ],
                fixed_private_events_for_actor=[e for e in[
                    action.private_result_for_actor
                    for action in state.resolver_output.resolved_actions
                    if action.actor_id == failed_character.character_id
                       and action.private_result_for_actor
                ] if e is not None],
                relevant_task_ids=original_briefing.relevant_task_ids,
                relevant_world_entry_ids=original_briefing.relevant_world_entry_ids,
                changed_scene_context=state.resolver_output.scene_result_summary,
                immediate_failure_context=failed_character.reason,
                retry_number=1,
                max_retries_this_round=1,
                allowed_reaction_scope="respond_to_failure",
                constraints=[
                    "Do not undo fixed resolved events.",
                    "Do not repeat the same failed action without a different method.",
                    "This is the final retry for this round.",
                ],
            )

        return [
            Send(
                "character_reaction",
                CharacterReactionState(
                    simulation=state.simulation,
                    state=state.state,
                    connection_profiles=state.connection_profiles,
                    user_input=state.user_input,
                    generated_proposals=state.generated_proposals,
                    reaction_context=build_reaction_context(failed_character),
                ),
            ) for failed_character in state.resolver_output.failed_characters
        ]

    def build_graph(self):
        graph = StateGraph(TurnGeneratorState)

        graph.add_node("load_simulation", self.load_simulation)
        graph.add_node("director_planning", self.director_planning)
        graph.add_node("memory_briefing", self.memory_briefing)
        graph.add_node("character_action", self.character_action)
        graph.add_node("character_reaction", self.character_reaction)
        graph.add_node("resolve_character_actions", self.resolve_character_actions)
        graph.add_node("resolve_character_reactions", self.resolve_character_reactions)
        graph.add_node("commit_changes", self.commit_changes)
        graph.add_node("narrate_resolved_turn", self.narrate_resolved_turn)
        graph.add_node("narrate_wait_for_user", self.narrate_wait_for_user)

        graph.add_edge(START, "load_simulation")
        graph.add_edge("load_simulation", "director_planning")
        graph.add_conditional_edges(
            "director_planning",
            self.route_after_director,
            {
                "memory": "memory_briefing",
                "narration": "narrate_wait_for_user",
            }
        )
        graph.add_conditional_edges(
            "memory_briefing",
            self.route_after_briefing,
        )
        graph.add_edge("character_action", "resolve_character_actions")
        graph.add_conditional_edges(
            "resolve_character_actions",
            self.route_after_resolving,
        )
        graph.add_edge("character_reaction", "resolve_character_reactions")
        graph.add_edge("resolve_character_reactions", "commit_changes")
        graph.add_edge("resolve_character_reactions", "narrate_resolved_turn")
        graph.add_edge("commit_changes", END)
        graph.add_edge("narrate_resolved_turn", END)
        graph.add_edge("narrate_wait_for_user", END)

        return graph.compile()

    async def write_commits_to_database(self, payload: dict):
        pass


class WorkflowRunner:
    def __init__(self,
                 graph: CompiledStateGraph,
                 langfuse_handler: CallbackHandler,
                 preserve_updates: list[str] | None = None,
                 callback: Callable[[dict], Awaitable] | None = None,
                 ):
        self._graph = graph
        self._langfuse_handler = langfuse_handler
        self._preserve_updates = preserve_updates or []
        self._callback = callback

        self._runs: dict[str, WorkflowRunHandle] = {}

    @staticmethod
    def _format_sse(event: str, data: Any):
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    async def _run_graph(self,
                         run_id: str,
                         input_data: dict[str, Any],
                         handle: WorkflowRunHandle,
                         run_name: str | None = None,
                         metadata: dict | None = None,
                         tags: list[str] | None = None,
                         ):
        payload = {}

        try:
            config: RunnableConfig = {
                "callbacks": [self._langfuse_handler],
                "configurable": {
                    "thread_id": run_id,
                },
            }
            if run_name:
                config["run_name"] = run_name
            if metadata:
                config["metadata"] = metadata
            if tags:
                config["tags"] = tags

            async for mode, chunk in self._graph.astream(
                input_data,
                config=config,
                stream_mode=["updates", "messages"],
            ):
                if mode == "updates":
                    for node_name, update in chunk.items():
                        if node_name in self._preserve_updates:
                            payload.update(update)

                    await handle.queue.put({
                        "event": "stage_update",
                        "data": chunk,
                    })

                elif mode == "messages":
                    await handle.queue.put({
                        "event": "token",
                        "data": chunk,
                    })

            await handle.queue.put({
                "event": "done",
                "data": {"run_id": run_id},
            })
        except asyncio.CancelledError:
            await handle.queue.put({
                "event": "cancelled",
                "data": {"run_id": run_id},
            })
        except Exception as e:
            await handle.queue.put({
                "event": "error",
                "data": {"message": str(e)},
            })
        finally:
            if self._callback:
                await self._callback(payload)

            handle.done.set()

    def has_run(self, run_id: str) -> bool:
        if run_id in self._runs:
            return True

        return False

    async def start(self,
                    input_data: dict[str, Any],
                    run_name: str | None = None,
                    metadata: dict | None = None,
                    tags: list[str] | None = None,
                    ) -> str:
        run_id = str(uuid4())
        handle = WorkflowRunHandle()
        self._runs[run_id] = handle

        input_data["run_id"] = run_id

        handle.task = asyncio.create_task(
            self._run_graph(
                run_id=run_id,
                input_data=input_data,
                handle=handle,
                run_name=run_name,
                metadata=metadata,
                tags=tags,
            )
        )

        return run_id

    async def events(self, run_id: str) -> AsyncIterator[str]:
        handle = self._runs.get(run_id)
        if handle is None:
            yield self._format_sse(
                event="error",
                data={"message": f"Run {run_id} not found"},
            )
            return

        try:
            while True:
                # Exit once producer finished and all buffered events were consumed.
                if handle.done.is_set() and handle.queue.empty():
                    break

                try:
                    event = await asyncio.wait_for(handle.queue.get(), timeout=55)
                except asyncio.TimeoutError:
                    yield self._format_sse(
                        event="ping",
                        data={"message": "ping"},
                    )
                    continue

                yield self._format_sse(
                    event=event["event"],
                    data=event["data"],
                )

                if event["event"] in {"done", "error", "cancelled"}:
                    break
        finally:
            if handle.done.is_set() and handle.queue.empty():
                self._runs.pop(run_id, None)
