from settings.config import config
from settings.logger import logger
from telethon import functions
from telethon.types import InputPeerUser
from utils import shared_cache

# client: TelegramClient
# client.edit_folder(chat, 1) 
# # 1 is archived 0 unarchived

async def is_fd(client, user_id) -> bool:
    logger.info(f"Проверка статуса ФД для пользователя {user_id}")
    
    try:
        logger.info(f"Используем кешированные архивные диалоги ({len(shared_cache.archived_dialogs_cache)} диалогов)")
        archived_dialogs_dict = shared_cache.archived_dialogs_cache
        
        # Проверяем, находится ли пользователь в архиве
        if user_id in archived_dialogs_dict:
            logger.info(f"Пользователь {user_id} найден в архиве")
            return False
            
        # Проверяем папки
        filters_obj = await client(functions.messages.GetDialogFiltersRequest())
        filters = filters_obj.filters
        
        # Проверяем, есть ли пользователь в какой-либо папке
        for f in filters:
            # Если папка называется "DD", то скипаем
            if hasattr(f, 'title') and (getattr(f.title, 'text', None) if hasattr(f.title, 'text') else f.title) == config.TECHNICAL_DATA.wait_payment_folder_name:
                continue 

            if hasattr(f, 'include_peers') and f.include_peers:
                for p in f.include_peers:
                    if isinstance(p, InputPeerUser) and hasattr(p, 'user_id') and p.user_id == user_id:
                        logger.info(f"Пользователь {user_id} найден в папке: {f.title if hasattr(f, 'title') else 'Без названия'}")
                        return False 

        return True
        
    except Exception as e:
        logger.error(f"Ошибка при проверке архивации: {e}", exc_info=True)
        return True