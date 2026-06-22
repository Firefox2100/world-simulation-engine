from langchain_core.messages import AIMessage
import pytest

from world_simulation_engine.misc.enums import LlmProvider
from world_simulation_engine.model import LlmConnectionProfile, ProposedLocation, ProposedItem, ProposedEntity, \
    ProposedWorldEntry
from world_simulation_engine.service.world_agent.world_generator_agent import WorldGeneratorAgent


@pytest.fixture
def mock_generator(fake_model,
                   mock_world_generator_profile,
                   ):
    yield WorldGeneratorAgent(
        profile=mock_world_generator_profile,
        connection=LlmConnectionProfile(
            id=1,
            provider=LlmProvider.OLLAMA,
            base_url="http://127.0.0.1:11434",
        )
    )


async def test_generate_location(fake_model,
                                 mock_generator,
                                 mock_locations,
                                 mock_simulation,
                                 mock_simulation_state_1,
                                 mock_characters,
                                 mock_items_0,
                                 mock_items_1,
                                 mock_items_2,
                                 mock_items_3,
                                 mock_items_4,
                                 ):
    fake_model.responses = [
        AIMessage(
            content='{"temp_id":"loc_ebad2afa_loc_temp_mine_sealed_chamber","primary_location":"Blackwater Ridge / '
                    'Old Mine","detailed_location":"Sealed Vein Chamber","scene":"Collapsed Passage Access",'
                    '"description":"A narrow chamber accessible only after clearing a rockfall from the Main '
                    'Tunnel. Rough timber supports brace the ceiling against further collapse. Dust coats rusted '
                    'mining carts and tracks that dead-end at a solid wall of slate. The air is stale, smelling '
                    'of black powder and wet stone. A makeshift workbench stands near the back, cluttered with '
                    'tools.","attributes":{},"stats":{},"entities":[],"reason":"Connects Arthur\'s action '
                    '(clearing debris) to the mystery (Harlan/Marcus experiments). Provides physical evidence of '
                    'underground activity without confirming Harlan\'s location or fate.","commit_policy":"'
                    'resolver_decides"}',
        ),
    ]

    goal = "Generate a location inside the old mine."
    trigger = ("Arthur Moore clears debris from a partially collapsed passage inside the old mine. A previously "
               "unknown area becomes accessible.")
    constraints = [
        "It should provide clues but not answers.",
        "It must feel consistent with a 1912 mining operation.",
        "Do not reveal Harlan's fate.",
    ]

    current_location = next(l for l in mock_locations if l.id == mock_simulation_state_1.scene)
    present_characters = [
        c for c in mock_characters if c.location == mock_simulation_state_1.scene
    ]
    existing_items = mock_items_0 + mock_items_1 + mock_items_2 + mock_items_3 + mock_items_4

    result = await mock_generator.generate_location(
        simulation=mock_simulation,
        state=mock_simulation_state_1,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=mock_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
    )

    assert isinstance(result, ProposedLocation)


async def test_generate_item(fake_model,
                             mock_generator,
                             mock_locations,
                             mock_characters,
                             mock_simulation,
                             mock_simulation_state_1,
                             mock_items_0,
                             mock_items_1,
                             mock_items_2,
                             mock_items_3,
                             mock_items_4,
                             ):
    fake_model.responses = [
        AIMessage(
            content='{"temp_id":"item_ce735e96_item_temp_mine_photo","name":"Developed Photograph of Harlan and '
                    'Graves","description":"A black-and-white photograph depicting Director Harlan and Eleanor '
                    'Graves standing together at the Old Mine entrance. The back is dated one week prior to '
                    'Harlan\'s disappearance.","quality":"worn","quantity":1,"unique":true,"proposed_owner_id":'
                    'null,"proposed_location_id":4,"reason":"Links Eleanor Graves to the Old Mine location '
                    'referenced in the Surveyor\'s Map, suggesting a private connection prior to the '
                    'disappearance without confirming guilt. Deepens the mystery by contradicting her public '
                    'stance of order and connecting the Unknown Visitor thread to the Director\'s personal life.'
                    '","commit_policy":"resolver_decides"}',
        ),
    ]

    goal = "Generate an item in the hidden compartment of a wardrobe."
    trigger = "A hidden compartment is discovered."
    constraints = [
        "Generate a clue item.",
        "The clue should deepen the mystery.",
        "The clue must not reveal the culprit.",
        "The clue should connect to an existing mystery thread.",
    ]

    current_location = next(l for l in mock_locations if l.id == mock_simulation_state_1.scene)
    present_characters = [
        c for c in mock_characters if c.location == mock_simulation_state_1.scene
    ]
    existing_items = mock_items_0 + mock_items_1 + mock_items_2 + mock_items_3 + mock_items_4

    result = await mock_generator.generate_item(
        simulation=mock_simulation,
        state=mock_simulation_state_1,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=mock_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
    )

    assert isinstance(result, ProposedItem)


async def test_generate_world_entry(fake_model,
                                    mock_generator,
                                    mock_locations,
                                    mock_characters,
                                    mock_simulation,
                                    mock_simulation_state_1,
                                    mock_items_0,
                                    mock_items_1,
                                    mock_items_2,
                                    mock_items_3,
                                    mock_items_4,
                                    ):
    fake_model.responses = [
        AIMessage(
            content='{"temp_id":"entry_0be45f14_entry_temp_mine_hum_rumour","scope":[3,4],"content":"Several '
                    'older residents whisper that the mine shafts were sealed decades ago because workers '
                    'reported hearing rhythmic humming from deep within, resembling the signal patterns now '
                    'detected beneath Blackwater Ridge.","visibility":"suspected","confidence":0.65,"'
                    'narration_permission":"visible","recall_type":"keyword","keywords":null,"chained_ids":null,'
                    '"semantic_instruction":null,"reason":"Connects the pre-observatory history to current '
                    'signal anomalies, suggesting Harlan may have investigated this link before vanishing.",'
                    '"commit_policy":"resolver_decides"}',
        ),
    ]

    goal = "Generate a world entry that introduces a new mystery about the old mine."
    trigger = "A local resident mentions an old story about the mine."
    constraints = [
        "Generate a world entry.",
        "This should be a rumour.",
        "Confidence should be below 0.8.",
        "Visibility should be suspected or perceived.",
    ]

    current_location = next(l for l in mock_locations if l.id == mock_simulation_state_1.scene)
    present_characters = [
        c for c in mock_characters if c.location == mock_simulation_state_1.scene
    ]
    existing_items = mock_items_0 + mock_items_1 + mock_items_2 + mock_items_3 + mock_items_4

    result = await mock_generator.generate_world_entry(
        simulation=mock_simulation,
        state=mock_simulation_state_1,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=mock_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
    )

    assert isinstance(result, ProposedWorldEntry)


async def test_generate_entity(fake_model,
                               mock_generator,
                               mock_locations,
                               mock_characters,
                               mock_simulation,
                               mock_simulation_state_1,
                               mock_items_0,
                               mock_items_1,
                               mock_items_2,
                               mock_items_3,
                               mock_items_4,
                               ):
    fake_model.responses = [
        AIMessage(
            content='{"temp_id":"entity_d061d5b9_entity_temp_hidden_note_shelf","name":"Concealed Handwritten '
                    'Note","type":"important-item","description":"A folded sheet of cream paper with dark ink '
                    'handwriting visible on the front. One corner is creased from being tucked away. A red wax '
                    'seal is attached but broken. Dust accumulates along the edges where it was hidden.","status'
                    '":"Wedged behind liquor bottles on the bar shelf, partially obscured by glassware.",'
                    '"interactions":["pull out","unfold","inspect seal"],"reason":"Satisfies trigger of finding '
                    'something hidden behind a shelf in the current location. Provides a potential clue regarding '
                    'communication between Harlan and Clara without solving the mystery immediately.",'
                    '"commit_policy":"resolver_decides"}',
        ),
    ]

    goal = "Generate an entity inside the room, behind the shelf."
    trigger = "Arthur discovers something hidden behind one shelf."
    constraints = [
        "Generate a physical entity.",
        "The entity must fit the room.",
        "It should be interactable.",
        "It should provide a potential clue.",
    ]

    current_location = next(l for l in mock_locations if l.id == mock_simulation_state_1.scene)
    present_characters = [
        c for c in mock_characters if c.location == mock_simulation_state_1.scene
    ]
    existing_items = mock_items_0 + mock_items_1 + mock_items_2 + mock_items_3 + mock_items_4

    result = await mock_generator.generate_entity(
        simulation=mock_simulation,
        state=mock_simulation_state_1,
        current_location=current_location,
        present_characters=present_characters,
        existing_locations=mock_locations,
        existing_entities=current_location.entities,
        existing_items=existing_items,
        goal=goal,
        trigger=trigger,
        constraints=constraints,
        entity_types=mock_simulation.data_preset.entity_types.keys(),
    )

    assert isinstance(result, ProposedEntity)
