from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User
from settings.logger import logger
from .payment import check_payment, get_payment

async def increment_global_counter(session: AsyncSession, user: User):
    """
    Increments the global message counter for a user.

    :param session: The asynchronous SQLAlchemy session.
    :param user: The User object.
    """
    logger.debug(f"Incrementing global message counter for user with Telegram ID {user.telegram}.")
    user.global_message_counter += 1
    await session.commit()
    logger.debug(f"Global message counter for user with Telegram ID {user.telegram} incremented.")


async def get_user(session: AsyncSession, user_id: int) -> User:
    """
    Retrieves a user from the database by their Telegram ID.
    If the user does not exist, creates a new one.

    :param session: The asynchronous SQLAlchemy session.
    :param user_id: The Telegram user ID.
    :return: The User object.
    """
    logger.debug(f"Attempting to retrieve user with Telegram ID {user_id}.")
    result = await session.execute(
        select(User).where(User.telegram == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        logger.info(f"User with Telegram ID {user_id} not found. Creating new user.")
        user = User(telegram=user_id)
        session.add(user)
        await session.commit()
        logger.debug(f"New user with Telegram ID {user_id} created and committed to the database.")
    else:
        logger.debug(f"User with Telegram ID {user_id} found in the database.")
    return user


async def set_payment_data_for_user(session: AsyncSession, user_id: int, bot_message: str):
    logger.debug(f'Starting set_payment_data_for_user with user_id={user_id}')

    if '{payment_data}' not in bot_message.lower() and '{payment_cash}' not in bot_message.lower():
        return bot_message, None

    logger.debug('Payment data placeholder detected in bot_reply')

    user = await get_user(session, user_id)

    # Check if user has payment data
    needs_update = not (user.data_one and user.data_two and user.data_three)

    if not needs_update:
        # If user has payment data, check if it's stopped or exists
        logger.debug('User has payment data, checking if it is stopped or exists')
        result = await check_payment(session, user.data_one)
        if not result:
            logger.debug('Current payment data is stopped or not exists, fetching new payment data')
            needs_update = True
    
    if needs_update:
        logger.debug('User payment data not found or stopped, fetching new payment data')
        user = await update_payment_data(session, user)
        logger.debug('Updated user payment data successfully')

    bot_message = bot_message.replace('{{payment_data}}', f"""

    {user.data_one}

    NOMBRE: {user.data_name}

    CLABE: {user.data_two}

    Сoncepto: {user.data_three}

    """)

    bot_message = bot_message.replace('{{payment_cash}}', f"""

    {user.data_one}

    NOMBRE: {user.data_name}

    Número de tarjeta: {user.data_two}

    """)

    logger.info('set_payment_data_for_user function completed successfully')
    return bot_message, user.data_photo


async def update_payment_data(session: AsyncSession, user: User):
    await session.refresh(user)
    payment = await get_payment(session)
    user.data_name = payment.data_name
    user.data_one = payment.data_one
    user.data_two = payment.data_two
    user.data_three = payment.data_three
    user.data_photo = payment.data_photo

    session.add(user)
    await session.commit()

    return user
