import os
import sys
import yaml
from pydantic_settings import BaseSettings
from typing import List, Optional


# Available model presets
MODEL_PRESETS = {
    "smart7": "qwen2.5:7b",
    "smart9": "qwen3.5:9b",
    "ultra": "qwen3.5:27b",
    "ultra-long": "qwen3.5-27b-dev:latest",
    "moe": "qwen3.5:35b-a3b-q4_k_m",
    "no-think": "qwen-no-think",
}


def resolve_model(value: str) -> str:
    """Resolve model name from preset or direct name."""
    return MODEL_PRESETS.get(value, value)


class LLMConfig(BaseSettings):
    provider: str = "dashscope"
    base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode"
    model: str = "qwen3-235b-a22b"
    temperature: float = 0.7
    max_tokens: int = 2048
    deep_thinking_tokens: int = 8192  # unlocked limit for complex tasks
    api_key: str = ""
    fallback_provider: str = ""
    fallback_base_url: str = ""
    fallback_api_key: str = ""
    fallback_model: str = ""

    def __init__(self, **data):
        super().__init__(**data)
        if self.provider == "ollama":
            self.model = resolve_model(self.model)


class TTSConfig(BaseSettings):
    provider: str = "voicebox"
    model_path: str = "./models/tts/cosyvoice"
    voice_sample_path: str = "./voice_samples"
    sample_rate: int = 22050
    voicebox_api_url: str = "http://localhost:17493"
    voicebox_profile_id: str = ""
    voicebox_horny_profile_id: str = ""
    voicebox_model_size: str = "1.7B"
    voicebox_concurrency: int = 2
    audio_fx_enabled: bool = True


class STTConfig(BaseSettings):
    provider: str = "sensevoice"
    model: str = "iic/SenseVoiceSmall"
    language: str = "auto"


class EmailConfig(BaseSettings):
    provider: str = "gmail"
    credentials_path: str = "../config/credentials.json"
    token_path: str = "../config/gmail_token.json"
    refresh_interval: int = 300


class CalendarConfig(BaseSettings):
    provider: str = "google_calendar"
    credentials_path: str = "../config/credentials.json"
    token_path: str = "../config/calendar_token.json"
    refresh_interval: int = 60
    timezone: str = "Asia/Taipei"


class WebSearchConfig(BaseSettings):
    provider: str = "searxng"
    base_url: str = "http://localhost:8080"
    brave_api_key: str = ""


class OpenCodeConfig(BaseSettings):
    server_url: str = "http://localhost:4096"
    auto_start: bool = True
    timeout: int = 600
    allowed_paths: List[str] = ["./server"]


class CharacterConfig(BaseSettings):
    default_model_path: str = "./server/static/models"
    animation_enabled: bool = True
    vrm_support: bool = True


class LanguageConfig(BaseSettings):
    supported: List[str] = ["zh-TW", "ja", "en"]
    default: str = "zh-TW"


class VisionConfig(BaseSettings):
    model: str = "llava"
    change_threshold: float = 0.3

    class Config:
        env_prefix = "VISION_"


class SoulConfig(BaseSettings):
    soul_path: str = "./server/soul/SOUL.md"
    profile_path: str = "./server/soul/PROFILE.md"


class MemoryConfig(BaseSettings):
    db_path: str = "./server/memory/memories.db"
    embedding_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    max_memories: int = 1000
    search_limit: int = 3
    use_embeddings: bool = True


class HeartbeatConfig(BaseSettings):
    enabled: bool = True
    config_path: str = "./server/heartbeat/HEARTBEAT.md"


class MCPConfig(BaseSettings):
    servers: List[dict] = []


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
    vision: VisionConfig = VisionConfig()
    soul: SoulConfig = SoulConfig()
    memory: MemoryConfig = MemoryConfig()
    heartbeat: HeartbeatConfig = HeartbeatConfig()
    mcp: MCPConfig = MCPConfig()


def load_config(config_path: str = "../config/server_config.yaml") -> ServerConfig:
    # Allow model override via CLI: python main.py --model ultra
    cli_model = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--model" and i + 1 < len(args):
            cli_model = args[i + 1]
        elif arg.startswith("--model="):
            cli_model = arg.split("=", 1)[1]

    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        server_data = data.pop("server", {})
        merged = {**server_data, **data}
        if cli_model:
            merged.setdefault("llm", {})["model"] = cli_model
        return ServerConfig(**merged)

    if cli_model:
        return ServerConfig(llm=LLMConfig(model=cli_model))
    return ServerConfig()


config = load_config()
