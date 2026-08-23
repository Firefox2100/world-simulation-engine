"""Shared helper for rewriting `SpeechBlock.character_id` references embedded in a serialized
`NarrationProposal` (a `Turn.content` value) - needed wherever a character/background-character id
changes but a turn's opaque JSON content must keep pointing at the right entity: copying a world's
turns into a new simulation (`TurnStore.copy_turns` + `TurnStore.remap_copied_turn_speaker_ids`),
and importing a world archive/assembled bundle (`WorldImportService._import_turns`) - the latter
remaps extraction-stage character ids (assigned by the SillyTavern pipeline before any database
row exists) to the freshly created `Character`/`BackgroundCharacter` ids.
"""

from pydantic import ValidationError

from world_simulation_engine.model import NarrationProposal, SpeechBlock


def remap_narration_character_ids(content: str, id_map: dict[str, str]) -> str | None:
    """Returns the remapped JSON if `content` is `NarrationProposal`-shaped and at least one
    embedded `SpeechBlock.character_id` was found in `id_map`, else `None` (not applicable, or
    nothing needed remapping)."""
    try:
        proposal = NarrationProposal.model_validate_json(content)
    except (ValidationError, ValueError):
        return None

    changed = False
    for block in proposal.blocks:
        if isinstance(block, SpeechBlock) and block.character_id in id_map:
            block.character_id = id_map[block.character_id]
            changed = True

    return proposal.model_dump_json() if changed else None
