from datetime import datetime
import re
from settings.config import config
from settings.logger import logger

TELEGRAM_HANDLE_OR_LINK_PATTERN = re.compile(r'@\w+|tg://')
PHONE_NUMBER_PATTERN = re.compile(r'\b\+\d{10,15}\b')

async def send_monitoring_notification(client, user_id: int, message_content: str, message_type: str = "text"):
    """
    Sends notification to monitoring chat when outgoing message is detected in non-favorite dialog.
    """
    try:
        monitoring_chat = config.TECHNICAL_DATA.monitoring_chat
        notification_text = (
            f"🚨 ВНИМАНИЕ: Обнаружено исходящее сообщение!\n\n"
            f"👤 Пользователю с ID: {user_id}\n"
            f"📝 Тип сообщения: {message_type}\n"
            f"💬 Содержимое: {message_content[:200]}{'...' if len(message_content) > 200 else ''}\n"
            f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await client.send_message(monitoring_chat, notification_text)
        logger.warning(f"Monitoring notification sent successfully for user {user_id} with {message_type} message")
    except Exception as e:
        logger.error(f"Failed to send monitoring notification: {e}", exc_info=True) 