"""Tests for event models and validation."""

from reporium_events.models import EVENT_SCHEMAS, EventType, ReporiumEvent
from reporium_events.validator import validate_payload


def test_event_type_values():
    assert EventType.SYNC_COMPLETED == "sync.completed"
    assert EventType.DB_SYNCED == "db.synced"


def test_reporium_event_dataclass():
    event = ReporiumEvent(
        event_type=EventType.SYNC_COMPLETED,
        source="forksync",
        build_number=1,
        timestamp="2026-03-20T00:00:00Z",
        status="success",
        payload={"repos_checked": 826},
        event_id="abc-123",
    )
    assert event.schema_version == "1.0"
    assert event.source == "forksync"


def test_validate_payload_valid():
    missing = validate_payload(
        EventType.SYNC_COMPLETED,
        {"repos_checked": 826, "repos_synced": 12, "duration_seconds": 68, "errors": 0},
    )
    assert missing == []


def test_validate_payload_missing_fields():
    missing = validate_payload(EventType.SYNC_COMPLETED, {"repos_checked": 826})
    assert "repos_synced" in missing
    assert "duration_seconds" in missing
    assert "errors" in missing


def test_all_event_types_have_schemas():
    for et in EventType:
        assert et in EVENT_SCHEMAS
