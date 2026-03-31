import os
import yaml
from pydantic_settings import BaseSettings
from typing import List, Optional


class LLMConfig(BaseSettings):
    provider: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "qwen2.5:72b"
    temperature: float = 0.7
    max_tokens: int = 4096


class TTSConfig(BaseSettings):
    provider: str = "cosyvoice"
    model_path: str = "./models/tts/cosyvoice"
    voice_sample_path: str = "./voice_samples"
    sample_rate: int = 22050


class STTConfig(BaseSettings):
    provider: str = "whisper"
    model: str = "medium"
    language: str = "auto"


class EmailConfig(BaseSettings):
    provider: str = "gmail"
    credentials_path: str = "./config/credentials.json"
    token_path: str = "./config/token.json"
    refresh_interval: int = 300


class CalendarConfig(BaseSettings):
    provider: str = "google_calendar"
    credentials_path: str = "./config/credentials.json"
    token_path: str = "./config/token.json"
    refresh_interval: int = 60


class WebSearchConfig(BaseSettings):
    provider: str = "searxng"
    base_url: str = "http://localhost:8080"


class OpenCodeConfig(BaseSettings):
    server_url: str = "http://localhost:4096"
    auto_start: bool = True
    timeout: int = 600
    allowed_paths: List[str] = ["./mobile_app", "./server"]


class CharacterConfig(BaseSettings):
    default_model_path: str = "./mobile_app/assets/models"
    animation_enabled: bool = True
    vrm_support: bool = True


class LanguageConfig(BaseSettings):
    supported: List[str] = ["zh-TW", "ja", "en"]
    default: str = "zh-TW"


class ServerConfig(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    llm: LLMConfig = LLMConfig()
    tts: TTSConfig = TTSConfig()
    stt: STTConfig = STTConfig()
    email: EmailConfig = EmailConfig()
    calendar: CalendarConfig = CalendarConfig()
    web_search: WebSearchConfig = WebSearchConfig()
    opencode: OpenCodeConfig = OpenCodeConfig()
    character: CharacterConfig = CharacterConfig()
    languages: LanguageConfig = LanguageConfig()


def load_config(config_path: str = "../config/server_config.yaml") -> ServerConfig:
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        server_data = data.pop("server", {})
        merged = {**server_data, **data}
        return ServerConfig(**merged)
    return ServerConfig()


config = load_config()
