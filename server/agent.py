import asyncio
import logging
import json
import re
from soul.soul_manager import SoulManager
from memory.memory_store import MemoryStore
from skills.registry import SkillRegistry

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    def __init__(self, llm_client, config, skill_registry: SkillRegistry,
                 soul_manager: SoulManager, memory_store: MemoryStore):
        self.llm = llm_client
        self.config = config
        self.skills = skill_registry
        self.soul = soul_manager
        self.memory = memory_store
        self.conversation_history: dict[str, list] = {}
        self.pending_plans: dict[str, dict] = {}
        self.max_history = 20

    async def _classify_intent(self, message: str) -> str:
        """Phase 0: Fast intent classification. Returns 'chat' or 'assist'."""
        prompt = """判斷用戶的意圖。只回覆一個 JSON：{"mode": "chat"} 或 {"mode": "assist"}
- chat: 日常聊天、閒聊、問候、情感交流、問問題
- assist: 需要執行操作（寄信、建檔案、查行程、搜尋、寫程式等）
用戶訊息：""" + message
        try:
            result = await self.llm.chat(
                [{"role": "user", "content": prompt}],
                think=False,
            )
            cleaned = result.strip()
            if "```" in cleaned:
                start = cleaned.find("{")
                end = cleaned.rfind("}") + 1
                if start >= 0 and end > start:
                    cleaned = cleaned[start:end]
            parsed = json.loads(cleaned)
            mode = parsed.get("mode", "chat")
            return mode if mode in ("chat", "assist") else "chat"
        except (json.JSONDecodeError, AttributeError, Exception) as e:
            logger.warning(f"Intent classification failed, defaulting to chat: {e}")
            return "chat"

    async def chat(self, message: str, language: str = "zh-TW", client_id: str = "default") -> dict:
        """Non-streaming chat — for backward compatibility with WebSocket handler."""
        mode = await self._classify_intent(message)

        if mode == "chat":
            return await self._chat_mode(message, language, client_id)
        else:
            return await self._assist_mode_nonstream(message, language, client_id)

    async def _chat_mode(self, message: str, language: str, client_id: str) -> dict:
        """Fast chat — no_think, no tools."""
        memories = await self.memory.search(message, limit=3)
        system_prompt = self.soul.get_chat_prompt(language)
        if memories:
            memory_text = "\n".join([f"- {m['content']}" for m in memories])
            system_prompt += f"\n\n## Relevant Memories\n{memory_text}"

        history = self._get_history(client_id)
        history.append({"role": "user", "content": message})
        self._trim_history(client_id)

        messages = [{"role": "system", "content": system_prompt}, *history]
        response_text = await self.llm.chat(messages, think=False)

        history.append({"role": "assistant", "content": response_text})
        self._trim_history(client_id)

        asyncio.create_task(self._learn_from_turn(message, response_text))

        clean_text, emotion = self._extract_emotion(response_text)
        return {"text": clean_text, "emotion": emotion, "language": language, "mode": "chat"}

    async def _assist_mode_nonstream(self, message: str, language: str, client_id: str) -> dict:
        """Non-streaming assist mode — returns plan for confirmation."""
        memories = await self.memory.search(message, limit=3)
        system_prompt = self.soul.get_assist_prompt(language)
        if memories:
            memory_text = "\n".join([f"- {m['content']}" for m in memories])
            system_prompt += f"\n\n## Relevant Memories\n{memory_text}"

        history = self._get_history(client_id)
        history.append({"role": "user", "content": message})
        self._trim_history(client_id)

        messages = [{"role": "system", "content": system_prompt}, *history]
        tools = self.skills.get_tool_definitions()
        result = await self.llm.chat(messages, tools=tools, think=True)

        if isinstance(result, dict) and result.get("tool_calls"):
            self.pending_plans[client_id] = {
                "tool_calls": result["tool_calls"],
                "plan_text": result.get("content", ""),
                "message": message,
                "language": language,
            }
            return {
                "text": result.get("content", ""),
                "emotion": "neutral",
                "mode": "assist",
                "awaiting_confirmation": True,
                "tool_calls": [
                    {"name": tc["function"]["name"],
                     "arguments": json.loads(tc["function"]["arguments"])}
                    for tc in result["tool_calls"]
                ],
            }
        else:
            content = result if isinstance(result, str) else result.get("content", "")
            history.append({"role": "assistant", "content": content})
            self._trim_history(client_id)
            clean_text, emotion = self._extract_emotion(content)
            return {"text": clean_text, "emotion": emotion, "mode": "assist"}

    async def chat_stream(self, message: str, language: str = "zh-TW", client_id: str = "default"):
        """Main entry point — streaming version."""
        mode = await self._classify_intent(message)

        yield json.dumps({"type": "mode_change", "mode": mode}, ensure_ascii=False)

        if mode == "chat":
            async for chunk in self._chat_mode_stream(message, language, client_id):
                yield chunk
        else:
            async for chunk in self._assist_mode_stream(message, language, client_id):
                yield chunk

    async def _chat_mode_stream(self, message: str, language: str, client_id: str):
        """Fast chat — no_think, no tools, streaming."""
        memories = await self.memory.search(message, limit=3)
        system_prompt = self.soul.get_chat_prompt(language)
        if memories:
            memory_text = "\n".join([f"- {m['content']}" for m in memories])
            system_prompt += f"\n\n## Relevant Memories\n{memory_text}"

        history = self._get_history(client_id)
        history.append({"role": "user", "content": message})
        self._trim_history(client_id)

        messages = [{"role": "system", "content": system_prompt}, *history]

        full_response = ""
        stream_gen = await self.llm.chat(messages, think=False, stream=True)
        async for chunk in stream_gen:
            full_response += chunk
            yield json.dumps({"type": "chunk", "data": chunk}, ensure_ascii=False)

        history.append({"role": "assistant", "content": full_response})
        self._trim_history(client_id)

        asyncio.create_task(self._learn_from_turn(message, full_response))

        clean_text, emotion = self._extract_emotion(full_response)
        yield json.dumps({"type": "done", "emotion": emotion, "text": clean_text}, ensure_ascii=False)

    async def _assist_mode_stream(self, message: str, language: str, client_id: str):
        """Assist mode — think, tools, confirmation flow."""
        # Phase 1: Quick notice
        notice = self._get_assist_notice(language)
        yield json.dumps({"type": "notice", "text": notice}, ensure_ascii=False)

        # Phase 2: Planning (think + tools)
        memories = await self.memory.search(message, limit=3)
        system_prompt = self.soul.get_assist_prompt(language)
        if memories:
            memory_text = "\n".join([f"- {m['content']}" for m in memories])
            system_prompt += f"\n\n## Relevant Memories\n{memory_text}"

        history = self._get_history(client_id)
        history.append({"role": "user", "content": message})
        self._trim_history(client_id)

        messages = [{"role": "system", "content": system_prompt}, *history]
        tools = self.skills.get_tool_definitions()

        result = await self.llm.chat(messages, tools=tools, think=True)

        if isinstance(result, dict) and result.get("tool_calls"):
            plan_text = result.get("content", "")
            tool_calls = result["tool_calls"]

            plan_description = self._format_plan(plan_text, tool_calls)

            self.pending_plans[client_id] = {
                "tool_calls": tool_calls,
                "plan_text": plan_text,
                "message": message,
                "language": language,
            }

            yield json.dumps({
                "type": "plan",
                "description": plan_description,
                "tool_calls": [
                    {"name": tc["function"]["name"],
                     "arguments": json.loads(tc["function"]["arguments"])}
                    for tc in tool_calls
                ],
                "awaiting_confirmation": True,
            }, ensure_ascii=False)
        else:
            content = result if isinstance(result, str) else result.get("content", "")
            history.append({"role": "assistant", "content": content})
            self._trim_history(client_id)
            clean_text, emotion = self._extract_emotion(content)
            yield json.dumps({"type": "done", "emotion": emotion, "text": clean_text}, ensure_ascii=False)

    async def confirm_plan(self, client_id: str):
        """User confirmed the plan — execute tools and stream results."""
        plan = self.pending_plans.pop(client_id, None)
        if not plan:
            yield json.dumps({"type": "error", "text": "No pending plan"}, ensure_ascii=False)
            return

        tool_calls = plan["tool_calls"]
        results = []

        for tc in tool_calls:
            func = tc["function"]
            tool_name = func["name"]
            arguments = json.loads(func["arguments"])
            result = await self.skills.execute(tool_name, arguments)
            results.append({"tool": tool_name, "result": result})
            yield json.dumps({
                "type": "tool_result", "tool": tool_name, "result": result
            }, ensure_ascii=False)

        # Phase 5: LLM summarizes results
        results_json = json.dumps(results, ensure_ascii=False, default=str)
        summary_msg = f"工具執行完成。結果：{results_json}\n請用簡短溫暖的語氣告訴用戶結果。"
        history = self._get_history(client_id)
        messages = [
            {"role": "system", "content": self.soul.get_chat_prompt(plan["language"])},
            *history,
            {"role": "user", "content": summary_msg},
        ]

        full_response = ""
        stream_gen = await self.llm.chat(messages, think=False, stream=True)
        async for chunk in stream_gen:
            full_response += chunk
            yield json.dumps({"type": "chunk", "data": chunk}, ensure_ascii=False)

        history.append({"role": "assistant", "content": full_response})
        self._trim_history(client_id)

        clean_text, emotion = self._extract_emotion(full_response)
        yield json.dumps({"type": "done", "emotion": emotion, "text": clean_text}, ensure_ascii=False)

    async def deny_plan(self, client_id: str, language: str = "zh-TW") -> dict:
        """User denied the plan."""
        self.pending_plans.pop(client_id, None)
        cancel_msg = {
            "zh-TW": "好的，取消了～",
            "ja": "了解、キャンセルしたよ～",
            "en": "OK, cancelled~",
        }
        return {
            "text": cancel_msg.get(language, cancel_msg["zh-TW"]),
            "emotion": "neutral",
        }

    async def execute_scheduled_task(self, action: str, language: str = "zh-TW") -> dict:
        """Execute a heartbeat scheduled task through the agent."""
        system_prompt = self.soul.get_assist_prompt(language)
        tools = self.skills.get_tool_definitions()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": action},
        ]
        result = await self.llm.chat(messages, tools=tools, think=True)

        if isinstance(result, dict) and result.get("tool_calls"):
            results = []
            for tc in result["tool_calls"]:
                func = tc["function"]
                tool_result = await self.skills.execute(
                    func["name"], json.loads(func["arguments"]))
                results.append({"tool": func["name"], "result": tool_result})
            return {"action": action, "results": results, "content": result.get("content", "")}
        else:
            content = result if isinstance(result, str) else result.get("content", "")
            return {"action": action, "content": content}

    def _get_assist_notice(self, language: str) -> str:
        notices = {
            "zh-TW": "好的，讓我來幫你處理～",
            "ja": "うん、任せて～",
            "en": "OK, let me help you with that~",
        }
        return notices.get(language, notices["zh-TW"])

    def _format_plan(self, plan_text: str, tool_calls: list) -> str:
        lines = [plan_text] if plan_text else []
        for tc in tool_calls:
            func = tc["function"]
            name = func["name"]
            args = json.loads(func["arguments"])
            lines.append(f"- {name}: {json.dumps(args, ensure_ascii=False)}")
        return "\n".join(lines)

    def _extract_emotion(self, text: str) -> tuple[str, str]:
        match = re.search(r'\[emotion:(happy|sad|angry|surprised|relaxed|neutral)\]\s*$', text)
        if match:
            return text[:match.start()].rstrip(), match.group(1)
        return text, "neutral"

    def _get_history(self, client_id: str) -> list:
        if client_id not in self.conversation_history:
            self.conversation_history[client_id] = []
        return self.conversation_history[client_id]

    def _trim_history(self, client_id: str):
        if len(self.conversation_history[client_id]) > self.max_history:
            self.conversation_history[client_id] = self.conversation_history[client_id][-self.max_history:]

    async def _learn_from_turn(self, user_msg: str, assistant_msg: str):
        """Background: extract memories from conversation turn."""
        try:
            await self.memory.extract_from_conversation(user_msg, assistant_msg, self.llm)
        except Exception as e:
            logger.warning(f"Memory extraction failed: {e}")
