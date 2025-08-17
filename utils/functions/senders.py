import asyncio
import os
import re
import tempfile
import telethon
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.tl.types import (
    SendMessageTypingAction, 
    SendMessageCancelAction, 
    SendMessageRecordAudioAction,
    SendMessageUploadDocumentAction, 
    SendMessageUploadPhotoAction, 
    SendMessageUploadVideoAction,
    DocumentAttributeVideo
)
from database.requests.message import add_message
from database.requests.user import set_payment_data_for_user
from settings.config import config
from settings.logger import logger
from external.channel import get_bot_id
from external.speech_api import generate_voice_message
from utils.functions.telegram_client_helpers import move_chat_to_folder_include_peers

TELEGRAM_HANDLE_OR_LINK_PATTERN = re.compile(r'@\w+|tg://')
PHONE_NUMBER_PATTERN = re.compile(r'\b\+?\d{7,}\b')

async def forward_media_to_favorites(client, sender, caption, document):
    try:
        text = f'ID: {sender.id} | Message from [{sender.first_name}](tg://user?id={sender.id})' + ('\n with caption: ' + caption if caption else '')
        await client.send_file('me', file=document, caption=text)
        logger.info(f"Object forwarded to Saved Messages with link to sender {sender.id}")
    except Exception as e:
        logger.error(f"Failed to forward object from sender {sender.id} to Saved Messages: {e}", exc_info=True)

async def send_combined_message(client: telethon.TelegramClient, session: AsyncSession, recipient_id: int,
                                user_message: str, message_data: bool):
    logger.info(f'send_combined_message Processing message data: {message_data}')

    # message_data это список словарей с order/type/body
    sorted_messages = sorted(message_data, key=lambda x: x.get('order', 999))
    logger.debug(f'Sending {len(sorted_messages)} messages in specified order to recipient_id={recipient_id}')

    for message in sorted_messages:
        message_type = message.get('type')
        body = message.get('body')
        if message_type == 'voice':
            if isinstance(body, tuple) and len(body) == 2:
                voice_message, transcript = body
                await send_voice_message_to_chat(client, session, recipient_id, user_message, voice_message, transcript)
        elif message_type == 'text':
            await send_text_message(client, session, recipient_id, user_message, body)
        elif message_type == 'image':
            if isinstance(body, tuple):
                body = [body]
            await send_photo_to_chat(client, session, recipient_id, body)
        elif message_type == 'video':
            if isinstance(body, tuple):
                video_path = body[0] 
            elif isinstance(body, list) and body:
                video_path = body[0].get('file')
            else:
                video_path = body 

            if video_path and "video_note" in os.path.basename(video_path):
                if isinstance(body, tuple):
                    body = [{'file': body[0], 'caption': body[1] if len(body) > 1 else ''}]
                elif isinstance(body, str):
                    body = [{'file': body, 'caption': ''}]
                await send_video_note_to_chat(client, session, recipient_id, body)
            else:
                if isinstance(body, tuple):
                    body = [body]
                await send_video_to_chat(client, session, recipient_id, body)
        elif message_type == 'document':
            if isinstance(body, tuple) and len(body) == 2:
                document_path, document_name = body
                await send_document_to_chat(client, session, recipient_id, document_path, document_name)

    logger.info('send_combined_message function completed successfully')

async def send_text_message(client: telethon.TelegramClient, session: AsyncSession, recipient_id: int, user_message: str, bot_message: str):
    is_payment_message = '{{payment_cash}}' in bot_message or '{{payment_bank}}' in bot_message
    
    # Update bot_reply with payment data if necessary
    bot_message, data_photo = await set_payment_data_for_user(session, recipient_id, bot_message)

    if is_payment_message:
        try:
            await move_chat_to_folder_include_peers(client, recipient_id, config.TECHNICAL_DATA.wait_payment_folder_name)
            logger.info(f"Successfully attempted to move user {recipient_id} to '{config.TECHNICAL_DATA.wait_payment_folder_name}' folder.")
        except Exception as e:
            logger.error(f"Failed to move user {recipient_id} to '{config.TECHNICAL_DATA.wait_payment_folder_name}' folder: {e}", exc_info=True)

    if data_photo:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp:
            tmp.write(data_photo)
            tmp_path = tmp.name
        try:
            await send_photo_to_chat(client, session, recipient_id, [{'file': tmp_path, 'description': 'Payment data photo with qr-code'}])
        finally:
            os.remove(tmp_path)

    if is_payment_message:
        await client.send_message(get_bot_id(), f'Dialogue: {recipient_id}, {bot_message}. Contact administrator!')

    # Log the message being added to the user
    await add_message(session, recipient_id, bot_message, True)
    await client.send_read_acknowledge(recipient_id)

    # Calculate delay based on user_reply length and log it
    delay = len(user_message) * config.TECHNICAL_DATA.read_delay
    await asyncio.sleep(delay)

    # Remove any surrounding quotes from the bot_reply if present
    if bot_message.startswith('"') or bot_message.startswith("'"):
        bot_message = bot_message[1:-1]

    # Calculate delay based on bot_reply length and log it
    async with client.action(recipient_id, SendMessageTypingAction()):
        delay = len(bot_message) * config.TECHNICAL_DATA.typing_delay
        await asyncio.sleep(delay)
        await client.send_message(recipient_id, bot_message)
        await client.action(recipient_id, SendMessageCancelAction())

    # Log successful message sending
    logger.info(f'Message sent successfully to recipient_id={recipient_id}')

async def send_generated_voice_message(client: telethon.TelegramClient, session: AsyncSession, recipient_id: int, user_message: str, bot_message: str):
    
    await add_message(session, recipient_id, bot_message, True)
    await client.send_read_acknowledge(recipient_id)

    async with client.action(recipient_id, SendMessageRecordAudioAction()):
        voice_file = await generate_voice_message(bot_message)
        await client.send_file(recipient_id, voice_file, voice_note=True)
        await client.action(recipient_id, SendMessageCancelAction())

    os.remove(voice_file)
    logger.debug(f'Voice file removed: {voice_file}')
    logger.info(f'Voice message sent successfully to recipient_id={recipient_id}')

async def send_voice_message_to_chat(client: telethon.TelegramClient, session: AsyncSession, recipient_id: int, user_message: str, voice_message: str, transcript: str):

    await add_message(session, recipient_id, transcript, True)

    # Read chat history for the user
    await client.send_read_acknowledge(recipient_id)

    # Calculate and log delays
    delay = len(user_message) * config.TECHNICAL_DATA.read_delay
    await asyncio.sleep(delay)

    await _send_media_to_chat(client, session, recipient_id, {'file': voice_message, 'caption': transcript}, SendMessageRecordAudioAction, 'voice', is_voice_note=True)

async def send_document_to_chat(client: telethon.TelegramClient, session: AsyncSession, recipient_id: int, document_path: str, document_name: str):
    """
    Sends one or multiple documents to the chat.
    Args:
        client: Telegram client
        session: Async session
        recipient_id: ID of the recipient
        document_path: Path to the document
        document_name: Name of the document
    """
    await _send_media_to_chat(client, session, recipient_id, {'file': document_path, 'caption': document_name}, SendMessageUploadDocumentAction, 'document')


async def send_photo_to_chat(client: telethon.TelegramClient, session: AsyncSession, recipient_id: int, photo_data):
    """
    Sends one or multiple photos to the chat.
    Args:
        client: Telegram client
        session: Async session
        recipient_id: ID of the recipient
        photo_data: List of dicts [{'file': path, 'caption': str, 'description': str}]
    """
    await _send_media_to_chat(client, session, recipient_id, photo_data, SendMessageUploadPhotoAction, 'photo')


async def send_video_to_chat(client: telethon.TelegramClient, session: AsyncSession, recipient_id: int, video_data):
    """
    Sends one or multiple videos to the chat.
    Args:
        client: Telegram client
        session: Async session
        recipient_id: ID of the recipient
        video_data: List of dicts [{'file': path, 'caption': str, 'description': str}]
    """
    
    if isinstance(video_data, str):
        video_data = [{'file': video_data}]
    elif isinstance(video_data, dict):
        video_data = [video_data]

    await _send_media_to_chat(client, session, recipient_id, video_data, SendMessageUploadVideoAction, 'video', is_voice_note=False)

async def send_video_note_to_chat(client: telethon.TelegramClient, session: AsyncSession, recipient_id: int, video_note_data):

    if isinstance(video_note_data, str):
        video_note_data = [{'file': video_note_data}]
    elif isinstance(video_note_data, dict):
        video_note_data = [video_note_data]

    await _send_media_to_chat(client, session, recipient_id, video_note_data, SendMessageUploadVideoAction, 'video_note', is_voice_note=True)

async def _send_media_to_chat(client: telethon.TelegramClient, session: AsyncSession, recipient_id: int, media_data, message_action_type, media_type: str, file_key: str = 'file', is_voice_note: bool = False):
    if isinstance(media_data, str):
        media_data = [{file_key: media_data}]
    elif isinstance(media_data, dict):
        media_data = [media_data]

    for item in media_data:
        path = item.get(file_key)
        caption = item.get('caption', '')
        description = item.get('description', '')
        log_message = f'attached: {media_type} {description} with caption {caption}'

        await add_message(session, recipient_id, log_message, True, attachment_path=path)
        async with client.action(recipient_id, message_action_type(50)):
            await asyncio.sleep(1)
            if is_voice_note:
                await client.send_file(
                    recipient_id,
                    path,
                    video_note=True,
                    attributes=[
                        DocumentAttributeVideo(
                            round_message=True,
                            duration=0,
                            nosound=True,
                            w=480,
                            h=480
                        )
                    ]
                )
            else:
                await client.send_file(recipient_id, path, caption=caption, voice_note=False, video=(media_type == 'video'))
    
    await client.action(recipient_id, SendMessageCancelAction())
    logger.info(f'{len(media_data)} {media_type}s sent successfully to recipient_id={recipient_id}')
