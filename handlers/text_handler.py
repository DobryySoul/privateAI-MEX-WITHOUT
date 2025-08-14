from telethon import events
from handlers.common import common_handler
from telethon.events import StopPropagation


async def text_handler(event: events.NewMessage.Event):
    if event.message.media:
        raise StopPropagation
    user_message = event.message.text  # Текст сообщения
    await common_handler(event, user_message)