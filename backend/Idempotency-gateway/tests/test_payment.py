
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
async def test_first_payment_success():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        response = await client.post(
            "/process-payment",
            headers={"Idempotency-Key": "key-001"},
            json={"amount": 100, "currency": "GHS"}
        )

        assert response.status_code == 200

        data = response.json()

        assert data["message"] == "Charged 100 GHS"
        assert data["amount"] == 100.0
        assert data["currency"] == "GHS"
        assert data["status"] == "SUCCESS"
        assert data["transaction_id"].startswith("tx_")

        assert response.headers.get("x-cache-hit") == "false"


@pytest.mark.asyncio
async def test_missing_idempotency_key():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        response = await client.post(
            "/process-payment",
            json={"amount": 100, "currency": "GHS"}
        )

        assert response.status_code == 400


@pytest.mark.asyncio
async def test_empty_idempotency_key():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        response = await client.post(
            "/process-payment",
            headers={"Idempotency-Key": "   "},
            json={"amount": 100, "currency": "GHS"}
        )

        assert response.status_code == 400


@pytest.mark.asyncio
async def test_invalid_amount_negative():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        response = await client.post(
            "/process-payment",
            headers={"Idempotency-Key": "key-002"},
            json={"amount": -50, "currency": "GHS"}
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_amount_zero():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        response = await client.post(
            "/process-payment",
            headers={"Idempotency-Key": "key-003"},
            json={"amount": 0, "currency": "GHS"}
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_currency_format():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        response = await client.post(
            "/process-payment",
            headers={"Idempotency-Key": "key-004"},
            json={"amount": 100, "currency": "123"}
        )

        assert response.status_code == 422


@pytest.mark.asyncio
async def test_currency_is_normalized():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:

        response = await client.post(
            "/process-payment",
            headers={"Idempotency-Key": "key-005"},
            json={"amount": 100, "currency": " rwf "}
        )

        assert response.status_code == 200
        assert response.json()["currency"] == "RWF"
