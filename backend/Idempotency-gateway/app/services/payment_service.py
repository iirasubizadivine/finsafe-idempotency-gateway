import asyncio
import uuid
import logging

from app.schemas.payment import PaymentResponse


logger = logging.getLogger(__name__)


class PaymentService:

    async def process_payment(
        self,
        amount: float,
        currency: str
    ) -> PaymentResponse:

        # Simulate payment processing.
        await asyncio.sleep(2)

        transaction_id = f"tx_{uuid.uuid4().hex[:10]}"

        formatted_amount = f"{amount:.2f}".rstrip("0").rstrip(".")

        message = f"Charged {formatted_amount} {currency}"

        logger.info(
            "Payment processed successfully. Transaction ID: %s",
            transaction_id
        )

        return PaymentResponse(
            message=message,
            amount=amount,
            currency=currency,
            transaction_id=transaction_id,
            status="SUCCESS"
        )


payment_service = PaymentService()