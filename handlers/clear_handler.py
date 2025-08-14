from database.engine import async_session
from telethon import events
from telethon.tl.functions.messages import SendReactionRequest
from telethon.tl.types import ReactionEmoji
from settings.logger import logger
from sqlalchemy import delete
from database.requests.user import get_user
from database.requests.message import get_messages_from_db, delete_messages
from database.models import User, PushNotification
from telethon.events import StopPropagation

@events.register(events.NewMessage(pattern=r"/clear"))
async def clear_handler(event):
    '''
    Очищает информацию о пользователе и все его сообщения по chat_id (Telegram ID).
    '''
    sender = await event.get_sender()
    chat_id = sender.id
    async with async_session() as session:
        # Получаем пользователя по Telegram ID
        user = await get_user(session, chat_id)
        if not user:
            await event.client(SendReactionRequest(
                peer=event.chat_id,
                msg_id=event.id,
                reaction=[ReactionEmoji(emoticon="👎")]
            ))
            raise StopPropagation  # Пользователь не найден, ничего не делаем
        
        # Получаем все сообщения пользователя
        messages = await get_messages_from_db(session, chat_id, sort=False)
        if messages:
            await delete_messages(session, messages)
            
        # Сначала удаляем связанные push-уведомления
        await session.execute(delete(PushNotification).where(PushNotification.user_id == user.id))
        
        # Теперь удаляем пользователя
        await session.execute(delete(User).where(User.id == user.id))
        await session.commit()
    
    # Логируем очистку
    logger.info(f"Очищена информация о пользователе и его сообщениях: {chat_id}")
    await event.client(SendReactionRequest(
        peer=event.chat_id,
        msg_id=event.id,
        reaction=[ReactionEmoji(emoticon="👍")]
    ))
    raise StopPropagation