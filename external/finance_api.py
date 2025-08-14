import random
from typing import Any, Dict, List
import httpx
# from settings.config import config  # предполагается, что у вас есть глобальный config
from settings.logger import logger

# BASE_URL = config.EXTERNAL.finance_api + "/accounts/requisites"

async def check_requisites(requisite: str, telegram_id: str) -> bool:
    """
    Поиск реквизитов по query. Возвращает True, если status=True и allow_fd=True, иначе False.
    """
    url = f"{BASE_URL}/search/"
    params = {"query": requisite, "telegram_id": telegram_id}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            if response.status_code == 404:
                logger.info(f"check_requisites: 404 Not Found для query={requisite}, telegram_id={telegram_id}")
                return False
            response.raise_for_status()
            data = response.json()
            if data:
                if data.get("status", False) is True and data.get("allow_fd", False) is True:
                    return True
                return False
            logger.warning(f"check_requisites: Пустой массив или неожиданный ответ: {data}")
            return False
    except httpx.HTTPError as e:
        logger.error(f"Ошибка при поиске реквизитов: {e}")
        return False


async def select_requisite(telegram_id: str) -> Dict[str, Any]:
    """
    Получает реквизит, удоволетворяющей условию по каналу, принадлежащему telegram_id.
    """
    url = f"{BASE_URL}/selection/"
    params = {"telegram_id": telegram_id}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params, timeout=10)
            if response.status_code == 404:
                logger.info(f"select_requisite: 404 Not Found для telegram_id={telegram_id}")
                return {}
            response.raise_for_status()
            data = response.json()
            if not data:
                logger.warning(f"get_all_requisites: Неожиданный ответ: {data}")
                return {}
            data_additional = data.get("dataadditional") or []
            data_requisite = {
                "data_name": data.get("holder") or "",
                "data_one": data.get("dataone") or "",
                "data_two": data_additional[0] if len(data_additional) > 0 else "",
                "data_three": data_additional[1] if len(data_additional) > 1 else "",
            }
            return data_requisite
    except httpx.HTTPError as e:
        logger.error(f"Ошибка при получении всех реквизитов: {e}")
        return {}
