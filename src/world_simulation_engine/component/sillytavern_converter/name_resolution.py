"""Shared name -> provisional-id resolution for stage-2/3 outputs that reference an
already-extracted entity by name (an LLM can copy a short string reasonably reliably, but not a
uuid - see SILLYTAVERN_IMPORT_PLAN.md §6.2).

Exact match comes first, followed by substring containment when exactly one candidate matches.
Ambiguous or very short partial matches remain unresolved.
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
