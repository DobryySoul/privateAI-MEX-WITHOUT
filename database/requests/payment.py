from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Payment, PaymentMethod
from settings.logger import logger

async def get_payment(session: AsyncSession, payment_method: PaymentMethod = None) -> Payment:
    """
    Получает платеж из базы данных.
    
    :param session: Асинхронная сессия SQLAlchemy
    :param payment_method: Метод оплаты (CASH или BANK). Если None, возвращает любой доступный платеж
    :return: Объект Payment или None
    """
    logger.info(f"Getting payment for method: {payment_method}")
    
    if payment_method:
        query = select(Payment).where(
            Payment.stop == False,
            Payment.type == payment_method
        ).order_by(Payment.use_count.asc()).limit(1)
    else:
        query = select(Payment).where(Payment.stop == False).order_by(Payment.use_count.asc()).limit(1)
    
    payment = await session.execute(query)
    payment = payment.scalar_one_or_none()
    
    if not payment:
        logger.warning(f"Payment not found for method: {payment_method}")
        return None
    
    logger.info(f"Found payment: {payment.id} with method: {payment.type}")
    return payment


async def check_payment(session: AsyncSession, payment_info: str, payment_method: PaymentMethod = None):
    """
    Проверяет существование платежа в базе данных.
    
    :param session: Асинхронная сессия SQLAlchemy
    :param payment_info: Информация о платеже для поиска
    :param payment_method: Метод оплаты для дополнительной фильтрации
    :return: Объект Payment или None
    """
    logger.info(f"Checking payment: {payment_info} for method: {payment_method}")
    
    if payment_method:
        query = select(Payment).where(
            Payment.data_one == payment_info,
            Payment.type == payment_method
        )
    else:
        query = select(Payment).where(Payment.data_one == payment_info)
    
    payment = await session.execute(query)
    payment = payment.scalar_one_or_none()
    
    if not payment:
        logger.warning(f"Payment not found for info: {payment_info}, method: {payment_method}")
        return None
    
    logger.info(f"Payment found: {payment.id}")
    return payment
