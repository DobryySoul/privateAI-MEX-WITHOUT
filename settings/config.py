from dataclasses import dataclass
import yaml
from openai import AsyncOpenAI
import os
from external.messages import *


@dataclass
class DBConfig:
    host: str
    user: str
    password: str
    database: str


@dataclass
class TelegramConfig:
    api_id: int
    api_hash: str
    account: str


@dataclass
class ExternalConfig:
    finance_api: str


@dataclass
class OpenAIAPIModelsConfig:
    text_generation: str
    photo_recognition: str
    push: str

@dataclass
class OpenAIAPIConfig:
    api_key: str
    base_url: str
    models: OpenAIAPIModelsConfig

@dataclass
class SpeechifyConfig:
    api_key: str
    voice_id: str
    model: str
    language: str

@dataclass
class TechnicalDataConfig:
    typing_delay: float
    read_delay: float
    voice_delay: float
    to_group_messages_delay_low: int
    to_group_messages_delay_high: int
    stop_responding: int
    time_zone: str
    download_path: str
    stop_phrase: str
    start_phrase: str
    folder_name: str
    wait_payment_folder_name: str
    monitoring_chat: str

@dataclass
class PromptDataConfig:
    general_prompt: str
    recognize_prompt: str
    push_4h_prompt: str
    push_8h_prompt: str
    push_reminder_prompt: str

@dataclass
class Config:
    DB: DBConfig
    TELEGRAM: TelegramConfig
    OPENAI_API: OpenAIAPIConfig
    SPEECH_API: SpeechifyConfig
    TECHNICAL_DATA: TechnicalDataConfig
    PROMPTS: PromptDataConfig
    EXTERNAL: ExternalConfig

def load_config(file_path: str) -> Config:
    # Проверяем ОС: если Windows, добавляем .local к имени файла, если такой файл существует
    if os.name == 'nt':
        root, ext = os.path.splitext(file_path)
        local_path = f"{root}.local{ext}"
        if os.path.exists(local_path):
            file_path = local_path
            print(f"Using local config file: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as file:
        data = yaml.safe_load(file)
        return Config(
            DB=DBConfig(**data['DB']),
            TELEGRAM=TelegramConfig(**data['TELEGRAM']),
            OPENAI_API=OpenAIAPIConfig(
                **{
                    **data['OPENAI_API'],
                    'models': OpenAIAPIModelsConfig(**data['OPENAI_API']['models'])
                }
            ),
            SPEECH_API=SpeechifyConfig(**data['SPEECH_API']),
            TECHNICAL_DATA=TechnicalDataConfig(**data['TECHNICAL_DATA']),
            PROMPTS=PromptDataConfig(**data['PROMPTS']),
            EXTERNAL=ExternalConfig(**data['EXTERNAL']),
        )

config = load_config('config.yaml')

messages = [m0]
openai = AsyncOpenAI(api_key=config.OPENAI_API.api_key, base_url=config.OPENAI_API.base_url)