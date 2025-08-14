from telethon import events
from handlers.common import common_handler
from settings.logger import logger
from telethon.events import StopPropagation

async def video_gif_handler(event: events.NewMessage.Event):
    media_type = 'gif' if event.gif else 'video'
    user_message = f"attached {media_type}: FAILED TO LOAD!!!"
    logger.info(f"New {media_type}")
    await common_handler(event, user_message)
    raise StopPropagation