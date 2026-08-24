"""Capture and restore a simulation's full mutable entity graph - the primitive behind turn
regeneration ("swipe") and, later, undoing an OOC-forced world state mutation.

A GraphStateSnapshot (graph_state_snapshot_store.py) only captures transient LangGraph proposal
state; it says nothing about the actual persisted Neo4j entities (character state, item locations,
variables, relationships, memories, ...). This service captures/restores exactly that, paired with
GraphStateSnapshot at the same simulation_id/turn boundary via WorldStateCheckpoint.

Restore always follows the same three-phase order, never interleaved per entity type:
1. create-missing + force-overwrite-existing, in dependency order (an entity referencing another
   must be created after the entity it references already exists/is restored)
2. re-home placement relationships (owner/holder/location/landmark/equipped) for every captured
   character/item_stack/equipment/container, whether freshly created or overwritten
3. delete-extra (present now, absent from the checkpoint), leaf-to-root, so nothing worth keeping
   (already re-homed in step 2) gets collaterally destroyed by a cascading delete
"""

from typing import Any

from world_simulation_engine.misc.enums import WorldStateCheckpointType
from world_simulation_engine.model import BackgroundCharacter, Character, Container, \
    EmotionState, EntityRelationship, EntityVariableSet, Equipment, Event, Item, ItemStack, \
    MemoryAtom, SubjectiveEntityClaim, Turn, WorldStateCheckpoint
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink
from world_simulation_engine.service.database.service import DatabaseService


class SimulationStateCheckpointService:
    def __init__(self, database: DatabaseService):
        self._db = database

    # ------------------------------------------------------------------ capture

    async def capture(
            self,
            *,
            simulation_id: str,
            type: WorldStateCheckpointType,
            turn: Turn | None,
    ) -> WorldStateCheckpoint:
        characters = await self._db.character.list_characters(simulation_id=simulation_id)
        character_positions = await self._db.character.get_position_map(source_id=simulation_id)
        background_characters = await self._db.character.list_background_characters(simulation_id=simulation_id)
        background_positions = await self._db.character.get_background_position_map(source_id=simulation_id)

        items = await self._db.item.list_items(simulation_id=simulation_id)
        item_stacks = await self._db.item.list_stacks(simulation_id=simulation_id)

        equipment_list = await self._db.equipment.list_equipment(simulation_id=simulation_id)
        hold_types = await self._db.equipment.get_hold_types([entry.id for entry in equipment_list])

        containers = await self._db.container.list_containers(simulation_id=simulation_id)
        unlocking_items = {
            container.id: [item.id for item in await self._db.container.get_unlocking_items(container.id)]
            for container in containers
        }

        variable_sets = await self._db.variable.list_variable_sets_by_source(simulation_id)

        entity_relationships = await self._db.entity_relationship.list_relationships(
            scope_id=simulation_id,
            active_only=False,
            limit=100_000,
        )

        character_ids = [character.id for character in characters]
        emotion_states = []
        for character_id in character_ids:
            state = await self._db.emotion.get_state(simulation_id=simulation_id, character_id=character_id)
            if state:
                emotion_states.append(state)

        subjective_entity_claims: list[SubjectiveEntityClaim] = []
        for character_id in character_ids:
            subjective_entity_claims.extend(await self._db.subjective_entity_claim.list_claims(
                simulation_id=simulation_id,
                observer_character_id=character_id,
                active_only=False,
                limit=1000,
            ))

        memories = await self._db.memory.list_memories(simulation_id=simulation_id)
        memory_ids = [memory.id for memory in memories]
        memory_event_links = await self._db.memory.get_event_links(memory_ids)
        memory_character_links = await self._db.memory.get_character_links(memory_ids)

        events = await self._db.event.list_events(simulation_id=simulation_id)
        event_ids = [event.id for event in events]
        event_turn_links = await self._db.event.get_turn_links(event_ids)
        event_involvements = await self._db.event.get_character_involvements(event_ids)

        checkpoint = WorldStateCheckpoint(
            simulation_id=simulation_id,
            type=type,
            turn_id=turn.id if turn else None,
            turn_sequence=turn.sequence if turn else None,
            characters=[
                {"entity": character.model_dump(mode="json"), **character_positions.get(character.id, {})}
                for character in characters
            ],
            background_characters=[
                {"entity": character.model_dump(mode="json"), **background_positions.get(character.id, {})}
                for character in background_characters
            ],
            items=[{"entity": item.model_dump(mode="json")} for item in items],
            item_stacks=[{"entity": stack.model_dump(mode="json")} for stack in item_stacks],
            equipment=[
                {
                    "entity": entry.model_dump(mode="json"),
                    **hold_types.get(entry.id, {"equipped": False, "equipped_position": None}),
                }
                for entry in equipment_list
            ],
            containers=[
                {
                    "entity": container.model_dump(mode="json"),
                    "unlocking_item_ids": unlocking_items.get(container.id, []),
                }
                for container in containers
            ],
            variable_sets=[{"entity": entry.model_dump(mode="json")} for entry in variable_sets],
            entity_relationships=[{"entity": entry.model_dump(mode="json")} for entry in entity_relationships],
            emotion_states=[{"entity": entry.model_dump(mode="json")} for entry in emotion_states],
            subjective_entity_claims=[{"entity": entry.model_dump(mode="json")} for entry in subjective_entity_claims],
            memories=[
                {
                    "entity": memory.model_dump(mode="json"),
                    "event_id": memory_event_links.get(memory.id, {}).get("event_id"),
                    "support_type": memory_event_links.get(memory.id, {}).get("support_type"),
                    "character_links": memory_character_links.get(memory.id, []),
                }
                for memory in memories
            ],
            events=[
                {
                    "entity": event.model_dump(mode="json"),
                    "turn_ids": event_turn_links.get(event.id, []),
                    "involvements": event_involvements.get(event.id, []),
                }
                for event in events
            ],
        )
        return await self._db.world_state_checkpoint.save_checkpoint(checkpoint)

    # ------------------------------------------------------------------ restore

    async def restore(self, *, simulation_id: str, checkpoint: WorldStateCheckpoint) -> None:
        if checkpoint.turn_sequence is not None:
            await self._db.turn.delete_turns_after(simulation_id, checkpoint.turn_sequence)

        current_character_ids = {
            entry.id for entry in await self._db.character.list_characters(simulation_id=simulation_id)
        }
        current_background_ids = {
            entry.id for entry in await self._db.character.list_background_characters(simulation_id=simulation_id)
        }
        current_item_ids = {entry.id for entry in await self._db.item.list_items(simulation_id=simulation_id)}
        current_stack_ids = {entry.id for entry in await self._db.item.list_stacks(simulation_id=simulation_id)}
        current_equipment_ids = {
            entry.id for entry in await self._db.equipment.list_equipment(simulation_id=simulation_id)
        }
        current_container_ids = {
            entry.id for entry in await self._db.container.list_containers(simulation_id=simulation_id)
        }
        current_variable_set_ids = {
            entry.id for entry in await self._db.variable.list_variable_sets_by_source(simulation_id)
        }
        current_relationship_ids = {
            entry.id for entry in await self._db.entity_relationship.list_relationships(
                scope_id=simulation_id, active_only=False, limit=100_000,
            )
        }
        current_memory_ids = {entry.id for entry in await self._db.memory.list_memories(simulation_id=simulation_id)}
        current_event_ids = {entry.id for entry in await self._db.event.list_events(simulation_id=simulation_id)}

        all_character_ids = current_character_ids | {
            entry["entity"]["id"] for entry in checkpoint.characters
        }
        current_emotion_ids = set()
        current_claim_ids = set()
        for character_id in all_character_ids:
            state = await self._db.emotion.get_state(simulation_id=simulation_id, character_id=character_id)
            if state:
                current_emotion_ids.add(state.id)
            current_claim_ids.update(
                claim.id for claim in await self._db.subjective_entity_claim.list_claims(
                    simulation_id=simulation_id, observer_character_id=character_id,
                    active_only=False, limit=1000,
                )
            )

        # Phase 1: create-missing + force-overwrite-existing, dependency order.
        for entry in checkpoint.characters:
            await self._restore_character(entry, simulation_id=simulation_id)
        for entry in checkpoint.background_characters:
            await self._restore_background_character(entry, simulation_id=simulation_id)
        for entry in checkpoint.items:
            await self._restore_item(entry, simulation_id=simulation_id)
        for entry in checkpoint.item_stacks:
            await self._restore_item_stack(entry, simulation_id=simulation_id)
        for entry in checkpoint.equipment:
            await self._restore_equipment(entry, simulation_id=simulation_id)
        for entry in checkpoint.containers:
            await self._restore_container(entry, simulation_id=simulation_id)
        for entry in checkpoint.variable_sets:
            await self._restore_variable_set(entry)
        for entry in checkpoint.events:
            await self._restore_event(entry)
        for entry in checkpoint.memories:
            await self._restore_memory(entry)
        for entry in checkpoint.emotion_states:
            await self._restore_emotion_state(entry)
        for entry in checkpoint.entity_relationships:
            await self._restore_relationship(entry)
        for entry in checkpoint.subjective_entity_claims:
            await self._restore_claim(entry)

        # Phase 2: re-home placement relationships for every captured character/stack/equipment/
        # container, whether freshly created or overwritten above.
        for entry in checkpoint.characters:
            await self._rehome_character(entry)
        for entry in checkpoint.background_characters:
            await self._rehome_background_character(entry)
        for entry in checkpoint.item_stacks:
            await self._rehome_item_stack(entry)
        for entry in checkpoint.equipment:
            await self._rehome_equipment(entry)
        for entry in checkpoint.containers:
            await self._rehome_container(entry)

        # Phase 3: delete-extra (present now, absent from the checkpoint), leaf-to-root.
        captured_relationship_ids = {entry["entity"]["id"] for entry in checkpoint.entity_relationships}
        captured_claim_ids = {entry["entity"]["id"] for entry in checkpoint.subjective_entity_claims}
        captured_emotion_ids = {entry["entity"]["id"] for entry in checkpoint.emotion_states}
        captured_variable_set_ids = {entry["entity"]["id"] for entry in checkpoint.variable_sets}
        captured_memory_ids = {entry["entity"]["id"] for entry in checkpoint.memories}
        captured_event_ids = {entry["entity"]["id"] for entry in checkpoint.events}
        captured_stack_ids = {entry["entity"]["id"] for entry in checkpoint.item_stacks}
        captured_equipment_ids = {entry["entity"]["id"] for entry in checkpoint.equipment}
        captured_container_ids = {entry["entity"]["id"] for entry in checkpoint.containers}
        captured_item_ids = {entry["entity"]["id"] for entry in checkpoint.items}
        captured_background_ids = {entry["entity"]["id"] for entry in checkpoint.background_characters}
        captured_character_ids = {entry["entity"]["id"] for entry in checkpoint.characters}

        for relationship_id in current_relationship_ids - captured_relationship_ids:
            await self._db.entity_relationship.delete_relationship(relationship_id)
        for claim_id in current_claim_ids - captured_claim_ids:
            await self._db.subjective_entity_claim.delete_claim(claim_id)
        for emotion_id in current_emotion_ids - captured_emotion_ids:
            await self._db.emotion.delete_state(emotion_id)
        for variable_set_id in current_variable_set_ids - captured_variable_set_ids:
            await self._db.variable.delete_variable_set(variable_set_id)
        for memory_id in current_memory_ids - captured_memory_ids:
            await self._db.memory.delete_memory(memory_id)
        for event_id in current_event_ids - captured_event_ids:
            await self._db.event.delete_event(event_id)
        for stack_id in current_stack_ids - captured_stack_ids:
            await self._db.item.delete_stack(stack_id)
        for equipment_id in current_equipment_ids - captured_equipment_ids:
            await self._db.equipment.delete_equipment(equipment_id)
        for container_id in current_container_ids - captured_container_ids:
            await self._db.container.delete_container(container_id)
        for item_id in current_item_ids - captured_item_ids:
            await self._db.item.delete_item(item_id)
        for background_id in current_background_ids - captured_background_ids:
            await self._db.character.delete_background_character(background_id)
        for character_id in current_character_ids - captured_character_ids:
            await self._db.character.delete_character(character_id)

    # ---------------------------------------------------------- phase 1: create/overwrite

    async def _restore_character(self, entry: dict[str, Any], *, simulation_id: str) -> None:
        character = Character.model_validate(entry["entity"])
        if await self._db.character.overwrite_character(character) is None:
            await self._db.character.create_character(
                character,
                source_id=simulation_id,
                location_id=entry.get("location_id"),
                position=entry.get("position"),
                landmark_id=entry.get("landmark_id"),
            )

    async def _restore_background_character(self, entry: dict[str, Any], *, simulation_id: str) -> None:
        character = BackgroundCharacter.model_validate(entry["entity"])
        if await self._db.character.overwrite_background_character(character) is None:
            await self._db.character.create_background_character(
                character,
                source_id=simulation_id,
                location_id=entry.get("location_id"),
                position=entry.get("position"),
                landmark_id=entry.get("landmark_id"),
            )

    async def _restore_item(self, entry: dict[str, Any], *, simulation_id: str) -> None:
        item = Item.model_validate(entry["entity"])
        if await self._db.item.overwrite_item(item) is None:
            await self._db.item.create_item(item, source_id=simulation_id)

    async def _restore_item_stack(self, entry: dict[str, Any], *, simulation_id: str) -> None:
        stack = ItemStack.model_validate(entry["entity"])
        if await self._db.item.overwrite_stack(stack) is None:
            await self._db.item.create_stack(
                item_id=stack.item.id,
                stack=stack,
                source_id=simulation_id,
                location_id=stack.location_id,
                position=stack.position,
                holder_id=stack.holder_id,
                owner_id=stack.owner_id,
            )

    async def _restore_equipment(self, entry: dict[str, Any], *, simulation_id: str) -> None:
        equipment = Equipment.model_validate(entry["entity"])
        if await self._db.equipment.overwrite_equipment(equipment) is None:
            await self._db.equipment.create_equipment(
                equipment,
                source_id=simulation_id,
                location_id=equipment.location_id,
                position=equipment.position,
            )

    async def _restore_container(self, entry: dict[str, Any], *, simulation_id: str) -> None:
        container = Container.model_validate(entry["entity"])
        if await self._db.container.overwrite_container(container) is None:
            await self._db.container.create_container(
                container,
                source_id=simulation_id,
                location_id=container.location_id,
                position=container.position,
            )

    async def _restore_variable_set(self, entry: dict[str, Any]) -> None:
        variable_set = EntityVariableSet.model_validate(entry["entity"])
        if await self._db.variable.force_set_variable_set(variable_set) is None:
            await self._db.variable.create_variable_set(variable_set)

    async def _restore_event(self, entry: dict[str, Any]) -> None:
        event = Event.model_validate(entry["entity"])
        turn_ids = entry.get("turn_ids") or []
        overwritten = await self._db.event.overwrite_event(event) is not None
        if not overwritten:
            if not turn_ids:
                return
            await self._db.event.create_event(event, turn_ids=turn_ids)
        if turn_ids:
            await self._db.event.replace_event_turns(event.id, turn_ids)
        await self._db.event.replace_character_involvements(event.id, entry.get("involvements") or [])

    async def _restore_memory(self, entry: dict[str, Any]) -> None:
        memory = MemoryAtom.model_validate(entry["entity"])
        event_id = entry.get("event_id")
        support_type = entry.get("support_type")
        character_links = [
            CharacterMemoryLink.model_validate(link)
            for link in entry.get("character_links") or []
        ]
        overwritten = await self._db.memory.overwrite_memory(memory) is not None
        if not overwritten:
            if not event_id or not character_links:
                return
            await self._db.memory.create_memory_atom(
                memory, event_id=event_id, support_type=support_type, character_links=character_links,
            )
            return
        if event_id:
            await self._db.memory.link_memory_event(memory.id, event_id, support_type)
        if character_links:
            await self._db.memory.replace_character_memories(memory.id, character_links)

    async def _restore_emotion_state(self, entry: dict[str, Any]) -> None:
        state = EmotionState.model_validate(entry["entity"])
        if await self._db.emotion.force_set_state(state) is None:
            await self._db.emotion.create_state(state)

    async def _restore_relationship(self, entry: dict[str, Any]) -> None:
        relationship = EntityRelationship.model_validate(entry["entity"])
        if await self._db.entity_relationship.force_set_relationship(relationship) is None:
            await self._db.entity_relationship.create_relationship(relationship)

    async def _restore_claim(self, entry: dict[str, Any]) -> None:
        claim = SubjectiveEntityClaim.model_validate(entry["entity"])
        if await self._db.subjective_entity_claim.force_set_claim(claim) is None:
            if claim.world_id:
                await self._db.subjective_entity_claim.create_world_claim(claim)
            else:
                await self._db.subjective_entity_claim.create_claim(claim)

    # ---------------------------------------------------------- phase 2: re-home

    async def _rehome_character(self, entry: dict[str, Any]) -> None:
        character_id = entry["entity"]["id"]
        location_id = entry.get("location_id")
        landmark_id = entry.get("landmark_id")
        if location_id:
            await self._db.character.move_to_location(character_id, location_id, entry.get("position"))
        else:
            await self._db.character.remove_character_location(character_id)
        if landmark_id:
            await self._db.character.anchor_to_landmark(character_id, landmark_id)
        else:
            await self._db.character.remove_character_landmark(character_id)

    async def _rehome_background_character(self, entry: dict[str, Any]) -> None:
        character_id = entry["entity"]["id"]
        location_id = entry.get("location_id")
        landmark_id = entry.get("landmark_id")
        if location_id:
            await self._db.character.move_background_character_to_location(
                character_id, location_id, entry.get("position"),
            )
        else:
            await self._db.character.remove_background_character_location(character_id)
        if landmark_id:
            await self._db.character.anchor_background_character_to_landmark(character_id, landmark_id)
        else:
            await self._db.character.remove_background_character_landmark(character_id)

    async def _rehome_item_stack(self, entry: dict[str, Any]) -> None:
        stack = entry["entity"]
        if stack.get("holder_id"):
            await self._db.item.assign_stack(stack["id"], holder_id=stack["holder_id"])
        elif stack.get("location_id"):
            await self._db.item.place_stack_in_location(stack["id"], stack["location_id"], stack.get("position"))
        if stack.get("owner_id"):
            await self._db.item.assign_stack(stack["id"], owner_id=stack["owner_id"])
        else:
            await self._db.item.remove_stack_owner(stack["id"])

    async def _rehome_equipment(self, entry: dict[str, Any]) -> None:
        equipment = entry["entity"]
        if equipment.get("holder_id"):
            await self._db.equipment.change_hold_state(
                equipment["id"],
                equipment["holder_id"],
                equipped=bool(entry.get("equipped")),
                equipped_position=entry.get("equipped_position"),
            )
        elif equipment.get("location_id"):
            await self._db.equipment.place_equipment_in_location(
                equipment["id"], equipment["location_id"], equipment.get("position"),
            )
        else:
            await self._db.equipment.remove_location(equipment["id"])
            await self._db.equipment.remove_holder(equipment["id"])
        if equipment.get("owner_id"):
            await self._db.equipment.change_owner(equipment["id"], equipment["owner_id"])
        else:
            await self._db.equipment.remove_owner(equipment["id"])

    async def _rehome_container(self, entry: dict[str, Any]) -> None:
        container = entry["entity"]
        if container.get("holder_id"):
            await self._db.container.assign_container(container["id"], holder_id=container["holder_id"])
        elif container.get("location_id"):
            await self._db.container.place_container_in_location(
                container["id"], container["location_id"], container.get("position"),
            )
        else:
            await self._db.container.remove_location(container["id"])
            await self._db.container.remove_holder(container["id"])
        if container.get("owner_id"):
            await self._db.container.assign_container(container["id"], owner_id=container["owner_id"])
        else:
            await self._db.container.remove_owner(container["id"])
        await self._db.container.replace_unlocking_items(container["id"], entry.get("unlocking_item_ids") or [])
