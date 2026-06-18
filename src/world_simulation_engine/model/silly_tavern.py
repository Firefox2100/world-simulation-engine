from typing import Literal, Optional, Any
from pydantic import BaseModel, Field


class SillyTavernCardV2BookEntry(BaseModel):
    keys: list[str] = Field(
        ...,
        description="The keywords to match against the chat history",
    )
    content: str = Field(
        ...,
        description="The content of the lore book entry",
    )
    extensions: dict[str, Any] = Field(
        default_factory=dict,
        description="The extensions used by other applications",
    )
    enabled: bool = Field(
        ...,
        description="Whether the book entry is enabled",
    )
    insertion_order: int = Field(
        ...,
        description="The insertion order of the book entry. Lower value means higher position",
    )
    case_sensitive: Optional[bool] = Field(
        None,
        description="Whether the match is case-sensitive",
    )

    name: Optional[str] = Field(
        None,
        description="The name of the book entry",
    )
    priority: Optional[int] = Field(
        None,
        description="The priority of the book entry. If token budget reached, lower priority entries "
                    "will be skipped.",
    )

    id: Optional[int] = Field(
        None,
        description="The ID of the book entry",
    )
    comment: Optional[str] = Field(
        None,
        description="The comment of the book entry",
    )
    selective: Optional[bool] = Field(
        None,
        description="If true, require a key from both keys and secondary_keys to trigger"
    )
    secondary_keys: Optional[list[str]] = Field(
        None,
        description="A list of secondary keys",
    )
    constant: Optional[bool] = Field(
        None,
        description="If true, always insert into the prompt",
    )
    position: Optional[Literal["before_char", "after_char"]] = Field(
        None,
        description="Controls if the entry is placed before or after the character definition"
    )


class SillyTavernCardV2CharacterBook(BaseModel):
    name: Optional[str] = Field(
        None,
        description="The name of the character lore book",
    )
    description: Optional[str] = Field(
        None,
        description="The description of the character lore book",
    )
    scan_depth: Optional[int] = Field(
        None,
        description="The chat history depth to match against the keywords",
    )
    token_budget: Optional[int] = Field(
        None,
        description="The context limit of injection",
    )
    recursive_scanning: Optional[bool] = Field(
        None,
        description="Whether entry content can trigger other entries"
    )
    extensions: dict[str, Any] = Field(
        default_factory=dict,
        description="The extensions for applications to use",
    )
    entries: list[SillyTavernCardV2BookEntry] = Field(
        default_factory=list,
        description="The entries inside the lore book",
    )


class SillyTavernCardV2Data(BaseModel):
    # Core fields from V1
    name: str = Field(
        "",
        description="The name of the tavern card",
    )
    description: str = Field(
        "",
        description="The description of the tavern card",
    )
    personality: str = Field(
        "",
        description="The personality of the tavern card character",
    )
    scenario: str = Field(
        "",
        description="The scenario of the tavern card",
    )
    first_mes: str = Field(
        "",
        description="The first message by the character",
    )
    mes_example: str = Field(
        "",
        description="The example message by the character",
    )

    # V2 extended fields
    creator_notes: str = Field(
        "",
        description="The creator notes for user and bots to read",
    )
    system_prompt: str = Field(
        "",
        description="The system prompt override",
    )
    post_history_instructions: str = Field(
        "",
        description="The post history instructions",
    )
    alternate_greetings: list[str] = Field(
        default_factory=list,
        description="The alternate greetings/first messages the user can switch in between",
    )
    character_book: Optional[SillyTavernCardV2CharacterBook] = Field(
        None,
        description="A character-specific lore book"
    )

    # May 9th addition fields
    tags: list[str] = Field(
        default_factory=list,
        description="A list of tags",
    )
    creator: str = Field(
        "",
        description="The creator of the tavern card",
    )
    character_version: str = Field(
        "",
        description="The version of the tavern card",
    )
    extensions: dict[str, Any] = Field(
        default_factory=dict,
        description="The place to store arbitrary key-value pairs used by applications",
    )


class SillyTavernCardV2(BaseModel):
    spec: Literal["chara_card_v2"]
    spec_version: Literal["2.0"]
    data: SillyTavernCardV2Data = Field(
        ...,
        description="The tavern card data"
    )

    def to_v3(self) -> "SillyTavernCardV3":
        v2_data = self.data.model_dump()

        character_book_payload = v2_data.get("character_book")
        if character_book_payload is not None:
            v3_entries: list[dict[str, Any]] = []
            for index, entry in enumerate(character_book_payload.get("entries", [])):
                context = f"character_book.entries[{index}]"

                # Fields that are required in V3 and cannot be defaulted.
                keys = _get_required_value(entry, "keys", context)
                content = _get_required_value(entry, "content", context)
                enabled = _get_required_value(entry, "enabled", context)
                insertion_order = _get_required_value(entry, "insertion_order", context)

                v3_entries.append({
                    "keys": keys,
                    "content": content,
                    "extensions": entry.get("extensions") or {},
                    "enabled": enabled,
                    "insertion_order": insertion_order,
                    "case_sensitive": entry.get("case_sensitive"),
                    "name": entry.get("name"),
                    "priority": entry.get("priority"),
                    "id": entry.get("id"),
                    "comment": entry.get("comment"),
                    "selective": entry.get("selective"),
                    "secondary_keys": entry.get("secondary_keys"),
                    "position": entry.get("position"),
                    # V3-only required fields: default safely when absent in V2.
                    "use_regex": False,
                    "constant": bool(entry.get("constant", False)),
                })

            character_book_payload["entries"] = v3_entries

        v3_payload = {
            "spec": "chara_card_v3",
            "spec_version": "3.0",
            "data": {
                **v2_data,
                "extensions": v2_data.get("extensions") or {},
                "alternate_greetings": v2_data.get("alternate_greetings") or [],
                "tags": v2_data.get("tags") or [],
                "group_only_greetings": v2_data.get("group_only_greetings") or [],
                "character_book": character_book_payload,
            },
        }

        return SillyTavernCardV3.model_validate(v3_payload)


def _get_required_value(payload: dict[str, Any], field_name: str, context: str) -> Any:
    value = payload.get(field_name)
    if value is None:
        raise ValueError(f"Missing required field '{field_name}' in {context}")
    return value


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
