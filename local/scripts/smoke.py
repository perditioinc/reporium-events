"""Local OSS smoke test for reporium-events.

Exercises the real publish -> subscribe delivery path against the local
Pub/Sub and Firestore emulators, using the unmodified package code.

Key assertion (guards the live bug noted in the epic): a Pub/Sub topic with
ZERO subscriptions silently drops published messages. So this smoke:

  1. creates the topic
  2. creates a subscription on it BEFORE publishing
  3. publishes a real event via reporium_events.publish_event
  4. pulls from the subscription and asserts the event is delivered

It also asserts the Firestore-backed build counter increments (proving the
build_counter path works against the emulator too).

Exits 0 on PASS, non-zero on FAIL.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from google.api_core import exceptions as gax_exceptions
from google.cloud import pubsub_v1

from reporium_events import EventType, publish_event

PROJECT_ID = os.environ.get("PUBSUB_PROJECT_ID", "perditio-platform")
TOPIC = os.environ.get("PUBSUB_TOPIC", "reporium-events")
SUBSCRIPTION = os.environ.get("PUBSUB_SUBSCRIPTION", "reporium-events-smoke")


def _fail(msg: str) -> None:
    print(f"SMOKE FAIL: {msg}")
    sys.exit(1)


def setup_topic_and_subscription() -> None:
    """Create topic and subscription on the emulator (idempotent)."""
    publisher = pubsub_v1.PublisherClient()
    subscriber = pubsub_v1.SubscriberClient()

    topic_path = publisher.topic_path(PROJECT_ID, TOPIC)
    sub_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION)

    try:
        publisher.create_topic(request={"name": topic_path})
        print(f"created topic: {topic_path}")
    except gax_exceptions.AlreadyExists:
        print(f"topic exists: {topic_path}")

    # Subscription MUST exist before publish, otherwise the message is dropped.
    try:
        subscriber.create_subscription(
            request={"name": sub_path, "topic": topic_path}
        )
        print(f"created subscription: {sub_path}")
    except gax_exceptions.AlreadyExists:
        print(f"subscription exists: {sub_path}")

    return sub_path


def pull_one(sub_path: str, timeout: float = 30.0) -> dict:
    """Pull a single message from the subscription and ack it."""
    subscriber = pubsub_v1.SubscriberClient()
    deadline = timeout
    # The emulator can need a moment; retry pulls until the deadline.
    import time

    end = time.time() + deadline
    while time.time() < end:
        resp = subscriber.pull(
            request={"subscription": sub_path, "max_messages": 1},
            timeout=10.0,
        )
        if resp.received_messages:
            rm = resp.received_messages[0]
            subscriber.acknowledge(
                request={"subscription": sub_path, "ack_ids": [rm.ack_id]}
            )
            return {
                "data": json.loads(rm.message.data.decode()),
                "attributes": dict(rm.message.attributes),
            }
        time.sleep(1.0)
    return {}


async def main() -> None:
    print("=== reporium-events local OSS smoke ===")
    print(f"PUBSUB_EMULATOR_HOST={os.environ.get('PUBSUB_EMULATOR_HOST')}")
    print(f"FIRESTORE_EMULATOR_HOST={os.environ.get('FIRESTORE_EMULATOR_HOST')}")

    if not os.environ.get("PUBSUB_EMULATOR_HOST"):
        _fail("PUBSUB_EMULATOR_HOST not set; refusing to run against real GCP")
    if not os.environ.get("FIRESTORE_EMULATOR_HOST"):
        _fail("FIRESTORE_EMULATOR_HOST not set; refusing to run against real GCP")

    sub_path = setup_topic_and_subscription()

    # Publish a real event through the package's public API.
    payload = {
        "repos_checked": 826,
        "repos_synced": 12,
        "duration_seconds": 68,
        "errors": 0,
    }
    event_id = await publish_event(
        event_type=EventType.SYNC_COMPLETED,
        source="smoke-test",
        payload=payload,
        project_id=PROJECT_ID,
        topic=TOPIC,
    )
    print(f"published event_id={event_id}")

    # Assert the build counter (Firestore emulator) produced a real number,
    # then assert it increments on a second call.
    from reporium_events.build_counter import get_next_build_number

    n1 = await get_next_build_number("smoke-test", PROJECT_ID)
    n2 = await get_next_build_number("smoke-test", PROJECT_ID)
    if n2 != n1 + 1:
        _fail(f"build counter did not increment: {n1} -> {n2}")
    print(f"build counter increments: {n1} -> {n2}  OK")

    # Pull and assert delivery (publish -> subscribe actually delivered).
    received = pull_one(sub_path)
    if not received:
        _fail("no message delivered to subscription (publish->subscribe broken)")

    data = received["data"]
    if data.get("event_id") != event_id:
        _fail(
            f"delivered event_id {data.get('event_id')} != published {event_id}"
        )
    if data.get("event_type") != EventType.SYNC_COMPLETED.value:
        _fail(f"unexpected event_type: {data.get('event_type')}")
    if data.get("payload") != payload:
        _fail(f"payload mismatch: {data.get('payload')}")

    print(f"delivered event_id={data['event_id']} type={data['event_type']}")
    print("publish -> subscribe delivery: OK")
    print("SMOKE PASS")


if __name__ == "__main__":
    asyncio.run(main())
