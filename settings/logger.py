import logging
from logging import handlers
import sys
import os

# Создание директорий для логов
os.makedirs("logs/debug", exist_ok=True)
os.makedirs("logs/info", exist_ok=True)

# Создание основного логгера
fmt = logging.Formatter(fmt='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s', datefmt='%m-%d %H:%M:%S')
logger = logging.getLogger('')
logger.setLevel(logging.DEBUG)

# Настройка файловых обработчиков для отладки и информации
debug_file = handlers.RotatingFileHandler("logs/debug/app_debug.log", maxBytes=(1048576*5), backupCount=10, encoding="utf-8")
debug_file.setFormatter(fmt)

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(fmt)
ch.setLevel(logging.INFO)

info_file = handlers.RotatingFileHandler("logs/info/app_info.log", maxBytes=(1048576*5), backupCount=7, encoding="utf-8")
info_file.setFormatter(fmt)
info_file.setLevel(logging.INFO)

# Добавление обработчиков к основному логгеру
logger.addHandler(info_file)
logger.addHandler(debug_file)
logger.addHandler(ch)

# # Логирование SQLAlchemy
# # Получаем логгер SQLAlchemy
# sqlalchemy_logger = logging.getLogger('sqlalchemy.pool')
# sqlalchemy_logger.setLevel(logging.DEBUG)  # Уровень логирования для SQLAlchemy
#
# # Добавляем существующие обработчики в логгер SQLAlchemy
# sqlalchemy_logger.addHandler(info_file)
# sqlalchemy_logger.addHandler(debug_file)
# sqlalchemy_logger.addHandler(ch)
