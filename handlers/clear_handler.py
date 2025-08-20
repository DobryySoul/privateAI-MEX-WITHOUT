from database.engine import async_session
from settings.logger import logger
from telethon import events
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
            event.respond("Пользователь не найден, ничего не делаем.")
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
    await event.respond("Диалог и данные пользователя очищены.")
    raise StopPropagation

@events.register(events.NewMessage(pattern=r"/delete (.+)", from_users='me'))
async def delete_in_favorites_handler(event):
    me = await event.client.get_me()

    if event.chat_id != me.id:
        await event.respond("Эта команда работает только в чате 'Избранное'.")
        return
    search_text = event.pattern_match.group(1).strip()

    if len(search_text) <= 7:
        await event.edit("Строка для поиска и удаления должна быть длиннее 7 символов.")
        return

    logger.info(f"Начинаем поиск сообщений с текстом: '{search_text}'")

    try:
        messages = await event.client.get_messages(None, limit=None, search=search_text)
        count = len(messages) - 1 

        if count == 0:
            await event.edit(f"Сообщения с текстом ```{search_text}``` не найдены.")
            return

        response_text = (
            f"Найдено сообщений с текстом:\n```{search_text}```\n\n"
            f"Количество: **{count}**\n\n"
            f"Для подтверждения удаления отправьте:\n```/confirm {search_text}```"
        )
        await event.edit(response_text)
        logger.info(f"Найдено {count} сообщений. Ожидаем подтверждения.")

    except Exception as e:
        logger.error(f"Ошибка при поиске сообщений: {e}")
        await event.edit(f"Произошла ошибка при поиске: {e}")


@events.register(events.NewMessage(pattern=r"/confirm (.+)", from_users='me'))
async def confirm_delete_handler(event):
    me = await event.client.get_me()

    if event.chat_id != me.id:
        await event.respond("Эта команда работает только в чате 'Избранное'.")
        return
    
    search_text = event.pattern_match.group(1).strip()

    if len(search_text) <= 7:
        await event.edit("Строка для удаления должна быть длиннее 7 символов.")
        return

    try:
        all_found_messages = await event.client.get_messages(None, search=search_text, limit=None)
        
        messages_to_delete = [msg for msg in all_found_messages if msg.chat_id != me.id]
        
        deleted_count = len(messages_to_delete)

        if deleted_count == 0:
            await event.edit(f"Сообщения для удаления с текстом ```{search_text}``` не найдены (вне чата 'Избранное').")
            return

        await event.client.delete_messages(None, [msg.id for msg in messages_to_delete])

        await event.respond(f"✅ **Успешно удалено {deleted_count} сообщений** с текстом:\n```{search_text}```")
        
        logger.info(f"Удалено {deleted_count} сообщений.")

    except Exception as e:
        logger.error(f"Ошибка при удалении сообщений: {e}")
        await event.respond(f"Произошла ошибка во время удаления: {e}")
