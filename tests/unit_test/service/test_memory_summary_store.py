from unittest.mock import AsyncMock, Mock

from world_simulation_engine.misc.enums import EventInvolvement, IntentHorizon, IntentStatus, IntentType, MemoryStance, \
    MemorySupportType, Salience
from world_simulation_engine.model import MemorySummaryProposal
from world_simulation_engine.service.database.memory_summary_store import MemorySummaryStore


async def test_apply_memory_summary_proposal_delegates_event_memory_and_intent_changes():
    event_store = Mock()
    event_store.create_event = AsyncMock()
    event_store.add_character_involvement = AsyncMock()
    event_store.add_turn_to_event = AsyncMock()
    event_store.update_event = AsyncMock()
    memory_store = Mock()
    memory_store.create_memory_atom = AsyncMock(return_value=Mock())
    memory_store.add_character_memory = AsyncMock(return_value=True)
    intent_store = Mock()
    intent_store.create_intent = AsyncMock()
    intent_store.update_intent = AsyncMock()
    intent_store.add_event_creation = AsyncMock()
    intent_store.add_event_contribution = AsyncMock()
    store = MemorySummaryStore(
        event_store=event_store,
        memory_store=memory_store,
        intent_store=intent_store,
    )
    proposal = MemorySummaryProposal.model_validate(
        {
            "operations": [
                {
                    "type": "create_event",
                    "proposed_id": "evt_event_1",
                    "name": "Glass Taken",
                    "summary": "Alex takes the glass.",
                    "turn_ids": ["turn_1"],
                    "involved_characters": [
                        {
                            "character_id": "character_1",
                            "involvement": EventInvolvement.PARTICIPATE,
                        }
                    ],
                    "reason": "The turn starts a notable interaction.",
                },
                {
                    "type": "create_memory",
                    "proposed_id": "memory_1",
                    "event_id": "evt_event_1",
                    "summary": "Alex took the glass.",
                    "keywords": ["glass"],
                    "support_type": MemorySupportType.DIRECT,
                    "character_links": [
                        {
                            "character_id": "character_1",
                            "confidence": 1,
                            "salience": Salience.MEDIUM,
                            "stance": MemoryStance.REMEMBER,
                        }
                    ],
                    "reason": "Alex should remember taking the glass.",
                },
                {
                    "type": "create_intent",
                    "proposed_id": "int_intent_1",
                    "character_id": "character_1",
                    "intent_type": IntentType.AGENDA,
                    "name": "Keep the glass",
                    "description": "Hold onto the glass.",
                    "priority": 0.4,
                    "urgency": 0.2,
                    "status": IntentStatus.ACTIVE,
                    "horizon": IntentHorizon.SHORT,
                    "created_by_event_id": "evt_event_1",
                    "reason": "The action created a small agenda.",
                },
            ],
        }
    )

    result = await store.apply_memory_summary_proposal(proposal=proposal, turn_id="turn_1")

    event_store.create_event.assert_awaited_once()
    event_store.add_character_involvement.assert_awaited_once_with(
        event_id="evt_event_1",
        character_id="character_1",
        involvement=EventInvolvement.PARTICIPATE,
    )
    memory_store.create_memory_atom.assert_awaited_once()
    intent_store.create_intent.assert_awaited_once()
    intent_store.add_event_creation.assert_awaited_once_with(
        event_id="evt_event_1",
        intent_id="int_intent_1",
    )
    assert result.created_memory_ids == ["memory_1"]
    assert result.memory_ids_by_character == {"character_1": ["memory_1"]}


async def test_apply_memory_summary_proposal_skips_unresolvable_memory_creation():
    event_store = Mock()
    memory_store = Mock()
    memory_store.create_memory_atom = AsyncMock(
        side_effect=ValueError("Could not create memory atom because the event or one or more characters were not found")
    )
    memory_store.add_character_memory = AsyncMock()
    intent_store = Mock()
    store = MemorySummaryStore(
        event_store=event_store,
        memory_store=memory_store,
        intent_store=intent_store,
    )
    proposal = MemorySummaryProposal.model_validate(
        {
            "operations": [
                {
                    "type": "create_memory",
                    "proposed_id": "memory_1",
                    "event_id": "event_1",
                    "summary": "Alex took the glass.",
                    "support_type": MemorySupportType.DIRECT,
                    "character_links": [
                        {
                            "character_id": "missing_character",
                            "confidence": 1,
                            "salience": Salience.MEDIUM,
                            "stance": MemoryStance.REMEMBER,
                        }
                    ],
                    "reason": "Alex should remember taking the glass.",
                },
                {
                    "type": "no_abstract_change",
                    "reason": "No further changes.",
                },
            ],
        }
    )

    await store.apply_memory_summary_proposal(proposal=proposal, turn_id="turn_1")

    memory_store.create_memory_atom.assert_awaited_once()
