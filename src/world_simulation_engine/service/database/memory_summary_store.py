from uuid import uuid4

from world_simulation_engine.model import Event, Intent, MemoryAtom, MemorySummaryProposal

from .event_store import EventStore
from .intent_store import IntentStore
from .memory_store import CharacterMemoryLink, MemoryStore


class MemorySummaryStore:
    def __init__(self,
                 event_store: EventStore,
                 memory_store: MemoryStore,
                 intent_store: IntentStore,
                 ):
        self._event = event_store
        self._memory = memory_store
        self._intent = intent_store

    async def apply_memory_summary_proposal(self,
                                            proposal: MemorySummaryProposal,
                                            turn_id: str,
                                            ):
        for operation in proposal.operations:
            if operation.type == "create_event":
                event = Event(
                    id=operation.proposed_id or str(uuid4()),
                    name=operation.name,
                    summary=operation.summary,
                )
                turn_ids = operation.turn_ids or [turn_id]
                await self._event.create_event(event=event, turn_ids=turn_ids)
                for involvement in operation.involved_characters:
                    await self._event.add_character_involvement(
                        event_id=event.id,
                        character_id=involvement.character_id,
                        involvement=involvement.involvement,
                    )
            elif operation.type == "link_turn_to_event":
                await self._event.add_turn_to_event(
                    event_id=operation.event_id,
                    turn_id=operation.turn_id,
                )
            elif operation.type == "update_event":
                await self._event.update_event(
                    event_id=operation.event_id,
                    name=operation.name,
                    summary=operation.summary,
                )
                for involvement in operation.involved_characters:
                    await self._event.add_character_involvement(
                        event_id=operation.event_id,
                        character_id=involvement.character_id,
                        involvement=involvement.involvement,
                    )
            elif operation.type == "create_memory":
                await self._memory.create_memory_atom(
                    memory=MemoryAtom(
                        id=operation.proposed_id or str(uuid4()),
                        summary=operation.summary,
                        keywords=operation.keywords,
                        embedding=None,
                    ),
                    event_id=operation.event_id,
                    support_type=operation.support_type,
                    character_links=[
                        CharacterMemoryLink(
                            character_id=link.character_id,
                            confidence=link.confidence,
                            salience=link.salience,
                            behavioural_relevance=link.behavioural_relevance,
                            stance=link.stance,
                        )
                        for link in operation.character_links
                    ],
                )
            elif operation.type == "link_existing_memory":
                await self._memory.add_character_memory(
                    memory_id=operation.memory_id,
                    character_link=CharacterMemoryLink(
                        character_id=operation.character_link.character_id,
                        confidence=operation.character_link.confidence,
                        salience=operation.character_link.salience,
                        behavioural_relevance=operation.character_link.behavioural_relevance,
                        stance=operation.character_link.stance,
                    ),
                )
            elif operation.type == "create_intent":
                intent = Intent(
                    id=operation.proposed_id or str(uuid4()),
                    type=operation.intent_type,
                    name=operation.name,
                    description=operation.description,
                    keywords=operation.keywords,
                    embedding=None,
                    priority=operation.priority,
                    urgency=operation.urgency,
                    status=operation.status,
                    desired_state=operation.desired_state,
                    success_conditions=operation.success_conditions,
                    failure_conditions=operation.failure_conditions,
                    maintenance_conditions=operation.maintenance_conditions,
                    deadline=operation.deadline,
                    horizon=operation.horizon,
                    constraints=operation.constraints,
                    current_plan=operation.current_plan,
                    next_action_biases=operation.next_action_biases,
                    blockers=operation.blockers,
                    open_threads=operation.open_threads,
                )
                await self._intent.create_intent(
                    intent=intent,
                    character_id=operation.character_id,
                )
                if operation.created_by_event_id:
                    await self._intent.add_event_creation(
                        event_id=operation.created_by_event_id,
                        intent_id=intent.id,
                    )
            elif operation.type == "update_intent":
                await self._intent.update_intent(
                    intent_id=operation.intent_id,
                    properties={
                        "status": operation.status,
                        "priority": operation.priority,
                        "urgency": operation.urgency,
                        "current_plan": operation.current_plan,
                        "next_action_biases": operation.next_action_biases,
                        "blockers": operation.blockers,
                        "open_threads": operation.open_threads,
                    },
                )
                if operation.event_id and operation.event_relationship == "contributes_to":
                    await self._intent.add_event_contribution(
                        event_id=operation.event_id,
                        intent_id=operation.intent_id,
                    )
                elif operation.event_id and operation.event_relationship == "creates":
                    await self._intent.add_event_creation(
                        event_id=operation.event_id,
                        intent_id=operation.intent_id,
                    )
