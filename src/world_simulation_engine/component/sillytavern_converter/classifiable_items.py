"""The set of card fields/lorebook entries stage 1 classifies - shared with stage 2, since every
extractor needs to resolve a classified item's `item_id` back to its actual text content, using
exactly the same item set stage 1 classified against (otherwise an extractor could look up an id
stage 1 never produced, or vice versa).
"""

from pydantic import BaseModel, ConfigDict, Field

from .card_preprocessor import PreprocessedCard

# Card-level fields worth classifying individually - per cards 02/04, the "real" character
# definition or world lore is just as likely to live in a top-level field as in the lorebook.
# creator_notes is included because it is where authors put GM/author-only truth the character
# must not know (e.g. card 01's "CANONICAL GM-SIDE TRUTH") - exactly the hidden_truth bucket this
# pipeline's knowledge-boundary rule depends on catching, not incidental packaging metadata.
CLASSIFIABLE_FIELDS = (
    "description", "personality", "scenario", "system_prompt", "post_history_instructions", "creator_notes",
)


class ClassifiableItem(BaseModel):
    """One unit of stage-1 work: a non-empty card field or an enabled lorebook entry."""

    model_config = ConfigDict(extra="forbid")

    item_id: str = Field(description="'field:<name>' or 'entry:<source_id>' - traces back to PreprocessedCard")
    card_name: str
    label: str = Field(description="Human-readable name for this item, for prompt context only")
    content: str
    keys: list[str] = Field(default_factory=list, description="Lorebook trigger keywords, empty for card fields")


def classifiable_items(card: PreprocessedCard) -> list[ClassifiableItem]:
    items = []
    for field_name in CLASSIFIABLE_FIELDS:
        content = getattr(card, field_name)
        if content.strip():
            items.append(ClassifiableItem(
                item_id=f"field:{field_name}",
                card_name=card.name,
                label=field_name,
                content=content,
            ))
    for entry in card.lorebook_entries:
        items.append(ClassifiableItem(
            item_id=f"entry:{entry.source_id}",
            card_name=card.name,
            label=entry.name or entry.source_id,
            content=entry.content,
            keys=entry.keys,
        ))
    return items


def content_by_item_id(card: PreprocessedCard) -> dict[str, str]:
    """Convenience index for stage-2 extractors resolving a classified item's id back to text."""
    return {item.item_id: item.content for item in classifiable_items(card)}
