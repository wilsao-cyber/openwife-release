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
import json
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

    # Phase 6: SFX Catalog
    progress.begin("SFX Catalog")
    try:
        from sfx_catalog import sfx_catalog
        sfx_catalog.build()
        progress.ok(f"{len(sfx_catalog.entries)} sound effects indexed")
    except Exception as e:
        progress.fail(str(e))

    # Phase 7: Skill System
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
    emotion = response.get("emotion", "neutral")
    audio_path, visemes = await tts_engine.synthesize(response["text"], language, emotion)

    return {
        "type": "chat_response",
        "text": response["text"],
        "emotion": emotion,
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
    emotion = response.get("emotion", "neutral")
    audio_path, visemes = await tts_engine.synthesize(response["text"], language, emotion)

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
    use_fallback = data.get("use_fallback", False)

    async def event_generator():
        async for chunk_json in agent.chat_stream(
            message, language, client_id, mode_override=mode_override,
            use_fallback=use_fallback,
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
    mix_sfx = data.get("mix_sfx", False)
    audio_path, _, ja_text = await tts_engine.synthesize(text, language, emotion)

    # In batch mode, auto-mix SFX based on emotion
    if mix_sfx and emotion in ("horny",):
        try:
            from sfx_catalog import sfx_catalog
            from scene_mixer import _load_wav_as_float, _mix_into, _fade_in, _fade_out, SAMPLE_RATE
            import numpy as np
            import wave
            from pathlib import Path

            # Map emotion to SFX query
            emotion_sfx = {
                "horny": ("エッチな生活音", 0.15),
            }
            query, vol = emotion_sfx.get(emotion, (None, 0))
            if query:
                results = sfx_catalog.search(query=query, limit=1)
                if results:
                    speech = _load_wav_as_float(f"./output/audio/{audio_path}")
                    sfx = _load_wav_as_float(results[0].path)
                    if speech is not None and sfx is not None:
                        # Loop SFX to match speech length
                        if len(sfx) > 0:
                            repeats = (len(speech) // len(sfx)) + 1
                            sfx_looped = np.tile(sfx, repeats)[:len(speech)]
                            sfx_looped = _fade_in(sfx_looped, 1.0)
                            sfx_looped = _fade_out(sfx_looped, 0.5)
                            mixed = speech + sfx_looped * vol
                            peak = np.max(np.abs(mixed))
                            if peak > 0.95:
                                mixed = mixed * (0.95 / peak)
                            out_path = Path(f"./output/audio/{audio_path}")
                            out_int16 = np.clip(mixed * 32768, -32768, 32767).astype(np.int16)
                            with wave.open(str(out_path), 'wb') as wf:
                                wf.setnchannels(1)
                                wf.setsampwidth(2)
                                wf.setframerate(SAMPLE_RATE)
                                wf.writeframes(out_int16.tobytes())
                            logger.info(f"SFX mixed into TTS: {query} @ {vol}")
        except Exception as e:
            logger.warning(f"SFX auto-mix failed: {e}")

    return {
        "audio_url": f"/audio/{audio_path}",
        "ja_text": ja_text,
    }


@app.post("/api/tts/stream")
async def tts_stream(data: dict):
    """SSE streaming TTS — yields per-sentence audio URLs as they are generated."""
    text = data.get("text", "")
    language = data.get("language", config.languages.default)
    emotion = data.get("emotion", "neutral")

    async def event_gen():
        try:
            async for event in tts_engine.synthesize_stream(text, language, emotion):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error(f"TTS SSE error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# --- Voice Profile Management ---


@app.get("/api/voice/profiles")
async def voice_profiles():
    """List all Voicebox profiles with active status."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{config.tts.voicebox_api_url}/profiles")
            resp.raise_for_status()
            profiles = resp.json()
    except Exception as e:
        return {"profiles": [], "error": str(e)}

    return {
        "profiles": profiles,
        "active_normal": config.tts.voicebox_profile_id,
        "active_horny": config.tts.voicebox_horny_profile_id,
    }


@app.post("/api/voice/switch")
async def voice_switch(data: dict):
    """Switch active voice profile."""
    profile_id = data.get("profile_id", "")
    mode = data.get("mode", "normal")
    if mode == "normal":
        config.tts.voicebox_profile_id = profile_id
    else:
        config.tts.voicebox_horny_profile_id = profile_id
    return {"ok": True, "mode": mode, "profile_id": profile_id}


@app.post("/api/voice/test")
async def voice_test(data: dict):
    """Test generate with a profile."""
    import httpx

    profile_id = data.get("profile_id", "")
    text = data.get("text", "こんにちは、今日もいい天気だね。")
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{config.tts.voicebox_api_url}/generate",
                json={
                    "profile_id": profile_id,
                    "text": text,
                    "language": "ja",
                    "instruct": "甘えた可愛い女の子の声で、愛情と温もりを込めて、ゆっくり話してください",
                },
            )
            resp.raise_for_status()
            gen = resp.json()
    except Exception as e:
        return {"error": str(e)}

    # Copy generated audio to our output dir for serving
    from pathlib import Path
    import shutil

    src = Path(gen.get("audio_path", ""))
    if not src.is_absolute():
        src = Path(config.tts.voicebox_api_url.replace("http://localhost:17493", "/home/wilsao6666/voicebox")) / src
    if src.exists():
        dst = Path("./output/audio") / src.name
        shutil.copy2(str(src), str(dst))
        return {"audio_url": f"/audio/{src.name}", "duration": gen.get("duration", 0)}
    return {"error": "Audio file not found"}


# --- TTS Service Management ---


@app.get("/api/tts/status")
async def tts_status():
    """Check Voicebox TTS service status."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{config.tts.voicebox_api_url}/profiles")
            if resp.status_code == 200:
                return {"status": "running", "profiles": len(resp.json())}
    except Exception:
        pass
    return {"status": "stopped"}


@app.post("/api/tts/kill")
async def tts_kill():
    """Force kill Voicebox TTS process."""
    import subprocess
    try:
        result = subprocess.run(
            ["pkill", "-9", "-f", "backend.main --port 17493"],
            capture_output=True, text=True
        )
        logger.info("Voicebox TTS killed")
        return {"ok": True, "message": "Voicebox TTS stopped"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/tts/restart")
async def tts_restart():
    """Restart Voicebox TTS service."""
    import subprocess
    # Kill existing
    subprocess.run(["pkill", "-9", "-f", "backend.main --port 17493"],
                   capture_output=True)
    await asyncio.sleep(1)

    # Restart
    try:
        proc = subprocess.Popen(
            ["bash", "-c",
             "cd /home/wilsao6666/voicebox && source backend/venv/bin/activate && "
             "python -m backend.main --port 17493"],
            stdout=open("../logs/voicebox.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        logger.info(f"Voicebox TTS restarted (PID: {proc.pid})")
        # Wait for it to come up
        import httpx
        for _ in range(30):
            await asyncio.sleep(1)
            try:
                async with httpx.AsyncClient(timeout=3) as client:
                    resp = await client.get(f"{config.tts.voicebox_api_url}/profiles")
                    if resp.status_code == 200:
                        return {"ok": True, "message": f"Voicebox TTS running (PID: {proc.pid})"}
            except Exception:
                continue
        return {"ok": False, "message": "Voicebox started but not responding after 30s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/sfx/upload")
async def sfx_upload(
    files: list[UploadFile] = File(...),
    category: str = "custom",
):
    """Upload SFX audio files to the library."""
    from sfx_catalog import sfx_catalog, SFX_ROOT
    from pathlib import Path
    import shutil

    target_dir = SFX_ROOT / "custom" / category
    target_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    for f in files:
        if not f.filename:
            continue
        dst = target_dir / f.filename
        content = await f.read()
        with open(dst, "wb") as out:
            out.write(content)
        uploaded.append(f.filename)

    # Rebuild catalog to include new files
    sfx_catalog.build()
    return {"uploaded": uploaded, "total": len(sfx_catalog.entries)}


@app.get("/api/sfx/{sfx_id}")
async def get_sfx(sfx_id: str):
    """Serve SFX audio file by catalog ID."""
    from sfx_catalog import sfx_catalog
    entry = sfx_catalog.entries.get(sfx_id)
    if not entry:
        raise HTTPException(status_code=404, detail="SFX not found")
    return FileResponse(entry.path)


@app.get("/api/sfx")
async def list_sfx(category: str = "", q: str = ""):
    """Search/browse SFX catalog."""
    from sfx_catalog import sfx_catalog
    if not category and not q:
        return {"categories": sfx_catalog.get_categories()}
    results = sfx_catalog.search(query=q, category=category, limit=20)
    return {"results": [{"id": e.id, "description": e.description, "category": e.category} for e in results]}


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
            # DashScope doesn't have a public model list API
            return {"models": [
                # Qwen3
                {"id": "qwen3-235b-a22b", "name": "Qwen3 235B MoE", "context": 131072, "free": False},
                {"id": "qwen3-32b", "name": "Qwen3 32B", "context": 131072, "free": False},
                {"id": "qwen3-30b-a3b", "name": "Qwen3 30B MoE", "context": 131072, "free": False},
                {"id": "qwen3-14b", "name": "Qwen3 14B", "context": 131072, "free": False},
                {"id": "qwen3-8b", "name": "Qwen3 8B", "context": 131072, "free": False},
                {"id": "qwen3-4b", "name": "Qwen3 4B", "context": 131072, "free": False},
                {"id": "qwen3-1.7b", "name": "Qwen3 1.7B", "context": 32768, "free": False},
                {"id": "qwen3-0.6b", "name": "Qwen3 0.6B", "context": 32768, "free": False},
                # Qwen3.5 / Qwen3.6
                {"id": "qwen3.5-7b", "name": "Qwen3.5 7B", "context": 131072, "free": False},
                {"id": "qwen3.5-14b", "name": "Qwen3.5 14B", "context": 131072, "free": False},
                {"id": "qwen3.5-32b", "name": "Qwen3.5 32B", "context": 131072, "free": False},
                # Qwen commercial
                {"id": "qwen-plus", "name": "Qwen Plus", "context": 131072, "free": False},
                {"id": "qwen-turbo", "name": "Qwen Turbo", "context": 1000000, "free": False},
                {"id": "qwen-max", "name": "Qwen Max", "context": 32768, "free": False},
                {"id": "qwen-long", "name": "Qwen Long", "context": 10000000, "free": False},
                # Qwen2.5
                {"id": "qwen2.5-72b-instruct", "name": "Qwen2.5 72B", "context": 131072, "free": False},
                {"id": "qwen2.5-32b-instruct", "name": "Qwen2.5 32B", "context": 131072, "free": False},
                {"id": "qwen2.5-14b-instruct", "name": "Qwen2.5 14B", "context": 131072, "free": False},
                {"id": "qwen2.5-7b-instruct", "name": "Qwen2.5 7B", "context": 131072, "free": False},
                # Qwen VL (multimodal)
                {"id": "qwen-vl-max", "name": "Qwen VL Max (Vision)", "context": 32768, "free": False},
                {"id": "qwen-vl-plus", "name": "Qwen VL Plus (Vision)", "context": 8192, "free": False},
                # Qwen Coder
                {"id": "qwen2.5-coder-32b-instruct", "name": "Qwen2.5 Coder 32B", "context": 131072, "free": False},
                {"id": "qwen2.5-coder-14b-instruct", "name": "Qwen2.5 Coder 14B", "context": 131072, "free": False},
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


# --- API Keys Management ---


@app.get("/api/config/keys")
async def get_api_keys():
    """Get current API keys status (masked)."""
    import os

    def mask(key: str) -> str:
        if not key:
            return ""
        return "***" + key[-4:] if len(key) > 4 else "***"

    return {
        "brave_api_key": mask(config.web_search.brave_api_key),
        "google_credentials": bool(os.path.exists(config.email.credentials_path)),
        "gmail_token": bool(os.path.exists(config.email.token_path)),
        "calendar_token": bool(os.path.exists(config.calendar.token_path)),
    }


@app.post("/api/config/keys")
async def set_api_keys(data: dict):
    """Update API keys at runtime."""
    updated = []

    brave_key = data.get("brave_api_key", "").strip()
    if brave_key:
        config.web_search.brave_api_key = brave_key
        updated.append("brave_api_key")

    return {"success": True, "updated": updated}


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
        audio_path, visemes = await tts_engine.synthesize(result["text"], language, result.get("emotion", "neutral"))
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
        audio_path, visemes = await tts_engine.synthesize(result["text"], language, result.get("emotion", "neutral"))
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
