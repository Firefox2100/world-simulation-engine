"""Application-wide structured event logging.

Langfuse owns model-call traces. This logger records important lifecycle facts only.
"""
import json
import logging
from typing import Any

from world_simulation_engine.model.simulation_audit import sanitize_audit_details

LOGGER_NAME = "world_simulation_engine.events"


def configure_event_logging() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log_event(event: str, **fields: Any) -> None:
    payload = sanitize_audit_details({"event": event, **fields})
    configure_event_logging().info(json.dumps(payload, sort_keys=True, default=str))

