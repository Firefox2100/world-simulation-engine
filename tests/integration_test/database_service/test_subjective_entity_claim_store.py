from datetime import UTC, datetime, timedelta
from uuid import uuid4

from world_simulation_engine.misc.enums import MemoryStance, MemorySupportType, Salience, TurnType
from world_simulation_engine.model import (
    Event, Location, MemoryAtom, RelationshipEntityRef, Simulation, SubjectiveClaimChangeAudit,
    SubjectiveEntityClaim, Turn,
)
from world_simulation_engine.service.database.event_store import EventStore
from world_simulation_engine.service.database.location_store import LocationStore
from world_simulation_engine.service.database.memory_store import CharacterMemoryLink, MemoryStore
from world_simulation_engine.service.database.simulation_store import SimulationStore
from world_simulation_engine.service.database.subjective_entity_claim_store import SubjectiveEntityClaimStore
from world_simulation_engine.service.database.turn_store import TurnStore
from tests.integration_test.database_service.helpers import create_character, create_world


async def test_claim_crud_is_observer_scoped_versioned_and_audited(clean_neo4j):
    world = await create_world(clean_neo4j)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    simulation = Simulation(id=str(uuid4()), name="Claims", current_time=now)
    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)
    observer = await create_character(clean_neo4j, simulation.id, name="Observer")
    other = await create_character(clean_neo4j, simulation.id, name="Other")
    turn = Turn(id=str(uuid4()), sequence=1, type=TurnType.USER_INPUT, content="Other hesitates.", start_time=now)
    event = Event(id=str(uuid4()), name="Hesitation", summary="Other hesitated.")
    memory = MemoryAtom(id=str(uuid4()), summary="Other hesitated.", keywords=["hesitated"], embedding=None)
    await TurnStore(clean_neo4j).create_turn(turn, source_id=simulation.id)
    await EventStore(clean_neo4j).create_event(event, turn_ids=[turn.id])
    await MemoryStore(clean_neo4j).create_memory_atom(
        memory, event_id=event.id, support_type=MemorySupportType.DIRECT,
        character_links=[CharacterMemoryLink(character_id=observer.id, confidence=.8, salience=Salience.HIGH,
                                             stance=MemoryStance.REMEMBER)],
    )
    claim = SubjectiveEntityClaim(
        simulation_id=simulation.id, observer_character_id=observer.id,
        subject=RelationshipEntityRef(type="character", id=other.id, name=other.name),
        category="personality", statement="Other may be cautious.",
        normalized_statement="other may be cautious", stance="suspects", confidence=.45,
        supporting_memory_ids=[memory.id], first_observed_at=now, last_updated_at=now,
    )
    store = SubjectiveEntityClaimStore(clean_neo4j)
    assert await store.create_claim(claim) == claim
    assert await store.list_claims(simulation_id=simulation.id, observer_character_id=observer.id) == [claim]
    assert await store.list_claims(simulation_id=simulation.id, observer_character_id=other.id) == []
    updated = claim.model_copy(update={"confidence": .55, "version": 2,
                                       "last_updated_at": now + timedelta(minutes=1)})
    assert await store.update_claim(updated) == updated
    audit = SubjectiveClaimChangeAudit(
        claim_id=claim.id, simulation_id=simulation.id, observer_character_id=observer.id,
        turn_id=turn.id, evidence_memory_ids=[memory.id], changed_at=updated.last_updated_at,
        change_type="update", previous_version=1, new_version=2,
        previous_state=claim.model_dump(mode="json"), new_state=updated.model_dump(mode="json"),
    )
    assert await store.create_change_audit(audit) == audit


async def test_claim_about_world_scoped_location_subject_can_be_created(clean_neo4j):
    """Locations are attached to the World, not the Simulation. A claim's subject-reachability
    check (scoped to the Simulation) must still find them via Simulation-[:BASED_ON]->World, not
    only entities attached directly to the Simulation or the previously Item-only special case.
    """
    world = await create_world(clean_neo4j)
    now = datetime(2026, 1, 1, tzinfo=UTC)
    simulation = Simulation(id=str(uuid4()), name="Location claims", current_time=now)
    await SimulationStore(clean_neo4j).create_simulation(simulation, world.id)
    observer = await create_character(clean_neo4j, simulation.id, name="Observer")
    location = Location(id=str(uuid4()), name="Old Mine Entrance", description="A sealed mine entrance.")
    await LocationStore(clean_neo4j).create_location(location=location, source_id=world.id)

    claim = SubjectiveEntityClaim(
        simulation_id=simulation.id, observer_character_id=observer.id,
        subject=RelationshipEntityRef(type="location", id=location.id, name=location.name),
        category="risk", statement="The old mine entrance feels unsafe.",
        normalized_statement="the old mine entrance feels unsafe", stance="believes", confidence=.6,
        supporting_memory_ids=[], first_observed_at=now, last_updated_at=now,
    )
    store = SubjectiveEntityClaimStore(clean_neo4j)
    assert await store.create_claim(claim) == claim
