"""Safe, author-facing operational audit records for simulator runs."""
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from world_simulation_engine.misc.enums import SimulationAuditCategory, SimulationAuditOrigin, \
    SimulationAuditStatus


_SENSITIVE_KEY_PARTS = (
    "api_key", "apikey", "authorization", "credential", "password", "prompt",
    "raw_response", "reasoning", "secret", "token",
)
_MAX_TEXT_LENGTH = 1000
_MAX_COLLECTION_LENGTH = 100
_MAX_DEPTH = 5


def sanitize_audit_details(value: Any, *, _depth: int = 0) -> Any:
    """Return bounded JSON-compatible diagnostics with sensitive fields removed."""
    if _depth >= _MAX_DEPTH:
        return "[depth limit]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value[:_MAX_TEXT_LENGTH]
    if isinstance(value, BaseModel):
        return sanitize_audit_details(value.model_dump(mode="json"), _depth=_depth)
    if isinstance(value, dict):
        cleaned = {}
        for key, item in list(value.items())[:_MAX_COLLECTION_LENGTH]:
            safe_key = str(key)
            normalized = safe_key.casefold()
            if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
                continue
            cleaned[safe_key] = sanitize_audit_details(item, _depth=_depth + 1)
        return cleaned
    if isinstance(value, (list, tuple, set)):
        return [
            sanitize_audit_details(item, _depth=_depth + 1)
            for item in list(value)[:_MAX_COLLECTION_LENGTH]
        ]
    return str(value)[:_MAX_TEXT_LENGTH]


class SimulationAuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    simulation_id: str
    run_id: str | None = None
    turn_id: str | None = None
    category: SimulationAuditCategory
    origin: SimulationAuditOrigin = SimulationAuditOrigin.CODE
    status: SimulationAuditStatus = SimulationAuditStatus.COMPLETED
    stage: str
    summary: str = Field(min_length=1, max_length=500)
    actor_ids: list[str] = Field(default_factory=list, max_length=100)
    entity_ids: list[str] = Field(default_factory=list, max_length=100)
    details: dict[str, Any] = Field(default_factory=dict)
    simulation_time: datetime | None = None
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))

    @field_validator("details", mode="before")
    @classmethod
    def sanitize_details(cls, value):
        cleaned = sanitize_audit_details(value or {})
        return cleaned if isinstance(cleaned, dict) else {}

