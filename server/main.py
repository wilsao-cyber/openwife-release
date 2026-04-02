from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    UploadFile,
    File,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import logging
import time
from typing import Optional

from config import config, resolve_model, MODEL_PRESETS
from llm_client import LLMClient
from tts_engine import TTSEngine
from stt_engine import STTEngine
from agent import AgentOrchestrator
from websocket_manager import WebSocketManager
from vrm_manager import VrmManager
from vision_analyzer import VisionAnalyzer
from soul.soul_manager import SoulManager
from memory.memory_store import MemoryStore
from skills.registry import SkillRegistry
from heartbeat.scheduler import HeartbeatScheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

ws_manager = WebSocketManager()
llm_client: Optional[LLMClient] = None
tts_engine: Optional[TTSEngine] = None
stt_engine: Optional[STTEngine] = None
agent: Optional[AgentOrchestrator] = None
vrm_manager = VrmManager()
vision_analyzer = VisionAnalyzer()
heartbeat: Optional[HeartbeatScheduler] = None

# ── Startup Progress Tracker ─────────────────────────────────────────


class StartupProgress:
    """Track and display startup phase progress with timestamps."""

    def __init__(self):
        self.start_time = time.time()
        self.phases = []

    def begin(self, name: str):
        logger.info(f"  → {name}...")
        self.phases.append({"name": name, "start": time.time(), "status": "running"})

    def ok(self, detail: str = ""):
        if self.phases and self.phases[-1]["status"] == "running":
            elapsed = time.time() - self.phases[-1]["start"]
            self.phases[-1]["status"] = "OK"
            self.phases[-1]["elapsed"] = elapsed
            msg = f"  ✓ {self.phases[-1]['name']} OK ({elapsed:.1f}s)"
            if detail:
                msg += f" — {detail}"
            logger.info(msg)

    def fail(self, detail: str = ""):
        if self.phases and self.phases[-1]["status"] == "running":
            elapsed = time.time() - self.phases[-1]["start"]
            self.phases[-1]["status"] = "FAILED"
            self.phases[-1]["elapsed"] = elapsed
            msg = f"  ✗ {self.phases[-1]['name']} FAILED ({elapsed:.1f}s)"
            if detail:
                msg += f" — {detail}"
            logger.warning(msg)

    def skip(self, detail: str = ""):
        if self.phases and self.phases[-1]["status"] == "running":
            elapsed = time.time() - self.phases[-1]["start"]
            self.phases[-1]["status"] = "SKIPPED"
            self.phases[-1]["elapsed"] = elapsed
            msg = f"  ⊘ {self.phases[-1]['name']} SKIPPED ({elapsed:.1f}s)"
            if detail:
                msg += f" — {detail}"
            logger.info(msg)

    def summary(self):
        total = time.time() - self.start_time
        ok_count = sum(1 for p in self.phases if p["status"] == "OK")
        fail_count = sum(1 for p in self.phases if p["status"] == "FAILED")
        skip_count = sum(1 for p in self.phases if p["status"] == "SKIPPED")
        logger.info("=" * 60)
        logger.info(f"Startup complete in {total:.1f}s")
        logger.info(f"  {ok_count} OK, {fail_count} FAILED, {skip_count} SKIPPED")
        for p in self.phases:
            status_icon = {"OK": "✓", "FAILED": "✗", "SKIPPED": "⊘"}.get(
                p["status"], "?"
            )
            logger.info(f"  {status_icon} {p['name']:<25s} {p.get('elapsed', 0):.1f}s")
        logger.info("=" * 60)


progress = StartupProgress()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global llm_client, tts_engine, stt_engine, agent, heartbeat

    import os
    os.makedirs("./output/screenshots", exist_ok=True)
    os.makedirs("./output/media", exist_ok=True)

    logger.info("=" * 60)
    logger.info("AI Wife Server — Starting up")
    logger.info("=" * 60)

    # Phase 1: LLM Client
    progress.begin("LLM Client")
    llm_client = LLMClient(config.llm)
    actual_model = resolve_model(config.llm.model)
    progress.ok(f"{config.llm.provider} @ {config.llm.base_url} [{actual_model}]")

    # Phase 1b: Test LLM connectivity (skip if using local ollama — user will configure cloud provider via UI)
    if config.llm.provider != "ollama":
        progress.begin("LLM Test Reply")
        try:
            await asyncio.sleep(0.1)
            test_reply = await llm_client.chat(
                [{"role": "user", "content": "回覆OK"}],
                think=False,
            )
            progress.ok(f"reply: {test_reply[:50]}")
        except Exception as e:
            progress.skip(f"{str(e)[:60]}")
    else:
        progress.begin("LLM Test Reply")
        progress.skip("ollama — will configure via UI")

    # Phase 2: TTS Engine
    progress.begin("TTS Engine")
    tts_engine = TTSEngine(config.tts, llm_client=llm_client)
    try:
        await tts_engine.initialize()
        progress.ok(f"{config.tts.provider}")
    except Exception as e:
        progress.fail(str(e))

    # Phase 3: STT Engine
    progress.begin("STT Engine")
    stt_engine = STTEngine(config.stt)
    try:
        await stt_engine.initialize()
        progress.ok(f"{config.stt.provider}")
    except Exception as e:
        progress.fail(str(e))

    # Phase 4: Soul System
    progress.begin("Soul System")
    soul_dir = str(config.soul.soul_path).rsplit("/", 1)[0]
    soul_manager = SoulManager(soul_dir=soul_dir)
    soul_text = soul_manager.load_soul()
    progress.ok(f"SOUL.md loaded ({len(soul_text)} chars)")

    # Phase 5: Memory System
    progress.begin("Memory System")
    memory_store = MemoryStore(
        db_path=config.memory.db_path,
        use_embeddings=config.memory.use_embeddings,
    )
    try:
        await memory_store.initialize()
        count = await memory_store.count()
        progress.ok(f"{count} memories in DB")
    except Exception as e:
        progress.fail(str(e))

    # Phase 6: Skill System
    progress.begin("Skill System")
    skill_registry = SkillRegistry()
    skill_registry.discover("skills/builtin")
    try:
        await skill_registry.initialize_all()
        tools = skill_registry.get_tool_definitions()
        progress.ok(f"{len(tools)} tools registered")
    except Exception as e:
        progress.fail(str(e))

    # Phase 7: Agent Orchestration
    progress.begin("Agent Orchestration")
    agent = AgentOrchestrator(
        llm_client=llm_client,
        config=config,
        skill_registry=skill_registry,
        soul_manager=soul_manager,
        memory_store=memory_store,
    )
    progress.ok("wired")

    # Phase 8: Heartbeat
    if config.heartbeat.enabled:
        progress.begin("Heartbeat Scheduler")
        try:
            heartbeat = HeartbeatScheduler(md_path=config.heartbeat.config_path)
            heartbeat.set_agent(agent)
            heartbeat.start()
            progress.ok("running")
        except Exception as e:
            progress.fail(str(e))
    else:
        progress.begin("Heartbeat Scheduler")
        progress.skip("disabled in config")

    progress.summary()
    logger.info(f"Server running on {config.host}:{config.port}")

    yield

    if heartbeat:
        heartbeat.stop()
    logger.info("Shutting down AI Wife Server...")


app = FastAPI(title="AI Wife Server", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://localhost:3000",
        "http://127.0.0.1:8000",
        "http://10.0.2.2:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- WebSocket ---


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await ws_manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_json()
            response = await handle_message(data, client_id)
            await ws_manager.send_json(client_id, response)
    except WebSocketDisconnect:
        ws_manager.disconnect(client_id)


async def handle_message(data: dict, client_id: str) -> dict:
    msg_type = data.get("type")

    if msg_type == "chat":
        return await handle_chat(data, client_id)
    elif msg_type == "voice_input":
        return await handle_voice_input(data, client_id)
    elif msg_type == "confirm":
        return {
            "type": "confirm_started",
            "message": "Use SSE endpoint for streaming confirmation",
        }
    elif msg_type == "deny":
        language = data.get("language", config.languages.default)
        result = await agent.deny_plan(client_id, language)
        return {"type": "denied", **result}
    else:
        return {"type": "error", "message": f"Unknown message type: {msg_type}"}


async def handle_chat(data: dict, client_id: str) -> dict:
    message = data.get("message", "")
    language = data.get("language", config.languages.default)

    response = await agent.chat(message, language, client_id)

    audio_path, visemes = await tts_engine.synthesize(response["text"], language)

    return {
        "type": "chat_response",
        "text": response["text"],
        "emotion": response.get("emotion", "neutral"),
        "mode": response.get("mode", "chat"),
        "audio_url": f"/audio/{audio_path}",
        "visemes": visemes,
        "awaiting_confirmation": response.get("awaiting_confirmation", False),
        "tool_calls": response.get("tool_calls", []),
    }


async def handle_voice_input(data: dict, client_id: str) -> dict:
    audio_file = data.get("audio_data")
    language = data.get("language", "auto")

    text = await stt_engine.transcribe(audio_file, language)

    response = await agent.chat(text, language, client_id)
    audio_path, visemes = await tts_engine.synthesize(response["text"], language)

    return {
        "type": "voice_response",
        "transcript": text,
        "response_text": response["text"],
        "audio_url": f"/audio/{audio_path}",
    }


# --- Chat API (REST) ---


@app.post("/api/chat")
async def api_chat(data: dict):
    message = data.get("message", "")
    language = data.get("language", config.languages.default)
    client_id = data.get("client_id", "default")
    response = await agent.chat(message, language, client_id)
    return response


@app.post("/api/chat/stream")
async def api_chat_stream(data: dict):
    message = data.get("message", "")
    language = data.get("language", config.languages.default)
    client_id = data.get("client_id", "default")
    mode_override = data.get("mode_override")

    async def event_generator():
        async for chunk_json in agent.chat_stream(
            message, language, client_id, mode_override=mode_override
        ):
            yield f"data: {chunk_json}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- Confirmation Flow ---


@app.post("/api/chat/confirm/{client_id}")
async def confirm_plan(client_id: str):
    async def event_generator():
        async for chunk_json in agent.confirm_plan(client_id):
            yield f"data: {chunk_json}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/chat/deny/{client_id}")
async def deny_plan(client_id: str, data: dict = {}):
    language = data.get("language", config.languages.default)
    return await agent.deny_plan(client_id, language)


# --- Memory Management ---


@app.get("/api/memory/list")
async def list_memories(limit: int = 50):
    memories = await agent.memory.list_all(limit=limit)
    return {"memories": memories}


@app.delete("/api/memory/{memory_id}")
async def delete_memory(memory_id: int):
    await agent.memory.delete(memory_id)
    return {"success": True}


# --- Soul/Personality ---


@app.get("/api/soul")
async def get_soul():
    return {
        "soul": agent.soul.load_soul(),
        "profile": agent.soul.load_profile(),
    }


@app.put("/api/soul")
async def update_soul(data: dict):
    if "soul" in data:
        agent.soul.update_soul(data["soul"])
    if "profile" in data:
        agent.soul.update_profile(data["profile"])
    return {"success": True}


# --- TTS / STT ---


@app.post("/api/stt")
async def api_stt(audio: UploadFile = File(...)):
    audio_data = await audio.read()
    text = await stt_engine.transcribe(audio_data)
    return {"text": text}


@app.post("/api/tts")
async def api_tts(data: dict):
    text = data.get("text", "")
    language = data.get("language", config.languages.default)
    emotion = data.get("emotion", "neutral")
    audio_path, _, ja_text = await tts_engine.synthesize(text, language, emotion)
    return {
        "audio_url": f"/audio/{audio_path}",
        "ja_text": ja_text,
    }


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    return FileResponse(f"./output/audio/{filename}")


@app.get("/models/{filename}")
async def get_model(filename: str):
    return FileResponse(f"./output/models/{filename}")


# --- Static / Web UI ---


@app.get("/")
async def web_index():
    return FileResponse(
        "static/index.html",
        media_type="text/html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Health ---


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "version": "2.0.0",
        "services": {
            "llm": llm_client is not None,
            "tts": tts_engine is not None,
            "stt": stt_engine is not None,
            "agent": agent is not None,
        },
    }


@app.get("/api/health/test")
async def health_test():
    """Run connectivity tests for all components."""
    results = {}

    # Test LLM
    try:
        logger.info(f"Health test LLM: provider={llm_client.provider}, model={llm_client.model}, has_key={bool(llm_client.api_key)}")
        t0 = time.time()
        reply = await llm_client.chat(
            [{"role": "user", "content": "回覆OK"}],
            think=False,
            max_tokens=10,
        )
        latency = int((time.time() - t0) * 1000)
        results["llm"] = {
            "ok": True,
            "model": llm_client.model,
            "provider": llm_client.provider,
            "latency_ms": latency,
            "reply": str(reply)[:30],
        }
    except Exception as e:
        results["llm"] = {"ok": False, "error": str(e)[:100]}

    # Test TTS (just check connectivity, don't do full synthesis)
    try:
        import httpx as _hx
        async with _hx.AsyncClient(timeout=5.0) as _tc:
            _tr = await _tc.get(f"{config.tts.voicebox_api_url}/profiles")
            if _tr.status_code == 200:
                results["tts"] = {"ok": True, "provider": config.tts.provider}
            else:
                results["tts"] = {"ok": False, "error": f"Voicebox returned {_tr.status_code}"}
    except Exception as e:
        results["tts"] = {"ok": False, "error": str(e)[:100]}

    # Test STT
    try:
        results["stt"] = {"ok": True, "provider": config.stt.provider}
    except Exception as e:
        results["stt"] = {"ok": False, "error": str(e)[:100]}

    # Test Skills
    try:
        tools = agent.skills.get_tool_definitions()
        results["skills"] = {"ok": True, "tool_count": len(tools)}
    except Exception as e:
        results["skills"] = {"ok": False, "error": str(e)[:100]}

    return results


@app.post("/api/config/model")
async def switch_model(data: dict):
    preset = data.get("model", "")
    actual = resolve_model(preset)
    try:
        await llm_client.switch_model(actual)
        config.llm.model = actual
        return {"success": True, "model": actual, "preset": preset}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/config/models")
async def list_models():
    labels = {
        "smart7": "Qwen 2.5 7B（快速）",
        "smart9": "Qwen 3.5 9B（平衡）",
        "ultra": "Qwen 3.5 27B（高品質）",
    }
    models = [
        {"preset": k, "actual": v, "label": labels.get(k, k)}
        for k, v in MODEL_PRESETS.items()
        if k in ("smart7", "smart9", "ultra")
    ]
    return {"models": models, "current": config.llm.model}


@app.get("/api/config/provider-models")
async def list_provider_models(provider: str = "", base_url: str = "", api_key: str = ""):
    """Fetch available models from a cloud provider."""
    import httpx

    try:
        if provider == "ollama":
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{base_url or 'http://localhost:9090'}/api/tags")
                if r.status_code == 200:
                    data = r.json()
                    return {"models": [
                        {"id": m["name"], "name": m["name"], "context": m.get("details", {}).get("parameter_size", "")}
                        for m in data.get("models", [])
                    ]}
            return {"models": [], "error": "Ollama not running"}

        elif provider == "openrouter":
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get("https://openrouter.ai/api/v1/models")
                if r.status_code == 200:
                    data = r.json()
                    models = []
                    for m in data.get("data", []):
                        mid = m.get("id", "")
                        pricing = m.get("pricing", {})
                        prompt_price = pricing.get("prompt", "0")
                        is_free = ":free" in mid or prompt_price == "0"
                        models.append({
                            "id": mid,
                            "name": m.get("name", mid),
                            "context": m.get("context_length", 0),
                            "free": is_free,
                        })
                    # Sort: free first, then by name
                    models.sort(key=lambda x: (not x["free"], x["name"]))
                    return {"models": models}
            return {"models": [], "error": "Failed to fetch"}

        elif provider == "dashscope":
            # DashScope doesn't have a model list API, return known models
            return {"models": [
                {"id": "qwen3-235b-a22b", "name": "Qwen3 235B MoE", "context": 131072, "free": False},
                {"id": "qwen3-32b", "name": "Qwen3 32B", "context": 131072, "free": False},
                {"id": "qwen3-8b", "name": "Qwen3 8B", "context": 131072, "free": False},
                {"id": "qwen-plus", "name": "Qwen Plus", "context": 131072, "free": False},
                {"id": "qwen-turbo", "name": "Qwen Turbo", "context": 131072, "free": False},
                {"id": "qwen-max", "name": "Qwen Max", "context": 32768, "free": False},
                {"id": "qwen2.5-72b-instruct", "name": "Qwen2.5 72B", "context": 131072, "free": False},
                {"id": "qwen2.5-32b-instruct", "name": "Qwen2.5 32B", "context": 131072, "free": False},
            ]}

        elif provider == "openai":
            if not api_key:
                return {"models": [
                    {"id": "gpt-4o", "name": "GPT-4o", "context": 128000, "free": False},
                    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context": 128000, "free": False},
                    {"id": "gpt-4.1", "name": "GPT-4.1", "context": 1047576, "free": False},
                    {"id": "gpt-4.1-mini", "name": "GPT-4.1 Mini", "context": 1047576, "free": False},
                    {"id": "gpt-4.1-nano", "name": "GPT-4.1 Nano", "context": 1047576, "free": False},
                ]}
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.get(
                    "https://api.openai.com/v1/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                if r.status_code == 200:
                    data = r.json()
                    return {"models": [
                        {"id": m["id"], "name": m["id"], "context": 0, "free": False}
                        for m in data.get("data", [])
                        if "gpt" in m["id"] or "o1" in m["id"] or "o3" in m["id"]
                    ]}
            return {"models": [], "error": "Failed to fetch"}

        return {"models": []}
    except Exception as e:
        return {"models": [], "error": str(e)[:100]}


@app.get("/api/config/provider")
async def get_provider():
    return {
        "provider": config.llm.provider,
        "base_url": config.llm.base_url,
        "model": config.llm.model,
        "has_api_key": bool(config.llm.api_key),
        "fallback_provider": config.llm.fallback_provider,
        "fallback_base_url": config.llm.fallback_base_url,
        "fallback_model": config.llm.fallback_model,
        "has_fallback_key": bool(config.llm.fallback_api_key),
    }


@app.post("/api/config/provider")
async def set_provider(data: dict):
    provider = data.get("provider", "").strip()
    base_url = data.get("base_url", "").strip()
    api_key = data.get("api_key", "").strip()
    model = data.get("model", "").strip()

    if not provider or not base_url or not model:
        return {"success": False, "error": "provider, base_url, model are required"}

    if provider != "ollama" and not api_key:
        return {"success": False, "error": "api_key is required for non-ollama providers"}

    logger.info(f"set_provider: provider={provider}, base_url={base_url}, model={model}, api_key={'***' + api_key[-4:] if api_key else 'empty'}")

    try:
        llm_client.update_provider(provider, base_url, api_key, model)
        config.llm.provider = provider
        config.llm.base_url = base_url
        config.llm.api_key = api_key
        config.llm.model = model
        # Fallback (optional)
        fb_provider = data.get("fallback_provider", "").strip()
        fb_base_url = data.get("fallback_base_url", "").strip()
        fb_api_key = data.get("fallback_api_key", "").strip()
        fb_model = data.get("fallback_model", "").strip()
        if fb_provider and fb_api_key:
            llm_client.update_fallback(fb_provider, fb_base_url, fb_api_key, fb_model)
            config.llm.fallback_provider = fb_provider
            config.llm.fallback_base_url = fb_base_url
            config.llm.fallback_api_key = fb_api_key
            config.llm.fallback_model = fb_model

        return {
            "success": True,
            "provider": provider,
            "model": model,
            "has_fallback": llm_client.has_fallback,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/media/{filename}")
async def get_media(filename: str):
    import os
    for directory in ["./output/screenshots", "./output/audio", "./output/media"]:
        path = os.path.join(directory, filename)
        if os.path.exists(path):
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="File not found")


@app.get("/api/health")
async def api_health():
    """Detailed health check for startup screen."""
    components = {}
    components["llm"] = {
        "status": "ok" if llm_client else "unavailable",
        "model": llm_client.model if llm_client else None,
        "base_url": config.llm.base_url,
    }
    components["tts"] = {
        "status": "ok" if tts_engine else "unavailable",
        "provider": config.tts.provider,
    }
    components["stt"] = {
        "status": "ok" if stt_engine else "unavailable",
        "provider": config.stt.provider,
    }
    components["email"] = {
        "status": "ok" if agent and agent.skills else "unavailable",
    }
    components["calendar"] = {
        "status": "ok" if agent and agent.skills else "unavailable",
    }
    if agent and agent.memory:
        try:
            count = await agent.memory.count()
            components["memory"] = {"status": "ok", "count": count}
        except Exception:
            components["memory"] = {"status": "error"}
    else:
        components["memory"] = {"status": "unavailable"}
    if agent and agent.skills:
        tools = agent.skills.get_tool_definitions()
        components["skills"] = {"status": "ok", "tool_count": len(tools)}
    else:
        components["skills"] = {"status": "unavailable"}
    return {"status": "ready", "components": components}


@app.post("/api/health/test")
async def api_health_test():
    """Run connectivity tests for startup screen."""
    results = {}
    # LLM test
    if llm_client:
        try:
            t0 = time.time()
            reply = await llm_client.chat(
                [{"role": "user", "content": "回覆OK"}], think=False
            )
            latency = int((time.time() - t0) * 1000)
            results["llm"] = {
                "ok": True,
                "reply": str(reply)[:50],
                "latency_ms": latency,
            }
        except Exception as e:
            results["llm"] = {"ok": False, "error": str(e)[:100]}
    else:
        results["llm"] = {"ok": False, "error": "not initialized"}
    # TTS test (connectivity check only, no full synthesis)
    try:
        import httpx as _hx2
        async with _hx2.AsyncClient(timeout=5.0) as _tc2:
            _tr2 = await _tc2.get(f"{config.tts.voicebox_api_url}/profiles")
            results["tts"] = {"ok": _tr2.status_code == 200, "provider": config.tts.provider}
    except Exception as e:
        results["tts"] = {"ok": False, "error": str(e)[:100]}
    # STT test
    results["stt"] = {"ok": stt_engine is not None}
    return results


# --- Legacy tool endpoints (kept for backward compat) ---


@app.post("/api/email/{action}")
async def api_email(action: str, data: dict = {}):
    try:
        result = await agent.skills.execute(f"email_{action}", data)
        return result
    except Exception as e:
        return {"error": str(e), "emails": []}


@app.post("/api/calendar/{action}")
async def api_calendar(action: str, data: dict = {}):
    try:
        result = await agent.skills.execute(f"calendar_{action}", data)
        return result
    except Exception as e:
        return {"error": str(e), "events": []}


# --- Heartbeat ---


@app.get("/api/heartbeat/jobs")
async def list_heartbeat_jobs():
    if not heartbeat:
        return []
    return heartbeat.list_jobs()


@app.post("/api/heartbeat/jobs")
async def add_or_update_heartbeat_job(data: dict):
    if not heartbeat:
        raise HTTPException(status_code=503, detail="Heartbeat not enabled")
    heartbeat.add_job(data)
    return {"success": True}


@app.delete("/api/heartbeat/jobs/{job_id}")
async def remove_heartbeat_job(job_id: str):
    if not heartbeat:
        raise HTTPException(status_code=503, detail="Heartbeat not enabled")
    heartbeat.remove_job(job_id)
    return {"success": True}


# --- VRM ---


@app.post("/api/vrm/upload")
async def upload_vrm(file: UploadFile = File(...)):
    data = await file.read()
    try:
        filename = vrm_manager.save(data, file.filename)
        return {"filename": filename, "size": len(data)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/vrm/list")
async def list_vrm():
    return {"models": vrm_manager.list_models()}


@app.get("/vrm/{filename}")
async def get_vrm(filename: str):
    try:
        path = vrm_manager.get_path(filename)
        return FileResponse(path, media_type="model/gltf-binary")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="VRM not found")


@app.delete("/api/vrm/{filename}")
async def delete_vrm(filename: str):
    try:
        vrm_manager.delete(filename)
        return {"success": True}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="VRM not found")


# --- Vision ---


@app.post("/api/vision/capture")
async def vision_capture(image: UploadFile = File(...), language: str = "zh-TW"):
    image_data = await image.read()
    result = await vision_analyzer.analyze_single(image_data, language)
    if result.get("text"):
        audio_path, visemes = await tts_engine.synthesize(result["text"], language)
        result["audio_url"] = f"/audio/{audio_path}"
        result["visemes"] = visemes
    return result


@app.post("/api/vision/stream")
async def vision_stream(
    image: UploadFile = File(...),
    previous_hash: str = "",
    language: str = "zh-TW",
    context: str = "",
):
    image_data = await image.read()
    previous_bytes = None
    result = await vision_analyzer.analyze_stream(
        image_data, previous_bytes, language, context
    )
    if result is None:
        return {"changed": False}
    if result.get("text"):
        audio_path, visemes = await tts_engine.synthesize(result["text"], language)
        result["audio_url"] = f"/audio/{audio_path}"
        result["visemes"] = visemes
    result["changed"] = True
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
    )
