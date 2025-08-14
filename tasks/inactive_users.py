import asyncio
import json
import random
from datetime import datetime, timedelta
from telethon import TelegramClient
from settings.logger import logger
from database.engine import async_session
from database.models import User, Message, PushNotification
from utils.functions.prompt import process_message, get_prompt
from utils.functions.senders import send_text_message, send_video_to_chat, send_photo_to_chat
from sqlalchemy import select, func, and_, or_, exists
from settings.config import config
from sqlalchemy.ext.asyncio import AsyncSession
from database.requests.message import get_messages_from_db, add_push_message
from settings.logger import logger
from utils.check_fd import is_fd

class PushPeriod:
    """Константы для периодов пуш-уведомлений"""
    HOURS_4 = "4h"
    HOURS_8 = "8h"


class PushPeriods:
    """Информация о периодах пуш-уведомлений"""
    _PERIODS = {
        PushPeriod.HOURS_4: {"delta": timedelta(hours=4), "label": "4 часа"},
        PushPeriod.HOURS_8: {"delta": timedelta(hours=8), "label": "8 часов (с видео)"},
    }
    
    @classmethod
    def get_all(cls):
        """Возвращает список всех периодов"""
        return [
            {"delta": data["delta"], "label": data["label"], "code": code}
            for code, data in cls._PERIODS.items()
        ]
    
    @classmethod
    def get_by_code(cls, code):
        """Возвращает информацию о периоде по коду"""
        if code in cls._PERIODS:
            return {"delta": cls._PERIODS[code]["delta"], "label": cls._PERIODS[code]["label"], "code": code}
        return None

PUSH_PERIODS = PushPeriods.get_all()

async def find_users_for_push(session: AsyncSession, period: dict, client: TelegramClient):
    """Находит пользователей, которым нужно отправить пуш за данный период"""
    now = datetime.now()
    time_ago = now - period["delta"]
    period_code = period["code"]

    last_message_subq = select(
        Message.user_id,
        func.max(Message.created_at).label('last_message_time'),
        func.max(Message.from_me).label('from_me')
    ).group_by(Message.user_id).subquery('last_message')

    if period_code == PushPeriod.HOURS_4:
        conditions = and_(
            last_message_subq.c.from_me == True,
            last_message_subq.c.last_message_time <= time_ago,
            User.stop == False,
            (User.data_one == None) | (User.data_one == "") | (User.data_two == None) | (User.data_two == "") | (User.data_three == None) | (User.data_three == "")
        )
    elif period_code == PushPeriod.HOURS_8:
        conditions = and_(
            last_message_subq.c.last_message_time <= time_ago,
            User.stop == False,
            exists(select(PushNotification.id).where(
                and_(
                    PushNotification.user_id == User.id,
                    PushNotification.period == PushPeriod.HOURS_4
                )
            ))
        )
    else:
        return []

    push_period_conditions = [PushNotification.period == period_code]
    if period_code == PushPeriod.HOURS_4:
        push_period_conditions.append(PushNotification.period == period_code + '_step1')
    
    subq_push_sent = select(PushNotification.id).where(
        and_(
            PushNotification.user_id == User.id,
            or_(*push_period_conditions)
        )
    ).exists()

    query = select(User.telegram).\
        select_from(User).\
        join(last_message_subq, User.id == last_message_subq.c.user_id).\
        where(and_(
            conditions,
            ~subq_push_sent 
        )).\
        order_by(last_message_subq.c.last_message_time)
     
    result = await session.execute(query)
    return [row[0] for row in result.all()]


async def send_push_notifications(client: TelegramClient):
    """Отправка пуш-уведомлений пользователям"""
    async with async_session() as session:
        logger.info(f"Ready to start push notification process at: {datetime.now()}")
        for period in PUSH_PERIODS:
            try:
                users = await find_users_for_push(session, period, client)
                logger.info(f"Найдено {len(users)} пользователей для периода {period['label']}")
                 
                if not users:
                    continue

                prompt_name = 'push_4h' if period['code'] == PushPeriod.HOURS_4 else 'push_8h'
                prompt_text = await get_prompt(prompt_name)

                for telegram_id in users:
                    try:
                        if not await is_fd(client, telegram_id):
                            logger.info(f"[Push] Skipping user {telegram_id} as they are in an archive or folder.")
                            continue

                        raw_dialogue = await get_messages_from_db(session, telegram_id, True)
                        dialogue_list = [{'text': message.text, 'sender': 'me' if message.from_me else 'user'} for message in raw_dialogue]
                        
                        ai_answer = await process_message(prompt_text, dialogue_list, config.OPENAI_API.models.push, as_json=True)
                        bot_answer = json.loads(ai_answer)
                        
                        texts = []
                        media_to_send = None
                        
                        if isinstance(bot_answer, list):
                            for item in bot_answer:
                                if isinstance(item, dict):
                                    if item.get('type') == 'text' and 'body' in item:
                                        texts.append(item['body'])
                                    elif item.get('type') in ['video', 'image'] and 'body' in item:
                                        media_to_send = item
                        
                        if not texts and not media_to_send:
                            logger.warning(f"Не найден текст или медиа в ответе для {period['code']} пуша: {bot_answer}")
                            continue
                        
                        if period['code'] == PushPeriod.HOURS_4:
                            sent_text_combined = []
                            for text_to_send in texts:
                                await send_text_message(client, session, telegram_id, '', text_to_send)
                                sent_text_combined.append(text_to_send)
                                await asyncio.sleep(random.uniform(3, 5))
                            
                            await add_push_message(session, telegram_id, " ".join(sent_text_combined), period['code'])
                            logger.info(f"Отправлен AI-пуш ({period['code']}) пользователю {telegram_id}")

                        elif period['code'] == PushPeriod.HOURS_8:
                            sent_text_combined = " ".join(texts)
                            if media_to_send:
                                file_path = media_to_send['body']['file']
                                caption = sent_text_combined if sent_text_combined else media_to_send['body'].get('caption', '')
                                description = media_to_send['body'].get('description', '')

                                if media_to_send['type'] == 'video':
                                    await send_video_to_chat(client, session, telegram_id, [{'file': file_path, 'caption': caption}])
                                elif media_to_send['type'] == 'image':
                                    await send_photo_to_chat(client, session, telegram_id, [{'file': file_path, 'caption': caption}])
                                    
                                await add_push_message(session, telegram_id, f'{sent_text_combined} [Медиа-пруф]', period['code'])
                                logger.info(f"Отправлен AI-пуш с медиа ({period['code']}) пользователю {telegram_id}")
                            else:
                                for text_to_send in texts:
                                    await send_text_message(client, session, telegram_id, '', text_to_send)
                                    await asyncio.sleep(random.uniform(1.5, 2.5))
                                await add_push_message(session, telegram_id, sent_text_combined, period['code'])
                                logger.info(f"Отправлен AI-пуш (только текст) ({period['code']}) пользователю {telegram_id}")
                        
                        await asyncio.sleep(random.uniform(10, 20))
                    except Exception as e:
                        logger.error(f"Ошибка при отправке пуш-уведомления пользователю {telegram_id} для периода {period['label']}: {e}")
                        continue
            except Exception as e:
                logger.error(f"Ошибка при поиске пользователей для периода {period['label']}: {e}")
                continue

async def start_push_notifications(client: TelegramClient):
    await asyncio.sleep(120)  # Добавляем 2 минуты задержки перед началом
    """Запуск периодической задачи отправки пуш-уведомлений"""
    while True:
        try:
            await send_push_notifications(client)
        except Exception as e:
            logger.error(f"Ошибка в периодической задаче пуш-уведомлений: {str(e)}")
        finally:
            logger.info("Ожидание 120 минут перед следующей проверкой пушей.")
            await asyncio.sleep(7000)