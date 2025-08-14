import asyncio
import json
from datetime import datetime, timedelta
import pytz
from telethon import TelegramClient
from settings.logger import logger
from database.engine import async_session
from database.models import User
from utils.functions.prompt import process_message, get_prompt
from utils.functions.senders import send_text_message, send_photo_to_chat
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from database.requests.message import add_push_message, get_messages_from_db, has_any_push_notification
from settings.config import config
from utils.check_fd import is_fd

async def find_users_for_30min_push(session: AsyncSession, client: TelegramClient):
    """
    Находит пользователей, которым нужно отправить 30-минутный payment push.
    Возвращает список кортежей (user, last_bot_msg).
    """
    tz = pytz.timezone(config.TECHNICAL_DATA.time_zone)
    now = datetime.now(tz)
    min_time = now - timedelta(minutes=35)
    max_time = now - timedelta(minutes=15)

    users_result = await session.execute(select(User).where(User.stop == False))
    users = users_result.scalars().all()
    eligible = []

    for user in users:
        if not user.data_one:
            continue
        if not await is_fd(client, user.telegram):
            logger.info(f"[30m Push] Skipping user {user.telegram} as they are in an archive or folder.")
            continue
        if await has_any_push_notification(session, user.telegram, '30m'):
            logger.info(f"[30m Push] Skipping user {user.telegram} as push already sent before.")
            continue
        messages = await get_messages_from_db(session, user.telegram, sort=True, limit=3)
        if not messages:
            continue
        last_bot_msg = None
        for msg in messages:
            msg_time = msg.created_at
            if msg_time.tzinfo is None:
                msg_time = pytz.utc.localize(msg_time).astimezone(tz)
            else:
                msg_time = msg_time.astimezone(tz)
            if msg.from_me and min_time <= msg_time <= max_time:
                last_bot_msg = msg
                break
        if not last_bot_msg:
            continue
        bot_msgs = []
        start_collecting = False
        for msg in messages:
            if msg.id == last_bot_msg.id:
                start_collecting = True
            if start_collecting:
                if msg.from_me:
                    bot_msgs.append(msg.text or "")
                else:
                    break
        if not bot_msgs:
            continue
        message_str = " ".join(reversed(bot_msgs))
        if user.data_one in message_str:
            eligible.append((user, last_bot_msg))
    return eligible

async def send_30min_payment_pushes(client: TelegramClient):
    """
    Отправляет 30-минутные payment push-уведомления подходящим пользователям.
    """
    async with async_session() as session:
        prompt_text = await get_prompt('PushReminder')
        eligible = await find_users_for_30min_push(session, client)
        logger.info(f"[30m Push] Found {len(eligible)} users eligible for 30-min payment push.")
        for user, last_msg in eligible:
            try:
                if not await is_fd(client, user.telegram):
                    logger.info(f"[30m Push] Skipping user {user.telegram} as they are in an archive or folder.")
                    continue
                raw_dialogue = await get_messages_from_db(session, user.telegram, True, limit=3)
                dialogue_list = [
                    {message.text: 'me' if message.from_me else 'user'}
                    for message in reversed(raw_dialogue)
                ]
                ai_answer = await process_message(prompt_text, dialogue_list, config.OPENAI_API.models.push, as_json=True)
                bot_answer = json.loads(ai_answer)
                texts = []
                photo_path = ''
                if isinstance(bot_answer, list):
                    for item in bot_answer:
                        if isinstance(item, dict):
                            if item.get('type') == 'text' and 'body' in item:
                                texts.append(item['body'])
                            elif item.get('type') == 'image' and 'body' in item and 'file' in item['body']:
                                photo_path = item['body']['file']
                elif isinstance(bot_answer, dict) and 'push_reminder_prompt' in bot_answer:
                    texts.append(bot_answer['push_reminder_prompt'])
                    if 'body' in bot_answer and isinstance(bot_answer['body'], dict) and 'file' in bot_answer['body']:
                        photo_path = bot_answer['body']['file']
                else:
                    text_from_fallback = (
                        bot_answer.get('body') or 
                        bot_answer.get('message') or 
                        bot_answer.get('text') or
                        (bot_answer.get('telegram_push_message', {}).get('text') if bot_answer.get('telegram_push_message') else None)
                    )
                    if text_from_fallback:
                        texts.append(text_from_fallback)
                    photo_path = bot_answer.get('telegram_push_message', {}).get('attachments', [])[0] if bot_answer.get('telegram_push_message') and bot_answer.get('telegram_push_message').get('attachments') else ''
                if not texts and not photo_path:
                    logger.warning(f"[30m Push] Missing required fields in response (no text or photo): {bot_answer}")
                    continue
                if photo_path:
                    await send_photo_to_chat(client, session, user.telegram, [{'file': photo_path}])
                sent_text_combined = []
                for text_to_send in texts:
                    if text_to_send:
                        await send_text_message(client, session, user.telegram, "", text_to_send)
                        sent_text_combined.append(text_to_send)
                        await asyncio.sleep(1.5)
                if sent_text_combined:
                    await add_push_message(session, user.telegram, " ".join(sent_text_combined), '30m')
                logger.info(f"[30m Push] Sent to user {user.telegram}")
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"[30m Push] Error for user {user.telegram}: {str(e)}")
                continue

async def start_30min_push_loop(client: TelegramClient):
    """
    Запускает периодическую задачу отправки 30-минутных payment push-уведомлений.
    """
    await asyncio.sleep(120)  # Задержка перед стартом
    while True:
        try:
            await send_30min_payment_pushes(client)
        except Exception as e:
            logger.error(f"[30m Push] Error in periodic task: {str(e)}")
        finally:
            await asyncio.sleep(900)  # 15 минут 