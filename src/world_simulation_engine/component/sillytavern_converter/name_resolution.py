"""Shared name -> provisional-id resolution for stage-2/3 outputs that reference an
already-extracted entity by name (an LLM can copy a short string reasonably reliably, but not a
uuid - see SILLYTAVERN_IMPORT_PLAN.md §6.2).

Exact match first, falling back to substring containment when there's exactly one candidate it
could mean - this local model doesn't always reproduce a multi-part name byte-for-byte across
calls (confirmed on a real card: a relationship about "艾琳·莫里亚蒂" failed to resolve under
exact-match-only lookup because the model returned the shorter "艾琳"). An ambiguous partial match
(more than one candidate) or a name below the minimum length is treated as unresolved rather than
guessed at - same guard `CharacterExtractor._merge_similar_names` uses for the same reason.
"""

_MIN_FUZZY_NAME_LENGTH = 2


def resolve_name(name: str, id_by_name: dict[str, str]) -> str | None:
    if name in id_by_name:
        return id_by_name[name]
    if len(name) < _MIN_FUZZY_NAME_LENGTH:
        return None
    matches = [
        roster_name for roster_name in id_by_name
        if len(roster_name) >= _MIN_FUZZY_NAME_LENGTH
        and (name in roster_name or roster_name in name)
    ]
    return id_by_name[matches[0]] if len(matches) == 1 else None


def resolve_names(names: list[str], id_by_name: dict[str, str]) -> list[str]:
    return [entity_id for name in names if (entity_id := resolve_name(name, id_by_name))]
