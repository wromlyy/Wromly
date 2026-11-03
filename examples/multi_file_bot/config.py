"""Настройки бота из локального файла .env."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str
    channel_id: int


def load_config() -> Config:
    env_path = Path(__file__).with_name(".env")
    if not env_path.is_file():
        raise RuntimeError("Создайте .env рядом с main.py по образцу .env.example")
    load_dotenv(env_path, override=True)
    token = os.getenv("BOT_TOKEN", "").strip()
    channel = os.getenv("CHANNEL_ID", "").strip()
    if not token or token == "123456789:replace_with_your_bot_token":
        raise RuntimeError("Укажите настоящий BOT_TOKEN в .env")
    try:
        channel_id = int(channel)
    except ValueError as exc:
        raise RuntimeError("CHANNEL_ID в .env должен быть числом") from exc
    return Config(token=token, channel_id=channel_id)
