from telethon import TelegramClient, events
import asyncio

from settings.config import config
from settings.logger import logger
from handlers import text_handler, photo_handler, document_handler, video_gif_handler, sticker_handler, clear_handler, voice_handler
from tasks.archive_cache import start_archive_cache_update
from tasks.inactive_users import start_push_notifications
from tasks.push_reminder import start_30min_push_loop


async def setup_handlers(client):
    """Настройка обработчиков событий"""
    client.add_event_handler(clear_handler, events.NewMessage(pattern=r"/clear"))
    client.add_event_handler(
        voice_handler,
        events.NewMessage(func=lambda e: e.is_private and getattr(e.message, 'voice', None) is not None)
    )
    client.add_event_handler(
        video_gif_handler, 
        events.NewMessage(func=lambda e: e.is_private and (e.video or e.gif))
    )
    client.add_event_handler(
        photo_handler, 
        events.NewMessage(func=lambda e: e.is_private and (e.photo and not e.gif))
    )
    client.add_event_handler(
        text_handler, 
        events.NewMessage(func=lambda e: e.is_private and (e.message.text and not e.message.media))
    )
    client.add_event_handler(
        sticker_handler, 
        events.NewMessage(func=lambda e: e.is_private and e.sticker)
    )
    client.add_event_handler(
        document_handler, 
        events.NewMessage(func=lambda e: e.is_private and (e.document and not (e.video or e.sticker)))
    )
    logger.info("Все обработчики успешно настроены")


async def main():
    """Основная функция запуска бота"""
    # Инициализация клиента
    client = TelegramClient(
        f"{config.TELEGRAM.account}.session", 
        config.TELEGRAM.api_id, 
        config.TELEGRAM.api_hash
    )
    
    try:
        # Запуск клиента
        await client.start()
        logger.info("Бот успешно запущен")
        
        # Настройка обработчиков
        await setup_handlers(client)
        
        # Запуск задачи отправки пуш-уведомлений
        asyncio.create_task(start_push_notifications(client))
        logger.info("Успешно запущена задача отправки пуш-уведомлений")
        
        # Запуск задачи обновления кеша архивных диалогов
        asyncio.create_task(start_archive_cache_update(client))
        logger.info("Успешно запущена задача обновления кеша архивных диалогов")

        # Запуск задачи 30-минутных пушей
        # asyncio.create_task(start_30min_push_loop(client))
        # logger.info("Успешно запущена задача 30-минутных пушей")

        await client.catch_up()
        # Поддержание работы бота
        await client.run_until_disconnected()
    except Exception as e:
        logger.error(f"Ошибка во время работы бота: {e}")
    finally:
        if client.is_connected():
            await client.disconnect()
            logger.info("Бот отключен")


if __name__ == "__main__":
    asyncio.run(main())
