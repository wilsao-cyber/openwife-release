import asyncio
import logging
import json
import re
import time
from typing import Optional
from soul.soul_manager import SoulManager
from memory.memory_store import MemoryStore
from skills.registry import SkillRegistry

logger = logging.getLogger(__name__)

MAX_REACT_ITERATIONS = 5


class _ThinkStripper:
    """Strips <think>...</think> blocks from a stream of text chunks."""

    def __init__(self):
        self.inside = False
        self.buf = ""

    def feed(self, chunk: str) -> str:
        self.buf += chunk
        output = []
        while self.buf:
            if self.inside:
                end = self.buf.find("</think>")
                if end == -1:
                    if len(self.buf) < 9 and self.buf in "</think>"[: len(self.buf)]:
                        break
                    self.buf = ""
                    break
                else:
                    self.buf = self.buf[end + 8 :]
                    self.inside = False
            else:
                start = self.buf.find("<think>")
                if start == -1:
                    for i in range(1, min(8, len(self.buf) + 1)):
                        if self.buf.endswith("<think>"[:i]):
                            output.append(self.buf[:-i])
                            self.buf = self.buf[-i:]
                            break
                    else:
                        output.append(self.buf)
                        self.buf = ""
                    break
                else:
                    output.append(self.buf[:start])
                    self.buf = self.buf[start + 7 :]
                    self.inside = True
        return "".join(output)

    def flush(self) -> str:
        if self.inside:
            return ""
        result = self.buf
        self.buf = ""
        return result


class AgentOrchestrator:
    """CoPAW-inspired ReAct agent with human-in-the-loop confirmation.

    Architecture:
    - Chat mode: single LLM call, no tools, think=False (fast)
    - Assist mode: single ReAct loop with tools, think=False
      Phase 1: LLM generates tool_calls (no separate intent classifier)
      Phase 2: User confirms/denies
      Phase 3: Execute tools, feed results back to LLM for summary
    """

    def __init__(
        self,
        llm_client,
        config,
        skill_registry: SkillRegistry,
        soul_manager: SoulManager,
        memory_store: MemoryStore,
    ):
        self.llm = llm_client
        self.config = config
        self.skills = skill_registry
        self.soul = soul_manager
        self.memory = memory_store
        self.conversation_history: dict[str, list] = {}
        self.pending_plans: dict[str, dict] = {}
        self.max_history = 20

    # ── Public API ──────────────────────────────────────────────────

    async def chat(
        self, message: str, language: str = "zh-TW", client_id: str = "default"
    ) -> dict:
        """Non-streaming chat — for backward compatibility."""
        mode = self._classify_intent_fast(message)
        if mode == "chat":
            return await self._chat_mode(message, language, client_id)
        else:
            return await self._assist_mode_nonstream(message, language, client_id)

    async def chat_stream(
        self,
        message: str,
        language: str = "zh-TW",
        client_id: str = "default",
        mode_override: Optional[str] = None,
        use_fallback: bool = False,
    ):
        """Main entry point — streaming version."""
        mode = mode_override or self._classify_intent_fast(message)
        yield json.dumps({"type": "mode_change", "mode": mode}, ensure_ascii=False)

        # Debug event for frontend debug panel
        matched = [p for p in self._get_assist_phrases() if p in message.lower()]
        yield json.dumps(
            {
                "type": "debug",
                "data": {
                    "mode": mode,
                    "model": str(self.llm.model),
                    "intent_keywords": matched,
                    "timestamp": time.time(),
                    "use_fallback": use_fallback,
                },
            },
            ensure_ascii=False,
        )

        if mode == "chat":
            async for chunk in self._chat_mode_stream(message, language, client_id, use_fallback=use_fallback):
                yield chunk
        else:
            async for chunk in self._assist_mode_stream(message, language, client_id, use_fallback=use_fallback):
                yield chunk

    def _get_display_hint(self, tool_name: str, result: dict) -> dict | None:
        """Generate display hint for virtual panel rendering."""
        hints = {
            "email_read": lambda r: {
                "type": "email",
                "title": r.get("subject", "Email"),
            },
            "email_list": lambda r: {"type": "table", "title": "Inbox"},
            "email_search": lambda r: {"type": "table", "title": "Search Results"},
            "calendar_view": lambda r: {"type": "calendar", "title": "Events"},
            "calendar_create": lambda r: {"type": "calendar", "title": "New Event"},
        }
        fn = hints.get(tool_name)
        return fn(result) if fn else None

    async def confirm_plan(self, client_id: str):
        """User confirmed — execute tools with ReAct loop."""
        plan = self.pending_plans.pop(client_id, None)
        if not plan:
            yield json.dumps(
                {"type": "error", "text": "No pending plan"}, ensure_ascii=False
            )
            return

        t0 = time.time()
        tool_calls = plan["tool_calls"]
        language = plan["language"]
        original_message = plan.get("message", "")
        history = self._get_history(client_id)
        system_prompt = self.soul.get_assist_prompt(language)

        # ReAct loop: execute tools, feed results back, let LLM decide next
        for iteration in range(MAX_REACT_ITERATIONS):
            if not tool_calls:
                break

            results = []
            for tc in tool_calls:
                func = tc["function"]
                tool_name = func["name"]
                arguments = json.loads(func["arguments"])
                logger.info(f"Executing tool: {tool_name}({arguments})")
                yield json.dumps(
                    {"type": "tool_start", "tool": tool_name, "arguments": arguments},
                    ensure_ascii=False,
                )

                result = await self.skills.execute(tool_name, arguments)
                results.append({"tool": tool_name, "result": result})
                display_hint = self._get_display_hint(tool_name, result)
                yield json.dumps(
                    {
                        "type": "tool_result",
                        "tool": tool_name,
                        "result": result,
                        "display_hint": display_hint,
                    },
                    ensure_ascii=False,
                )

            # Feed results back to LLM for next iteration or summary
            results_json = json.dumps(results, ensure_ascii=False, default=str)
            tool_result_msg = (
                f"[系統] 用戶原始請求：{original_message}\n"
                f"工具執行結果：{results_json}\n"
                f"你已經拿到了上面的工具結果資料，請直接使用這些資料回答用戶。\n"
                f"如果任務已完成，請用簡短溫暖的語氣直接告訴用戶結果內容。不要說你沒有權限或無法讀取。\n"
                f"如果還需要更多步驟，請繼續呼叫工具。"
            )
            messages = [
                {"role": "system", "content": system_prompt},
                *history,
                {"role": "user", "content": tool_result_msg},
            ]
            tools = self.skills.get_tool_definitions()

            # Last iteration: no tools, just summary
            is_last = iteration >= MAX_REACT_ITERATIONS - 1
            try:
                next_result = await self.llm.chat(
                    messages,
                    tools=None if is_last else tools,
                    think=False,
                    max_tokens=512 if is_last else 1024,
                )
            except Exception as e:
                logger.error(f"LLM call failed in confirm_plan iteration {iteration}: {e}")
                yield json.dumps({"type": "error", "text": f"LLM 呼叫失敗: {str(e)[:80]}"}, ensure_ascii=False)
                yield json.dumps({"type": "done", "emotion": "sad", "text": "抱歉老公，處理的時候出了點問題..."}, ensure_ascii=False)
                return

            if (
                is_last
                or not isinstance(next_result, dict)
                or not next_result.get("tool_calls")
            ):
                # Final summary — stream it
                content = (
                    next_result
                    if isinstance(next_result, str)
                    else next_result.get("content", "")
                )
                history.append({"role": "assistant", "content": content})
                self._trim_history(client_id)
                clean_text, emotion = self._extract_emotion(content)
                elapsed_ms = int((time.time() - t0) * 1000)
                yield json.dumps(
                    {"type": "done", "emotion": emotion, "text": clean_text},
                    ensure_ascii=False,
                )
                yield json.dumps(
                    {
                        "type": "debug",
                        "data": {
                            "phase": "confirm_plan",
                            "iterations": iteration + 1,
                            "tools_executed": [r["tool"] for r in results],
                            "elapsed_ms": elapsed_ms,
                            "model": str(self.llm.model),
                        },
                    },
                    ensure_ascii=False,
                )
                return

            # LLM wants more tools — continue ReAct loop
            tool_calls = next_result["tool_calls"]
            history.append(
                {"role": "assistant", "content": next_result.get("content", "")}
            )
            history.append(
                {
                    "role": "tool",
                    "content": results_json,
                    "tool_call_id": tool_calls[0]["id"] if tool_calls else "0",
                }
            )

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

    async def execute_scheduled_task(
        self, action: str, language: str = "zh-TW"
    ) -> dict:
        """Execute a heartbeat scheduled task."""
        system_prompt = self.soul.get_assist_prompt(language)
        tools = self.skills.get_tool_definitions()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": action},
        ]
        result = await self.llm.chat(messages, tools=tools, think=False, max_tokens=512)

        if isinstance(result, dict) and result.get("tool_calls"):
            results = []
            for tc in result["tool_calls"]:
                func = tc["function"]
                tool_result = await self.skills.execute(
                    func["name"], json.loads(func["arguments"])
                )
                results.append({"tool": func["name"], "result": tool_result})
            return {
                "action": action,
                "results": results,
                "content": result.get("content", ""),
            }
        else:
            content = result if isinstance(result, str) else result.get("content", "")
            return {"action": action, "content": content}

    # ── Chat mode (fast, no tools) ──────────────────────────────────

    async def _chat_mode(self, message: str, language: str, client_id: str) -> dict:
        """Fast chat — no_think, no tools."""
        messages = await self._build_chat_messages(message, language, client_id)
        response_text = await self.llm.chat(messages, think=False)

        history = self._get_history(client_id)
        history.append({"role": "assistant", "content": response_text})
        self._trim_history(client_id)
        asyncio.create_task(self._learn_from_turn(message, response_text))

        clean_text, emotion = self._extract_emotion(response_text)
        return {
            "text": clean_text,
            "emotion": emotion,
            "language": language,
            "mode": "chat",
        }

    async def _chat_mode_stream(self, message: str, language: str, client_id: str, use_fallback: bool = False):
        """Fast chat — streaming."""
        t0 = time.time()
        messages = await self._build_chat_messages(message, language, client_id)

        full_response = ""
        think_chars = 0
        stripper = _ThinkStripper()
        stream_gen = await self.llm.chat(messages, think=False, stream=True, use_fallback=use_fallback)
        async for chunk in stream_gen:
            visible = stripper.feed(chunk)
            think_chars += len(chunk) - len(visible)
            full_response += visible
            if visible:
                yield json.dumps({"type": "chunk", "data": visible}, ensure_ascii=False)
        tail = stripper.flush()
        if tail:
            full_response += tail
            yield json.dumps({"type": "chunk", "data": tail}, ensure_ascii=False)

        history = self._get_history(client_id)
        history.append({"role": "assistant", "content": full_response})
        self._trim_history(client_id)
        asyncio.create_task(self._learn_from_turn(message, full_response))

        clean_text, emotion = self._extract_emotion(full_response)
        yield json.dumps(
            {"type": "done", "emotion": emotion, "text": clean_text}, ensure_ascii=False
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        yield json.dumps(
            {
                "type": "debug",
                "data": {
                    "phase": "chat_stream",
                    "elapsed_ms": elapsed_ms,
                    "think_stripped_chars": think_chars,
                    "response_len": len(full_response),
                    "model": str(self.llm.model),
                },
            },
            ensure_ascii=False,
        )

    async def _build_chat_messages(
        self, message: str, language: str, client_id: str
    ) -> list[dict]:
        memories = await self.memory.search(message, limit=3)
        system_prompt = self.soul.get_chat_prompt(language)
        if memories:
            memory_text = "\n".join([f"- {m['content']}" for m in memories])
            system_prompt += f"\n\n## Relevant Memories\n{memory_text}"
        history = self._get_history(client_id)
        history.append({"role": "user", "content": message})
        self._trim_history(client_id)
        return [{"role": "system", "content": system_prompt}, *history]

    # ── Assist mode (ReAct with confirmation) ───────────────────────

    async def _assist_mode_nonstream(
        self, message: str, language: str, client_id: str
    ) -> dict:
        """Non-streaming assist — single LLM call with tools, think=False."""
        messages = await self._build_assist_messages(message, language, client_id)
        tools = self.skills.get_tool_definitions()
        result = await self.llm.chat(messages, tools=tools, think=False, max_tokens=512)

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
                    {
                        "name": tc["function"]["name"],
                        "arguments": json.loads(tc["function"]["arguments"]),
                    }
                    for tc in result["tool_calls"]
                ],
            }
        else:
            content = result if isinstance(result, str) else result.get("content", "")
            history = self._get_history(client_id)
            history.append({"role": "assistant", "content": content})
            self._trim_history(client_id)
            clean_text, emotion = self._extract_emotion(content)
            return {"text": clean_text, "emotion": emotion, "mode": "assist"}

    async def _assist_mode_stream(self, message: str, language: str, client_id: str, use_fallback: bool = False):
        """Streaming assist — notice + planning with confirmation."""
        notice = self._get_assist_notice(language)
        yield json.dumps({"type": "notice", "text": notice}, ensure_ascii=False)

        messages = await self._build_assist_messages(message, language, client_id)
        tools = self.skills.get_tool_definitions()

        result = await self.llm.chat(messages, tools=tools, think=False, max_tokens=512, use_fallback=use_fallback)

        if isinstance(result, dict) and result.get("tool_calls"):
            plan_text = result.get("content", "")
            tool_calls = result["tool_calls"]

            self.pending_plans[client_id] = {
                "tool_calls": tool_calls,
                "plan_text": plan_text,
                "message": message,
                "language": language,
            }

            yield json.dumps(
                {
                    "type": "plan",
                    "description": self._format_plan(plan_text, tool_calls),
                    "tool_calls": [
                        {
                            "name": tc["function"]["name"],
                            "arguments": json.loads(tc["function"]["arguments"]),
                        }
                        for tc in tool_calls
                    ],
                    "awaiting_confirmation": True,
                },
                ensure_ascii=False,
            )
        else:
            content = result if isinstance(result, str) else result.get("content", "")
            history = self._get_history(client_id)
            history.append({"role": "assistant", "content": content})
            self._trim_history(client_id)
            clean_text, emotion = self._extract_emotion(content)
            yield json.dumps(
                {"type": "done", "emotion": emotion, "text": clean_text},
                ensure_ascii=False,
            )

    async def _build_assist_messages(
        self, message: str, language: str, client_id: str
    ) -> list[dict]:
        memories = await self.memory.search(message, limit=3)
        system_prompt = self.soul.get_assist_prompt(language)
        if memories:
            memory_text = "\n".join([f"- {m['content']}" for m in memories])
            system_prompt += f"\n\n## Relevant Memories\n{memory_text}"
        history = self._get_history(client_id)
        history.append({"role": "user", "content": message})
        self._trim_history(client_id)
        return [{"role": "system", "content": system_prompt}, *history]

    # ── Utilities ───────────────────────────────────────────────────

    def _get_assist_phrases(self) -> list[str]:
        """Return list of phrases that trigger assist mode."""
        return [
            "寄信",
            "發信",
            "寫信",
            "回信",
            "看信",
            "讀信",
            "查信",
            "最近的信",
            "收件",
            "看行程",
            "查行程",
            "建行程",
            "加行程",
            "排行程",
            "寫進行事曆",
            "加到行事曆",
            "建立行程",
            "建立檔案",
            "寫入檔案",
            "存檔",
            "搜尋",
            "查一下",
            "查一查",
            "查查",
            "幫我查",
            "幫我找",
            "幫我搜",
            "上網",
            "股價",
            "天氣",
            "新聞",
            "search",
            "google",
            "找圖",
            "找圖片",
            "找影片",
            "看圖",
            "看圖片",
            "下載",
            "打開",
            "開啟",
            "讀取",
            "讀檔",
            "看檔",
            "網頁",
            "網址",
            "圖片",
            "影片",
            "照片",
            "給我看",
            "幫我寄",
            "幫我寫",
            "幫我建",
            "幫我看",
            "幫我讀",
            "幫我排",
            "幫我加",
            "send email",
            "read email",
            "check email",
            "create event",
            "schedule",
            "截圖",
            "screenshot",
            "播放",
            "放音",
            "音效",
            "效果音",
            "雨聲",
            "環境音",
            "bgm",
            "sfx",
            "play",
            "sound",
            "停止播放",
            "停止音效",
            "語音",
            "voice",
            "切換語音",
            "想聽",
            "聽聽",
            "放一些",
            "放點",
            "再聽",
            "再播",
            "繼續播",
            "場景",
            "scene",
            "親密場景",
            "互動",
            "打手槍",
            "幫我弄",
            "口交",
            "做愛",
            "sex",
            "幫我擼",
            "舔",
            "吸",
            "插",
            "抱我",
            "摸我",
            "親我",
            "脫",
        ]

    def _classify_intent_fast(self, message: str) -> str:
        """Rule-based intent classification — zero LLM calls."""
        msg_lower = message.lower()
        if any(phrase in msg_lower for phrase in self._get_assist_phrases()):
            return "assist"
        return "chat"

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
        match = re.search(
            r"\[emotion:(happy|sad|angry|surprised|relaxed|neutral)\]\s*$", text
        )
        if match:
            return text[: match.start()].rstrip(), match.group(1)
        return text, "neutral"

    def _get_history(self, client_id: str) -> list:
        if client_id not in self.conversation_history:
            self.conversation_history[client_id] = []
        return self.conversation_history[client_id]

    def _trim_history(self, client_id: str):
        if len(self.conversation_history[client_id]) > self.max_history:
            self.conversation_history[client_id] = self.conversation_history[client_id][
                -self.max_history :
            ]

    async def _learn_from_turn(self, user_msg: str, assistant_msg: str):
        """Background: extract memories from conversation turn."""
        try:
            await self.memory.extract_from_conversation(
                user_msg, assistant_msg, self.llm
            )
        except Exception as e:
            logger.warning(f"Memory extraction failed: {e}")
