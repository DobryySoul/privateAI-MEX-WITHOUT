from typing import List
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Message, User, PushNotification
from database.requests.user import get_user
from settings.logger import logger


async def delete_messages(session: AsyncSession, messages: List[Message]) -> int:
    """
    Deletes a list of messages from the database.

    :param session: The asynchronous SQLAlchemy session.
    :param messages: A list of Message objects to be deleted.
    :return: The number of messages successfully deleted.
    """
    try:
        # Get the list of message IDs to delete
        message_ids = [message.id for message in messages]
        logger.debug(f"Deleting messages with IDs: {message_ids}")

        # Delete all messages in a single SQL query
        await session.execute(delete(Message).where(Message.id.in_(message_ids)))

        # Commit the changes
        await session.commit()
        logger.info(f"{len(messages)} messages successfully deleted.")
        return len(messages)
    except Exception as e:
        logger.error(f"Error while deleting messages: {e}", exc_info=True)
        return 0


async def add_message(session: AsyncSession, user_id: int, message_text: str, from_me: bool = False, attachment_path: str | None = None) -> (Message, User):
    """
    Adds a new message to the database associated with a user.

    :param session: The asynchronous SQLAlchemy session.
    :param user_id: The Telegram user ID.
    :param message_text: The text content of the message.
    :param from_me: Boolean indicating if the message is from the bot.
    :param attachment_path: Optional path to the attachment file.
    :return: A tuple containing the new Message object and the User object.
    """
    logger.debug(f"Adding message for user_id {user_id}: '{message_text}', from_me={from_me}, attachment_path={attachment_path}")
    # Find the user by their Telegram ID
    user = await get_user(session, user_id)

    if not user:
        logger.error(f"User with id {user_id} not found")
        raise ValueError(f"User with id {user_id} not found")

    # Create a new message with the correct user_id
    new_message = Message(
        user_id=user.id,  # Corrected here
        text=message_text,
        from_me=from_me,
        attachment_path=attachment_path
    )

    # Increment user's message counters
    if not from_me:
        user.message_counter += 1
        logger.debug(
            f"Updated message counter for user_id {user_id}, message_counter={user.message_counter}")

    # Add the new message to the session
    session.add(new_message)

    # Save changes to the database
    await session.commit()
    logger.info(f"New message added for user_id {user_id}")

    return new_message, user

async def add_push_message(session: AsyncSession, telegram_id: int, message_text: str, period: str) -> (Message, User):
    """
    Adds a new message to the database associated with a user.

    :param session: The asynchronous SQLAlchemy session.
    :param telegram_id: The Telegram user ID.
    :param message_text: The text content of the message.
    :param period: The period of the push notification.
    :return: A tuple containing the new Message object and the User object.
    """
    logger.debug(f"Adding push message for user_id {telegram_id}: '{message_text}', period={period}")
    # Find the user by their Telegram ID
    user = await get_user(session, telegram_id)

    if not user:
        logger.error(f"User with id {telegram_id} not found")
        raise ValueError(f"User with id {telegram_id} not found")

    new_push = PushNotification(
        user_id=user.id,
        period=period,
        sent_at=datetime.now()
    )
    session.add(new_push)

    # Create a new message with the correct user_id
    new_message = Message(
        user_id=user.id,    
        text=message_text,
        from_me=True,
        push_id=new_push.id
    )


    # Add the new message to the session
    session.add(new_message)

    # Save changes to the database
    await session.commit()
    logger.info(f"New push message added for user_id {user.id}")

    return new_message, user

async def get_messages_from_db(
        session: AsyncSession, user_id: int, sort: bool = True, limit: int = None
) -> List[Message]:
    """
    Получает сообщения пользователя из базы данных с оптимизацией SQL-запроса.

    :param session: Асинхронная сессия SQLAlchemy.
    :param user_id: ID пользователя в Telegram.
    :param sort: Сортировать ли сообщения по убыванию ID.
    :param limit: Максимальное количество сообщений для извлечения.
    :return: Список объектов Message.
    """
    logger.info(f"Fetching messages for user_id: {user_id}, sort: {sort}, limit: {limit}")

    # Основной запрос для извлечения сообщений пользователя
    stmt = (
        select(Message)
        .join(User, User.id == Message.user_id)  # Присоединяем таблицу User для фильтрации по user_id
        .filter(User.telegram == user_id)
    )

    result = await session.execute(stmt)
    messages = result.scalars().all()

    if sort:
        messages = sorted(messages, key=lambda x: x.id, reverse=True)
    if limit:
        messages = messages[:limit]

    logger.info(f"Fetched {len(messages)} messages for user_id: {user_id}")
    return messages

async def has_any_push_notification(session: AsyncSession, telegram_id: int, period: str) -> bool:

    user = await get_user(session, telegram_id)
    if not user:
        return False
    stmt = (
        select(PushNotification)
        .where(PushNotification.user_id == user.id)
        .where(PushNotification.period == period)
    )
    result = await session.execute(stmt)
    push = result.scalars().first()
    return push is not None
