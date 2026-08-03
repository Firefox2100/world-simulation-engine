import io
import json
from pathlib import Path

import pytest
from PIL import Image

from world_simulation_engine.component.sillytavern_converter import DataExtractor
from world_simulation_engine.model.silly_tavern import SillyTavernCardV3


CARDS_DIR = Path("tests/evaluation_test/assets/st-cards")
OUTPUT_DIR = Path("tests/evaluation_test/assets/card-data")

CARD_PATHS = sorted(CARDS_DIR.glob("*.png")) if CARDS_DIR.is_dir() else []


@pytest.mark.parametrize(
    "card_path",
    CARD_PATHS or [pytest.param(None, marks=pytest.mark.skip(reason=f"No sample cards found in {CARDS_DIR}"))],
    ids=[path.stem for path in CARD_PATHS] or ["no_cards"],
)
def test_extract_sillytavern_card(card_path: Path):
    extractor = DataExtractor()
    card_bytes = card_path.read_bytes()

    extracted = extractor.extract(card_bytes)

    # The extractor always normalises to the V3 spec, regardless of whether the source card was
    # embedded as a "chara" (V2/legacy) or "ccv3" (V3) text chunk.
    assert isinstance(extracted.card, SillyTavernCardV3)
    assert extracted.card.spec == "chara_card_v3"
    assert extracted.card.spec_version == "3.0"
    assert extracted.card.data.name

    # The cleaned image must still be a valid, openable PNG, and must no longer carry the
    # embedded character card text chunks - those are persisted separately once converted.
    cleaned_image = Image.open(io.BytesIO(extracted.image))
    cleaned_image.load()
    assert cleaned_image.format == "PNG"
    assert "chara" not in cleaned_image.info
    assert "ccv3" not in cleaned_image.info

    # Round-trip the parsed model through JSON to make sure nothing generated here is only
    # representable in memory.
    dumped = extracted.card.model_dump(mode="json")
    assert SillyTavernCardV3.model_validate(dumped) == extracted.card

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / f"{card_path.stem}.json").write_text(
        json.dumps(dumped, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (OUTPUT_DIR / f"{card_path.stem}.png").write_bytes(extracted.image)
