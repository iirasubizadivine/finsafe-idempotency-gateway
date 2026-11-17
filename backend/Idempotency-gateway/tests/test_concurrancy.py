
import pytest
import pytest_asyncio
import asyncio

from unittest.mock import patch

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services.payment_service import payment_service
from app.storage.idempotency_store import idempotency_store


@pytest_asyncio.fixture(autouse=True)
async def clear_store():
    await idempotency_store.clear()
    yield
    await idempotency_store.clear()


@pytest.mark.asyncio
async def test_concurrent_in_flight_requests_executed_once():

    execution_counter = 0

    original_process = payment_service.process_payment

    async def mock_process(amount: float, currency: str):
        nonlocal execution_counter

        execution_counter += 1

        return await original_process(amount, currency)

    with patch.object(
        payment_service,
        "process_payment",
        side_effect=mock_process
    ):

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:

            headers = {
                "Idempotency-Key": "concurrent-key-999"
            }

            payload = {
                "amount": 300,
                "currency": "GHS"
            }

            tasks = [
                client.post(
                    "/process-payment",
                    headers=headers,
                    json=payload
                )
                for _ in range(5)
            ]

            responses = await asyncio.gather(*tasks)

    # Every request should succeed.
    for response in responses:
        assert response.status_code == 200

    # Exactly one request should process the payment.
    assert execution_counter == 1

    # One original request and four cached responses.
    cache_hits = [
        response.headers.get("x-cache-hit")
        for response in responses
    ]

    assert cache_hits.count("false") == 1
    assert cache_hits.count("true") == 4


    transaction_ids = {
        response.json()["transaction_id"]
        for response in responses
    }

    assert len(transaction_ids) == 1

    response_bodies = [
        response.json()
        for response in responses
    ]

    assert all(
        body == response_bodies[0]
        for body in response_bodies
    )

    assert response_bodies[0]["amount"] == 300.0
    assert response_bodies[0]["currency"] == "GHS"
    assert response_bodies[0]["status"] == "SUCCESS"
