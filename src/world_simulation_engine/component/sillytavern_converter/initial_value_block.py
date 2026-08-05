"""Shared heuristic for detecting an MVU-style `<UpdateVariable><initvar>...</initvar>
</UpdateVariable>` block in a card's opening message - the source both `VariableSchemaExtractor` and
`EquipmentExtractor` parse for real per-character initial values (generic tracked stats and worn
clothing respectively), gated so cards without such a block never spend an LLM call looking for one.
"""

_INITIAL_VALUE_BLOCK_MARKERS = ("updatevariable", "initvar")


def has_initial_value_block(first_message: str) -> bool:
    lowered = first_message.lower()
    return any(marker in lowered for marker in _INITIAL_VALUE_BLOCK_MARKERS)
