"""Schema-invariant tests guarding the cross-repo event contract.

These invariants protect the contract consumed by downstream repos (audit/db)
that deserialize events off the Pub/Sub topic. They assert structural
properties that must hold for EVERY EventType, so a future edit that adds a
member, renames a value, or empties a schema fails loudly here rather than
silently breaking a consumer.

No infra is touched: pure introspection of models.
"""

from __future__ import annotations

import re

from reporium_events.models import EVENT_SCHEMAS, EventType


# ---------------------------------------------------------------------------
# Every EventType has a stable, well-formed string value.
# ---------------------------------------------------------------------------


def test_every_event_type_has_str_value():
    for et in EventType:
        assert isinstance(et.value, str)
        assert et.value, f"{et.name} has an empty wire value"


def test_event_type_values_follow_dotted_namespace_convention():
    """Wire values are lowercase 'namespace.action' tokens.

    Consumers route on this shape; an off-convention value (uppercase, spaces,
    extra dots) would silently mis-route.
    """
    pattern = re.compile(r"^[a-z]+\.[a-z]+$")
    for et in EventType:
        assert pattern.match(et.value), f"{et.name}={et.value!r} breaks namespace convention"


def test_event_type_values_are_unique():
    """No two members may share a wire value, else dispatch is ambiguous."""
    values = [et.value for et in EventType]
    assert len(values) == len(set(values)), f"duplicate EventType values: {values}"


def test_event_type_names_are_unique_against_values():
    """The name->value map is a bijection (no collisions either direction)."""
    by_value = {et.value: et.name for et in EventType}
    assert len(by_value) == len(list(EventType))


# ---------------------------------------------------------------------------
# Stable-value guard: pins the exact wire strings of the current contract.
# Changing any of these is a breaking change for audit/db consumers and must
# be a deliberate edit to this test, not an accident in models.py.
# ---------------------------------------------------------------------------

EXPECTED_EVENT_VALUES = {
    "SYNC_COMPLETED": "sync.completed",
    "DB_SYNCED": "db.synced",
    "INGESTION_COMPLETED": "ingestion.completed",
    "REPO_ADDED": "repo.added",
    "REPO_UPDATED": "repo.updated",
    "HEALTH_CHECK": "health.check",
    "BUILD_FAILED": "build.failed",
    "API_DEPLOYED": "api.deployed",
}


def test_event_type_wire_values_are_stable():
    """The published contract for each known member must not drift."""
    actual = {et.name: et.value for et in EventType}
    assert actual == EXPECTED_EVENT_VALUES


# ---------------------------------------------------------------------------
# Every EventType has a required-fields schema, and those schemas are sane.
# ---------------------------------------------------------------------------


def test_every_event_type_has_a_schema_entry():
    for et in EventType:
        assert et in EVENT_SCHEMAS, f"{et.name} is missing from EVENT_SCHEMAS"


def test_no_orphan_schema_entries():
    """EVENT_SCHEMAS keys must all be real EventType members."""
    for key in EVENT_SCHEMAS:
        assert isinstance(key, EventType)


def test_schema_keys_match_event_type_set_exactly():
    """The schema map covers the EventType set with no gaps and no extras."""
    assert set(EVENT_SCHEMAS.keys()) == set(EventType)


def test_every_schema_has_at_least_one_required_field():
    """A consumer relies on required fields to validate; an empty list is a bug."""
    for et, fields in EVENT_SCHEMAS.items():
        assert len(fields) >= 1, f"{et.name} has no required fields"


def test_schema_required_fields_are_nonempty_unique_strings():
    for et, fields in EVENT_SCHEMAS.items():
        for f in fields:
            assert isinstance(f, str) and f, f"{et.name} has a non-string/empty field"
        assert len(fields) == len(set(fields)), f"{et.name} has duplicate required fields"
