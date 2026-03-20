"""Schema validation per event type."""

from __future__ import annotations

from typing import Any

from reporium_events.models import EVENT_SCHEMAS, EventType


def validate_payload(event_type: EventType, payload: dict[str, Any]) -> list[str]:
    """Validate payload has required fields for event type. Returns list of missing fields."""
    required = EVENT_SCHEMAS.get(event_type, [])
    return [f for f in required if f not in payload]
