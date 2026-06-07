# Local OSS substrate for reporium-events

A self-contained, $0, local-only dev substrate that runs the full
publish -> subscribe event path without any real GCP project, credentials,
or spend. It is purely additive: no application code is modified, and nothing
here touches production or live cloud.

## Cloud -> OSS map

| Production dependency | Local OSS substitute | How the app finds it |
|---|---|---|
| GCP Pub/Sub (`publisher.py`) | Pub/Sub emulator (`gcloud beta emulators pubsub`) | `PUBSUB_EMULATOR_HOST` env var, auto-detected by `google-cloud-pubsub` |
| GCP Firestore (`build_counter.py`) | Firestore emulator (`gcloud beta emulators firestore`) | `FIRESTORE_EMULATOR_HOST` env var, auto-detected by `google-cloud-firestore` |

Both emulators ship in the official `google-cloud-cli:emulators` image and are
free to run locally. The `google-cloud-*` client libraries switch to the
emulators automatically when the `*_EMULATOR_HOST` vars are present, so the
published client code runs unchanged (env-pointed stub, zero app edits).

## Requirements

- Docker (with `docker compose`)
- make (optional; you can run the scripts directly)

No host Python is required: the smoke test runs inside a `python:3.12-slim`
container attached to the compose network.

## Usage

```bash
cp .env.example .env        # optional; defaults work out of the box

make up      # start both emulators, wait until healthy
make smoke   # create topic + subscription, publish, pull, assert delivery
make down    # stop and remove everything (-v)
```

From the repo root you can also use the passthrough targets:

```bash
make local-up
make local-smoke
make local-down
```

## What the smoke proves

`scripts/smoke.py`:

1. Creates the `reporium-events` topic on the emulator.
2. Creates a subscription on that topic **before** publishing.
3. Publishes a real `sync.completed` event via `reporium_events.publish_event`.
4. Asserts the Firestore-backed build counter returns a number and increments.
5. Pulls from the subscription and asserts the published event was delivered
   (matching `event_id`, `event_type`, and `payload`).

Step 2 plus step 5 guard the known live bug: a Pub/Sub topic with zero
subscriptions silently drops events. The smoke asserts that
publish -> subscribe actually delivers.

Exit code is 0 on `SMOKE PASS`, non-zero on any failure.
