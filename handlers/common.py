from database.engine import async_session
from database.requests.user import increment_global_counter, get_user
from settings.config import config
from settings.logger import logger
from utils.functions.fetchers import fetch_dialogue, check_sensitive_data
from utils.functions.prompt import get_api_response, get_prompt
from utils.functions.senders import send_text_message, send_generated_voice_message, send_photo_to_chat, send_video_to_chat, send_video_note_to_chat
from utils.functions.telegram_client_helpers import send_reaction_to_message
from utils.functions.formatters import format_user_info_message
from external.channel import get_bot_id
from utils.check_fd import is_fd
from telethon.tl.types import User
from utils.shared_state import _user_stop_cache, _user_stop_lock
from handlers.schedule_message_handler import schedule_message

async def common_handler(event, user_message, is_payment_details=False):
    client = event.client
    sender = await event.get_sender()
    my_id = await get_bot_id(client)  # Получаем ID бота один раз

    async with _user_stop_lock:
        if sender.id in _user_stop_cache:
            logger.info(f"User {sender.id} is in immediate stop cache. Ignoring message.")
            return 

    try:
        chat = await event.get_chat()
        if not isinstance(chat, User) or chat.bot:
            logger.info(f"Message in not user chat. Returning without processing dialogue for chat: {chat.id}")
            return
    except Exception as e:
        logger.error(f"Failed to get chat: {e}")
    
    # Получение информации о пользователе
    sender = await event.get_sender()

    from_me = sender.id == my_id  # True, если сообщение отправлено самим ботом

    if from_me:
        await check_sensitive_data(client, event.chat_id, user_message)

    if not from_me and (not await is_fd(client, sender.id) or event.chat_id == my_id):
        logger.info(f"Returning early for incoming message from user {sender.id} (not FD or saved messages)")
        return

    if event.chat_id == my_id:
        return

    async with (async_session() as session):
        user = await get_user(session, sender.id)

        if user.stop and not is_payment_details:
            logger.info(f"User {sender.id} is already stopped - ignore message")
            return

        if user.global_message_counter == 0 and not user.stop and not from_me:
            user_message = format_user_info_message(sender, user_message)

        dialogue_list, new_message, user = await fetch_dialogue(session, event.chat_id, user_message, from_me)
        logger.info(f"Fetched successfully, len of dialogue_list: {len(dialogue_list)}")

        if from_me:
            user_message_lower = user_message.lower()
            if config.TECHNICAL_DATA.stop_phrase in user_message_lower or config.TECHNICAL_DATA.start_phrase in user_message_lower:
                user.stop = config.TECHNICAL_DATA.stop_phrase in user_message_lower
                await session.commit()
                logger.info(f"User {sender.id} has {'stopped' if user.stop else 'started'} the conversation.")
            return

        if is_payment_details:
            user.stop = True
            await session.commit()
            logger.info(f"User {sender.id} has sent payment details, conversation stopped.")
            return

        if len(dialogue_list) == 0:
            logger.info(f"User send many messages, wait new messages.")
            return

        await increment_global_counter(session, user)

        if user.global_message_counter > config.TECHNICAL_DATA.stop_responding:
            logger.info(f"User {sender.id} has reached the message limit, stopping.")
            return

        prompt_text = await get_prompt()  # reason='Text'

        bot_answer = await get_api_response(
            prompt_text=prompt_text,
            dialogue_list=dialogue_list,
            model=config.OPENAI_API.models.text_generation,
            max_attempts=5,
            as_json=True
        )
        
        # if bot_answer is None:
        #     logger.error(f"[NON-ANSWERED] Failed to get valid response after {max_attempts} attempts")
        #     return

        for msg in bot_answer:
            msg_type = msg.get('type')
            body = msg.get('body')
            logger.debug(f"Processing message type: {msg_type}, body type: {type(body)}, body: {body}")
            if msg_type not in ['voice', 'text', 'image', 'video', 'document', 'reaction', 'schedule_message']:
                logger.warning(f"Unknown message type: {msg_type}")
                continue
            try:
                if msg_type == 'voice':
                    await send_generated_voice_message(client, session, sender.id, user_message, body)
                elif msg_type == 'text':
                    await send_text_message(client, session, sender.id, user_message, body)
                elif msg_type == 'image':
                    await send_photo_to_chat(client, session, sender.id, body)
                elif msg_type == 'video':
                    video_path = body.get('file') if isinstance(body, dict) else body
                    caption = body.get('caption', '') if isinstance(body, dict) else ''
                    if video_path and 'note' in video_path:
                        if caption:
                            await send_text_message(client, session, sender.id, user_message, caption)
                        await send_video_note_to_chat(client, session, sender.id, {'file': video_path})
                    else:
                        await send_video_to_chat(client, session, sender.id, body)
                elif msg_type == 'reaction':
                    await send_reaction_to_message(client, sender.id, event.id, body)
                elif msg_type == 'schedule_message':
                    await schedule_message(client, sender.id, body)
                else:
                    logger.warning(f"Unknown message type: {msg_type}")

            except Exception as e:
                logger.error(f"Error processing message type {msg_type} for user {sender.id}: {e}", exc_info=True)
                try:
                    await session.rollback()
                    logger.info("Session rollback successful after exception.")
                except Exception as rollback_exc:
                    logger.error(f"Session rollback failed: {rollback_exc}")