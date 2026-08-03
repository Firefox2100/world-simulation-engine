import json
import re
from pathlib import Path

import pytest

from world_simulation_engine.component.sillytavern_converter import CardPreprocessor, DataExtractor


CARDS_DIR = Path("tests/evaluation_test/assets/st-cards")
OUTPUT_DIR = Path("tests/evaluation_test/assets/card-data")

CARD_PATHS = sorted(CARDS_DIR.glob("*.png")) if CARDS_DIR.is_dir() else []

_RAW_MACRO_PATTERN = re.compile(r"\{\{\s*char\s*\}\}|\{\{\s*user\s*\}\}|<BOT>|<USER>", re.IGNORECASE)


@pytest.mark.parametrize(
    "card_path",
    CARD_PATHS or [pytest.param(None, marks=pytest.mark.skip(reason=f"No sample cards found in {CARDS_DIR}"))],
    ids=[path.stem for path in CARD_PATHS] or ["no_cards"],
)
def test_preprocess_real_sillytavern_card(card_path: Path):
    extracted = DataExtractor().extract(card_path.read_bytes())
    preprocessed = CardPreprocessor.preprocess(extracted.card)

    # No raw SillyTavern macro syntax should survive stage 0 - every occurrence in every
    # normalized free-text field must have become this system's own placeholder syntax.
    normalized_fields = [
        preprocessed.description,
        preprocessed.personality,
        preprocessed.scenario,
        preprocessed.first_message,
        preprocessed.system_prompt,
        preprocessed.post_history_instructions,
        preprocessed.creator_notes,
        *preprocessed.example_dialogue,
        *(entry.content for entry in preprocessed.lorebook_entries),
    ]
    for field in normalized_fields:
        assert not _RAW_MACRO_PATTERN.search(field), f"Unnormalized macro survived in: {field[:200]!r}"

    # Only enabled entries survive, and every one keeps a traceable source_id.
    assert all(entry.source_id for entry in preprocessed.lorebook_entries)

    # A card with no lorebook at all still preprocesses cleanly to an empty list, not an error.
    if extracted.card.data.character_book is None:
        assert preprocessed.lorebook_entries == []

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{card_path.stem}.preprocessed.json").write_text(
        json.dumps(preprocessed.model_dump(mode="json"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
