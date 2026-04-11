import pytest
import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock

# Mock google auth modules (not installed in test env)
for mod in [
    "google.oauth2.credentials",
    "google.auth.transport.requests",
    "google_auth_oauthlib.flow",
    "googleapiclient.discovery",
]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


@pytest.fixture
def mock_llm():
    return AsyncMock()


@pytest.fixture
def mock_soul():
    soul = MagicMock()
    soul.get_chat_prompt.return_value = "You are a test AI wife."
    soul.get_assist_prompt.return_value = "You are a test AI wife.\n\n## Assist Mode"
    return soul


@pytest.fixture
def mock_memory():
    memory = AsyncMock()
    memory.search.return_value = []
    memory.extract_from_conversation.return_value = None
    return memory


@pytest.fixture
def mock_skills():
    skills = MagicMock()
    skills.get_tool_definitions.return_value = [
        {
            "type": "function",
            "function": {
                "name": "file_write",
                "description": "write file",
                "parameters": {"type": "object", "properties": {}},
            },
        }
    ]
    skills.execute = AsyncMock(return_value={"success": True, "path": "/tmp/test.txt"})
    return skills


@pytest.fixture
def agent(mock_llm, mock_soul, mock_memory, mock_skills):
    from agent import AgentOrchestrator

    a = AgentOrchestrator.__new__(AgentOrchestrator)
    a.llm = mock_llm
    a.soul = mock_soul
    a.memory = mock_memory
    a.skills = mock_skills
    a.conversation_history = {}
    a.pending_plans = {}
    a.max_history = 20
    return a


# ── Intent Classification (rule-based, no LLM) ────────────────────


def test_classify_intent_chat(agent):
    mode = agent._classify_intent_fast("你好啊")
    assert mode == "chat"


def test_classify_intent_assist(agent):
    mode = agent._classify_intent_fast("幫我寫一封信")
    assert mode == "assist"


def test_classify_intent_assist_email(agent):
    mode = agent._classify_intent_fast("幫我讀最新email")
    assert mode == "assist"


def test_classify_intent_assist_calendar(agent):
    mode = agent._classify_intent_fast("幫我排行程")
    assert mode == "assist"


def test_classify_intent_assist_search(agent):
    mode = agent._classify_intent_fast("搜尋一下")
    assert mode == "assist"


# ── Chat Mode Stream ──────────────────────────────────────────────


def test_chat_mode_stream(agent, mock_llm):
    async def fake_stream():
        for chunk in ["Hello", " there", "!"]:
            yield chunk

    mock_llm.chat.return_value = fake_stream()

    async def run():
        chunks = []
        async for chunk in agent._chat_mode_stream("你好", "zh-TW", "test"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(run())
    types = [json.loads(c)["type"] for c in chunks]
    assert "chunk" in types
    assert "done" in types


# ── Assist Mode Stream ────────────────────────────────────────────


def test_assist_mode_stream_with_tool_calls(agent, mock_llm, mock_skills):
    mock_llm.chat.return_value = {
        "content": "我來幫你建立檔案",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "file_write",
                    "arguments": '{"path": "~/Downloads/test.txt", "content": "hello"}',
                },
            }
        ],
    }

    async def run():
        chunks = []
        async for chunk in agent._assist_mode_stream("幫我建一個txt", "zh-TW", "test"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(run())
    types = [json.loads(c)["type"] for c in chunks]
    assert "notice" in types
    assert "plan" in types

    plan_chunk = [json.loads(c) for c in chunks if json.loads(c)["type"] == "plan"][0]
    assert plan_chunk["awaiting_confirmation"] is True
    assert agent.pending_plans.get("test") is not None


def test_assist_mode_stream_no_tools(agent, mock_llm):
    mock_llm.chat.return_value = "好的，我來幫你～"

    async def run():
        chunks = []
        async for chunk in agent._assist_mode_stream("你好", "zh-TW", "test"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(run())
    types = [json.loads(c)["type"] for c in chunks]
    assert "done" in types


# ── Confirm Plan (ReAct loop) ─────────────────────────────────────


def test_confirm_plan_single_tool(agent, mock_llm, mock_skills):
    agent.pending_plans["test"] = {
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "file_write",
                    "arguments": '{"path": "~/test.txt", "content": "hello"}',
                },
            }
        ],
        "plan_text": "寫檔案",
        "message": "建檔案",
        "language": "zh-TW",
    }
    agent.conversation_history["test"] = []

    # LLM returns a summary (no tool_calls) after tool execution
    mock_llm.chat.return_value = "Done! [emotion:happy]"

    async def run():
        chunks = []
        async for chunk in agent.confirm_plan("test"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(run())
    types = [json.loads(c)["type"] for c in chunks]
    assert "tool_start" in types
    assert "tool_result" in types
    assert "done" in types
    mock_skills.execute.assert_called_once()


def test_confirm_plan_no_pending(agent, mock_llm):
    async def run():
        chunks = []
        async for chunk in agent.confirm_plan("nonexistent"):
            chunks.append(chunk)
        return chunks

    chunks = asyncio.run(run())
    types = [json.loads(c)["type"] for c in chunks]
    assert "error" in types


# ── Deny Plan ─────────────────────────────────────────────────────


def test_deny_plan(agent):
    agent.pending_plans["test"] = {
        "tool_calls": [],
        "plan_text": "",
        "message": "",
        "language": "zh-TW",
    }
    result = asyncio.run(agent.deny_plan("test", "zh-TW"))
    assert "取消" in result["text"]
    assert "test" not in agent.pending_plans


# ── Emotion Extraction ────────────────────────────────────────────


def test_extract_emotion(agent):
    text, emotion = agent._extract_emotion("你好！[emotion:happy]")
    assert text == "你好！"
    assert emotion == "happy"


def test_extract_emotion_default(agent):
    text, emotion = agent._extract_emotion("你好！")
    assert text == "你好！"
    assert emotion == "neutral"


# ── History Management ────────────────────────────────────────────


def test_history_management(agent):
    history = agent._get_history("new_client")
    assert history == []
    history.append({"role": "user", "content": "test"})
    assert len(agent._get_history("new_client")) == 1


def test_format_plan(agent):
    tool_calls = [
        {
            "function": {
                "name": "file_write",
                "arguments": '{"path": "~/test.txt", "content": "hello"}',
            }
        }
    ]
    plan = agent._format_plan("I will create a file", tool_calls)
    assert "file_write" in plan
    assert "test.txt" in plan


# ── Think Stripper ────────────────────────────────────────────────


def test_think_stripper_basic():
    from agent import _ThinkStripper

    s = _ThinkStripper()
    assert s.feed("<think>internal</think>Hello") == "Hello"


def test_think_stripper_split_tags():
    from agent import _ThinkStripper

    s = _ThinkStripper()
    assert s.feed("<think>thinking...") == ""
    assert s.feed("still thinking") == ""
    assert s.feed("</think>visible text") == "visible text"


def test_think_stripper_no_think():
    from agent import _ThinkStripper

    s = _ThinkStripper()
    assert s.feed("just normal text") == "just normal text"


def test_think_stripper_split_close_tag():
    from agent import _ThinkStripper

    s = _ThinkStripper()
    s.feed("<think>x")
    assert s.feed("</thi") == ""
    assert s.feed("nk>after") == "after"
