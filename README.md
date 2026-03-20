# reporium-events

<!-- perditio-badges-start -->
[![Tests](https://github.com/perditioinc/reporium-events/actions/workflows/test.yml/badge.svg)](https://github.com/perditioinc/reporium-events/actions/workflows/test.yml)
![Last Commit](https://img.shields.io/github/last-commit/perditioinc/reporium-events)
![python](https://img.shields.io/badge/python-3.11%2B-3776ab)
![suite](https://img.shields.io/badge/suite-Reporium-6e40c9)
<!-- perditio-badges-end -->

> Event schema definitions and Python publisher client for the Reporium platform event system using GCP Pub/Sub.

## Install

```bash
pip install git+https://github.com/perditioinc/reporium-events.git
```

## Usage

```python
from reporium_events import publish_event, EventType

await publish_event(
    event_type=EventType.SYNC_COMPLETED,
    source="forksync",
    payload={
        "repos_checked": 826,
        "repos_synced": 12,
        "duration_seconds": 68,
        "errors": 0,
    },
)
```

## Event Types

| Event | Source | Required Payload |
|---|---|---|
| `sync.completed` | forksync | repos_checked, repos_synced, duration_seconds, errors |
| `db.synced` | reporium-db | repos_tracked, new_repos, updated_repos, duration_seconds, api_calls |
| `ingestion.completed` | reporium-ingestion | repos_enriched, categories_added, duration_seconds |
| `repo.added` | any | name_with_owner, stars, language |
| `repo.updated` | any | name_with_owner, changed_fields |
| `health.check` | reporium-audit | service, status, details |
| `build.failed` | any | service, workflow, error_summary, run_url |
| `api.deployed` | reporium-api | service, version, url |
