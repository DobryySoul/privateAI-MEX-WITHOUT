import aiohttp
import base64
import ssl
from pathlib import Path
from datetime import datetime

from settings.config import config
from settings.logger import logger

async def generate_voice_message(text: str) -> str:
    """
    Генерация голосового сообщения с использованием Speechify API
    Args:
        text: Текст для озвучивания
    Returns:
        str: Путь к сгенерированному аудиофайлу или пустая строка при ошибке
    """
    api_key = config.SPEECH_API.api_key
    voice_id = config.SPEECH_API.voice_id
    model = config.SPEECH_API.model
    language = config.SPEECH_API.language
    audio_path = Path('assets/voice_messages/generated')
    audio_path.mkdir(parents=True, exist_ok=True)
    api_url = "https://api.sws.speechify.com/v1"

    payload = {
        "input": text,
        "voice_id": voice_id,
        "audio_format": "mp3",
        "model": model,
        "language": language
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    try:
        async with aiohttp.ClientSession(connector=connector) as http_session:
            async with http_session.post(api_url + "/audio/speech", json=payload, headers=headers) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Ошибка API Speechify: {response.status}, {error_text}")
                    return ""
                response_data = await response.json()
                if 'audio_data' in response_data:
                    audio_data = base64.b64decode(response_data['audio_data'])
                else:
                    logger.error("API Speechify не вернул аудио-данные")
                    return ""
        filename = f"speech_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
        file_path = audio_path / filename
        with open(file_path, "wb") as f:
            f.write(audio_data)
        logger.info(f"Сгенерировано голосовое сообщение: {file_path}")
        return str(file_path)
    except Exception as e:
        logger.error(f"Ошибка при генерации голосового сообщения через Speechify: {e}")
        return ""