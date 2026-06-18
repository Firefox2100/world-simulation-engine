import base64
import io
import json
from PIL import Image

from world_simulation_engine.model import SillyTavernCardV2, SillyTavernCardV3
from world_simulation_engine.service import DatabaseService


class SillyTavernImporter:
    def __init__(self,
                 db: DatabaseService,
                 ):
        self._db = db

    @staticmethod
    def _extract_v2_card(card_data: bytes) -> SillyTavernCardV2:
        image = Image.open(io.BytesIO(card_data))
        payload = image.text.get("chara")
        if not payload:
            raise ValueError("The character card is not a valid Silly Tavern v2 card. Missing 'chara' metadata.")

        decoded = base64.b64encode(payload).decode("utf-8")

        return SillyTavernCardV2.model_validate(decoded)

    @staticmethod
    def _extract_v3_card(card_data: bytes) -> SillyTavernCardV3:
        image = Image.open(io.BytesIO(card_data))
        payload = image.text.get("ccv3")
        if not payload:
            raise ValueError("The character card is not a valid Silly Tavern v3 card. Missing 'ccv3' metadata.")

        decoded = base64.b64decode(payload).decode("utf-8")

        return SillyTavernCardV3.model_validate_json(decoded)

    def _extract_card(self, card_data: bytes) -> SillyTavernCardV3:
        try:
            # Try to decode as JSON first
            json_text = card_data.decode("utf-8")
            json_data = json.loads(json_text)

            if json_data.get("spec") == "chara_card_v3" and json_data.get("spec_version") == "3.0":
                # Silly Tavern V3 card
                return SillyTavernCardV3.model_validate(json_data)
            elif json_data.get("spec") == "chara_card_v2" and json_data.get("spec_version") == "2.0":
                # Silly Tavern V2 card
                v2_card = SillyTavernCardV2.model_validate(json_data)
                return v2_card.to_v3()
        except Exception:
            pass

        try:
            image = Image.open(io.BytesIO(card_data))
            if image.format != "PNG":
                raise ValueError("The card is not a PNG image. Silly Tavern cards can only use PNG containers.")

            try:
                return self._extract_v3_card(card_data)
            except ValueError:
                # Maybe a V2 card
                v2_card = self._extract_v2_card(card_data)
                return v2_card.to_v3()
        except Exception:
            pass

        raise ValueError("Decoding failed for the uploaded card. It's not a valid Silly Tavern card.")

    async def import_card(self, card_data: bytes):
        card = self._extract_card(card_data)
