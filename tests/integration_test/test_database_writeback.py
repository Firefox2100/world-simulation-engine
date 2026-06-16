import pytest

from world_simulation_engine.component import TurnGenerator


@pytest.fixture(autouse=True)
async def setup(db,
                mock_simulation,
                mock_simulation_state_1,
                mock_locations,
                mock_characters,
                mock_tasks,
                mock_world_entries,
                mock_items_0,
                mock_items_1,
                mock_items_2,
                mock_items_3,
                mock_items_4,
                mock_equipments_0,
                mock_equipments_1,
                mock_equipments_2,
                mock_equipments_3,
                mock_equipments_4,
                mock_factions,
                mock_faction_relationships,
                mock_llm_connection_create,
                ):
    await db.connection.llm.create(mock_llm_connection_create)
    await db.simulation.create(mock_simulation)
    for location in mock_locations:
        await db.location.create(location=location, simulation_id=1)

    await db.state.create(mock_simulation_state_1)
    for character in mock_characters:
        await db.character.create(character=character, simulation_id=1)

    for task in mock_tasks:
        await db.task.create(task=task)
    for world_entry in mock_world_entries:
        await db.entry.create(world_entry=world_entry, simulation_id=1)
    for item in mock_items_0:
        await db.item.create(item=item, simulation_id=1)
    for item in mock_items_1:
        await db.item.create(item=item, simulation_id=1, character_id=1)
    for item in mock_items_2:
        await db.item.create(item=item, simulation_id=1, character_id=2)
    for item in mock_items_3:
        await db.item.create(item=item, simulation_id=1, character_id=3)
    for item in mock_items_4:
        await db.item.create(item=item, simulation_id=1, character_id=4)
    for equipment in mock_equipments_0:
        await db.equipment.create(equipment=equipment, simulation_id=1)
    for equipment in mock_equipments_1:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=1)
    for equipment in mock_equipments_2:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=2)
    for equipment in mock_equipments_3:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=3)
    for equipment in mock_equipments_4:
        await db.equipment.create(equipment=equipment, simulation_id=1, character_id=4)

    for faction in mock_factions:
        await db.faction.create(faction=faction, simulation_id=1)
    for relationship in mock_faction_relationships:
        await db.faction_relationship.create(relationship=relationship)


@pytest.fixture
def mock_committer_output_payload():
    return {
    "committer_output": {
        "simulation_id": 1,
        "ready_to_commit": True,
        "round_summary": "Clara Whitlock successfully verified the occupancy record for Room 7 against her private receipt, confirming a discrepancy in the guest name. She holds this information privately while maintaining a neutral demeanor toward Arthur Moore.",
        "mutation_log": [
            {
                "mutation_id": "482abf7d-6bfc-4fb3-99d8-11b8370f22b9",
                "operation": "update",
                "target": {
                    "object_type": "entity",
                    "object_id": 5
                },
                "payload": {
                    "location_id": 3,
                    "status": "Closed and resting on the bar surface after being accessed."
                },
                "reason": "Ledger was accessed and is now closed on bar surface per resolver visible result",
                "source_event": None
            },
            {
                "mutation_id": "b82c30c0-6f36-4e80-b3cf-e3f0576f42c9",
                "operation": "update",
                "target": {
                    "object_type": "task",
                    "object_id": 12
                },
                "payload": {
                    "progress": 45
                },
                "reason": "Clara found concrete evidence about Room 7 discrepancy, advancing her investigation task progress from 30 to 45",
                "source_event": None
            },
            {
                "mutation_id": "a95f4922-d16f-4044-8cbe-944747d92e21",
                "operation": "update",
                "target": {
                    "object_type": "state",
                    "object_id": 1
                },
                "payload": {
                    "recent_history_summary": "Arthur arrived at the Iron Stag Inn during the Founder's Festival. Clara noticed his controlled manner and suspected he was not merely a curious traveller. Eleanor briefly greeted Arthur, presenting the town as orderly and festive while probing his purpose. Arthur has not yet revealed the anonymous letter. Arthur asked Clara about Room 7 occupancy before Harlan vanished; Clara checked the Visitor's Room Ledger and found it recorded a cash payment with no guest name listed."
                },
                "reason": "Capture this turn's events in recent history summary",
                "source_event": None
            }
        ],
        "warnings": [],
        "final_state": {
            "simulation": {
                "id": 1,
                "name": "The Blackwater Observatory",
                "description": "The year is 1912. The isolated mountain town of Blackwater Ridge was built around an astronomical observatory that once conducted secret government-funded research.\n\nThree weeks ago, the observatory's director vanished. Officially, he left without notice. However, nobody believes that. The player arrives in town during the annual Founder's Festival, where tensions between residents are beginning to surface.",
                "language": "en"
            },
            "state": {
                "id": 1,
                "scene": 3,
                "turn_number": 0,
                "state": "Arthur Moore has arrived at the Iron Stag Inn during the Founder's Festival. Clara Whitlock is behind the bar, managing guests while quietly observing Arthur. The inn is busy with locals and festival visitors, making it a useful place to gather rumours without drawing immediate attention. Arthur has not yet revealed the full contents of the anonymous letter. Eleanor Graves is aware that an outside investigator has arrived in town, but has not yet confronted him directly. Marcus Reed remains at or near the observatory, anxious about Harlan's missing notebook and the unauthorized signal experiments.",
                "time_label": "Founder's Festival evening, three weeks after Director Harlan's disappearance",
                "recent_history_summary": "Arthur arrived at the Iron Stag Inn during the Founder's Festival. Clara noticed his controlled manner and suspected he was not merely a curious traveller. Eleanor briefly greeted Arthur, presenting the town as orderly and festive while probing his purpose. Arthur has not yet revealed the anonymous letter. Arthur asked Clara about Room 7 occupancy before Harlan vanished; Clara checked the Visitor's Room Ledger and found it recorded a cash payment with no guest name listed.",
                "long_term_history_summary": "Director Harlan disappeared three weeks ago. Officially he left without notice, but many residents doubt this. The observatory, the old mine, altered property records, the unknown visitor, and Harlan's missing notebook are all unresolved investigation threads."
            },
            "characters": [
                {
                    "id": 1,
                    "name": "Eleanor Graves",
                    "user_controlled": False,
                    "location": 3,
                    "public_state": "Welcoming Arthur Moore to Blackwater Ridge while presenting the town as orderly, festive, and untroubled by Director Harlan's disappearance.",
                    "private_state": "Trying to determine what Arthur Moore is actually here for, whether he was truly hired as an independent investigator, and whether his presence threatens the altered property records, the town's finances, or her own position.",
                    "attributes": {
                        "relationship": [
                            "Marcus Reed:distrust",
                            "Clara Whitlock:wary respect",
                            "Arthur Moore:cautious scrutiny",
                            "Director Harlan:concern mixed with political fear"
                        ]
                    },
                    "stats": {}
                },
                {
                    "id": 2,
                    "name": "Marcus Reed",
                    "user_controlled": False,
                    "location": 1,
                    "public_state": "Continuing limited observatory work while insisting that Director Harlan's disappearance must have a rational explanation.",
                    "private_state": "Desperate to recover Harlan's missing notebook before Eleanor, Arthur, or anyone else uses it to expose his unauthorized experiments. He suspects the underground signals are connected to Harlan's disappearance but fears admitting how much he knows.",
                    "attributes": {
                        "relationship": [
                            "Eleanor Graves:suspicion",
                            "Clara Whitlock:trust and reliance",
                            "Arthur Moore:intellectual curiosity mixed with caution",
                            "Director Harlan:guilt, loyalty, and unresolved dependence"
                        ]
                    },
                    "stats": {}
                },
                {
                    "id": 3,
                    "name": "Clara Whitlock",
                    "user_controlled": False,
                    "location": 3,
                    "public_state": "Running the Iron Stag Inn during the Founder's Festival, serving guests, listening to rumours, and presenting herself as merely curious about Arthur Moore's arrival.",
                    "private_state": "Trying to uncover the truth behind Director Harlan's disappearance, partly out of concern and partly because she believes the story could be valuable to a newspaper. She is also quietly watching Marcus, whom she believes is frightened rather than malicious.",
                    "attributes": {
                        "relationship": [
                            "Eleanor Graves:wary",
                            "Marcus Reed:protective fondness",
                            "Arthur Moore:friendly curiosity",
                            "Director Harlan:concerned respect"
                        ]
                    },
                    "stats": {}
                },
                {
                    "id": 4,
                    "name": "Arthur Moore",
                    "user_controlled": True,
                    "location": 3,
                    "public_state": "Arriving in Blackwater Ridge during the Founder's Festival as an independent investigator, presenting himself as professionally interested in Director Harlan's disappearance.",
                    "private_state": "Investigating who anonymously hired him, why payment depends on obtaining evidence, and whether Harlan's disappearance is connected to the observatory, the old mine, or the town's leadership.",
                    "attributes": {
                        "relationship": [
                            "Eleanor Graves:professionally cautious",
                            "Marcus Reed:unresolved suspicion",
                            "Clara Whitlock:tentative trust",
                            "Director Harlan:case subject"
                        ]
                    },
                    "stats": {}
                }
            ],
            "locations": [
                {
                    "id": 1,
                    "primary_location": "Blackwater Ridge",
                    "detailed_location": "Blackwater Observatory",
                    "scene": "Director's Office",
                    "description": "The private office of the missing Director Harlan. Tall windows face the mountains, while shelves of astronomical records, correspondence and field notes line the walls. The room is orderly, quiet, and formal.",
                    "attributes": {},
                    "stats": {},
                    "entities": [
                        {
                            "id": 1,
                            "name": "Director's Desk",
                            "type": "important-item",
                            "description": "A heavy oak desk used by Director Harlan. Its drawers hold correspondence, old stationery, and observatory paperwork.",
                            "status": "Closed. The surface is neat.",
                            "interactions": [
                                "inspect",
                                "open drawers",
                                "search for hidden compartment"
                            ]
                        },
                        {
                            "id": 2,
                            "name": "Locked Filing Cabinet",
                            "type": "important-item",
                            "description": "A reinforced metal cabinet used for observatory administrative records and archived research paperwork.",
                            "status": "Locked. The lock plate is visibly scratched.",
                            "interactions": [
                                "inspect",
                                "attempt to unlock",
                                "force open"
                            ]
                        }
                    ]
                },
                {
                    "id": 2,
                    "primary_location": "Blackwater Ridge",
                    "detailed_location": "Blackwater Observatory",
                    "scene": "Telescope Chamber",
                    "description": "The main chamber of the observatory, dominated by a large brass-and-steel telescope mounted beneath the rotating dome. The room smells of machine oil, cold stone and dust. Instruments, calibration charts and star tables are arranged around the chamber.",
                    "attributes": {},
                    "stats": {},
                    "entities": [
                        {
                            "id": 3,
                            "name": "Main Telescope",
                            "type": "important-item",
                            "description": "The observatory's primary telescope, a large and finely maintained astronomical instrument aimed through the dome aperture.",
                            "status": "Functional. Its alignment controls are not currently set to their marked resting positions.",
                            "interactions": [
                                "inspect",
                                "adjust alignment",
                                "look through"
                            ]
                        },
                        {
                            "id": 4,
                            "name": "Signal Recording Apparatus",
                            "type": "important-item",
                            "description": "A collection of coils, receivers, paper rolls and improvised attachments used to record signal patterns alongside astronomical observations.",
                            "status": "Powered down. Several paper recording strips remain attached to the machine.",
                            "interactions": [
                                "inspect",
                                "read recording strips",
                                "attempt to operate"
                            ]
                        }
                    ]
                },
                {
                    "id": 3,
                    "primary_location": "Blackwater Ridge",
                    "detailed_location": "Iron Stag Inn",
                    "scene": "Bar",
                    "description": "The busy ground-floor bar of the Iron Stag Inn. Locals gather here for drink, gossip and festival talk. The room is warm, noisy and crowded enough that a careful listener can overhear many things without appearing suspicious.",
                    "attributes": {},
                    "stats": {},
                    "entities": [
                        {
                            "id": 5,
                            "name": "Visitor's Room Ledger",
                            "type": "important-item",
                            "description": "The inn's room ledger, recording room usage, dates, names, payments and occasional notes made by Clara Whitlock.",
                            "status": "Closed and resting on the bar surface after being accessed.",
                            "interactions": [
                                "read",
                                "inspect Room 7 entry",
                                "add entry"
                            ]
                        },
                        {
                            "id": 6,
                            "name": "Notice Board",
                            "type": "important-item",
                            "description": "A public notice board covered with festival announcements, missing notices, trade offers and local messages.",
                            "status": "Crowded with new festival notices. Older papers are pinned underneath.",
                            "interactions": [
                                "inspect",
                                "read notices",
                                "remove notice"
                            ]
                        }
                    ]
                },
                {
                    "id": 4,
                    "primary_location": "Blackwater Ridge",
                    "detailed_location": "Iron Stag Inn",
                    "scene": "Room 7",
                    "description": "A modest guest room on the upper floor of the Iron Stag Inn. It is tidy, sparse, and quiet, with a small writing desk and a window overlooking the side alley.",
                    "attributes": {},
                    "stats": {},
                    "entities": [
                        {
                            "id": 7,
                            "name": "Room 7 Writing Desk",
                            "type": "important-item",
                            "description": "A small guest writing desk with a worn surface, an ink bottle and a narrow drawer.",
                            "status": "Mostly clean. Faint pressure marks are visible on the writing surface.",
                            "interactions": [
                                "inspect",
                                "search drawer",
                                "take rubbing of writing marks"
                            ]
                        },
                        {
                            "id": 8,
                            "name": "Guest Room Window",
                            "type": "important-item",
                            "description": "A window overlooking the side alley beside the inn.",
                            "status": "Closed but not latched. The sill has faint scrape marks.",
                            "interactions": [
                                "inspect",
                                "open",
                                "look outside"
                            ]
                        }
                    ]
                },
                {
                    "id": 5,
                    "primary_location": "Blackwater Ridge",
                    "detailed_location": "Town Hall",
                    "scene": "Mayor's Office",
                    "description": "Eleanor Graves's office inside Town Hall. The room is formal, controlled and carefully arranged. A locked cabinet, a polished desk and framed town charters communicate authority and civic stability.",
                    "attributes": {},
                    "stats": {},
                    "entities": [
                        {
                            "id": 9,
                            "name": "Mayor's Desk",
                            "type": "important-item",
                            "description": "A polished desk containing official correspondence, festival planning papers and sealed municipal documents.",
                            "status": "Orderly.",
                            "interactions": [
                                "inspect",
                                "search",
                                "read visible papers"
                            ]
                        },
                        {
                            "id": 10,
                            "name": "Municipal Lockbox",
                            "type": "important-item",
                            "description": "A compact iron lockbox used for sensitive town documents and private administrative records.",
                            "status": "Locked and kept inside the mayor's office.",
                            "interactions": [
                                "inspect",
                                "attempt to unlock",
                                "move"
                            ]
                        }
                    ]
                },
                {
                    "id": 6,
                    "primary_location": "Blackwater Ridge",
                    "detailed_location": "Town Hall",
                    "scene": "Records Room",
                    "description": "A cramped archival room filled with shelves of deeds, survey papers, council minutes and tax records. Dust hangs in the air, and the shelves are densely packed with folders and document boxes.",
                    "attributes": {},
                    "stats": {},
                    "entities": [
                        {
                            "id": 11,
                            "name": "Property Record Shelves",
                            "type": "important-item",
                            "description": "Shelves containing land ownership records for Blackwater Ridge and its surrounding territory, including the old mine area.",
                            "status": "Dusty. Some folders are unevenly aligned on the shelves.",
                            "interactions": [
                                "inspect",
                                "search records",
                                "compare documents"
                            ]
                        },
                        {
                            "id": 12,
                            "name": "Survey Archive Cabinet",
                            "type": "important-item",
                            "description": "A cabinet containing older surveyor records and historical mine documentation.",
                            "status": "Closed but not locked.",
                            "interactions": [
                                "open",
                                "search",
                                "retrieve map"
                            ]
                        }
                    ]
                },
                {
                    "id": 7,
                    "primary_location": "Blackwater Ridge",
                    "detailed_location": "Town Square",
                    "scene": "Festival Monument",
                    "description": "The centre of Blackwater Ridge, currently decorated for the Founder's Festival. A stone monument commemorates the town's founding and stands among bunting, stalls and temporary wooden stages.",
                    "attributes": {},
                    "stats": {},
                    "entities": [
                        {
                            "id": 13,
                            "name": "Festival Monument",
                            "type": "important-item",
                            "description": "A commemorative stone monument with a plaque marking the town's founding.",
                            "status": "Decorated for the festival.",
                            "interactions": [
                                "inspect",
                                "remove plaque",
                                "hide item",
                                "retrieve hidden item"
                            ]
                        },
                        {
                            "id": 14,
                            "name": "Festival Stalls",
                            "type": "important-item",
                            "description": "Temporary market stalls set up for the Founder's Festival, selling food, trinkets and local crafts.",
                            "status": "Active during the day and partly covered at night.",
                            "interactions": [
                                "inspect",
                                "ask vendors",
                                "search after closing"
                            ]
                        }
                    ]
                },
                {
                    "id": 8,
                    "primary_location": "Blackwater Ridge",
                    "detailed_location": "Old Mine",
                    "scene": "Mine Entrance",
                    "description": "The boarded entrance to the abandoned silver mine north of town. The official closure signs are old and weathered, and the ground nearby is rough and uneven.",
                    "attributes": {},
                    "stats": {},
                    "entities": [
                        {
                            "id": 15,
                            "name": "Boarded Mine Entrance",
                            "type": "important-item",
                            "description": "The sealed entrance to the old silver mine where eleven workers died twenty years ago.",
                            "status": "Officially closed. Boards cover the entrance.",
                            "interactions": [
                                "inspect",
                                "remove boards",
                                "enter mine"
                            ]
                        },
                        {
                            "id": 16,
                            "name": "Old Warning Sign",
                            "type": "important-item",
                            "description": "A weathered municipal warning sign declaring the mine unsafe and closed by town order.",
                            "status": "Faded and partially broken.",
                            "interactions": [
                                "inspect",
                                "read",
                                "move aside"
                            ]
                        }
                    ]
                },
                {
                    "id": 9,
                    "primary_location": "Blackwater Ridge",
                    "detailed_location": "Old Mine",
                    "scene": "Main Tunnel",
                    "description": "A dark, unstable tunnel inside the abandoned mine. The air is cold and mineral-heavy. Old rails run into darkness, and sounds echo strangely through unseen side passages.",
                    "attributes": {},
                    "stats": {},
                    "entities": [
                        {
                            "id": 17,
                            "name": "Collapsed Side Passage",
                            "type": "important-item",
                            "description": "A partially collapsed passage branching from the main tunnel. Loose stones and cracked support beams make it dangerous to disturb.",
                            "status": "Blocked, but not completely sealed.",
                            "interactions": [
                                "inspect",
                                "listen",
                                "clear debris"
                            ]
                        },
                        {
                            "id": 18,
                            "name": "Rusting Mine Cart",
                            "type": "important-item",
                            "description": "An old ore cart sitting on warped rails, half-filled with stone fragments and rotting wood.",
                            "status": "Stationary. Its wheels are rusted.",
                            "interactions": [
                                "inspect",
                                "search",
                                "push"
                            ]
                        }
                    ]
                },
                {
                    "id": 10,
                    "primary_location": "Blackwater Ridge",
                    "detailed_location": "North Forest",
                    "scene": "Abandoned Cabin",
                    "description": "A small hunter's cabin hidden among the trees north of town. It has been abandoned for years. Dust lies across the room, and the air smells of damp timber and old ash.",
                    "attributes": {},
                    "stats": {},
                    "entities": [
                        {
                            "id": 19,
                            "name": "Cabin Hearth",
                            "type": "important-item",
                            "description": "A stone hearth filled with ash.",
                            "status": "Cold.",
                            "interactions": [
                                "inspect",
                                "search ash",
                                "light fire"
                            ]
                        },
                        {
                            "id": 20,
                            "name": "Loose Floorboard",
                            "type": "important-item",
                            "description": "A warped floorboard near the cabin wall.",
                            "status": "Slightly raised from the surrounding floor.",
                            "interactions": [
                                "inspect",
                                "lift",
                                "hide item",
                                "retrieve hidden item"
                            ]
                        }
                    ]
                }
            ],
            "inventory": {
                "0": {
                    "items": [
                        {
                            "id": 1,
                            "name": "Harlan's Notebook",
                            "description": "Director Harlan's missing notebook, containing research notes, rough mine sketches, observatory calculations, and several encoded entries.",
                            "quantity": 1,
                            "quality": None
                        },
                        {
                            "id": 2,
                            "name": "Brass Laboratory Key",
                            "description": "A small brass key that opens the locked laboratory in Blackwater Observatory. It is currently hidden inside the hollow festival monument in town square.",
                            "quantity": 1,
                            "quality": None
                        },
                        {
                            "id": 3,
                            "name": "Silver Pocket Watch",
                            "description": "Director Harlan's silver pocket watch. It stopped at 11:17 PM and may indicate when something significant happened.",
                            "quantity": 1,
                            "quality": "damaged"
                        },
                        {
                            "id": 4,
                            "name": "Unknown Visitor's Note Fragment",
                            "description": "A torn fragment of paper connected to the unknown visitor who rented Room 7. It contains only partial handwriting and is not enough to identify the writer by itself.",
                            "quantity": 1,
                            "quality": "torn"
                        }
                    ],
                    "equipments": []
                },
                "1": {
                    "items": [
                        {
                            "id": 5,
                            "name": "Surveyor's Map",
                            "description": "An old surveyor's map of the mine and surrounding land. It shows a tunnel not present on official town records.",
                            "quantity": 1,
                            "quality": "aged"
                        },
                        {
                            "id": 6,
                            "name": "Mayor's Administrative Seal",
                            "description": "Eleanor Graves's official municipal seal, used to authenticate town documents and records.",
                            "quantity": 1,
                            "quality": None
                        }
                    ],
                    "equipments": []
                },
                "2": {
                    "items": [
                        {
                            "id": 7,
                            "name": "Signal Recording Strip",
                            "description": "A narrow paper strip from the observatory's recording apparatus, marked with irregular signal patterns detected beneath Blackwater Ridge.",
                            "quantity": 1,
                            "quality": None
                        },
                        {
                            "id": 8,
                            "name": "Marcus's Calibration Notes",
                            "description": "Marcus Reed's personal technical notes on telescope alignment, receiver behaviour, and his unauthorized signal experiments.",
                            "quantity": 1,
                            "quality": None
                        }
                    ],
                    "equipments": []
                },
                "3": {
                    "items": [
                        {
                            "id": 9,
                            "name": "Clara's Gossip Notebook",
                            "description": "Clara Whitlock's private notebook of rumours, guest observations, suspicious behaviour, and overheard conversations at the Iron Stag Inn.",
                            "quantity": 1,
                            "quality": None
                        },
                        {
                            "id": 10,
                            "name": "Room 7 Cash Receipt",
                            "description": "A receipt for the unknown visitor's payment for Room 7 at the Iron Stag Inn. The name written on it is believed to be false.",
                            "quantity": 1,
                            "quality": None
                        }
                    ],
                    "equipments": []
                },
                "4": {
                    "items": [
                        {
                            "id": 11,
                            "name": "Anonymous Letter",
                            "description": "The letter that brought Arthur Moore to Blackwater Ridge. It requests an investigation into Director Harlan's disappearance and states that payment depends on obtaining evidence.",
                            "quantity": 1,
                            "quality": None
                        },
                        {
                            "id": 12,
                            "name": "Investigator's Notebook",
                            "description": "Arthur Moore's own notebook for case notes, witness statements, deductions, timelines, and contradictions.",
                            "quantity": 1,
                            "quality": None
                        }
                    ],
                    "equipments": [
                        {
                            "id": 1,
                            "name": "Pocket Revolver",
                            "description": "Arthur Moore's compact personal revolver, carried for protection rather than open intimidation.",
                            "status": "equipped",
                            "quality": None
                        },
                        {
                            "id": 2,
                            "name": "Investigator's Coat",
                            "description": "A practical dark travelling coat with deep pockets suitable for carrying papers, small tools, and evidence.",
                            "status": "equipped",
                            "quality": None
                        }
                    ]
                }
            },
            "factions": [
                {
                    "id": 1,
                    "name": "Blackwater Observatory",
                    "description": "The astronomical observatory overlooking Blackwater Ridge. Publicly, it studies stars and celestial phenomena; privately, it has received secret government funding for unusual signal research. Its reputation is scholarly, but its isolation and secrecy make it a source of local suspicion.",
                    "attributes": {},
                    "stats": {}
                },
                {
                    "id": 2,
                    "name": "Blackwater Town Council",
                    "description": "The municipal authority of Blackwater Ridge, responsible for town administration, public records, festival arrangements and official decisions. It is closely associated with Mayor Eleanor Graves and the public image of the town.",
                    "attributes": {},
                    "stats": {}
                },
                {
                    "id": 3,
                    "name": "Iron Stag Inn",
                    "description": "The central inn and tavern of Blackwater Ridge. It is not a political institution, but it acts as the town's informal information hub because locals, visitors and festival guests regularly gather there.",
                    "attributes": {},
                    "stats": {}
                },
                {
                    "id": 4,
                    "name": "Unknown Government Contractor",
                    "description": "A vague outside interest connected to the observatory's original secret funding. Its exact identity, authority and current involvement are not publicly known, but it is relevant to Director Harlan's past work and the unknown visitor who came before his disappearance.",
                    "attributes": {},
                    "stats": {}
                },
                {
                    "id": 5,
                    "name": "Mine Land Shell Companies",
                    "description": "A set of obscure legal entities associated with property purchases around the abandoned old mine. They may not operate openly in town, but they are repeatedly connected to altered records and suspicious land transfers.",
                    "attributes": {},
                    "stats": {}
                }
            ],
            "faction_relationships": [
                {
                    "id": None,
                    "from_type": "character",
                    "from_id": 1,
                    "to_type": "faction",
                    "to_id": 2,
                    "relationship": "mayor",
                    "private": False
                },
                {
                    "id": None,
                    "from_type": "character",
                    "from_id": 2,
                    "to_type": "faction",
                    "to_id": 1,
                    "relationship": "employee",
                    "private": False
                },
                {
                    "id": None,
                    "from_type": "character",
                    "from_id": 3,
                    "to_type": "faction",
                    "to_id": 3,
                    "relationship": "proprietor",
                    "private": False
                },
                {
                    "id": None,
                    "from_type": "character",
                    "from_id": 1,
                    "to_type": "faction",
                    "to_id": 5,
                    "relationship": "concealed administrative connection",
                    "private": True
                },
                {
                    "id": None,
                    "from_type": "faction",
                    "from_id": 4,
                    "to_type": "faction",
                    "to_id": 1,
                    "relationship": "secret research sponsor",
                    "private": True
                },
                {
                    "id": None,
                    "from_type": "faction",
                    "from_id": 5,
                    "to_type": "faction",
                    "to_id": 2,
                    "relationship": "records irregularity subject",
                    "private": True
                }
            ],
            "tasks": [
                {
                    "id": 1,
                    "character_ids": [
                        4
                    ],
                    "private": False,
                    "priority": "urgent",
                    "status": "in_progress",
                    "type": "main_quest",
                    "goal": "Determine what happened to Director Harlan.",
                    "progress": 0,
                    "source": "Anonymous Letter"
                },
                {
                    "id": 2,
                    "character_ids": [
                        4
                    ],
                    "private": True,
                    "priority": "important",
                    "status": "in_progress",
                    "type": "side_quest",
                    "goal": "Identify who anonymously hired Arthur Moore.",
                    "progress": 0,
                    "source": "Arthur Moore's professional suspicion"
                },
                {
                    "id": 3,
                    "character_ids": [
                        4
                    ],
                    "private": False,
                    "priority": "normal",
                    "status": "in_progress",
                    "type": "side_quest",
                    "goal": "Locate Harlan's missing notebook.",
                    "progress": 0,
                    "source": "Investigation into Harlan's final movements"
                },
                {
                    "id": 4,
                    "character_ids": [
                        4
                    ],
                    "private": False,
                    "priority": "normal",
                    "status": "in_progress",
                    "type": "side_quest",
                    "goal": "Discover the identity of the unknown visitor who stayed in Room 7.",
                    "progress": 0,
                    "source": "The suspicious Room 7 ledger entry"
                },
                {
                    "id": 5,
                    "character_ids": [
                        1
                    ],
                    "private": True,
                    "priority": "urgent",
                    "status": "in_progress",
                    "type": "main_quest",
                    "goal": "Prevent public panic regarding Director Harlan's disappearance.",
                    "progress": 70,
                    "source": "Mayoral duty and concern for the town's reputation"
                },
                {
                    "id": 6,
                    "character_ids": [
                        1
                    ],
                    "private": True,
                    "priority": "important",
                    "status": "in_progress",
                    "type": "side_quest",
                    "goal": "Determine why Arthur Moore has come to Blackwater Ridge and whether he is a threat.",
                    "progress": 10,
                    "source": "Eleanor's suspicion of outside investigators"
                },
                {
                    "id": 7,
                    "character_ids": [
                        1
                    ],
                    "private": True,
                    "priority": "important",
                    "status": "in_progress",
                    "type": "side_quest",
                    "goal": "Prevent investigation of irregular land transactions near the old mine.",
                    "progress": 60,
                    "source": "Eleanor's connection to the altered property records"
                },
                {
                    "id": 8,
                    "character_ids": [
                        2
                    ],
                    "private": True,
                    "priority": "urgent",
                    "status": "in_progress",
                    "type": "main_quest",
                    "goal": "Recover Harlan's notebook before anyone else obtains it.",
                    "progress": 15,
                    "source": "Marcus's fear that the notebook exposes his unauthorized experiments"
                },
                {
                    "id": 9,
                    "character_ids": [
                        2
                    ],
                    "private": True,
                    "priority": "important",
                    "status": "in_progress",
                    "type": "side_quest",
                    "goal": "Conceal evidence of unauthorized signal experiments.",
                    "progress": 80,
                    "source": "Marcus's self-preservation"
                },
                {
                    "id": 10,
                    "character_ids": [
                        2
                    ],
                    "private": True,
                    "priority": "normal",
                    "status": "paused",
                    "type": "side_quest",
                    "goal": "Determine the source of the underground radio signals.",
                    "progress": None,
                    "source": "Marcus's scientific obsession"
                },
                {
                    "id": 11,
                    "character_ids": [
                        3
                    ],
                    "private": True,
                    "priority": "important",
                    "status": "in_progress",
                    "type": "side_quest",
                    "goal": "Learn the truth about Director Harlan's disappearance.",
                    "progress": 20,
                    "source": "Clara's curiosity and concern"
                },
                {
                    "id": 12,
                    "character_ids": [
                        3
                    ],
                    "private": True,
                    "priority": "normal",
                    "status": "in_progress",
                    "type": "side_quest",
                    "goal": "Identify the unknown visitor who rented Room 7.",
                    "progress": 45,
                    "source": "Clara's inn records and memory of the visitor"
                },
                {
                    "id": 13,
                    "character_ids": [
                        3
                    ],
                    "private": True,
                    "priority": "background",
                    "status": "in_progress",
                    "type": "daily",
                    "goal": "Collect and organize rumours heard at the Iron Stag Inn.",
                    "progress": None,
                    "source": "Clara's occupation and habits"
                },
                {
                    "id": 14,
                    "character_ids": [
                        1,
                        2
                    ],
                    "private": True,
                    "priority": "background",
                    "status": "in_progress",
                    "type": "side_quest",
                    "goal": "Keep the observatory operational despite Director Harlan's absence.",
                    "progress": 65,
                    "source": "Observatory responsibility and town reputation"
                }
            ],
            "world_entries": [
                {
                    "id": 1,
                    "scope": [
                        0
                    ],
                    "content": "Blackwater Ridge is an isolated mountain town built around Blackwater Observatory.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "visible",
                    "recall_type": "always",
                    "keywords": None,
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 2,
                    "scope": [
                        0
                    ],
                    "content": "The current year is 1912, and Blackwater Ridge is holding its annual Founder's Festival.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "visible",
                    "recall_type": "always",
                    "keywords": None,
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 3,
                    "scope": [
                        0
                    ],
                    "content": "Director Harlan, head of Blackwater Observatory, disappeared three weeks ago. Officially, he left without notice.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "visible",
                    "recall_type": "always",
                    "keywords": None,
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 4,
                    "scope": [
                        0
                    ],
                    "content": "Many residents of Blackwater Ridge do not believe the official explanation for Director Harlan's disappearance.",
                    "visibility": "perceived",
                    "confidence": 0.85,
                    "narration_permission": "visible",
                    "recall_type": "semantic",
                    "keywords": None,
                    "chained_ids": None,
                    "semantic_instruction": "Recall when the scene involves public mood, rumours, townspeople, the festival, or discussion of Harlan's disappearance."
                },
                {
                    "id": 5,
                    "scope": [
                        0
                    ],
                    "content": "Twenty years ago, a collapse in the old silver mine killed eleven workers. The mine was officially closed after the incident.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "visible",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "old mine",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "mine collapse",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "eleven workers",
                            "similarity": 0.75,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 6,
                    "scope": [
                        1,
                        2
                    ],
                    "content": "Eight years ago, Blackwater Observatory began receiving secret government funding.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "may_hint",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "government funding",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "observatory funding",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "secret funding",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 7,
                    "scope": [
                        -1
                    ],
                    "content": "The secret government funding for Blackwater Observatory was connected to unusual signal research rather than ordinary astronomy.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "invisible",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        6
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 8,
                    "scope": [
                        1
                    ],
                    "content": "Three years ago, property around the old mine was sold to shell companies through irregular transactions.",
                    "visibility": "known",
                    "confidence": 0.95,
                    "narration_permission": "may_hint",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "property records",
                            "similarity": 0.7,
                            "embedding": None
                        },
                        {
                            "keyword": "shell companies",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "mine land",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 9,
                    "scope": [
                        1
                    ],
                    "content": "Some town property records concerning land near the old mine were altered.",
                    "visibility": "known",
                    "confidence": 0.95,
                    "narration_permission": "may_hint",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        8
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 10,
                    "scope": [
                        -1
                    ],
                    "content": "The altered property records are connected to the hidden mine tunnel and the underground chamber beneath the mine.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "invisible",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        8,
                        9
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 11,
                    "scope": [
                        2
                    ],
                    "content": "Six months ago, Marcus Reed began unauthorized experiments involving underground radio signals.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "may_hint",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "Marcus experiments",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "underground signals",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "radio signals",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 12,
                    "scope": [
                        2
                    ],
                    "content": "Marcus Reed has detected strange signal patterns that appear to originate from beneath Blackwater Ridge.",
                    "visibility": "known",
                    "confidence": 0.9,
                    "narration_permission": "may_hint",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        11
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 13,
                    "scope": [
                        1,
                        2
                    ],
                    "content": "Five weeks ago, Director Harlan discovered irregularities in property records connected to land near the old mine.",
                    "visibility": "known",
                    "confidence": 0.95,
                    "narration_permission": "may_hint",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "Harlan property records",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "Harlan discovered",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "land records",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 14,
                    "scope": [
                        0
                    ],
                    "content": "Four weeks ago, Director Harlan began carrying a notebook everywhere.",
                    "visibility": "perceived",
                    "confidence": 0.9,
                    "narration_permission": "visible",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "Harlan's Notebook",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "Harlan carrying notebook",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "missing notebook",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 15,
                    "scope": [
                        0
                    ],
                    "content": "Harlan's Notebook is currently missing. It contains research notes, maps, and encoded entries.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "visible",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "Harlan's Notebook",
                            "similarity": 0.7,
                            "embedding": None
                        },
                        {
                            "keyword": "missing notebook",
                            "similarity": 0.7,
                            "embedding": None
                        },
                        {
                            "keyword": "encoded entries",
                            "similarity": 0.75,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 16,
                    "scope": [
                        2
                    ],
                    "content": "Marcus knows that the brass laboratory key is hidden inside the hollow festival monument in town square.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "may_hint",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "brass laboratory key",
                            "similarity": 0.7,
                            "embedding": None
                        },
                        {
                            "keyword": "hollow festival monument",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "laboratory key",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 17,
                    "scope": [
                        -1
                    ],
                    "content": "The brass laboratory key opens the locked laboratory inside Blackwater Observatory.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "invisible",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        16
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 18,
                    "scope": [
                        3
                    ],
                    "content": "An unknown visitor arrived in Blackwater Ridge five days before Director Harlan disappeared.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "may_hint",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "unknown visitor",
                            "similarity": 0.7,
                            "embedding": None
                        },
                        {
                            "keyword": "Room 7",
                            "similarity": 0.7,
                            "embedding": None
                        },
                        {
                            "keyword": "visitor before Harlan disappeared",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 19,
                    "scope": [
                        3
                    ],
                    "content": "The unknown visitor rented Room 7 at the Iron Stag Inn under a false name and paid in cash.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "may_hint",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        18
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 20,
                    "scope": [
                        3
                    ],
                    "content": "Clara Whitlock knows the unknown visitor met secretly with Director Harlan before Harlan disappeared.",
                    "visibility": "known",
                    "confidence": 0.95,
                    "narration_permission": "may_hint",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        18,
                        19
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 21,
                    "scope": [
                        3
                    ],
                    "content": "Clara does not know the unknown visitor's true identity.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "may_hint",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        18,
                        19,
                        20
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 22,
                    "scope": [
                        2
                    ],
                    "content": "Marcus believes Director Harlan became increasingly paranoid before his disappearance.",
                    "visibility": "perceived",
                    "confidence": 0.85,
                    "narration_permission": "may_hint",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "Harlan paranoid",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "Marcus Harlan",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 23,
                    "scope": [
                        1
                    ],
                    "content": "Eleanor publicly presents Director Harlan as overworked rather than frightened or endangered.",
                    "visibility": "perceived",
                    "confidence": 0.85,
                    "narration_permission": "may_hint",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "Harlan overworked",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "Eleanor Harlan",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 24,
                    "scope": [
                        3
                    ],
                    "content": "Clara believes Director Harlan seemed frightened of someone shortly before he vanished.",
                    "visibility": "perceived",
                    "confidence": 0.85,
                    "narration_permission": "may_hint",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "Harlan frightened",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "Clara Harlan",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 25,
                    "scope": [
                        4
                    ],
                    "content": "Arthur Moore was anonymously hired to investigate Director Harlan's disappearance.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "visible",
                    "recall_type": "always",
                    "keywords": None,
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 26,
                    "scope": [
                        4
                    ],
                    "content": "Arthur's payment will only be delivered if he obtains evidence concerning Harlan's disappearance.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "may_hint",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        25
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 27,
                    "scope": [
                        4
                    ],
                    "content": "Arthur does not know the identity of the person who hired him.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "may_hint",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        25
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 28,
                    "scope": [
                        3
                    ],
                    "content": "Clara Whitlock's Visitor's Room Ledger records the Room 7 rental under a false name.",
                    "visibility": "known",
                    "confidence": 0.95,
                    "narration_permission": "may_hint",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "Visitor's Room Ledger",
                            "similarity": 0.7,
                            "embedding": None
                        },
                        {
                            "keyword": "Room 7 ledger",
                            "similarity": 0.7,
                            "embedding": None
                        },
                        {
                            "keyword": "false name",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": [
                        18,
                        19
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 29,
                    "scope": [
                        0
                    ],
                    "content": "The Surveyor's Map shows an old mine tunnel that is not present on official records.",
                    "visibility": "known",
                    "confidence": 0.95,
                    "narration_permission": "visible",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "Surveyor's Map",
                            "similarity": 0.7,
                            "embedding": None
                        },
                        {
                            "keyword": "hidden tunnel",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "mine map",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 30,
                    "scope": [
                        0
                    ],
                    "content": "Director Harlan's silver pocket watch stopped at 11:17 PM.",
                    "visibility": "known",
                    "confidence": 0.95,
                    "narration_permission": "visible",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "silver pocket watch",
                            "similarity": 0.7,
                            "embedding": None
                        },
                        {
                            "keyword": "11:17 PM",
                            "similarity": 0.8,
                            "embedding": None
                        },
                        {
                            "keyword": "Harlan's watch",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 31,
                    "scope": [
                        -1
                    ],
                    "content": "Director Harlan's silver pocket watch will be found in the abandoned cabin in the North Forest unless events change its location.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "invisible",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        30
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 32,
                    "scope": [
                        0
                    ],
                    "content": "Locals sometimes report seeing lights inside the old mine despite its official closure.",
                    "visibility": "suspected",
                    "confidence": 0.7,
                    "narration_permission": "visible",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "lights in the mine",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "old mine rumours",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "mine entrance",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 33,
                    "scope": [
                        0
                    ],
                    "content": "Locals have recently mentioned fresh footprints near the abandoned cabin in the North Forest.",
                    "visibility": "perceived",
                    "confidence": 0.75,
                    "narration_permission": "visible",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "North Forest cabin",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "fresh footprints",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "abandoned cabin",
                            "similarity": 0.72,
                            "embedding": None
                        }
                    ],
                    "chained_ids": None,
                    "semantic_instruction": None
                },
                {
                    "id": 34,
                    "scope": [
                        -1
                    ],
                    "content": "Director Harlan discovered illegal land sales, a hidden mine tunnel, and an underground chamber beneath the old mine.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "invisible",
                    "recall_type": "semantic",
                    "keywords": None,
                    "chained_ids": None,
                    "semantic_instruction": "Recall only for GM-side reasoning when resolving the true cause of Harlan's disappearance, the mine mystery, the shell companies, or the hidden underground chamber."
                },
                {
                    "id": 35,
                    "scope": [
                        -1
                    ],
                    "content": "The unknown visitor was a government contractor connected to Blackwater Observatory's original secret funding.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "invisible",
                    "recall_type": "semantic",
                    "keywords": None,
                    "chained_ids": None,
                    "semantic_instruction": "Recall only for GM-side reasoning involving the unknown visitor, secret funding, government contractors, or Harlan's final meeting."
                },
                {
                    "id": 36,
                    "scope": [
                        -1
                    ],
                    "content": "Director Harlan entered the hidden mine tunnel during his investigation and was trapped by a tunnel collapse.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "invisible",
                    "recall_type": "semantic",
                    "keywords": None,
                    "chained_ids": None,
                    "semantic_instruction": "Recall only for GM-side reasoning when determining Harlan's true fate, mine exploration outcomes, or clues pointing to a collapse."
                },
                {
                    "id": 37,
                    "scope": [
                        -1
                    ],
                    "content": "Director Harlan is still alive but stranded underground.",
                    "visibility": "known",
                    "confidence": 1,
                    "narration_permission": "invisible",
                    "recall_type": "chained",
                    "keywords": None,
                    "chained_ids": [
                        36
                    ],
                    "semantic_instruction": None
                },
                {
                    "id": 38,
                    "scope": [
                        -1
                    ],
                    "content": "Close inspection of Director Harlan's desk can reveal signs that some papers were removed and the room was later restored to order.",
                    "visibility": "known",
                    "confidence": 0.9,
                    "narration_permission": "invisible",
                    "recall_type": "keyword",
                    "keywords": [
                        {
                            "keyword": "Director's Desk",
                            "similarity": 0.72,
                            "embedding": None
                        },
                        {
                            "keyword": "missing papers",
                            "similarity": 0.72,
                            "embedding": None
                            },
                            {
                                "keyword": "searched office",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 39,
                        "scope": [
                            -1
                        ],
                        "content": "Inspection of the locked filing cabinet can suggest that someone may have tried to open it without the key.",
                        "visibility": "perceived",
                        "confidence": 0.75,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Locked Filing Cabinet",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "scratched lock",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "attempt to unlock",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 40,
                        "scope": [
                            2
                        ],
                        "content": "Marcus Reed knows the main telescope is misaligned from its standard calibration position.",
                        "visibility": "known",
                        "confidence": 1,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Main Telescope",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "misaligned telescope",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "calibration position",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 41,
                        "scope": [
                            2
                        ],
                        "content": "Marcus Reed knows several recent recording strips on the signal recording apparatus contain irregular signal patterns.",
                        "visibility": "known",
                        "confidence": 0.95,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Signal Recording Apparatus",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "recording strips",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "irregular signal patterns",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            11,
                            12
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 42,
                        "scope": [
                            -1
                        ],
                        "content": "A careful search of Room 7 can reveal signs that someone stayed briefly while avoiding obvious traces.",
                        "visibility": "perceived",
                        "confidence": 0.8,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Room 7",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "guest room",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "stayed briefly",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            18,
                            19
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 43,
                        "scope": [
                            -1
                        ],
                        "content": "The pressure marks on the Room 7 writing desk may preserve traces of something written there.",
                        "visibility": "perceived",
                        "confidence": 0.8,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Room 7 Writing Desk",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "pressure marks",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "writing marks",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            42
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 44,
                        "scope": [
                            -1
                        ],
                        "content": "The scrape marks on the Room 7 window sill may indicate that the window was used carefully or repeatedly.",
                        "visibility": "perceived",
                        "confidence": 0.7,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Guest Room Window",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "scrape marks",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "Room 7 window",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            42
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 45,
                        "scope": [
                            1
                        ],
                        "content": "Eleanor Graves habitually watches her desk and municipal papers carefully when others are in her office.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "may_hint",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Mayor's Desk",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "municipal papers",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "Eleanor office",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": None,
                        "semantic_instruction": None
                    },
                    {
                        "id": 46,
                        "scope": [
                            -1
                        ],
                        "content": "Inspection of the property record shelves can reveal that folders concerning mine-adjacent land were recently removed and replaced.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Property Record Shelves",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "mine-adjacent land",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "recent removal",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            8,
                            9
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 47,
                        "scope": [
                            -1
                        ],
                        "content": "Searching the survey archive cabinet can reveal older maps and mine documentation not normally consulted in public town business.",
                        "visibility": "known",
                        "confidence": 0.85,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Survey Archive Cabinet",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "older maps",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "mine documentation",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            29
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 48,
                        "scope": [
                            -1
                        ],
                        "content": "Close inspection of the festival monument can reveal that one plaque is loose and that there is a hollow space behind it.",
                        "visibility": "known",
                        "confidence": 0.9,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Festival Monument",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "loose plaque",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "hollow monument",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            16
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 49,
                        "scope": [
                            -1
                        ],
                        "content": "Inspection of the boarded mine entrance can reveal that several boards have been loosened and replaced more than once.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Boarded Mine Entrance",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "loosened boards",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "enter mine",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            32
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 50,
                        "scope": [
                            -1
                        ],
                        "content": "Inspection of the old warning sign can reveal that dirt around its base was cleared recently.",
                        "visibility": "perceived",
                        "confidence": 0.75,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Old Warning Sign",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "cleared dirt",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "mine entrance",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            32
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 51,
                        "scope": [
                            -1
                        ],
                        "content": "Air can be felt moving faintly through gaps in the collapsed side passage.",
                        "visibility": "perceived",
                        "confidence": 0.8,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Collapsed Side Passage",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "air moving",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "clear debris",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            36
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 52,
                        "scope": [
                            -1
                        ],
                        "content": "Inspection of the abandoned cabin can reveal disturbed dust consistent with recent use.",
                        "visibility": "perceived",
                        "confidence": 0.8,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Abandoned Cabin",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "disturbed dust",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "recent use",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            33
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 53,
                        "scope": [
                            -1
                        ],
                        "content": "Searching the cabin hearth can reveal traces of a recent small fire beneath the older ash.",
                        "visibility": "perceived",
                        "confidence": 0.85,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Cabin Hearth",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "recent fire",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "search ash",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            52
                        ],
                        "semantic_instruction": None
                    },
                    {
                        "id": 54,
                        "scope": [
                            -1
                        ],
                        "content": "Lifting the loose floorboard in the abandoned cabin can reveal whether a small object has been hidden beneath it.",
                        "visibility": "known",
                        "confidence": 0.85,
                        "narration_permission": "invisible",
                        "recall_type": "keyword",
                        "keywords": [
                            {
                                "keyword": "Loose Floorboard",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "retrieve hidden item",
                                "similarity": 0.72,
                                "embedding": None
                            },
                            {
                                "keyword": "hidden beneath",
                                "similarity": 0.72,
                                "embedding": None
                            }
                        ],
                        "chained_ids": [
                            31
                        ],
                        "semantic_instruction": None
                    }
                ]
            },
            "database_patch_preview": [
                {
                    "mutation_id": "482abf7d-6bfc-4fb3-99d8-11b8370f22b9",
                    "operation": "update",
                    "target": {
                        "object_type": "entity",
                        "object_id": 5
                    },
                    "payload": {
                        "location_id": 3,
                        "status": "Closed and resting on the bar surface after being accessed."
                    },
                    "reason": "Ledger was accessed and is now closed on bar surface per resolver visible result",
                    "source_event": None
                },
                {
                    "mutation_id": "b82c30c0-6f36-4e80-b3cf-e3f0576f42c9",
                    "operation": "update",
                    "target": {
                        "object_type": "task",
                        "object_id": 12
                    },
                    "payload": {
                        "progress": 45
                    },
                    "reason": "Clara found concrete evidence about Room 7 discrepancy, advancing her investigation task progress from 30 to 45",
                    "source_event": None
                },
                {
                    "mutation_id": "a95f4922-d16f-4044-8cbe-944747d92e21",
                    "operation": "update",
                    "target": {
                        "object_type": "state",
                        "object_id": 1
                    },
                    "payload": {
                        "recent_history_summary": "Arthur arrived at the Iron Stag Inn during the Founder's Festival. Clara noticed his controlled manner and suspected he was not merely a curious traveller. Eleanor briefly greeted Arthur, presenting the town as orderly and festive while probing his purpose. Arthur has not yet revealed the anonymous letter. Arthur asked Clara about Room 7 occupancy before Harlan vanished; Clara checked the Visitor's Room Ledger and found it recorded a cash payment with no guest name listed."
                    },
                    "reason": "Capture this turn's events in recent history summary",
                    "source_event": None
                }
            ]
        }
    }


async def test_write_to_database(db,
                                 mock_committer_output_payload,
                                 ):
    turn_generator = TurnGenerator(db)

    result = await turn_generator.persist_state_to_database(mock_committer_output_payload)
