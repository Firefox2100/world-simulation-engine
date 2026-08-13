"""Shared name-gathering/merging helpers for stage-2 character extraction.

`CharacterExtractor` (main, agent-driving characters) and `BackgroundCharacterExtractor` (minor,
reactive characters - see that module's docstring) both cluster candidate names out of the same
pool of character-related lorebook content. They need to agree on exactly what counts as "the same
name" so a name `BackgroundCharacterExtractor` treats as an orphan is recognized identically by
`CharacterExtractor`'s own clustering, and vice versa - a shared module keeps that single-sourced
instead of two copies drifting apart.
"""

from world_simulation_engine.misc.enums import LorebookItemBucket

from .lorebook_classifier import LorebookClassification

# A name shorter than this is never used as a merge target, to avoid a short/common substring
# accidentally absorbing an unrelated longer name.
MIN_NAME_MERGE_LENGTH = 2

# Every lorebook bucket that can carry a character's name, whether or not that name ever gets its
# own character_bio entry.
CHARACTER_RELATED_BUCKETS = (
    LorebookItemBucket.CHARACTER_BIO, LorebookItemBucket.CHARACTER_VOICE,
    LorebookItemBucket.HISTORY_EVENT, LorebookItemBucket.RELATIONSHIP,
)


def character_related_names(classification: LorebookClassification) -> set[str]:
    """Every distinct target_name appearing in any character-related bucket."""
    return {
        classified.target_name
        for bucket in CHARACTER_RELATED_BUCKETS
        for classified in classification.by_bucket(bucket)
        if classified.target_name
    }


def merge_similar_names(names: set[str]) -> dict[str, str]:
    """Map each name to a canonical form, merging names that are substrings of one another.

    Stage 1 classifies every item in isolation, so the same character can appear under different
    surface forms across items. Names shorter than `MIN_NAME_MERGE_LENGTH` are never merge targets.
    """
    canonical: dict[str, str] = {}
    for name in sorted(names, key=len, reverse=True):
        match = None
        for existing in dict.fromkeys(canonical.values()):
            if len(existing) < MIN_NAME_MERGE_LENGTH or len(name) < MIN_NAME_MERGE_LENGTH:
                continue
            if name in existing or existing in name:
                match = existing
                break
        canonical[name] = match or name
    return canonical
