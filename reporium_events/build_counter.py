"""Firestore build number tracking."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def get_next_build_number(source: str, project_id: str = "perditio-platform") -> int:
    """Atomically increment build counter for source in Firestore.

    Collection: build_counters, document: source name.
    """
    from google.cloud.firestore_v1 import AsyncClient

    db = AsyncClient(project=project_id)
    doc_ref = db.collection("build_counters").document(source)

    @db.async_transactional
    async def update_in_transaction(transaction):
        snapshot = await doc_ref.get(transaction=transaction)
        current = snapshot.get("count") if snapshot.exists else 0
        next_val = current + 1
        transaction.set(doc_ref, {"count": next_val})
        return next_val

    transaction = db.transaction()
    return await update_in_transaction(transaction)
