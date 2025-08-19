import json
import os
from telethon import events
from external.generators import generate_name
from handlers.common import common_handler
from settings.config import config
from settings.logger import logger
from utils.functions.prompt import recognize_image
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

    logger.info(f"[Photo] Start processing for user {sender.id} (msg: {event.message.id})")
    async with _user_stop_lock:
        _user_stop_cache[sender.id] = True

    is_payment_details = False
    photo_path = None
    user_reply = ""

    try:
        my_id = await get_bot_id(client)
        from_me = sender.id == my_id
        user_message = event.message.text or ''

        if not await is_fd(client, sender.id):
            logger.info(f"[Photo] User {sender.id} is not in a folder, skipping.")
            return

        if hasattr(event.message, 'media') and hasattr(event.message.media, 'webpage'):
            logger.info(f"[Photo] Message from user {sender.id} contains a webpage, skipping.")
            return

        file_name = f"{config.TECHNICAL_DATA.download_path}{await generate_name(15)}.png"
        photo_path = await client.download_media(event.message.photo, file=file_name)
        
        user_reply_json = await recognize_image(photo_path, config.OPENAI_API.models.photo_recognition)
        
        photo_name = 'Unknown'
        description = ''
        try:
            user_reply_data = json.loads(user_reply_json)
            is_payment_details = user_reply_data.get('is_payment_details', False)
            photo_name = user_reply_data.get('photo_name', 'Unknown')
            description = user_reply_data.get('description', '')
            logger.info(f"[Photo] Recognition for user {sender.id} complete. Payment: {is_payment_details}")
        except (json.JSONDecodeError, KeyError):
            logger.error(f"[Photo] Failed to parse AI response for user {sender.id}. Raw: '{user_reply_json}'")

        user_reply = f"{user_message} | attached photo: {photo_name} \nAI VISION: '{description}'" if user_message else f"attached photo: {photo_name} \nAI VISION: '{description}'"

        if not from_me:
            async with async_session() as session:
                user = await get_user(session, sender.id)
                if is_payment_details:
                    logger.info(f"[Photo] Payment detected for user {sender.id}. Forwarding and stopping.")
                    await forward_document_to_chat(client, sender, user_message, event.message.photo)
                    user.stop = True
                    await session.commit()
                    await move_chat_to_folder_include_peers(client, sender.id, config.TECHNICAL_DATA.folder_name)
                else:
                    if user.stop:
                        logger.info(f"[Photo] Not a payment. Un-stopping user {sender.id}.")
                        user.stop = False
                        await session.commit()

    except Exception as e:
        logger.error(f"[Photo] Error for user {sender.id}: {e}", exc_info=True)
    finally:
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        async with _user_stop_lock:
            _user_stop_cache.pop(sender.id, None)

    async with async_session() as session:
        user_after_photo_processing = await get_user(session, sender.id)
        if not user_after_photo_processing.stop:
            logger.info(f"[Photo] Calling common_handler for user {sender.id}.")
            await common_handler(event, user_reply, is_payment_details)
        else:
            logger.info(f"[Photo] User {sender.id} is stopped. Skipping common_handler.")
    
    logger.info(f"[Photo] End processing for user {sender.id} (msg: {event.message.id})")
    raise StopPropagation