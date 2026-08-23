from world_simulation_engine.model import NarrationBlock, NarrationProposal, SpeechBlock
from world_simulation_engine.service.turn_content_remap import remap_narration_character_ids


def test_remaps_speech_block_character_id_found_in_map():
    content = NarrationProposal(blocks=[
        SpeechBlock(type="speech", character_id="old-id", character_name="Alex", text="Hello."),
        NarrationBlock(type="narration", text="Alex waves."),
    ]).model_dump_json()

    remapped = remap_narration_character_ids(content, {"old-id": "new-id"})

    assert remapped is not None
    proposal = NarrationProposal.model_validate_json(remapped)
    assert proposal.blocks[0].character_id == "new-id"
    assert proposal.blocks[1].text == "Alex waves."


def test_returns_none_when_no_character_id_matches():
    content = NarrationProposal(blocks=[
        SpeechBlock(type="speech", character_id="old-id", character_name="Alex", text="Hello."),
    ]).model_dump_json()

    assert remap_narration_character_ids(content, {"unrelated-id": "new-id"}) is None


def test_returns_none_when_content_is_not_narration_proposal_json():
    assert remap_narration_character_ids("Alex arrives at the market.", {"old-id": "new-id"}) is None
    assert remap_narration_character_ids("{not valid json", {"old-id": "new-id"}) is None
