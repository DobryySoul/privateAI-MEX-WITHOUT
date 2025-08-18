import base64
import json
import time
import asyncio
from datetime import datetime
import pytz
from settings.config import config
from settings.config import openai
from settings.logger import logger

async def get_prompt(reason='Text'):
    if reason == 'Image':
        return config.PROMPTS.recognize_prompt
    if reason == 'push_4h':
        return config.PROMPTS.push_4h_prompt
    if reason == 'push_8h':
        return config.PROMPTS.push_8h_prompt
    if reason == 'PushReminder':
        return config.PROMPTS.push_reminder_prompt
    return config.PROMPTS.general_prompt


async def get_api_response(prompt_text, dialogue_list, model, max_attempts=5, as_json=True):
    """
    Получает ответ от API с несколькими попытками в случае ошибки.
    
    Args:
        prompt_text: Текст промпта для API
        dialogue_list: История диалога
        model: Модель для генерации текста
        max_attempts: Максимальное количество попыток
        as_json: Требуется ли ответ в формате JSON
        
    Returns:
        Ответ от API в виде объекта (если as_json=True) или строки
    """
    attempt = 0
    response = None
    
    while response is None and attempt < max_attempts:
        attempt += 1
        logger.info(f"API request attempt {attempt}/{max_attempts}")
        
        try:
            ai_answer = await process_message(prompt_text, dialogue_list, model, as_json=as_json)
            logger.debug(f"API response: {ai_answer}")
            if as_json:
                # Проверяем, что ответ - валидный JSON
                response = json.loads(ai_answer)
                
                if not isinstance(response, list):
                    logger.warning(f"Invalid response from API (list): {ai_answer}")
                    response = None
                    await asyncio.sleep(1)
                    continue
            else:
                response = ai_answer
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Failed to process message: {e}")
            await asyncio.sleep(1)
    return response


async def process_message(prompt, dialogue_list, model='gpt-4o-mini', as_json=False):
    start_time = time.time()
    logger.debug('Starting process_message function')

    try:
        timezone = pytz.timezone(config.TECHNICAL_DATA.time_zone)
        current_time = datetime.now(timezone).strftime("%Y-%m-%d %H:%M:%S %Z%z")
        prompt = f"{prompt}\nCurrent time: {current_time}"
        logger.debug(f"Current time added to prompt: {current_time}")
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"Unknown time zone specified in config: {config.TECHNICAL_DATA.time_zone}. Proceeding without timestamp.")
    except Exception as e:
        logger.error(f"Error adding timestamp to prompt: {e}")

    logger.debug(f'Using premade prompt: {dialogue_list}')

    system_prompt = [{"role": "system", "content": prompt}]

    for phrase in dialogue_list[::-1]:
        for message, role in phrase.items():
            role = 'assistant' if role == 'me' else 'user'
            system_prompt.append({"role": role, "content": message})

    logger.debug(f'Final system_prompt: {system_prompt}')

    completion = await openai.chat.completions.create(
        model=model,
        response_format={"type": "json_object"} if as_json else {"type": "text"},
        messages=system_prompt,
        temperature=0
    )
    
    logger.info(f"{'=' * 16}TOKENS USAGE STAT{'=' * 16}")
    logger.info(f"Reasoning: {completion.usage.completion_tokens_details.reasoning_tokens} | Prompt: {completion.usage.prompt_tokens} | Completion: {completion.usage.completion_tokens} | Total: {completion.usage.total_tokens} | Cached: {completion.usage.prompt_tokens_details.cached_tokens}")
    logger.info(f"{'=' * 49}")

    response = completion.choices[0].message.content
    end_time = time.time()
    logger.debug(f'OpenAI completion response: {response}')
    logger.debug(f'OpenAI completion time: {end_time - start_time}')

    if as_json:
        response = clean_response(response)
        
    return response

def clean_response(response):
    logger.debug('Starting clean_response function')
    # Удаляем цепочки рассуждений в тегах <think>
    if '<think>' in response and '</think>' in response:
        try:
            while '<think>' in response and '</think>' in response:
                start_think = response.find('<think>')
                end_think = response.find('</think>') + 8
                if start_think >= 0 and end_think > start_think:
                    response = response[:start_think] + response[end_think:]
                else:
                    break
            logger.debug(f'Removed <think> tags from response: {response}')
        except Exception as e:
            logger.error(f'Error removing <think> tags: {e}')
    
    # Извлекаем JSON из блоков ```json
    if '`json' in response:
        try:
            response = response.split('`json')[-1].replace('`', '')
            logger.debug(f'Extracted JSON content: {response}')
        except Exception as e:
            logger.error(f'Error extracting JSON from response: {e}')
    
    logger.info(f'Final response: {response}')
    return response

async def recognize_image(photo, user_id, model='gpt-4o'):
    # Open the image file and encode it to base64
    with open(photo, 'rb') as image_file:
        base64_image = base64.b64encode(image_file.read()).decode('utf-8')

    # Create the completion request to OpenAI
    completion = await openai.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": config.PROMPTS.recognize_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
    )
    response = completion.choices[0].message.content

    logger.debug(f'OpenAI completion response for user {user_id}: {response}')

    return response