"""Publisher error-path and serialization tests.

All GCP infra is mocked: no Pub/Sub network calls, no Firestore, no credentials.
We patch reporium_events.build_counter.get_next_build_number (the Firestore hop)
and google.cloud.pubsub_v1.PublisherClient (the Pub/Sub transport).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from reporium_events.models import EVENT_SCHEMAS, EventType, ReporiumEvent
from reporium_events.publisher import publish_event


def _valid_payload(event_type: EventType) -> dict:
    """Build a payload that satisfies every required field for event_type."""
    return {field: f"value-{field}" for field in EVENT_SCHEMAS[event_type]}


async def _noop_build_number(source: str, project_id: str = "perditio-platform") -> int:
    return 42


class _FakeFuture:
    """Stand-in for the Pub/Sub publish future."""

    def __init__(self, result_value="message-id-1", exc: Exception | None = None):
        self._result_value = result_value
        self._exc = exc
        self.result_calls: list[dict] = []

    def result(self, timeout=None):
        self.result_calls.append({"timeout": timeout})
        if self._exc is not None:
            raise self._exc
        return self._result_value


class _FakePublisherClient:
    """Records publish() calls and returns a configurable future."""

    last_instance: "_FakePublisherClient | None" = None

    def __init__(self, future: _FakeFuture | None = None):
        self.future = future or _FakeFuture()
        self.publish_calls: list[dict] = []
        type(self).last_instance = self

    def topic_path(self, project_id: str, topic: str) -> str:
        return f"projects/{project_id}/topics/{topic}"

    def publish(self, topic_path, data, **attrs):
        self.publish_calls.append(
            {"topic_path": topic_path, "data": data, "attrs": attrs}
        )
        return self.future


def _patch_pubsub(client: _FakePublisherClient):
    """Patch the pubsub module so PublisherClient() returns our fake.

    publisher.py does `from google.cloud import pubsub_v1` inside the function,
    so we must patch the attribute on the real pubsub_v1 module.
    """
    from google.cloud import pubsub_v1

    return patch.object(pubsub_v1, "PublisherClient", lambda: client)


# ---------------------------------------------------------------------------
# Happy path: confirms the mock wiring produces a real, well-formed publish.
# ---------------------------------------------------------------------------


async def test_publish_event_serializes_payload_and_returns_event_id():
    client = _FakePublisherClient()
    with patch(
        "reporium_events.build_counter.get_next_build_number",
        new=_noop_build_number,
    ), _patch_pubsub(client):
        event_id = await publish_event(
            EventType.SYNC_COMPLETED,
            source="forksync",
            payload=_valid_payload(EventType.SYNC_COMPLETED),
        )

    # Exactly one publish, on the correct topic path, with the typed attrs.
    assert len(client.publish_calls) == 1
    call = client.publish_calls[0]
    assert call["topic_path"] == "projects/perditio-platform/topics/reporium-events"
    assert call["attrs"]["event_type"] == "sync.completed"
    assert call["attrs"]["source"] == "forksync"

    # The wire payload is valid JSON carrying the contract fields.
    wire = json.loads(call["data"].decode())
    assert wire["event_type"] == "sync.completed"
    assert wire["source"] == "forksync"
    assert wire["build_number"] == 42
    assert wire["schema_version"] == "1.0"
    assert wire["event_id"] == event_id
    # publish_event returns the same event_id it stamped on the wire.
    assert isinstance(event_id, str) and len(event_id) > 0

    # future.result was awaited with the 30s timeout the publisher specifies.
    assert client.future.result_calls == [{"timeout": 30}]


async def test_publish_event_routes_to_custom_project_and_topic():
    client = _FakePublisherClient()
    with patch(
        "reporium_events.build_counter.get_next_build_number",
        new=_noop_build_number,
    ), _patch_pubsub(client):
        await publish_event(
            EventType.API_DEPLOYED,
            source="reporium-api",
            payload=_valid_payload(EventType.API_DEPLOYED),
            project_id="other-project",
            topic="other-topic",
        )

    call = client.publish_calls[0]
    assert call["topic_path"] == "projects/other-project/topics/other-topic"


# ---------------------------------------------------------------------------
# Error path 1: malformed payload is rejected BEFORE any infra is touched.
# ---------------------------------------------------------------------------


async def test_publish_event_rejects_malformed_payload_before_publish():
    client = _FakePublisherClient()
    build_number_mock = MagicMock()

    with patch(
        "reporium_events.build_counter.get_next_build_number",
        new=build_number_mock,
    ), _patch_pubsub(client):
        with pytest.raises(ValueError) as exc_info:
            # SYNC_COMPLETED requires four fields; supply only one.
            await publish_event(
                EventType.SYNC_COMPLETED,
                source="forksync",
                payload={"repos_checked": 1},
            )

    # The error names the missing fields and the event type.
    msg = str(exc_info.value)
    assert "sync.completed" in msg
    assert "repos_synced" in msg

    # Validation short-circuits: neither Firestore nor Pub/Sub was contacted.
    build_number_mock.assert_not_called()
    assert client.publish_calls == []


async def test_publish_event_empty_payload_lists_all_required_fields():
    client = _FakePublisherClient()
    with patch(
        "reporium_events.build_counter.get_next_build_number",
        new=_noop_build_number,
    ), _patch_pubsub(client):
        with pytest.raises(ValueError) as exc_info:
            await publish_event(
                EventType.DB_SYNCED,
                source="dbsync",
                payload={},
            )

    msg = str(exc_info.value)
    for field in EVENT_SCHEMAS[EventType.DB_SYNCED]:
        assert field in msg
    assert client.publish_calls == []


# ---------------------------------------------------------------------------
# Error path 2: Pub/Sub publish transport failure propagates.
# ---------------------------------------------------------------------------


async def test_publish_event_propagates_publish_future_failure():
    failing_future = _FakeFuture(exc=RuntimeError("pubsub transport down"))
    client = _FakePublisherClient(future=failing_future)

    with patch(
        "reporium_events.build_counter.get_next_build_number",
        new=_noop_build_number,
    ), _patch_pubsub(client):
        with pytest.raises(RuntimeError, match="pubsub transport down"):
            await publish_event(
                EventType.HEALTH_CHECK,
                source="watchdog",
                payload=_valid_payload(EventType.HEALTH_CHECK),
            )

    # The publish was attempted exactly once before the future raised.
    assert len(client.publish_calls) == 1
    assert failing_future.result_calls == [{"timeout": 30}]


# ---------------------------------------------------------------------------
# Error path 3: Firestore build-number failure propagates and stops publish.
# ---------------------------------------------------------------------------


async def test_publish_event_propagates_build_number_failure_without_publishing():
    client = _FakePublisherClient()

    async def _boom(source: str, project_id: str = "perditio-platform") -> int:
        raise ConnectionError("firestore unreachable")

    with patch(
        "reporium_events.build_counter.get_next_build_number",
        new=_boom,
    ), _patch_pubsub(client):
        with pytest.raises(ConnectionError, match="firestore unreachable"):
            await publish_event(
                EventType.REPO_ADDED,
                source="forksync",
                payload=_valid_payload(EventType.REPO_ADDED),
            )

    # Build-number hop failed -> nothing was published.
    assert client.publish_calls == []


# ---------------------------------------------------------------------------
# EventType round-trip serialization (enum <-> wire string).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("event_type", list(EventType))
def test_event_type_round_trip_through_json(event_type: EventType):
    """An event serialized to JSON and back yields the same EventType.

    This is the cross-repo contract: a consumer (audit/db) reconstructs the
    enum from the wire string. Round-trip must be lossless for every member.
    """
    wire = json.dumps({"event_type": event_type.value})
    restored_value = json.loads(wire)["event_type"]
    assert restored_value == event_type.value
    # Reconstruct the enum from the raw string the consumer would see.
    assert EventType(restored_value) is event_type


@pytest.mark.parametrize("event_type", list(EventType))
def test_event_type_value_is_str_enum_member(event_type: EventType):
    """str-Enum members compare equal to their wire string (used by consumers)."""
    assert isinstance(event_type.value, str)
    assert event_type == event_type.value


def test_reporium_event_full_json_round_trip():
    """A ReporiumEvent serialized the way the publisher does survives a round-trip."""
    event = ReporiumEvent(
        event_type=EventType.BUILD_FAILED,
        source="ci",
        build_number=7,
        timestamp="2026-06-13T00:00:00+00:00",
        status="failure",
        payload={"service": "reporium-api", "workflow": "test", "error_summary": "x", "run_url": "u"},
        event_id="evt-1",
    )
    wire = json.dumps(
        {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "source": event.source,
            "build_number": event.build_number,
            "timestamp": event.timestamp,
            "status": event.status,
            "payload": event.payload,
            "schema_version": event.schema_version,
        }
    )
    restored = json.loads(wire)
    assert EventType(restored["event_type"]) is EventType.BUILD_FAILED
    assert restored["build_number"] == 7
    assert restored["schema_version"] == "1.0"
    assert restored["payload"]["service"] == "reporium-api"
