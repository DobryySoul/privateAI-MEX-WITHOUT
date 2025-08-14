"""
Модуль для хранения общих кешей и данных, используемых в разных частях приложения
"""

import time

# Кеш для хранения архивных диалогов
archived_dialogs_cache = {}
last_cache_time = 0

# Константа для интервала обновления кеша в секундах (10 минут)
CACHE_UPDATE_INTERVAL = 600

def get_cache_age():
    """
    Возвращает время в секундах с момента последнего обновления кеша
    """
    return time.time() - last_cache_time

def is_cache_expired():
    """
    Проверяет, истек ли срок действия кеша
    """
    return get_cache_age() > CACHE_UPDATE_INTERVAL
