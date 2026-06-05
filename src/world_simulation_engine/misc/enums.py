from enum import StrEnum


class NarrationPermission(StrEnum):
    VISIBLE = "visible"
    MAY_HINT = "may_hint"
    INVISIBLE = "invisible"


class WorldEntryVisibility(StrEnum):
    KNOWN = "known"
    SUSPECTED = "suspected"
    PERCEIVED = "perceived"
    INFERRED = "inferred"
