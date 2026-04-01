import pytest
import asyncio
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from llm_client import LLMClient
from config import LLMConfig


@pytest.fixture
def llm_config():
    return LLMConfig(
        provider="ollama",
        base_url="http://localhost:9090",
        model="qwen2.5:7b",
        temperature=0.7,
        max_tokens=2048,
    )


@pytest.fixture
def llm_client(llm_config):
    return LLMClient(llm_config)


class TestLLMClientRetry:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_try(self, llm_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}]
        }

        with patch.object(llm_client.client, "post", new_callable=AsyncMock, return_value=mock_response):
            result = await llm_client.chat([{"role": "user", "content": "hi"}])
            assert result == "Hello!"

    @pytest.mark.asyncio
    async def test_retries_on_500_then_succeeds(self, llm_client):
        error_response = httpx.Response(500, request=httpx.Request("POST", "http://test"))
        ok_response = MagicMock()
        ok_response.raise_for_status = MagicMock()
        ok_response.json.return_value = {
            "choices": [{"message": {"content": "OK after retry"}}]
        }

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.HTTPStatusError("Server Error", request=httpx.Request("POST", "http://test"), response=error_response)
            return ok_response

        with patch.object(llm_client.client, "post", side_effect=mock_post):
            with patch("llm_client.asyncio.sleep", new_callable=AsyncMock):
                result = await llm_client.chat([{"role": "user", "content": "hi"}])
                assert result == "OK after retry"
                assert call_count == 2

    @pytest.mark.asyncio
    async def test_no_retry_on_4xx(self, llm_client):
        error_response = httpx.Response(400, request=httpx.Request("POST", "http://test"))

        async def mock_post(*args, **kwargs):
            raise httpx.HTTPStatusError("Bad Request", request=httpx.Request("POST", "http://test"), response=error_response)

        with patch.object(llm_client.client, "post", side_effect=mock_post):
            with pytest.raises(httpx.HTTPStatusError):
                await llm_client.chat([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self, llm_client):
        ok_response = MagicMock()
        ok_response.raise_for_status = MagicMock()
        ok_response.json.return_value = {
            "choices": [{"message": {"content": "recovered"}}]
        }

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise httpx.TimeoutException("timeout")
            return ok_response

        with patch.object(llm_client.client, "post", side_effect=mock_post):
            with patch("llm_client.asyncio.sleep", new_callable=AsyncMock):
                result = await llm_client.chat([{"role": "user", "content": "hi"}])
                assert result == "recovered"
                assert call_count == 3

    @pytest.mark.asyncio
    async def test_fails_after_max_retries(self, llm_client):
        async def mock_post(*args, **kwargs):
            raise httpx.TimeoutException("timeout")

        with patch.object(llm_client.client, "post", side_effect=mock_post):
            with patch("llm_client.asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(httpx.TimeoutException):
                    await llm_client.chat([{"role": "user", "content": "hi"}])

    @pytest.mark.asyncio
    async def test_retries_on_connect_error(self, llm_client):
        ok_response = MagicMock()
        ok_response.raise_for_status = MagicMock()
        ok_response.json.return_value = {
            "choices": [{"message": {"content": "connected"}}]
        }

        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("Connection refused")
            return ok_response

        with patch.object(llm_client.client, "post", side_effect=mock_post):
            with patch("llm_client.asyncio.sleep", new_callable=AsyncMock):
                result = await llm_client.chat([{"role": "user", "content": "hi"}])
                assert result == "connected"
