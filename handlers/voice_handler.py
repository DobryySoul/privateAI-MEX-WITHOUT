from re import L
from telethon import events
from handlers.common import common_handler
from settings.logger import logger
from utils.functions.recognize import transcribe_voice
from telethon.events import StopPropagation

async def voice_handler(event: events.NewMessage.Event): 
    voice = getattr(event.message, 'voice', None)
    if not voice:
        logger.info("No voice message in event, skipping")
        return
    
    logger.info(f"New voice message received from {event.chat_id}")
    
    result = await transcribe_voice(event)
    if not result or len(result) == 0:
        logger.warning("Не удалось получить текст из голосового сообщения после всех попыток.")
        return
    
    logger.info(f"Итоговая расшифровка: {result}")
    
    user_reply = f"voice message: {result}"
    await common_handler(event, user_reply)
    raise StopPropagation