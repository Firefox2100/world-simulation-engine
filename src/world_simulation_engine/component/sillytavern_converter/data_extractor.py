import base64
import io
import json
from dataclasses import dataclass
from typing import Any

from PIL import Image, UnidentifiedImageError

from world_simulation_engine.model.silly_tavern import SillyTavernCardV2, SillyTavernCardV3
from world_simulation_engine.service.storage_service import FormatNormaliser


@dataclass(frozen=True, slots=True)
class ExtractedCharacterCard:
    card: SillyTavernCardV3
    image: bytes | None = None


class DataExtractor:
    """Parses a SillyTavern character card into this system's card model.

    Two upload formats are supported: a PNG card, which embeds character data as base64-encoded
    JSON in PNG text chunks ("ccv3" holds a V3 card, "chara" holds a V2, or in older exports a
    spec-less V1, card - when both are present "chara" is kept only for backward compatibility
    with older readers, so "ccv3" takes precedence); and a plain JSON export of the same "chara"
    chunk payload, with no cover image. Format is detected from the file's magic bytes rather than
    its declared content type/filename, since neither is trustworthy.
    """

    _PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

    @staticmethod
    def _load_image(card_bytes: bytes) -> Image.Image:
        try:
            image = Image.open(io.BytesIO(card_bytes))
            # Text chunks that trail the image data (as SillyTavern's do) are only populated into
            # `.info` once the pixel data has been fully read.
            image.load()
        except UnidentifiedImageError as e:
            raise ValueError("File is not a valid image") from e

        return image

    @staticmethod
    def _decode_chunk(raw: str, *, chunk_name: str) -> dict[str, Any]:
        try:
            return json.loads(base64.b64decode(raw))
        except ValueError as e:
            raise ValueError(
                f"'{chunk_name}' text chunk does not contain a valid base64-encoded JSON payload"
            ) from e

    @staticmethod
    def _repair_v3_character_book(payload: dict[str, Any]) -> dict[str, Any]:
        """Backfill lorebook entry fields some real-world "V3" exports omit.

        A number of card editors label a card `spec: "chara_card_v3"` but still write V2-shaped
        lorebook entries that never had a reason to include the V3-only `use_regex`/`constant`
        fields, so those entries fail V3 validation despite the card otherwise being valid. Treat
        that the same way `SillyTavernCardV2.to_v3` already treats a genuine V2 card's entries:
        default `use_regex` to False and coerce `constant` to a bool.
        """
        character_book = payload.get("data", {}).get("character_book")
        if not character_book:
            return payload

        for entry in character_book.get("entries", []):
            entry.setdefault("use_regex", False)
            entry["constant"] = bool(entry.get("constant", False))

        return payload

    def _parse_card_payload(self, payload: dict[str, Any]) -> SillyTavernCardV3:
        spec = payload.get("spec")

        if spec == "chara_card_v3":
            return SillyTavernCardV3.model_validate(self._repair_v3_character_book(payload))
        if spec == "chara_card_v2":
            return SillyTavernCardV2.model_validate(payload).to_v3()

        raise ValueError(f"Unsupported or missing character card spec {spec!r}")

    def _parse_card(self, info: dict[str, Any]) -> SillyTavernCardV3:
        if "ccv3" in info:
            payload = self._decode_chunk(info["ccv3"], chunk_name="ccv3")
            return SillyTavernCardV3.model_validate(self._repair_v3_character_book(payload))

        if "chara" in info:
            payload = self._decode_chunk(info["chara"], chunk_name="chara")
            try:
                return self._parse_card_payload(payload)
            except ValueError as e:
                raise ValueError(f"{e} in 'chara' text chunk") from e

        raise ValueError("PNG does not contain an embedded SillyTavern character card ('chara'/'ccv3' text chunk)")

    def _extract_png(self, card_bytes: bytes) -> ExtractedCharacterCard:
        image = self._load_image(card_bytes)
        card = self._parse_card(image.info)
        cleaned_image = FormatNormaliser.normalise_image(card_bytes)

        return ExtractedCharacterCard(card=card, image=cleaned_image)

    def _extract_json(self, card_bytes: bytes) -> ExtractedCharacterCard:
        try:
            payload = json.loads(card_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ValueError("File is not a valid PNG character card or JSON character card export") from e

        if not isinstance(payload, dict):
            raise ValueError("JSON character card export must be a JSON object")

        return ExtractedCharacterCard(card=self._parse_card_payload(payload), image=None)

    def extract(self, card_bytes: bytes) -> ExtractedCharacterCard:
        """Parse a character card, either a PNG with the card embedded in its text chunks or a
        plain JSON export of the same payload, detected from the file's magic bytes.

        For a PNG upload, returns the character data normalised to the V3 spec alongside the PNG
        re-encoded without its embedded text chunks - the card data is restructured and persisted
        separately by later stages of the import workflow, so it must not be duplicated inside the
        stored image. A JSON upload carries no image, so `image` is `None`.
        """
        if card_bytes.startswith(self._PNG_MAGIC):
            return self._extract_png(card_bytes)

        return self._extract_json(card_bytes)
