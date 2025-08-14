from telethon import events
from telethon.tl.types import DocumentAttributeSticker

from handlers.common import common_handler
from settings.logger import logger
from telethon.events import StopPropagation

async def sticker_handler(event: events.NewMessage.Event):   
    sticker = next(attr for attr in event.message.sticker.attributes if isinstance(attr, DocumentAttributeSticker)).alt
    user_message = sticker or '😀'
    logger.info(f"New sticker received: {user_message}")
    await common_handler(event, user_message)
    raise StopPropagation