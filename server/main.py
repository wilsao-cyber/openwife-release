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
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import logging
from typing import Optional

from config import config, load_config
from llm_client import LLMClient
from tts_engine import TTSEngine
from stt_engine import STTEngine
from agent import AgentOrchestrator
from websocket_manager import WebSocketManager
from vrm_manager import VrmManager
from vision_analyzer import VisionAnalyzer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ws_manager = WebSocketManager()
llm_client: Optional[LLMClient] = None
tts_engine: Optional[TTSEngine] = None
stt_engine: Optional[STTEngine] = None
agent: Optional[AgentOrchestrator] = None
vrm_manager = VrmManager()
vision_analyzer = VisionAnalyzer()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    global llm_client, tts_engine, stt_engine, agent

    logger.info("Initializing AI Wife Server...")

    llm_client = LLMClient(config.llm)
    tts_engine = TTSEngine(config.tts)
    stt_engine = STTEngine(config.stt)
    agent = AgentOrchestrator(llm_client, config)

    try:
        await tts_engine.initialize()
    except Exception as e:
        logger.warning(f"TTS engine initialization failed (non-critical): {e}")

    try:
        await stt_engine.initialize()
    except Exception as e:
        logger.warning(f"STT engine initialization failed (non-critical): {e}")

    for tool_name, tool in agent.tools.items():
        if hasattr(tool, "initialize"):
            try:
                await tool.initialize()
            except Exception as e:
                logger.warning(
                    f"Tool '{tool_name}' initialization failed (non-critical): {e}"
                )

    logger.info(f"Server running on {config.host}:{config.port}")

    yield

    # --- shutdown ---
    logger.info("Shutting down AI Wife Server...")


app = FastAPI(title="AI Wife Server", version="1.0.0", lifespan=lifespan)

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
    elif msg_type == "email_action":
        return await handle_email_action(data, client_id)
    elif msg_type == "calendar_action":
        return await handle_calendar_action(data, client_id)
    elif msg_type == "web_search":
        return await handle_web_search(data, client_id)
    elif msg_type == "file_action":
        return await handle_file_action(data, client_id)
    elif msg_type == "opencode_task":
        return await handle_opencode_task(data, client_id)
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
        "audio_url": f"/audio/{audio_path}",
        "visemes": visemes,
        "metadata": response.get("metadata", {}),
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


async def handle_email_action(data: dict, client_id: str) -> dict:
    action = data.get("action")
    params = data.get("params", {})
    result = await agent.execute_tool("email", action, params)
    return {"type": "email_result", **result}


async def handle_calendar_action(data: dict, client_id: str) -> dict:
    action = data.get("action")
    params = data.get("params", {})
    result = await agent.execute_tool("calendar", action, params)
    return {"type": "calendar_result", **result}


async def handle_web_search(data: dict, client_id: str) -> dict:
    query = data.get("query", "")
    result = await agent.execute_tool("web_search", "search", {"query": query})
    return {"type": "search_result", **result}


async def handle_file_action(data: dict, client_id: str) -> dict:
    action = data.get("action")
    params = data.get("params", {})
    result = await agent.execute_tool("file_ops", action, params)
    return {"type": "file_result", **result}


async def handle_opencode_task(data: dict, client_id: str) -> dict:
    task = data.get("task", "")
    project_path = data.get("project_path", "./mobile_app")
    result = await agent.execute_tool(
        "opencode",
        "execute",
        {
            "task_description": task,
            "project_path": project_path,
        },
    )
    return {"type": "opencode_result", **result}


@app.post("/api/chat")
async def api_chat(data: dict):
    message = data.get("message", "")
    language = data.get("language", config.languages.default)
    response = await agent.chat(message, language)
    return response


@app.post("/api/stt")
async def api_stt(audio: UploadFile = File(...)):
    audio_data = await audio.read()
    text = await stt_engine.transcribe(audio_data)
    return {"text": text}


@app.post("/api/tts")
async def api_tts(data: dict):
    text = data.get("text", "")
    language = data.get("language", config.languages.default)
    audio_path, _ = await tts_engine.synthesize(text, language)
    return FileResponse(audio_path, media_type="audio/wav")


@app.get("/audio/{filename}")
async def get_audio(filename: str):
    return FileResponse(f"./output/audio/{filename}")


@app.get("/models/{filename}")
async def get_model(filename: str):
    return FileResponse(f"./output/models/{filename}")


@app.get("/")
async def web_index():
    return FileResponse("static/index.html", media_type="text/html")


app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "llm": llm_client is not None,
            "tts": tts_engine is not None,
            "stt": stt_engine is not None,
            "agent": agent is not None,
        },
    }


@app.post("/api/email/{action}")
async def api_email(action: str, data: dict = {}):
    try:
        result = await agent.execute_tool("email", action, data)
        return result
    except Exception as e:
        return {"error": str(e), "emails": []}


@app.post("/api/calendar/{action}")
async def api_calendar(action: str, data: dict = {}):
    try:
        result = await agent.execute_tool("calendar", action, data)
        return result
    except Exception as e:
        return {"error": str(e), "events": []}


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


@app.post("/api/vision/capture")
async def vision_capture(image: UploadFile = File(...), language: str = "zh-TW"):
    image_data = await image.read()
    result = vision_analyzer.analyze_single(image_data, language)
    if result.get("text"):
        audio_path, visemes = await tts_engine.synthesize(result["text"], language)
        result["audio_url"] = f"/audio/{audio_path}"
        result["visemes"] = visemes
    return result


@app.post("/api/vision/stream")
async def vision_stream(image: UploadFile = File(...), previous_hash: str = "", language: str = "zh-TW", context: str = ""):
    image_data = await image.read()
    previous_bytes = None
    result = vision_analyzer.analyze_stream(image_data, previous_bytes, language, context)
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
