from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Payment
from settings.logger import logger

async def get_payment(session: AsyncSession) -> Payment:
    logger.info("Getting payment")
    payment = await session.execute(select(Payment).where(Payment.stop == False).order_by(Payment.use_count.asc()).limit(1))
    payment = payment.scalar_one_or_none()
    if not payment:
        logger.warning("Payment not found")
        return None
    return payment


async def check_payment(session: AsyncSession, payment_info: str):
    logger.info("Checking payment")
    payment = await session.execute(select(Payment).where(Payment.data_one == payment_info))
    payment = payment.scalar_one_or_none()
    if not payment:
        logger.warning("Payment not found")
        return None
    return payment
