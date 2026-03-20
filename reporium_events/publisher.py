"""Async Pub/Sub publisher for Reporium platform events."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from reporium_events.models import EventType, ReporiumEvent
from reporium_events.validator import validate_payload

logger = logging.getLogger(__name__)


async def publish_event(
    event_type: EventType,
    source: str,
    payload: dict[str, Any],
    status: str = "success",
    project_id: str = "perditio-platform",
    topic: str = "reporium-events",
) -> str:
    """Publish typed event to GCP Pub/Sub reporium-events topic.

    Validates payload against EVENT_SCHEMAS before publishing.
    Fetches and increments build_number from Firestore atomically.
    Returns event_id.
    """
    missing = validate_payload(event_type, payload)
    if missing:
        raise ValueError(f"Missing required fields for {event_type.value}: {missing}")

    from reporium_events.build_counter import get_next_build_number

    build_number = await get_next_build_number(source, project_id)
    event_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat()

    event = ReporiumEvent(
        event_type=event_type,
        source=source,
        build_number=build_number,
        timestamp=timestamp,
        status=status,
        payload=payload,
        event_id=event_id,
    )

    from google.cloud import pubsub_v1

    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic)

    data = json.dumps({
        "event_id": event.event_id,
        "event_type": event.event_type.value,
        "source": event.source,
        "build_number": event.build_number,
        "timestamp": event.timestamp,
        "status": event.status,
        "payload": event.payload,
        "schema_version": event.schema_version,
    }).encode()

    future = publisher.publish(
        topic_path,
        data,
        event_type=event.event_type.value,
        source=event.source,
    )
    future.result(timeout=30)

    logger.info("Published %s event from %s (build %d)", event_type.value, source, build_number)
    return event_id
