import pytest
import sys
from unittest.mock import AsyncMock, patch, MagicMock

# Mock google auth modules so agent.py can import without google libs
for mod in [
    "google", "google.oauth2", "google.oauth2.credentials",
    "google.auth.transport.requests", "google_auth_oauthlib",
    "google_auth_oauthlib.flow", "googleapiclient", "googleapiclient.discovery",
]:
    sys.modules.setdefault(mod, MagicMock())

from agent import AgentOrchestrator
from config import ServerConfig


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    llm.chat = AsyncMock()
    return llm


@pytest.fixture
def agent(mock_llm):
    config = ServerConfig()
    orch = AgentOrchestrator(mock_llm, config)
    return orch


class TestToolDetection:
    @pytest.mark.asyncio
    async def test_valid_tool_call(self, agent, mock_llm):
        mock_llm.chat.return_value = '[["email", "list_emails", {"limit": 10}]]'
        result = await agent._detect_tool_calls("show my emails", "en")
        assert len(result) == 1
        assert result[0][0] == "email"
        assert result[0][1] == "list_emails"

    @pytest.mark.asyncio
    async def test_empty_array(self, agent, mock_llm):
        mock_llm.chat.return_value = "[]"
        result = await agent._detect_tool_calls("hello", "en")
        assert result == []

    @pytest.mark.asyncio
    async def test_malformed_json_returns_empty(self, agent, mock_llm):
        mock_llm.chat.return_value = "this is not json at all"
        result = await agent._detect_tool_calls("hello", "en")
        assert result == []

    @pytest.mark.asyncio
    async def test_markdown_wrapped_json(self, agent, mock_llm):
        mock_llm.chat.return_value = '```json\n[["calendar", "view_events", {"days_ahead": 7}]]\n```'
        result = await agent._detect_tool_calls("show my schedule", "en")
        assert len(result) == 1
        assert result[0][0] == "calendar"

    @pytest.mark.asyncio
    async def test_unknown_tool_filtered(self, agent, mock_llm):
        mock_llm.chat.return_value = '[["unknown_tool", "action", {}]]'
        result = await agent._detect_tool_calls("do something", "en")
        assert result == []

    @pytest.mark.asyncio
    async def test_mixed_valid_and_invalid(self, agent, mock_llm):
        mock_llm.chat.return_value = '[["email", "list_emails", {}], ["fake", "x", {}]]'
        result = await agent._detect_tool_calls("emails", "en")
        assert len(result) == 1
        assert result[0][0] == "email"

    @pytest.mark.asyncio
    async def test_llm_error_returns_empty(self, agent, mock_llm):
        mock_llm.chat.side_effect = Exception("LLM down")
        result = await agent._detect_tool_calls("hello", "en")
        assert result == []


class TestEmotionExtraction:
    def test_extract_happy(self, agent):
        text = "Hello there! [emotion:happy]"
        clean, emotion = agent._extract_emotion(text)
        assert clean == "Hello there!"
        assert emotion == "happy"

    def test_extract_sad(self, agent):
        text = "I'm sorry to hear that. [emotion:sad]"
        clean, emotion = agent._extract_emotion(text)
        assert emotion == "sad"

    def test_no_emotion_tag(self, agent):
        text = "Just a normal response"
        clean, emotion = agent._extract_emotion(text)
        assert clean == "Just a normal response"
        assert emotion == "neutral"

    def test_invalid_emotion_tag(self, agent):
        text = "Something [emotion:excited]"
        clean, emotion = agent._extract_emotion(text)
        assert emotion == "neutral"


class TestConversationHistory:
    @pytest.mark.asyncio
    async def test_history_limit_enforced(self, agent, mock_llm):
        mock_llm.chat.return_value = "response [emotion:neutral]"
        client_id = "test_client"

        for i in range(25):
            await agent.chat(f"message {i}", "en", client_id)

        # Trim happens before LLM call, then assistant response is appended after.
        # So history can be max_history + 1 (the new assistant message).
        assert len(agent.conversation_history[client_id]) <= agent.max_history + 1

    @pytest.mark.asyncio
    async def test_separate_client_histories(self, agent, mock_llm):
        mock_llm.chat.return_value = "hi [emotion:neutral]"

        await agent.chat("msg1", "en", "client_a")
        await agent.chat("msg2", "en", "client_b")

        assert "client_a" in agent.conversation_history
        assert "client_b" in agent.conversation_history
        assert agent.conversation_history["client_a"] != agent.conversation_history["client_b"]
