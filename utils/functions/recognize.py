import asyncio
from settings.logger import logger
from telethon.tl.functions.messages import TranscribeAudioRequest
from telethon.errors import FloodWaitError
from telethon.errors.rpcerrorlist import InterdcCallErrorError


async def transcribe_voice(event, max_attempts: int = 10):
    """
    Транскрибирует голосовое сообщение из события Telegram.
    Возвращает текст или None, если не удалось получить результат.
    """
    # Ищем duration pythonic-способом
    duration = next((a.duration for a in getattr(event.message.voice, 'attributes', []) if hasattr(a, 'duration')), 10)
    if not duration:
        logger.warning("Не удалось определить длительность голосового сообщения, используем значение по умолчанию (10 сек)")
        duration = 10
    delay = (duration / max_attempts) * 1.5
    for attempt in range(1, max_attempts + 1):
        try:
            result = await event.client(TranscribeAudioRequest(
                peer=event.chat_id,
                msg_id=event.message.id
            ))
            logger.debug(f"[Transcribe attempt {attempt}/{max_attempts}] text: {getattr(result, 'text', None)}")
            if getattr(result, 'text', None):
                return result.text
        except FloodWaitError as e:
            logger.warning(f"FloodWait: sleeping for {e.seconds} seconds (attempt {attempt})")
            await asyncio.sleep(e.seconds * 2)
        except InterdcCallErrorError as e:
            logger.warning(f"InterdcCallError (likely transient) caught during transcription (attempt {attempt}): {e}")
            await asyncio.sleep(delay * 2) 
        except Exception as e:
            logger.error(f"Transcribe error (attempt {attempt}): {e}")
        await asyncio.sleep(delay)
    logger.warning("Транскрипция не удалась после всех попыток.")
    return None