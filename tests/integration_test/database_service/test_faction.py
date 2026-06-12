import pytest

from world_simulation_engine.misc.enums import FactionRelationshipEntity
from world_simulation_engine.model import Faction, FactionRelationship


@pytest.fixture(autouse=True)
async def setup(db,
                mock_simulation,
                ):
    await db.simulation.create(mock_simulation)


async def test_create_and_get_faction(db,
                                      mock_factions,
                                      ):
    result = await db.faction.create(
        faction=mock_factions[0],
        simulation_id=1,
    )

    fetched = await db.faction.get(result.id)

    assert isinstance(fetched, Faction)
    assert fetched.id == result.id
    assert fetched.name == mock_factions[0].name


async def test_list_factions(db,
                             mock_factions,
                             ):
    for faction in mock_factions:
        await db.faction.create(
            faction=faction,
            simulation_id=1,
        )

    fetched = await db.faction.list(simulation_id=1)

    assert len(fetched) == len(mock_factions)


async def test_list_relevant_faction_relationships(db,
                                                   mock_faction_relationships,
                                                   ):
    for relationship in mock_faction_relationships:
        await db.faction_relationship.create(relationship=relationship)

    fetched = await db.faction_relationship.list(
        entity_refs=[(FactionRelationshipEntity.CHARACTER, 1)],
    )

    assert all(isinstance(relationship, FactionRelationship) for relationship in fetched)
    assert any(relationship.relationship == "mayor" for relationship in fetched)


async def test_list_public_faction_relationships(db,
                                                 mock_faction_relationships,
                                                 ):
    for relationship in mock_faction_relationships:
        await db.faction_relationship.create(relationship=relationship)

    fetched = await db.faction_relationship.list(
        entity_refs=[(FactionRelationshipEntity.CHARACTER, 1)],
        private=False,
    )

    assert fetched
    assert all(not relationship.private for relationship in fetched)
