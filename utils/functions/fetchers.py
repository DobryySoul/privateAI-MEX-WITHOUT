import asyncio
import json
import random

from sqlalchemy.ext.asyncio import AsyncSession
from database.requests.message import get_messages_from_db, delete_messages, add_message
from settings.config import config
from settings.logger import logger
from utils.functions.notification_senders import send_monitoring_notification
from utils.functions.notification_senders import TELEGRAM_HANDLE_OR_LINK_PATTERN, PHONE_NUMBER_PATTERN
from utils.check_fd import is_fd


async def update_status(session: AsyncSession, user, status):
    logger.debug(f'Starting update_status for user_id={user.id}, status={status}')
    statuses = json.loads(user.status_list.lower())
    statuses[int(status)] = True

    user.status_list = json.dumps(statuses)
    await session.commit()
    logger.info(f'Status updated successfully for user_id={user.id}, status={status}')


async def check_sensitive_data(client, recipient_id, user_message):
    """
    Проверяет наличие чувствительных данных в сообщениях для архивных диалогов
    и отправляет уведомление мониторинга при обнаружении.
    
    Args:
        client: Telegram клиент
        recipient_id: ID получателя сообщения
        user_message: Текст сообщения для проверки
    """
    is_normal_dialog = await is_fd(client, recipient_id)
    if not is_normal_dialog:  # Диалог в архиве
        if (
            TELEGRAM_HANDLE_OR_LINK_PATTERN.search(user_message or "") or
            PHONE_NUMBER_PATTERN.search(user_message or "")
        ):
            await send_monitoring_notification(client, recipient_id, user_message)
            logger.warning(f"Outgoing message with sensitive data detected in archived dialog to {recipient_id}")


async def fetch_dialogue(session: AsyncSession, user_id: int, message_text: str, from_me: bool = False):
    """
    Fetches the dialogue history for a user and updates message counters.
    If the message is from the bot, returns immediately.
    Otherwise, processes the message and updates the dialogue.

    :param session: The asynchronous SQLAlchemy session.
    :param user_id: The Telegram user ID.
    :param message_text: The text content of the message.
    :param from_me: Boolean indicating if the message is from the bot.
    :return: A tuple containing the dialogue list and the new message.
    """
    logger.info(f"Starting fetch_dialogue for user_id={user_id}")

    try:
        # Add the new message to the database
        new_message, user = await add_message(session, user_id, message_text, from_me)
        if from_me:
            logger.info(f"Message is from bot. Returning without processing dialogue for user_id={user_id}")
            return [], message_text, user

        # Retrieve the dialogue history
        # message_counter = max(20, user.message_counter)

        sleep_time = random.randint(config.TECHNICAL_DATA.to_group_messages_delay_low,
                                    config.TECHNICAL_DATA.to_group_messages_delay_high)
        logger.debug(f'Sleep for: {sleep_time}, with {user_id}')

        await asyncio.sleep(sleep_time)

        raw_dialogue = await get_messages_from_db(session, user_id, True)

        if message_text != raw_dialogue[0].text:
            logger.debug(f'Message text: {message_text}, last dialogue: {raw_dialogue[0].text}')
            logger.info(f'User {user_id} sent two+ messages, exiting...')
            return [], message_text, user

        # Build the dialogue list
        dialogue_list = []
        for message in raw_dialogue:
            message_content = message.text
            if message.from_me and message.attachment_path:
                message_content = f"BOT SENT ATTACHMENT: {message.attachment_path} -- {message.text}"
            dialogue_list.append({message_content: 'me' if message.from_me else 'user'})
            
        if user.message_counter == 1:
            user.message_counter = 0
            await session.commit()
            logger.info(f"Function fetch_dialogue completed successfully for user_id={user_id}")
            return dialogue_list, new_message, user

        # Logging the user's message counter
        logger.debug(f"User message_counter for user_id {user_id}: {user.message_counter}")

        last_messages = raw_dialogue[:user.message_counter]

        # Extract the text from the last messages
        messages_list = [msg.text for msg in last_messages[::-1]]

        # Delete the last messages from the database
        await delete_messages(session, last_messages)
        logger.debug(f"Deleted {user.message_counter} messages from user_id={user_id}")

        # Combine the messages into a single string
        new_message = ' '.join(messages_list)

        # Add the combined message back to the database
        await add_message(session, user_id, new_message)
        logger.debug(f"Updated user reply: {new_message}")

        # Reset the user's message counter
        user.message_counter = 0
        await session.commit()
        logger.info(f"Function fetch_dialogue completed successfully for user_id={user_id}")

        return dialogue_list, new_message, user
    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
        raise