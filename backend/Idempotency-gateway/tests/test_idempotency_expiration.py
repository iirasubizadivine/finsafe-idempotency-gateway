
from datetime import datetime, timedelta, timezone

import pytest

from app.storage.idempotency_store import InMemoryIdempotencyStore


@pytest.mark.asyncio
async def test_key_is_reused_after_expiration():
    store = InMemoryIdempotencyStore(ttl_seconds=86400)

    # Create the first record
    record, is_new = await store.get_or_create(
        key="expiration-test",
        fingerprint="fingerprint-1"
    )

    assert is_new is True

    # Complete the payment
    await store.complete(
        key="expiration-test",
        response_body={"message": "Charged 100 RWF"},
        status_code=200
    )

    # Before expiration, the existing record should be returned
    existing_record, is_new = await store.get_or_create(
        key="expiration-test",
        fingerprint="fingerprint-1"
    )

    assert is_new is False
    assert existing_record is record

    # Simulate 24 hours passing
    record.completed_at = (
        datetime.now(timezone.utc) - timedelta(hours=25)
    )

    # The expired key should now create a new record
    new_record, is_new = await store.get_or_create(
        key="expiration-test",
        fingerprint="fingerprint-1"
    )

    assert is_new is True
    assert new_record is not record
    assert new_record.status == "processing"


@pytest.mark.asyncio
async def test_cleanup_does_not_remove_processing_records():
    store = InMemoryIdempotencyStore(ttl_seconds=86400)

    record, is_new = await store.get_or_create(
        key="processing-test",
        fingerprint="fingerprint-2"
    )

    assert is_new is True

    # Simulate an old creation time
    record.created_at = (
        datetime.now(timezone.utc) - timedelta(hours=25)
    )

    removed = await store.cleanup_expired()

    assert removed == 0
    assert await store.count() == 1
