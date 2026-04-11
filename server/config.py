import os
import platform
import sys
from pathlib import Path
import yaml
from pydantic_settings import BaseSettings
from typing import List, Optional

IS_WINDOWS = platform.system() == "Windows"

# ── Project root resolution ──────────────────────────────────────────
# PROJECT_ROOT = the top-level openwife/ directory (parent of server/)
# All relative paths in config are resolved against this.
_this_dir = Path(__file__).resolve().parent          # …/server/
PROJECT_ROOT = _this_dir.parent                      # …/openwife/
CONFIG_DIR   = PROJECT_ROOT / "config"
SERVER_DIR   = PROJECT_ROOT / "server"


def _resolve(rel: str) -> str:
    """Resolve a config path relative to PROJECT_ROOT.
    Absolute paths are returned as-is."""
    p = Path(rel)
    if p.is_absolute():
        return str(p)
    return str((PROJECT_ROOT / p).resolve())


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
    voicebox_path: str = ""  # Path to voicebox installation (auto-detected if empty)
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


def _default_config_path() -> str:
    return str(CONFIG_DIR / "server_config.yaml")


def load_config(config_path: str = "") -> ServerConfig:
    if not config_path:
        config_path = _default_config_path()

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


def save_config(cfg: ServerConfig, config_path: str = ""):
    """Persist current ServerConfig back to YAML."""
    if not config_path:
        config_path = _default_config_path()
    data = {
        "server": {"host": cfg.host, "port": cfg.port, "debug": cfg.debug},
        "llm": {
            "provider": cfg.llm.provider, "base_url": cfg.llm.base_url,
            "model": cfg.llm.model, "temperature": cfg.llm.temperature,
            "max_tokens": cfg.llm.max_tokens, "deep_thinking_tokens": cfg.llm.deep_thinking_tokens,
            "api_key": cfg.llm.api_key,
            "fallback_provider": cfg.llm.fallback_provider,
            "fallback_base_url": cfg.llm.fallback_base_url,
            "fallback_api_key": cfg.llm.fallback_api_key,
            "fallback_model": cfg.llm.fallback_model,
        },
        "tts": {
            "provider": cfg.tts.provider, "voicebox_api_url": cfg.tts.voicebox_api_url,
            "voicebox_path": cfg.tts.voicebox_path,
            "voicebox_profile_id": cfg.tts.voicebox_profile_id,
            "voicebox_horny_profile_id": cfg.tts.voicebox_horny_profile_id,
            "voicebox_model_size": cfg.tts.voicebox_model_size,
            "voicebox_concurrency": cfg.tts.voicebox_concurrency,
            "audio_fx_enabled": cfg.tts.audio_fx_enabled,
            "model_path": cfg.tts.model_path,
            "voice_sample_path": cfg.tts.voice_sample_path,
            "sample_rate": cfg.tts.sample_rate,
        },
        "stt": {
            "provider": cfg.stt.provider, "model": cfg.stt.model,
            "language": cfg.stt.language,
        },
        "email": {
            "provider": cfg.email.provider,
            "credentials_path": cfg.email.credentials_path,
            "token_path": cfg.email.token_path,
            "refresh_interval": cfg.email.refresh_interval,
        },
        "calendar": {
            "provider": cfg.calendar.provider,
            "credentials_path": cfg.calendar.credentials_path,
            "token_path": cfg.calendar.token_path,
            "refresh_interval": cfg.calendar.refresh_interval,
            "timezone": cfg.calendar.timezone,
        },
        "web_search": {
            "provider": cfg.web_search.provider,
            "base_url": cfg.web_search.base_url,
            "brave_api_key": cfg.web_search.brave_api_key,
        },
        "character": {
            "default_model_path": cfg.character.default_model_path,
            "animation_enabled": cfg.character.animation_enabled,
            "vrm_support": cfg.character.vrm_support,
        },
        "languages": {
            "supported": cfg.languages.supported,
            "default": cfg.languages.default,
        },
        "soul": {
            "soul_path": cfg.soul.soul_path,
            "profile_path": cfg.soul.profile_path,
        },
        "memory": {
            "db_path": cfg.memory.db_path,
            "embedding_model": cfg.memory.embedding_model,
            "max_memories": cfg.memory.max_memories,
            "search_limit": cfg.memory.search_limit,
            "use_embeddings": cfg.memory.use_embeddings,
        },
        "heartbeat": {
            "enabled": cfg.heartbeat.enabled,
            "config_path": cfg.heartbeat.config_path,
        },
        "mcp": {"servers": cfg.mcp.servers},
    }
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)


config = load_config()
