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


async def test_list_faction_relationships_by_simulation_id(db,
                                                           mock_simulation,
                                                           mock_factions,
                                                           ):
    await db.simulation.create(
        mock_simulation.model_copy(update={"id": 2, "name": "Secondary Simulation"}),
    )

    primary_a = await db.faction.create(faction=mock_factions[0], simulation_id=1)
    primary_b = await db.faction.create(faction=mock_factions[1], simulation_id=1)
    secondary_a = await db.faction.create(faction=mock_factions[2], simulation_id=2)
    secondary_b = await db.faction.create(faction=mock_factions[3], simulation_id=2)

    await db.faction_relationship.create(
        relationship=FactionRelationship(
            from_type=FactionRelationshipEntity.FACTION,
            from_id=primary_a.id,
            to_type=FactionRelationshipEntity.FACTION,
            to_id=primary_b.id,
            relationship="ally",
            private=False,
        ),
    )
    await db.faction_relationship.create(
        relationship=FactionRelationship(
            from_type=FactionRelationshipEntity.FACTION,
            from_id=secondary_a.id,
            to_type=FactionRelationshipEntity.FACTION,
            to_id=secondary_b.id,
            relationship="rival",
            private=False,
        ),
    )

    primary_relationships = await db.faction_relationship.list(simulation_id=1)
    secondary_relationships = await db.faction_relationship.list(simulation_id=2)

    assert len(primary_relationships) == 1
    assert primary_relationships[0].relationship == "ally"
    assert len(secondary_relationships) == 1
    assert secondary_relationships[0].relationship == "rival"

