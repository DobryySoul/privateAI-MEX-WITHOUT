import json
import os
from telethon import events
from external.generators import generate_name
from handlers.common import common_handler
from settings.config import config
from settings.logger import logger
from utils.functions.prompt import recognize_image
from utils.functions.fetchers import check_sensitive_data
from external.channel import get_bot_id
from utils.check_fd import is_fd
from telethon.events import StopPropagation
from utils.functions.telegram_client_helpers import move_chat_to_folder_include_peers, forward_document_to_chat
from database.engine import async_session
from database.requests.user import get_user
from utils.shared_state import _user_stop_cache, _user_stop_lock

async def photo_handler(event: events.NewMessage.Event):
    client = event.client
    sender = await event.get_sender()
    if sender.bot:
        return

    logger.info(f"New photo from {sender.id}")

    async with _user_stop_lock:
        _user_stop_cache[sender.id] = True

    is_payment_details = False
    photo_path = None

    try:
        # Проверка айди
        my_id = await get_bot_id(client)
        from_me = sender.id == my_id

        user_message = event.message.text or ''  # Caption of the photo, if any

        # Проверка на исходящие сообщения с фото (ДО проверки URL)
        if from_me:
            await check_sensitive_data(client, event.chat_id, user_message)

        if not await is_fd(client, sender.id):
            return

        # Проверка на наличие URL в медиа - пропускаем ссылки на веб-страницы
        if hasattr(event.message, 'media') and hasattr(event.message.media, 'webpage') and hasattr(event.message.media.webpage, 'url'):
            logger.info(f"Received media with URL: {event.message.media.webpage.url}, skipping processing")
            return

        file_name = f"{config.TECHNICAL_DATA.download_path}{await generate_name(15)}.png"
        photo_path = await client.download_media(event.message.photo, file=file_name)

        user_reply_json = await recognize_image(photo_path, config.OPENAI_API.models.photo_recognition)
        os.remove(photo_path) # Clean up the downloaded photo

        try:
            user_reply_data = json.loads(user_reply_json)
            is_payment_details = user_reply_data.get('is_payment_details', False)
            photo_name = user_reply_data.get('photo_name', 'Unknown')
            description = user_reply_data.get('description', '')
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Error parsing AI response: {e}")

        if not from_me: 
            async with async_session() as session:
                user = await get_user(session, sender.id)
                if is_payment_details:
                    logger.info(f"Attempting to forward photo from {event.chat_id} to favorites.")
                    await forward_document_to_chat(client, sender, user_message, event.message.photo)
                    user.stop = True
                    await session.commit()
                    await move_chat_to_folder_include_peers(client, sender.id, config.TECHNICAL_DATA.folder_name)
                else:
                    if user.stop:
                        user.stop = False
                        await session.commit()

        user_reply = f"{user_message} | attached photo: {photo_name} \nAI VISION: '{description}'" if user_message else f"attached photo: {photo_name} \nAI VISION: '{description}'"

    except Exception as e:
        logger.error(f"Error in photo_handler: {e}", exc_info=True)
    finally:
        async with _user_stop_lock:
            _user_stop_cache.pop(sender.id, None)

    async with async_session() as session:
        user_after_photo_processing = await get_user(session, sender.id)
        if not user_after_photo_processing.stop:
            await common_handler(event, user_reply, is_payment_details)
        else:
            logger.info(f"User {sender.id} is stopped due to payment. No common_handler call for photo.")

    raise StopPropagation