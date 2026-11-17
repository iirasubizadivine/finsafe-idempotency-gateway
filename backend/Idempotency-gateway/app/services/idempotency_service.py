
import asyncio
import logging

from typing import Any, Dict, Tuple, Callable, Awaitable

from app.storage.idempotency_store import (
    generate_fingerprint,
    IdempotencyRecord
)

from app.core.exceptions import IdempotencyConflictException


logger = logging.getLogger(__name__)


def _get_record_attr(record: Any, attr: str, default=None):
    """Get an attribute whether the record is a dictionary or object."""

    if isinstance(record, dict):
        return record.get(attr, default)

    return getattr(record, attr, default)


class IdempotencyService:

    def __init__(self, store: Any):
        self.store = store

    async def execute_idempotent(
        self,
        key: str,
        payload: Dict[str, Any],
        action: Callable[
            [],
            Awaitable[Tuple[Dict[str, Any], int]]
        ]
    ) -> Tuple[Dict[str, Any], int, bool]:

        fingerprint = generate_fingerprint(payload)

        record, is_new = await self.store.get_or_create(
            key=key,
            fingerprint=fingerprint
        )

        # Existing key: check whether the request is identical.
        if not is_new:

            if _get_record_attr(record, "fingerprint") != fingerprint:

                logger.warning(
                    "Idempotency conflict for key: %s", key
                )

                raise IdempotencyConflictException()

            # Completed payment: replay the original response.
            if _get_record_attr(record, "status") == "completed":

                logger.info(
                    "Returning cached response for key: %s", key
                )

                return (
                    _get_record_attr(record, "response_body"),
                    _get_record_attr(record, "status_code"),
                    True
                )

            # Payment still processing: wait for the first request.
            if _get_record_attr(record, "status") == "processing":

                if hasattr(record, "event"):

                    await record.event.wait()

                    if _get_record_attr(record, "status") == "completed":

                        return (
                            _get_record_attr(record, "response_body"),
                            _get_record_attr(record, "status_code"),
                            True
                        )

                    raise RuntimeError(
                        "Original payment failed. Please retry."
                    )

                raise RuntimeError(
                    "Payment is still processing. Please retry."
                )

            raise RuntimeError(
                f"Unexpected record status: "
                f"{_get_record_attr(record, 'status')}"
            )

        # New key: execute the payment.
        try:

            logger.info(
                "Processing payment for key: %s", key
            )

            response_body, status_code = await action()

            await self.store.complete(
                key=key,
                response_body=response_body,
                status_code=status_code
            )

            return response_body, status_code, False

        except BaseException:

            await asyncio.shield(
                self.store.fail(key)
            )

            logger.exception(
                "Payment processing failed for key: %s", key
            )

            raise
