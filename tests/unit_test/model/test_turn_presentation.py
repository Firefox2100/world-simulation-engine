from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from world_simulation_engine.model import (
    PresentationBlockType,
    PresentationCompletion,
    TurnPresentationBlock,
    TurnPresentationRendering,
)


NOW = datetime(2026, 1, 1, tzinfo=UTC)


def block(sequence=0, **updates):
    values = dict(
        turn_id="turn_1",
        sequence=sequence,
        type=PresentationBlockType.NARRATION,
        text="Visible prose.",
        completion=PresentationCompletion.COMPLETE,
        created_at=NOW,
        updated_at=NOW,
    )
    values.update(updates)
    return TurnPresentationBlock(**values)


def test_rendering_keeps_order_and_completion_outside_canonical_turn():
    rendering = TurnPresentationRendering(
        turn_id="turn_1",
        blocks=[
            block(0),
            block(
                1,
                type=PresentationBlockType.SPEECH,
                text="Hello.",
                speaker_id="character_1",
                completion=PresentationCompletion.STREAMING,
            ),
        ],
    )

    assert [entry.sequence for entry in rendering.blocks] == [0, 1]
    assert rendering.blocks[1].completion == PresentationCompletion.STREAMING


def test_rendering_rejects_gaps_cross_variant_blocks_and_invalid_payloads():
    with pytest.raises(ValidationError, match="contiguous"):
        TurnPresentationRendering(turn_id="turn_1", blocks=[block(1)])
    with pytest.raises(ValidationError, match="belong to the rendering"):
        TurnPresentationRendering(
            turn_id="turn_1",
            blocks=[block(rendering_id="alternate")],
        )
    with pytest.raises(ValidationError, match="speaker attribution"):
        block(type=PresentationBlockType.SPEECH)
    with pytest.raises(ValidationError, match="media_id"):
        block(type=PresentationBlockType.MEDIA, text=None)
