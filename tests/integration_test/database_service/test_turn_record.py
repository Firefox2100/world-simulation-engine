from world_simulation_engine.misc.enums import TurnType
from world_simulation_engine.model import TurnRecordCreate


async def test_get_last_records_latest_n_when_start_from_is_none(db, mock_simulation):
    simulation = await db.simulation.create(simulation=mock_simulation)

    for turn_number in range(6):
        await db.record.create(
            TurnRecordCreate(
                simulation_id=simulation.id,
                turn_number=turn_number,
                type=TurnType.AI_RESPONSE,
                narration=f"turn {turn_number}",
            )
        )

    fetched = await db.record.get_last_records(simulation_id=simulation.id, last_n=3)

    assert [record.turn_number for record in fetched] == [3, 4, 5]


async def test_get_last_records_before_start_from_id(db, mock_simulation):
    simulation = await db.simulation.create(simulation=mock_simulation)

    created_records = []
    for turn_number in range(6):
        created_records.append(
            await db.record.create(
                TurnRecordCreate(
                    simulation_id=simulation.id,
                    turn_number=turn_number,
                    type=TurnType.AI_RESPONSE,
                    narration=f"turn {turn_number}",
                )
            )
        )

    fetched_one = await db.record.get_last_records(
        simulation_id=simulation.id,
        last_n=1,
        start_from=created_records[5].id,
    )
    fetched_many = await db.record.get_last_records(
        simulation_id=simulation.id,
        last_n=5,
        start_from=created_records[5].id,
    )

    assert [record.id for record in fetched_one] == [created_records[4].id]
    assert [record.id for record in fetched_many] == [
        created_records[0].id,
        created_records[1].id,
        created_records[2].id,
        created_records[3].id,
        created_records[4].id,
    ]

