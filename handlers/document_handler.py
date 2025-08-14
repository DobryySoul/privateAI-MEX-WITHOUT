from telethon import events
from settings.config import config
from database.engine import async_session
from database.requests.user import get_user, increment_global_counter
from settings.logger import logger
from utils.functions.senders import forward_media_to_favorites
from utils.functions.telegram_client_helpers import move_chat_to_folder_include_peers
from external.channel import get_bot_id
from telethon.events import StopPropagation
from utils.check_fd import is_fd

async def document_handler(event: events.NewMessage.Event):
    client = event.client
    my_id = await get_bot_id(client)

    sender = await event.get_sender()
    if sender.bot:
        return

    # Проверка на исходящие сообщения с документами в не архивных диалогах
    from_me = sender.id == my_id

    if not await is_fd(client, sender.id) or from_me:
        return
    
    logger.info(f"New file received from {sender.id}")

    user_message = event.message.text or ''
    document = event.message.file.id

    async with (async_session() as session):
        user = await get_user(session, sender.id)
        user.stop = True
        await increment_global_counter(session, user)
        await session.commit()
        await move_chat_to_folder_include_peers(event.client, sender.id, config.TECHNICAL_DATA.folder_name)
        await forward_media_to_favorites(event.client, sender, user_message, document)
    
    raise StopPropagation