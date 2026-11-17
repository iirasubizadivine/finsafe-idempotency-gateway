
import asyncio
import hashlib
import json
import logging

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class IdempotencyRecord:
    key: str
    fingerprint: str
    status: str = "processing"

    response_body: Optional[Dict[str, Any]] = None
    status_code: Optional[int] = None

    event: asyncio.Event = field(default_factory=asyncio.Event)

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    completed_at: Optional[datetime] = None


class InMemoryIdempotencyStore:

    def __init__(self, ttl_seconds: int = 86400):
        self._store: Dict[str, IdempotencyRecord] = {}
        self._lock = asyncio.Lock()
        self.ttl_seconds = ttl_seconds

    def _is_expired(self, record: IdempotencyRecord) -> bool:
        """
        Expiration starts after a payment has completed.

        Processing records must never expire.
        """

        if record.status != "completed":
            return False

        if record.completed_at is None:
            return False

        elapsed = (
            datetime.now(timezone.utc) - record.completed_at
        ).total_seconds()

        return elapsed >= self.ttl_seconds

    async def get_or_create(
        self,
        key: str,
        fingerprint: str
    ) -> Tuple[IdempotencyRecord, bool]:

        async with self._lock:

            record = self._store.get(key)

            if record is not None:

                if self._is_expired(record):

                    logger.info(
                        "Idempotency key expired: %s", key
                    )

                    del self._store[key]

                else:
                    return record, False

            record = IdempotencyRecord(
                key=key,
                fingerprint=fingerprint
            )

            self._store[key] = record

            return record, True

    async def complete(
        self,
        key: str,
        response_body: Dict[str, Any],
        status_code: int
    ) -> None:

        async with self._lock:

            record = self._store.get(key)

            if record is None:
                raise KeyError(
                    f"Idempotency record not found: {key}"
                )

            if record.status != "processing":
                raise ValueError(
                    "Only processing records can be completed."
                )

            record.response_body = response_body
            record.status_code = status_code
            record.status = "completed"

            # Start the 24-hour retention period now.
            record.completed_at = datetime.now(timezone.utc)

            # Notify concurrent requests waiting for this payment.
            record.event.set()

    async def fail(self, key: str) -> None:

        async with self._lock:

            record = self._store.get(key)

            if record is None or record.status != "processing":
                return

            record.status = "failed"

            # Wake up waiting requests.
            record.event.set()

            # Allow a retry after a failed payment.
            if self._store.get(key) is record:
                del self._store[key]

    async def clear(self) -> None:

        async with self._lock:

            if any(
                record.status == "processing"
                for record in self._store.values()
            ):
                raise ValueError(
                    "Cannot clear the store while payments are processing."
                )

            self._store.clear()

    async def count(self) -> int:

        async with self._lock:
            return len(self._store)

    async def cleanup_expired(self) -> int:
        """
        Remove expired completed records.

        Processing records are never removed.
        Returns the number of removed records.
        """

        async with self._lock:

            expired_keys = [
                key
                for key, record in self._store.items()
                if self._is_expired(record)
            ]

            for key in expired_keys:
                del self._store[key]

            if expired_keys:
                logger.info(
                    "Removed %d expired idempotency records.",
                    len(expired_keys)
                )

            return len(expired_keys)


def generate_fingerprint(payload: Dict[str, Any]) -> str:
    """
    Generate a consistent SHA-256 fingerprint.

    Normalize Decimal values so 100, 100.0 and 100.00
    produce the same fingerprint.
    """

    normalized_payload = {
        key: (
            format(value.normalize(), "f")
            if isinstance(value, Decimal)
            else value
        )
        for key, value in payload.items()
    }

    canonical_json = json.dumps(
        normalized_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )

    return hashlib.sha256(
        canonical_json.encode("utf-8")
    ).hexdigest()


# Shared in-memory idempotency store.
# Default retention period: 24 hours.
idempotency_store = InMemoryIdempotencyStore(
    ttl_seconds=86400
)
