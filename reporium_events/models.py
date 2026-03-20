"""Event models and schema definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class EventType(str, Enum):
    SYNC_COMPLETED = "sync.completed"
    DB_SYNCED = "db.synced"
    INGESTION_COMPLETED = "ingestion.completed"
    REPO_ADDED = "repo.added"
    REPO_UPDATED = "repo.updated"
    HEALTH_CHECK = "health.check"
    BUILD_FAILED = "build.failed"
    API_DEPLOYED = "api.deployed"


@dataclass
class ReporiumEvent:
    event_type: EventType
    source: str
    build_number: int
    timestamp: str
    status: str
    payload: dict[str, Any]
    event_id: str
    schema_version: str = "1.0"


EVENT_SCHEMAS: dict[EventType, list[str]] = {
    EventType.SYNC_COMPLETED: [
        "repos_checked", "repos_synced", "duration_seconds", "errors",
    ],
    EventType.DB_SYNCED: [
        "repos_tracked", "new_repos", "updated_repos", "duration_seconds", "api_calls",
    ],
    EventType.INGESTION_COMPLETED: [
        "repos_enriched", "categories_added", "duration_seconds",
    ],
    EventType.REPO_ADDED: ["name_with_owner", "stars", "language"],
    EventType.REPO_UPDATED: ["name_with_owner", "changed_fields"],
    EventType.HEALTH_CHECK: ["service", "status", "details"],
    EventType.BUILD_FAILED: ["service", "workflow", "error_summary", "run_url"],
    EventType.API_DEPLOYED: ["service", "version", "url"],
}
