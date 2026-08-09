import base64
import io
import json

import pytest
from PIL import Image, PngImagePlugin

from world_simulation_engine.component.sillytavern_converter import DataExtractor

_V3_DATA = {
    "name": "Example",
    "description": "desc",
    "personality": "p",
    "scenario": "s",
    "first_mes": "hi",
    "mes_example": "",
    "creator_notes": "",
    "system_prompt": "",
    "post_history_instructions": "",
    "alternate_greetings": [],
    "character_book": None,
    "tags": [],
    "creator": "",
    "character_version": "",
    "extensions": {},
}


def _v3_payload() -> dict:
    return {"spec": "chara_card_v3", "spec_version": "3.0", "data": _V3_DATA}


def _v2_payload() -> dict:
    data = {k: v for k, v in _V3_DATA.items() if k != "character_book"}
    return {"spec": "chara_card_v2", "spec_version": "2.0", "data": data}


def _png_with_chunk(chunk_name: str, payload: dict) -> bytes:
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text(chunk_name, base64.b64encode(json.dumps(payload).encode()).decode())
    output = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(output, format="PNG", pnginfo=metadata)
    return output.getvalue()


def test_extract_parses_a_png_with_a_ccv3_chunk_and_returns_the_cleaned_image():
    extracted = DataExtractor().extract(_png_with_chunk("ccv3", _v3_payload()))

    assert extracted.card.data.name == "Example"
    assert extracted.image is not None


def test_extract_parses_a_plain_json_v3_export_with_no_image():
    extracted = DataExtractor().extract(json.dumps(_v3_payload()).encode())

    assert extracted.card.data.name == "Example"
    assert extracted.image is None


def test_extract_parses_a_plain_json_v2_export_and_converts_to_v3():
    extracted = DataExtractor().extract(json.dumps(_v2_payload()).encode())

    assert extracted.card.data.name == "Example"
    assert extracted.image is None


def test_extract_rejects_json_missing_a_supported_spec():
    with pytest.raises(ValueError, match="Unsupported or missing character card spec"):
        DataExtractor().extract(json.dumps({"name": "No spec"}).encode())


def test_extract_rejects_unparsable_bytes():
    with pytest.raises(ValueError):
        DataExtractor().extract(b"not a png and not json either")


def test_extract_rejects_a_png_with_no_embedded_card():
    output = io.BytesIO()
    Image.new("RGB", (2, 2), "white").save(output, format="PNG")

    with pytest.raises(ValueError, match="does not contain an embedded SillyTavern character card"):
        DataExtractor().extract(output.getvalue())
