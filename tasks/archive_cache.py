import asyncio
import time
from settings.logger import logger
from telethon import TelegramClient
from telethon.errors import FloodWaitError, ServerError, TimedOutError, RPCError
from utils import shared_cache  # Импортируем общий модуль для кеша

async def update_archived_dialogs_cache(client: TelegramClient):
    """
    Периодическое обновление кеша архивных диалогов
    """
    # Используем общий кеш из shared_cache
    
    try:
        logger.debug("Плановое обновление кеша архивных диалогов")
        
        try:
            logger.debug("Начало получения архивных диалогов через итератор")
            
            shared_cache.archived_dialogs_cache = {}
            dialog_count = 0
            
            async for dialog in client.iter_dialogs(archived=True):
                dialog_count += 1
                if hasattr(dialog.entity, 'id'):
                    shared_cache.archived_dialogs_cache[dialog.entity.id] = dialog
                    if dialog_count % 50 == 0:
                        logger.debug(f"Получено {dialog_count} диалогов...")
            
            logger.debug(f"Всего получено {dialog_count} диалогов, из них в кеш добавлено {len(shared_cache.archived_dialogs_cache)}")
                    
            shared_cache.last_cache_time = time.time()
            logger.info(f"Кеш архивных диалогов обновлен. Получено {len(shared_cache.archived_dialogs_cache)} диалогов")
        except FloodWaitError as e:
            wait_time = e.seconds + 30
            shared_cache.last_cache_time = time.time() - shared_cache.CACHE_UPDATE_INTERVAL + wait_time
            
            logger.warning(f"Получен FloodWaitError при запросе диалогов. Ожидание {e.seconds} секунд. Следующая попытка через {wait_time} секунд")
        except (ServerError, TimedOutError) as e:
            shared_cache.last_cache_time = time.time() - shared_cache.CACHE_UPDATE_INTERVAL + 120
            logger.error(f"Ошибка сервера при обновлении кеша архивных диалогов: {e}. Следующая попытка через 2 минуты")
        except RPCError as e:
            shared_cache.last_cache_time = time.time() - shared_cache.CACHE_UPDATE_INTERVAL + 300
            logger.error(f"RPC ошибка при обновлении кеша архивных диалогов: {e}. Следующая попытка через 5 минут")
        except Exception as e:
            shared_cache.last_cache_time = time.time() - shared_cache.CACHE_UPDATE_INTERVAL + 300
            logger.error(f"Неизвестная ошибка при обновлении кеша архивных диалогов: {e}. Следующая попытка через 5 минут")
    except Exception as e:
        logger.error(f"Критическая ошибка в задаче обновления кеша архивных диалогов: {e}")

async def start_archive_cache_update(client: TelegramClient):
    """
    Запуск периодической задачи обновления кеша архивных диалогов
    """
    # Начальная задержка для предотвращения конфликтов при запуске
    await asyncio.sleep(15)  # Увеличиваем задержку для более надежного запуска
    
    while True:
        try:
            await update_archived_dialogs_cache(client)
        except Exception as e:
            logger.error(f"Критическая ошибка в периодической задаче обновления кеша: {e}")
        finally:
            # Проверяем, когда нужно выполнить следующее обновление
            current_time = time.time()
            time_since_last_update = current_time - shared_cache.last_cache_time
            
            # Если кеш был обновлен менее чем CACHE_UPDATE_INTERVAL назад, ждем оставшееся время
            if time_since_last_update < shared_cache.CACHE_UPDATE_INTERVAL:
                wait_time = shared_cache.CACHE_UPDATE_INTERVAL - time_since_last_update
                logger.debug(f"Следующее обновление кеша через {wait_time:.0f} секунд")
                await asyncio.sleep(wait_time)
            else:
                # Иначе обновляем сразу на следующей итерации
                logger.debug("Кеш устарел, обновляем немедленно")
                await asyncio.sleep(1)