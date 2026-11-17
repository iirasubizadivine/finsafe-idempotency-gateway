
import pytest
import pytest_asyncio

from httpx import AsyncClient, ASGITransport

from app.main import app
from app.storage.idempotency_store import idempotency_store


@pytest_asyncio.fixture(autouse=True)
async def clear_store():
    await idempotency_store.clear()
    yield
    await idempotency_store.clear()


@pytest.mark.asyncio
async def test_duplicate_request_returns_cached_response():

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        payload = {
            "amount": 250,
            "currency": "GHS"
        }

        headers = {
            "Idempotency-Key": "dup-key-100"
        }

        res1 = await client.post(
            "/process-payment",
            headers=headers,
            json=payload
        )

        assert res1.status_code == 200
        assert res1.headers.get("x-cache-hit") == "false"

        res2 = await client.post(
            "/process-payment",
            headers=headers,
            json=payload
        )

        assert res2.status_code == 200
        assert res2.headers.get("x-cache-hit") == "true"

        assert res1.json() == res2.json()

        assert (
            res1.json()["transaction_id"]
            == res2.json()["transaction_id"]
        )


@pytest.mark.asyncio
async def test_same_key_different_body_returns_conflict():

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        headers = {
            "Idempotency-Key": "conflict-key-100"
        }

        res1 = await client.post(
            "/process-payment",
            headers=headers,
            json={
                "amount": 100,
                "currency": "GHS"
            }
        )

        assert res1.status_code == 200

        res2 = await client.post(
            "/process-payment",
            headers=headers,
            json={
                "amount": 500,
                "currency": "GHS"
            }
        )

        assert res2.status_code == 409

        assert res2.json()["detail"] == (
            "Idempotency key already used for a different request body."
        )


@pytest.mark.asyncio
async def test_same_payload_with_different_json_key_order():

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        headers = {
            "Idempotency-Key": "order-key-100"
        }

        res1 = await client.post(
            "/process-payment",
            headers=headers,
            json={
                "amount": 100,
                "currency": "GHS"
            }
        )

        res2 = await client.post(
            "/process-payment",
            headers=headers,
            json={
                "currency": "GHS",
                "amount": 100
            }
        )

        assert res1.status_code == 200
        assert res2.status_code == 200

        assert res2.headers.get("x-cache-hit") == "true"

        assert res1.json() == res2.json()


@pytest.mark.asyncio
async def test_different_keys_process_separate_payments():

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        payload = {
            "amount": 100,
            "currency": "GHS"
        }

        res1 = await client.post(
            "/process-payment",
            headers={"Idempotency-Key": "separate-key-001"},
            json=payload
        )

        res2 = await client.post(
            "/process-payment",
            headers={"Idempotency-Key": "separate-key-002"},
            json=payload
        )

        assert res1.status_code == 200
        assert res2.status_code == 200

        assert res1.headers.get("x-cache-hit") == "false"
        assert res2.headers.get("x-cache-hit") == "false"

        assert (
            res1.json()["transaction_id"]
            != res2.json()["transaction_id"]
        )
