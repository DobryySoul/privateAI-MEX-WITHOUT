import pytz
from datetime import datetime, timedelta
from telethon.tl.functions.messages import DeleteScheduledMessagesRequest
from settings.config import config
from settings.logger import logger

async def schedule_message(client, sender_id: int, body):
    body_dict = body if isinstance(body, dict) else {}
    send_at_date = body_dict.get('send_at_date')
    message = body_dict.get('message')

    if not (send_at_date and message):
        logger.warning(f"schedule_message missing send_at_date or message: {body}")
        return False

    try:
        tz = pytz.timezone(config.TECHNICAL_DATA.time_zone)
        if 'T' in send_at_date:
            date_part = send_at_date.split('T')[0]
        else:
            date_part = send_at_date 

        send_time_local = datetime.strptime(f"{date_part} 13:00:00", "%Y-%m-%d %H:%M:%S")
        send_time_aware = tz.localize(send_time_local)
        
        if send_time_aware < (datetime.now(tz) - timedelta(minutes=5)):
            logger.error(
                f"CRITICAL AI ERROR: Attempted to schedule a message in the past for date {send_at_date}. "
                f"CURRENT DATE IS {datetime.now(tz).strftime('%Y-%m-%d')}. Message will NOT be sent."
            )
            return False

        existing_scheduled_messages = []
        async for scheduled_msg in client.iter_messages(sender_id, scheduled=True):
            existing_scheduled_messages.append(scheduled_msg.id)

        if existing_scheduled_messages:
            logger.info(f"Deleting {len(existing_scheduled_messages)} existing scheduled messages for user {sender_id}")
            await client(DeleteScheduledMessagesRequest(
                peer=sender_id,
                id=existing_scheduled_messages
            ))
            logger.info(f"Successfully deleted existing scheduled messages for user {sender_id}")

        await client.send_message(
            sender_id,
            message,
            schedule=send_time_aware
        )
        logger.info(f"Successfully scheduled message for user {sender_id} at {send_time_aware}")
        return True

    except Exception as e:
        logger.error(f"Failed to schedule message via Telegram API: {e}")
        return False 