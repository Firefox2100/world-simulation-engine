from typing import Literal, Optional, Any
from pydantic import BaseModel, Field

from .card_v2 import SillyTavernCardV2BookEntry, SillyTavernCardV2CharacterBook, SillyTavernCardV2Data


class SillyTavernCardV3BookEntry(SillyTavernCardV2BookEntry):
    use_regex: bool = Field(
        ...,
        description="Whether to use regex for matching",
    )
    constant: bool = Field(
        ...,
        description="If true, always insert into the prompt",
    )


class SillyTavernCardV3LoreBook(SillyTavernCardV2CharacterBook):
    entries: list[SillyTavernCardV3BookEntry] = Field(
        default_factory=list,
        description="The entries inside the lore book",
    )


class SillyTavernCardV3Asset(BaseModel):
    type: str = Field(
        ...,
        description="The type of the asset",
    )
    uri: str = Field(
        ...,
        description="The URI of the asset",
    )
    name: str = Field(
        ...,
        description="The name of the asset",
    )
    ext: str = Field(
        ...,
        description="The extension of the asset",
    )


class SillyTavernCardV3Data(SillyTavernCardV2Data):
    assets: Optional[list[SillyTavernCardV3Asset]] = Field(
        None,
        description="A list of assets used by this card"
    )
    nickname: Optional[str] = Field(
        None,
        description="The nickname of the character",
    )
    creator_notes_multilingual: Optional[dict[str, str]] = Field(
        None,
        description="The creator notes in different languages, the key being ISO 639-1 code, value being the "
                    "creator notes in that language",
    )
    source: Optional[list[str]] = Field(
        None,
        description="The source URL or IDs of this character card",
    )
    group_only_greetings: list[str] = Field(
        default_factory=list,
        description="A list of greetings used only in group chats"
    )
    creation_date: Optional[int] = Field(
        None,
        description="The creation time of this card, in Unix seconds",
    )
    modification_date: Optional[int] = Field(
        None,
        description="The modification time of this card, in Unix seconds",
    )

    character_book: Optional[SillyTavernCardV3LoreBook] = Field(
        None,
        description="A character-specific lore book",
    )


class SillyTavernCardV3(BaseModel):
    spec: Literal["chara_card_v3"]
    spec_version: Literal["3.0"]
    data: SillyTavernCardV3Data = Field(
        ...,
        description="The tavern card data",
    )
