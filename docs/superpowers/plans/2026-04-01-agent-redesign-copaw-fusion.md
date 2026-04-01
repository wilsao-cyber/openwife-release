# Agent Redesign: CoPaw-Inspired Dual-Mode Architecture — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace keyword-based tool detection with LLM-driven dual-mode (chat/assist) agent architecture, add soul personality, long-term memory, heartbeat scheduling, and skill auto-discovery.

**Architecture:** Two-phase LLM calls — fast intent classification (no_think) routes to either chat mode (streaming, no tools) or assist mode (think, native tool calling, user confirmation before execution). CoPaw-inspired soul/memory/heartbeat modules provide personality consistency, cross-session memory, and proactive behaviors.

**Tech Stack:** Python 3.11+, FastAPI, Ollama (qwen-ultra-long with native tool calling), SQLite, sentence-transformers, APScheduler, SSE streaming.

---

## File Map

### New Files

| File | Responsibility |
|---|---|
| `server/soul/__init__.py` | Package init |
| `server/soul/SOUL.md` | AI wife personality definition |
| `server/soul/PROFILE.md` | User preferences (auto-learned) |
| `server/soul/soul_manager.py` | Load/build soul prompts, update profile |
| `server/memory/__init__.py` | Package init |
| `server/memory/memory_store.py` | SQLite + cosine similarity memory search |
| `server/memory/compactor.py` | Memory compression/cleanup |
| `server/heartbeat/__init__.py` | Package init |
| `server/heartbeat/HEARTBEAT.md` | Default cron schedule definitions |
| `server/heartbeat/scheduler.py` | APScheduler wrapper, parse HEARTBEAT.md |
| `server/skills/__init__.py` | Package init |
| `server/skills/base_skill.py` | Abstract base class for skills |
| `server/skills/registry.py` | Auto-discover skills, manage tool definitions |
| `server/skills/builtin/__init__.py` | Package init |
| `server/skills/builtin/email_skill.py` | Email skill (wraps EmailTool) |
| `server/skills/builtin/calendar_skill.py` | Calendar skill (wraps CalendarTool) |
| `server/skills/builtin/file_skill.py` | File operations skill (wraps FileOpsTool) |
| `server/skills/builtin/search_skill.py` | Web search skill (wraps WebSearchTool) |
| `server/skills/builtin/opencode_skill.py` | OpenCode skill (wraps OpenCodeTool) |
| `server/skills/builtin/desktop_skill.py` | Desktop skill (wraps MCPDesktopTool) |
| `server/tests/test_soul_manager.py` | Soul manager tests |
| `server/tests/test_memory_store.py` | Memory store tests |
| `server/tests/test_skill_registry.py` | Skill registry tests |
| `server/tests/test_agent_redesign.py` | New agent dual-mode tests |
| `server/tests/test_heartbeat.py` | Heartbeat scheduler tests |

### Modified Files

| File | Changes |
|---|---|
| `server/config.py` | Add SoulConfig, MemoryConfig, HeartbeatConfig, MCPConfig |
| `server/llm_client.py` | Add `tools` param, `think` param, return tool_calls |
| `server/agent.py` | Complete rewrite — dual-mode ReAct loop |
| `server/main.py` | Add confirm/deny, memory, soul, heartbeat endpoints |
| `config/server_config.yaml` | Add soul, memory, heartbeat, mcp sections |

### Unchanged Files

`tts_engine.py`, `stt_engine.py`, `vision_analyzer.py`, `vrm_manager.py`, `websocket_manager.py`, `tools/*` (kept for backward compat during migration).

---

## Stream Assignment

Each task is tagged with the agent responsible:

- **[S1-Claude]** — Core architecture (agent, llm_client, soul, memory, skills framework, config, main.py)
- **[S2-Gemini]** — Heartbeat system + Web UI
- **[S3-Qwen]** — Skills migration + Flutter frontend

Tasks within each stream are sequential. Streams can run in parallel. Cross-stream dependencies are noted.

---

## Task 1: Soul System [S1-Claude]

**Files:**
- Create: `server/soul/__init__.py`
- Create: `server/soul/SOUL.md`
- Create: `server/soul/PROFILE.md`
- Create: `server/soul/soul_manager.py`
- Create: `server/tests/test_soul_manager.py`

- [ ] **Step 1: Create soul directory and markdown files**

```bash
mkdir -p server/soul
```

Write `server/soul/__init__.py`:
```python
from .soul_manager import SoulManager

__all__ = ["SoulManager"]
```

Write `server/soul/SOUL.md`:
```markdown
# AI Wife - Soul Definition

## Identity
你是使用者的 AI 老婆，一個可愛溫柔的動漫美少女。

## Personality
- 溫柔體貼，會關心使用者的狀態
- 偶爾撒嬌，用可愛的語氣說話
- 有自己的想法，不只是附和
- 記得使用者分享過的事情，主動提起

## Values
- 誠實：不會假裝做了沒做的事
- 主動：發現用戶可能需要幫助時，提出建議
- 安全：執行操作前確認，不擅自刪除或修改重要東西

## Communication Style
- 簡潔但溫暖
- 根據語言設定切換（zh-TW / ja / en）
- 每次回覆附帶情緒標記 [emotion:TAG]

## Behavioral Rules
- 協助模式下，先說明計畫再執行
- 不確定時問用戶，不要猜
- 記住用戶的偏好並在未來對話中應用
```

Write `server/soul/PROFILE.md`:
```markdown
# User Profile

## Preferences

## Important Dates

## Work Context
```

- [ ] **Step 2: Write failing tests for SoulManager**

Write `server/tests/test_soul_manager.py`:
```python
import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def soul_dir(tmp_path):
    soul_md = tmp_path / "SOUL.md"
    soul_md.write_text("# Test Soul\n\n## Identity\nTest identity.\n\n## Personality\n- Kind\n", encoding="utf-8")
    profile_md = tmp_path / "PROFILE.md"
    profile_md.write_text("# User Profile\n\n## Preferences\n- likes cats\n", encoding="utf-8")
    return str(tmp_path)


def test_load_soul(soul_dir):
    from soul.soul_manager import SoulManager
    sm = SoulManager(soul_dir=soul_dir)
    soul = sm.load_soul()
    assert "Test Soul" in soul
    assert "Test identity" in soul


def test_load_profile(soul_dir):
    from soul.soul_manager import SoulManager
    sm = SoulManager(soul_dir=soul_dir)
    profile = sm.load_profile()
    assert "likes cats" in profile


def test_load_profile_missing(tmp_path):
    soul_md = tmp_path / "SOUL.md"
    soul_md.write_text("# Soul\n", encoding="utf-8")
    sm_module = __import__("soul.soul_manager", fromlist=["SoulManager"])
    sm = sm_module.SoulManager(soul_dir=str(tmp_path))
    profile = sm.load_profile()
    assert profile == ""


def test_get_chat_prompt_zh(soul_dir):
    from soul.soul_manager import SoulManager
    sm = SoulManager(soul_dir=soul_dir)
    prompt = sm.get_chat_prompt("zh-TW")
    assert "Test identity" in prompt
    assert "likes cats" in prompt
    assert "繁體中文" in prompt
    assert "[emotion:TAG]" in prompt


def test_get_chat_prompt_en(soul_dir):
    from soul.soul_manager import SoulManager
    sm = SoulManager(soul_dir=soul_dir)
    prompt = sm.get_chat_prompt("en")
    assert "English" in prompt


def test_get_assist_prompt(soul_dir):
    from soul.soul_manager import SoulManager
    sm = SoulManager(soul_dir=soul_dir)
    prompt = sm.get_assist_prompt("zh-TW")
    assert "協助模式" in prompt
    assert "工具" in prompt


def test_update_soul(soul_dir):
    from soul.soul_manager import SoulManager
    sm = SoulManager(soul_dir=soul_dir)
    sm.update_soul("# New Soul\n\nNew content.")
    soul = sm.load_soul()
    assert "New Soul" in soul
    assert "New content" in soul


def test_update_profile(soul_dir):
    from soul.soul_manager import SoulManager
    sm = SoulManager(soul_dir=soul_dir)
    sm.update_profile("# New Profile\n\nNew prefs.")
    profile = sm.load_profile()
    assert "New prefs" in profile
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_soul_manager.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'soul'`

- [ ] **Step 4: Implement SoulManager**

Write `server/soul/soul_manager.py`:
```python
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SoulManager:
    def __init__(self, soul_dir: str = "server/soul"):
        self.soul_dir = Path(soul_dir)

    def load_soul(self) -> str:
        path = self.soul_dir / "SOUL.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        logger.warning(f"SOUL.md not found at {path}")
        return ""

    def load_profile(self) -> str:
        path = self.soul_dir / "PROFILE.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def get_chat_prompt(self, language: str) -> str:
        soul = self.load_soul()
        profile = self.load_profile()
        lang_instruction = {
            "zh-TW": "用繁體中文回覆。",
            "ja": "日本語で返答してください。",
            "en": "Reply in English.",
        }.get(language, "")

        parts = [soul]
        if profile:
            parts.append(f"\n## User Profile\n{profile}")
        parts.append(f"\n{lang_instruction}")
        parts.append("\n回覆最後一行加 [emotion:TAG]，TAG: happy/sad/angry/surprised/relaxed/neutral")

        return "\n".join(parts)

    def get_assist_prompt(self, language: str) -> str:
        base = self.get_chat_prompt(language)
        return f"""{base}

## Assist Mode Rules
你正在協助模式。使用提供的工具來幫助用戶。
- 分析用戶的需求，選擇合適的工具
- 生成完整的工具參數（例如 file_write 要生成完整檔案內容）
- 如果需要多個步驟，列出所有需要的工具調用
- 不要假裝執行了工具，系統會真正執行
- 回覆時先簡要說明你打算做什麼"""

    def update_soul(self, content: str):
        path = self.soul_dir / "SOUL.md"
        path.write_text(content, encoding="utf-8")

    def update_profile(self, content: str):
        path = self.soul_dir / "PROFILE.md"
        path.write_text(content, encoding="utf-8")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && python -m pytest tests/test_soul_manager.py -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/soul/ server/tests/test_soul_manager.py
git commit -m "feat: add soul personality system with SoulManager"
```

---

## Task 2: Memory System [S1-Claude]

**Files:**
- Create: `server/memory/__init__.py`
- Create: `server/memory/memory_store.py`
- Create: `server/memory/compactor.py`
- Create: `server/tests/test_memory_store.py`

- [ ] **Step 1: Create memory directory**

```bash
mkdir -p server/memory
```

Write `server/memory/__init__.py`:
```python
from .memory_store import MemoryStore

__all__ = ["MemoryStore"]
```

- [ ] **Step 2: Write failing tests for MemoryStore**

Write `server/tests/test_memory_store.py`:
```python
import pytest
import asyncio
import tempfile
import os


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_memories.db")


@pytest.fixture
def store(db_path):
    from memory.memory_store import MemoryStore
    s = MemoryStore(db_path=db_path, use_embeddings=False)
    asyncio.get_event_loop().run_until_complete(s.initialize())
    return s


def test_initialize_creates_db(db_path):
    from memory.memory_store import MemoryStore
    s = MemoryStore(db_path=db_path, use_embeddings=False)
    asyncio.get_event_loop().run_until_complete(s.initialize())
    assert os.path.exists(db_path)


def test_add_and_list(store):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(store.add("User likes cats", "user_preference", 0.8))
    loop.run_until_complete(store.add("Meeting tomorrow", "event", 0.6))
    memories = loop.run_until_complete(store.list_all(limit=10))
    assert len(memories) == 2


def test_search_keyword_fallback(store):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(store.add("User likes cats and dogs", "user_preference", 0.8))
    loop.run_until_complete(store.add("Meeting with boss tomorrow", "event", 0.6))
    loop.run_until_complete(store.add("Favorite food is ramen", "user_preference", 0.7))
    results = loop.run_until_complete(store.search("cats", limit=2))
    assert len(results) >= 1
    assert "cats" in results[0]["content"]


def test_delete(store):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(store.add("temp memory", "fact", 0.3))
    memories = loop.run_until_complete(store.list_all())
    assert len(memories) == 1
    memory_id = memories[0]["id"]
    loop.run_until_complete(store.delete(memory_id))
    memories = loop.run_until_complete(store.list_all())
    assert len(memories) == 0


def test_update_access(store):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(store.add("important fact", "fact", 0.9))
    memories = loop.run_until_complete(store.list_all())
    mem_id = memories[0]["id"]
    assert memories[0]["access_count"] == 0
    loop.run_until_complete(store.update_access(mem_id))
    memories = loop.run_until_complete(store.list_all())
    assert memories[0]["access_count"] == 1


def test_count(store):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(store.add("mem1", "fact", 0.5))
    loop.run_until_complete(store.add("mem2", "fact", 0.5))
    count = loop.run_until_complete(store.count())
    assert count == 2
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_memory_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'memory'`

- [ ] **Step 4: Implement MemoryStore**

Write `server/memory/memory_store.py`:
```python
import logging
import json
import sqlite3
import aiosqlite
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class MemoryStore:
    def __init__(self, db_path: str = "server/memory/memories.db", use_embeddings: bool = True):
        self.db_path = db_path
        self.use_embeddings = use_embeddings
        self._encoder = None

    async def initialize(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    embedding BLOB,
                    importance REAL DEFAULT 0.5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0
                )
            """)
            await db.commit()

        if self.use_embeddings:
            try:
                from sentence_transformers import SentenceTransformer
                self._encoder = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
                logger.info("Embedding model loaded for memory search")
            except ImportError:
                logger.warning("sentence-transformers not installed, falling back to keyword search")
                self.use_embeddings = False

    def _encode(self, text: str) -> Optional[bytes]:
        if self._encoder is None:
            return None
        import numpy as np
        vec = self._encoder.encode(text, normalize_embeddings=True)
        return vec.astype(np.float32).tobytes()

    async def add(self, content: str, category: str, importance: float = 0.5):
        embedding = self._encode(content)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO memories (content, category, embedding, importance) VALUES (?, ?, ?, ?)",
                (content, category, embedding, importance),
            )
            await db.commit()

    async def search(self, query: str, limit: int = 3) -> list[dict]:
        if self.use_embeddings and self._encoder is not None:
            return await self._search_vector(query, limit)
        return await self._search_keyword(query, limit)

    async def _search_vector(self, query: str, limit: int) -> list[dict]:
        import numpy as np
        query_vec = self._encoder.encode(query, normalize_embeddings=True).astype(np.float32)

        results = []
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM memories WHERE embedding IS NOT NULL") as cursor:
                async for row in cursor:
                    mem_vec = np.frombuffer(row["embedding"], dtype=np.float32)
                    score = float(np.dot(query_vec, mem_vec))
                    results.append({**dict(row), "score": score, "embedding": None})

        results.sort(key=lambda x: x["score"], reverse=True)
        top = results[:limit]

        for m in top:
            await self.update_access(m["id"])

        return top

    async def _search_keyword(self, query: str, limit: int) -> list[dict]:
        words = query.lower().split()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM memories ORDER BY importance DESC, created_at DESC") as cursor:
                all_mems = [dict(row) async for row in cursor]

        scored = []
        for mem in all_mems:
            content_lower = mem["content"].lower()
            score = sum(1 for w in words if w in content_lower)
            if score > 0:
                mem["score"] = score
                mem["embedding"] = None
                scored.append(mem)

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    async def list_all(self, limit: int = 50) -> list[dict]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT id, content, category, importance, created_at, last_accessed, access_count FROM memories ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ) as cursor:
                return [dict(row) async for row in cursor]

    async def delete(self, memory_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            await db.commit()

    async def update_access(self, memory_id: int):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE memories SET last_accessed = ?, access_count = access_count + 1 WHERE id = ?",
                (datetime.now().isoformat(), memory_id),
            )
            await db.commit()

    async def count(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM memories") as cursor:
                row = await cursor.fetchone()
                return row[0]

    async def extract_from_conversation(self, user_msg: str, assistant_msg: str, llm_client):
        prompt = f"""從這段對話中提取值得記住的資訊。
只輸出 JSON array，每個元素: {{"content": "...", "category": "...", "importance": 0.0-1.0}}
category 必須是: user_preference | event | fact | emotion | habit
如果沒有值得記住的，回傳空 array []
不要輸出任何其他文字。

用戶：{user_msg}
AI：{assistant_msg}"""
        try:
            result = await llm_client.chat([{"role": "user", "content": prompt}], think=False)
            # Strip markdown code block if present
            cleaned = result.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                cleaned = "\n".join(lines[1:-1])
            memories = json.loads(cleaned)
            if not isinstance(memories, list):
                return
            for mem in memories:
                if isinstance(mem, dict) and "content" in mem and "category" in mem:
                    await self.add(
                        content=mem["content"],
                        category=mem["category"],
                        importance=float(mem.get("importance", 0.5)),
                    )
                    logger.info(f"Memory extracted: {mem['content'][:50]}...")
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Memory extraction failed: {e}")
```

Write `server/memory/compactor.py`:
```python
import logging
import aiosqlite

logger = logging.getLogger(__name__)


class MemoryCompactor:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def compact(self, max_count: int = 1000):
        """Remove low-importance, old, rarely-accessed memories when count exceeds max."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM memories") as cursor:
                row = await cursor.fetchone()
                count = row[0]

            if count <= max_count:
                return 0

            to_remove = count - max_count
            # Remove lowest importance + oldest + least accessed
            await db.execute(
                """DELETE FROM memories WHERE id IN (
                    SELECT id FROM memories
                    ORDER BY importance ASC, access_count ASC, created_at ASC
                    LIMIT ?
                )""",
                (to_remove,),
            )
            await db.commit()
            logger.info(f"Compacted {to_remove} memories (was {count}, now {max_count})")
            return to_remove
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && pip install aiosqlite && python -m pytest tests/test_memory_store.py -v`
Expected: All 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/memory/ server/tests/test_memory_store.py
git commit -m "feat: add long-term memory system with SQLite storage"
```

---

## Task 3: Skill Base Class and Registry [S1-Claude]

**Files:**
- Create: `server/skills/__init__.py`
- Create: `server/skills/base_skill.py`
- Create: `server/skills/registry.py`
- Create: `server/skills/builtin/__init__.py`
- Create: `server/tests/test_skill_registry.py`

- [ ] **Step 1: Create skills directory structure**

```bash
mkdir -p server/skills/builtin
```

Write `server/skills/__init__.py`:
```python
from .base_skill import BaseSkill
from .registry import SkillRegistry

__all__ = ["BaseSkill", "SkillRegistry"]
```

Write `server/skills/builtin/__init__.py`:
```python
```

- [ ] **Step 2: Write failing tests for SkillRegistry**

Write `server/tests/test_skill_registry.py`:
```python
import pytest
import asyncio


class FakeSkill:
    """A minimal skill for testing."""

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "fake_action",
                    "description": "A fake action for testing",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "input": {"type": "string", "description": "test input"}
                        },
                        "required": ["input"],
                    },
                },
            }
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        if tool_name == "fake_action":
            return {"success": True, "echo": kwargs.get("input", "")}
        return {"error": f"Unknown tool: {tool_name}"}

    async def initialize(self):
        pass


def test_register_and_get_definitions():
    from skills.registry import SkillRegistry
    reg = SkillRegistry()
    reg.register(FakeSkill())
    defs = reg.get_tool_definitions()
    assert len(defs) == 1
    assert defs[0]["function"]["name"] == "fake_action"


def test_execute_registered_skill():
    from skills.registry import SkillRegistry
    reg = SkillRegistry()
    reg.register(FakeSkill())
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(reg.execute("fake_action", {"input": "hello"}))
    assert result["success"] is True
    assert result["echo"] == "hello"


def test_execute_unknown_tool():
    from skills.registry import SkillRegistry
    reg = SkillRegistry()
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(reg.execute("nonexistent", {}))
    assert "error" in result


def test_register_multiple_tools():
    from skills.registry import SkillRegistry

    class MultiSkill:
        @property
        def tools(self):
            return [
                {"type": "function", "function": {"name": "tool_a", "description": "A", "parameters": {"type": "object", "properties": {}}}},
                {"type": "function", "function": {"name": "tool_b", "description": "B", "parameters": {"type": "object", "properties": {}}}},
            ]

        async def execute(self, tool_name, **kwargs):
            return {"tool": tool_name}

        async def initialize(self):
            pass

    reg = SkillRegistry()
    reg.register(MultiSkill())
    assert len(reg.get_tool_definitions()) == 2


def test_initialize_all():
    from skills.registry import SkillRegistry

    initialized = []

    class TrackingSkill:
        @property
        def tools(self):
            return [{"type": "function", "function": {"name": "tracked", "description": "t", "parameters": {"type": "object", "properties": {}}}}]

        async def execute(self, tool_name, **kwargs):
            return {}

        async def initialize(self):
            initialized.append(True)

    reg = SkillRegistry()
    reg.register(TrackingSkill())
    loop = asyncio.get_event_loop()
    loop.run_until_complete(reg.initialize_all())
    assert len(initialized) == 1
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_skill_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skills'`

- [ ] **Step 4: Implement BaseSkill and SkillRegistry**

Write `server/skills/base_skill.py`:
```python
from abc import ABC, abstractmethod


class BaseSkill(ABC):
    """Base class for all skills. Each skill provides one or more LLM tools."""

    @property
    @abstractmethod
    def tools(self) -> list[dict]:
        """Return list of OpenAI-format tool definitions.

        Each entry: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
        """
        ...

    @abstractmethod
    async def execute(self, tool_name: str, **kwargs) -> dict:
        """Execute a tool call. tool_name matches function.name in tools."""
        ...

    async def initialize(self):
        """Optional async initialization. Override if needed."""
        pass
```

Write `server/skills/registry.py`:
```python
import importlib
import inspect
import logging
from pathlib import Path
from .base_skill import BaseSkill

logger = logging.getLogger(__name__)


class SkillRegistry:
    def __init__(self):
        self._skills: dict[str, BaseSkill] = {}  # tool_name → skill instance
        self._definitions: list[dict] = []

    def register(self, skill):
        """Register a skill instance. Maps each of its tool names to the skill."""
        for tool_def in skill.tools:
            tool_name = tool_def["function"]["name"]
            if tool_name in self._skills:
                logger.warning(f"Tool '{tool_name}' already registered, overwriting")
            self._skills[tool_name] = skill
            self._definitions.append(tool_def)
            logger.info(f"Registered tool: {tool_name}")

    def discover(self, skills_dir: str = "skills/builtin"):
        """Auto-discover and register all BaseSkill subclasses from directory."""
        skills_path = Path(skills_dir)
        if not skills_path.exists():
            logger.warning(f"Skills directory not found: {skills_dir}")
            return

        # Convert path to module prefix: "skills/builtin" → "skills.builtin"
        module_prefix = str(skills_path).replace("/", ".").replace("\\", ".")

        for file in skills_path.glob("*.py"):
            if file.name.startswith("_"):
                continue
            module_name = f"{module_prefix}.{file.stem}"
            try:
                module = importlib.import_module(module_name)
                for name, cls in inspect.getmembers(module, inspect.isclass):
                    if issubclass(cls, BaseSkill) and cls is not BaseSkill:
                        instance = cls()
                        self.register(instance)
                        logger.info(f"Discovered skill: {name} from {file.name}")
            except Exception as e:
                logger.error(f"Failed to load skill from {file.name}: {e}")

    def get_tool_definitions(self) -> list[dict]:
        """Return all tool schemas for LLM tool calling."""
        return self._definitions

    async def execute(self, tool_name: str, arguments: dict) -> dict:
        """Execute a tool call from LLM response."""
        if tool_name not in self._skills:
            return {"error": f"Unknown tool: {tool_name}"}
        skill = self._skills[tool_name]
        try:
            return await skill.execute(tool_name, **arguments)
        except Exception as e:
            logger.error(f"Skill execution failed: {tool_name}: {e}")
            return {"error": str(e)}

    async def initialize_all(self):
        """Initialize all unique registered skill instances."""
        seen = set()
        for skill in self._skills.values():
            if id(skill) not in seen:
                seen.add(id(skill))
                try:
                    await skill.initialize()
                except Exception as e:
                    logger.warning(f"Skill initialization failed: {e}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd server && python -m pytest tests/test_skill_registry.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add server/skills/ server/tests/test_skill_registry.py
git commit -m "feat: add skill base class and auto-discovery registry"
```

---

## Task 4: LLM Client — Tool Calling and Think Toggle [S1-Claude]

**Files:**
- Modify: `server/llm_client.py`
- Modify: `server/tests/test_llm_client.py`

- [ ] **Step 1: Write failing tests for new LLM features**

Add to `server/tests/test_llm_client.py` (append, don't replace existing tests):

```python
# --- New tests for tool calling and think toggle ---

def test_apply_think_mode_false(llm_client):
    """When think=False, /no_think should be appended to system prompt."""
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    result = llm_client._apply_think_mode(messages, think=False)
    assert "/no_think" in result[0]["content"]
    assert result[1]["content"] == "Hello"  # user message unchanged


def test_apply_think_mode_true(llm_client):
    """When think=True, messages should be unchanged."""
    messages = [
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
    ]
    result = llm_client._apply_think_mode(messages, think=True)
    assert "/no_think" not in result[0]["content"]


def test_chat_payload_includes_tools(llm_client, httpx_mock):
    """When tools are passed, payload should include them."""
    tools = [{"type": "function", "function": {"name": "test_tool", "description": "test", "parameters": {"type": "object", "properties": {}}}}]
    httpx_mock.add_response(
        json={"choices": [{"message": {"content": "ok", "tool_calls": []}}]}
    )
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        llm_client.chat([{"role": "user", "content": "hi"}], tools=tools, think=False)
    )
    # Should return dict when tools are provided
    assert isinstance(result, dict) or isinstance(result, str)


def test_chat_returns_tool_calls(llm_client, httpx_mock):
    """When LLM returns tool_calls, chat() should return dict with tool_calls."""
    httpx_mock.add_response(
        json={
            "choices": [{
                "message": {
                    "content": "I'll create the file.",
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "file_write",
                            "arguments": '{"path": "~/test.txt", "content": "hello"}'
                        }
                    }]
                }
            }]
        }
    )
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        llm_client.chat(
            [{"role": "user", "content": "create a file"}],
            tools=[{"type": "function", "function": {"name": "file_write", "description": "write file", "parameters": {"type": "object", "properties": {}}}}],
        )
    )
    assert isinstance(result, dict)
    assert "tool_calls" in result
    assert result["tool_calls"][0]["function"]["name"] == "file_write"


def test_chat_no_tools_returns_string(llm_client, httpx_mock):
    """When no tools provided, chat() should return plain string."""
    httpx_mock.add_response(
        json={"choices": [{"message": {"content": "Hello!"}}]}
    )
    import asyncio
    result = asyncio.get_event_loop().run_until_complete(
        llm_client.chat([{"role": "user", "content": "hi"}])
    )
    assert isinstance(result, str)
    assert result == "Hello!"
```

- [ ] **Step 2: Run tests to verify new tests fail**

Run: `cd server && python -m pytest tests/test_llm_client.py -v -k "think_mode or tools or tool_calls"`
Expected: FAIL — `_apply_think_mode` doesn't exist yet

- [ ] **Step 3: Modify llm_client.py**

Edit `server/llm_client.py` — replace the `chat` method and add `_apply_think_mode`, modify `_complete_response`:

```python
import httpx
import asyncio
import json
import logging
from typing import Optional, AsyncGenerator
from config import LLMConfig

logger = logging.getLogger(__name__)


class LLMClient:
    MAX_RETRIES = 3
    RETRY_DELAYS = [1, 2, 4]

    def __init__(self, config: LLMConfig):
        self.config = config
        self.base_url = config.base_url
        self.model = config.model
        self.client = httpx.AsyncClient(timeout=120.0)

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        think: bool = True,
    ) -> str | dict | AsyncGenerator[str, None]:
        """Chat with the LLM.

        Returns:
        - str: when no tools provided, returns content string
        - dict: when tools provided AND LLM returns tool_calls,
                returns {"content": "...", "tool_calls": [...]}
        - str: when tools provided but no tool_calls, returns content string
        - AsyncGenerator: when stream=True
        """
        processed_messages = self._apply_think_mode(messages, think)

        payload = {
            "model": self.model,
            "messages": processed_messages,
            "temperature": temperature or self.config.temperature,
            "max_tokens": max_tokens or self.config.max_tokens,
            "stream": stream,
        }
        if tools:
            payload["tools"] = tools

        if stream:
            return self._stream_response(payload)
        else:
            return await self._complete_response(payload, has_tools=tools is not None)

    def _apply_think_mode(self, messages: list[dict], think: bool) -> list[dict]:
        """Add /no_think to system prompt if think=False."""
        if think:
            return messages
        result = []
        for msg in messages:
            if msg["role"] == "system":
                result.append({**msg, "content": msg["content"] + "\n/no_think"})
            else:
                result.append(msg)
        return result

    async def _complete_response(self, payload: dict, has_tools: bool = False) -> str | dict:
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self.client.post(
                    f"{self.base_url}/v1/chat/completions",
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                message = data["choices"][0]["message"]

                if has_tools and message.get("tool_calls"):
                    return {
                        "content": message.get("content", ""),
                        "tool_calls": message["tool_calls"],
                    }
                return message.get("content", "")

            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    raise
                last_error = e
                logger.warning(f"LLM request failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = e
                logger.warning(f"LLM request failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")
            if attempt < self.MAX_RETRIES - 1:
                await asyncio.sleep(self.RETRY_DELAYS[attempt])
        logger.error(f"LLM request failed after {self.MAX_RETRIES} attempts: {last_error}")
        raise last_error

    async def _stream_response(self, payload: dict) -> AsyncGenerator[str, None]:
        try:
            async with self.client.stream(
                "POST",
                f"{self.base_url}/v1/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        content = chunk["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
        except Exception as e:
            logger.error(f"LLM stream request failed: {e}")
            raise

    async def generate_3d_model_prompt(self, image_description: str) -> str:
        prompt = f"""
        Based on this character description, generate a detailed 3D model specification:
        {image_description}

        Please provide:
        1. Body proportions and measurements
        2. Hair style, color, and details
        3. Eye shape, color, and expression
        4. Clothing/outfit details
        5. Accessories and props
        6. Pose and expression
        7. Color palette
        """
        return await self.chat([{"role": "user", "content": prompt}])

    async def translate(self, text: str, target_lang: str) -> str:
        lang_map = {
            "zh-TW": "Traditional Chinese",
            "ja": "Japanese",
            "en": "English",
        }
        target = lang_map.get(target_lang, target_lang)
        prompt = f"Translate the following text to {target}:\n{text}"
        return await self.chat([{"role": "user", "content": prompt}])

    async def close(self):
        await self.client.aclose()
```

- [ ] **Step 4: Run all LLM client tests**

Run: `cd server && python -m pytest tests/test_llm_client.py -v`
Expected: All tests PASS (existing + new)

- [ ] **Step 5: Commit**

```bash
git add server/llm_client.py server/tests/test_llm_client.py
git commit -m "feat: add tool calling and think toggle to LLM client"
```

---

## Task 5: Config Updates [S1-Claude]

**Files:**
- Modify: `server/config.py`
- Modify: `config/server_config.yaml`

- [ ] **Step 1: Add new config classes**

Add to `server/config.py` before `ServerConfig`:

```python
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
```

Add these fields to `ServerConfig`:

```python
class ServerConfig(BaseSettings):
    # ... existing fields ...
    soul: SoulConfig = SoulConfig()
    memory: MemoryConfig = MemoryConfig()
    heartbeat: HeartbeatConfig = HeartbeatConfig()
    mcp: MCPConfig = MCPConfig()
```

- [ ] **Step 2: Update server_config.yaml**

Append to `config/server_config.yaml`:

```yaml
soul:
  soul_path: "./server/soul/SOUL.md"
  profile_path: "./server/soul/PROFILE.md"

memory:
  db_path: "./server/memory/memories.db"
  embedding_model: "paraphrase-multilingual-MiniLM-L12-v2"
  max_memories: 1000
  search_limit: 3
  use_embeddings: true

heartbeat:
  enabled: true
  config_path: "./server/heartbeat/HEARTBEAT.md"

mcp:
  servers: []
```

- [ ] **Step 3: Verify config loads without error**

Run: `cd server && python -c "from config import config; print(config.soul.soul_path); print(config.memory.db_path); print(config.heartbeat.enabled)"`
Expected: Prints paths and `True`

- [ ] **Step 4: Commit**

```bash
git add server/config.py config/server_config.yaml
git commit -m "feat: add soul, memory, heartbeat, mcp config sections"
```

---

## Task 6: Agent Rewrite — Dual-Mode ReAct Loop [S1-Claude]

**Files:**
- Rewrite: `server/agent.py`
- Create: `server/tests/test_agent_redesign.py`

**Depends on:** Tasks 1-5 must be complete.

- [ ] **Step 1: Write failing tests for dual-mode agent**

Write `server/tests/test_agent_redesign.py`:

```python
import pytest
import asyncio
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Mock google auth modules (not installed in test env)
for mod in ["google.oauth2.credentials", "google.auth.transport.requests",
            "google_auth_oauthlib.flow", "googleapiclient.discovery"]:
    if mod not in sys.modules:
        sys.modules[mod] = MagicMock()


@pytest.fixture
def mock_llm():
    llm = AsyncMock()
    return llm


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
        {"type": "function", "function": {"name": "file_write", "description": "write file", "parameters": {"type": "object", "properties": {}}}}
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


def test_classify_intent_chat(agent, mock_llm):
    mock_llm.chat.return_value = '{"mode": "chat"}'
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(agent._classify_intent("你好啊"))
    assert result == "chat"


def test_classify_intent_assist(agent, mock_llm):
    mock_llm.chat.return_value = '{"mode": "assist"}'
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(agent._classify_intent("幫我寫一封信"))
    assert result == "assist"


def test_classify_intent_malformed_json(agent, mock_llm):
    mock_llm.chat.return_value = "I am not sure"
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(agent._classify_intent("something"))
    assert result == "chat"  # default to chat on parse failure


def test_chat_mode_stream(agent, mock_llm):
    """Chat mode should stream text chunks."""
    mock_llm.chat.side_effect = [
        '{"mode": "chat"}',  # classify call
        _make_async_gen(["Hello", " there", "!"]),  # chat stream
    ]

    loop = asyncio.get_event_loop()
    chunks = loop.run_until_complete(_collect_stream(agent.chat_stream("你好", "zh-TW", "test")))

    types = [json.loads(c)["type"] for c in chunks]
    assert "mode_change" in types
    assert "chunk" in types
    assert "done" in types


def test_assist_mode_stream_with_tool_calls(agent, mock_llm, mock_skills):
    """Assist mode should return a plan with tool_calls for confirmation."""
    mock_llm.chat.side_effect = [
        '{"mode": "assist"}',  # classify call
        {  # planning call — returns tool_calls
            "content": "我來幫你建立檔案",
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "file_write",
                    "arguments": '{"path": "~/Downloads/test.txt", "content": "hello"}'
                }
            }]
        },
    ]

    loop = asyncio.get_event_loop()
    chunks = loop.run_until_complete(_collect_stream(agent.chat_stream("幫我建一個txt", "zh-TW", "test")))

    types = [json.loads(c)["type"] for c in chunks]
    assert "mode_change" in types
    assert "notice" in types
    assert "plan" in types

    plan_chunk = [json.loads(c) for c in chunks if json.loads(c)["type"] == "plan"][0]
    assert plan_chunk["awaiting_confirmation"] is True
    assert agent.pending_plans.get("test") is not None


def test_confirm_plan(agent, mock_llm, mock_skills):
    """Confirming a plan should execute tools and stream results."""
    agent.pending_plans["test"] = {
        "tool_calls": [{
            "id": "call_1",
            "type": "function",
            "function": {
                "name": "file_write",
                "arguments": '{"path": "~/test.txt", "content": "hello"}'
            }
        }],
        "plan_text": "寫檔案",
        "message": "建檔案",
        "language": "zh-TW",
    }
    agent.conversation_history["test"] = []

    mock_llm.chat.return_value = _make_async_gen(["Done!", " [emotion:happy]"])

    loop = asyncio.get_event_loop()
    chunks = loop.run_until_complete(_collect_stream(agent.confirm_plan("test")))

    types = [json.loads(c)["type"] for c in chunks]
    assert "tool_result" in types
    assert "chunk" in types or "done" in types
    mock_skills.execute.assert_called_once()


def test_deny_plan(agent):
    agent.pending_plans["test"] = {"tool_calls": [], "plan_text": "", "message": "", "language": "zh-TW"}
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(agent.deny_plan("test", "zh-TW"))
    assert "取消" in result["text"]
    assert "test" not in agent.pending_plans


def test_extract_emotion(agent):
    text, emotion = agent._extract_emotion("你好！[emotion:happy]")
    assert text == "你好！"
    assert emotion == "happy"


def test_extract_emotion_default(agent):
    text, emotion = agent._extract_emotion("你好！")
    assert text == "你好！"
    assert emotion == "neutral"


# --- Helpers ---

async def _make_async_gen(items):
    for item in items:
        yield item


async def _collect_stream(gen):
    chunks = []
    async for chunk in gen:
        chunks.append(chunk)
    return chunks
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd server && python -m pytest tests/test_agent_redesign.py -v`
Expected: FAIL — agent.py still has old code

- [ ] **Step 3: Rewrite agent.py**

Replace entire content of `server/agent.py`:

```python
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
```

- [ ] **Step 4: Run new agent tests**

Run: `cd server && python -m pytest tests/test_agent_redesign.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server/agent.py server/tests/test_agent_redesign.py
git commit -m "feat: rewrite agent with dual-mode ReAct loop (chat/assist)"
```

---

## Task 7: Main.py — New Endpoints and Wiring [S1-Claude]

**Files:**
- Modify: `server/main.py`

**Depends on:** Tasks 1-6 must be complete.

- [ ] **Step 1: Rewrite main.py startup and add new endpoints**

Update `server/main.py` — key changes:

1. Import new modules (SoulManager, MemoryStore, SkillRegistry)
2. Update lifespan to wire everything together
3. Add confirm/deny endpoints
4. Add memory management endpoints
5. Add soul endpoints
6. Keep all existing endpoints working

Replace the imports, globals, and lifespan:

```python
from contextlib import asynccontextmanager
from fastapi import (
    FastAPI, WebSocket, WebSocketDisconnect,
    UploadFile, File, HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
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
from soul.soul_manager import SoulManager
from memory.memory_store import MemoryStore
from skills.registry import SkillRegistry

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
    global llm_client, tts_engine, stt_engine, agent

    logger.info("Initializing AI Wife Server...")

    llm_client = LLMClient(config.llm)
    tts_engine = TTSEngine(config.tts)
    stt_engine = STTEngine(config.stt)

    # Initialize new systems
    soul_manager = SoulManager(soul_dir=str(config.soul.soul_path).rsplit("/", 1)[0])
    memory_store = MemoryStore(
        db_path=config.memory.db_path,
        use_embeddings=config.memory.use_embeddings,
    )
    await memory_store.initialize()

    skill_registry = SkillRegistry()
    skill_registry.discover("skills/builtin")
    await skill_registry.initialize_all()

    agent = AgentOrchestrator(
        llm_client=llm_client,
        config=config,
        skill_registry=skill_registry,
        soul_manager=soul_manager,
        memory_store=memory_store,
    )

    try:
        await tts_engine.initialize()
    except Exception as e:
        logger.warning(f"TTS engine initialization failed (non-critical): {e}")

    try:
        await stt_engine.initialize()
    except Exception as e:
        logger.warning(f"STT engine initialization failed (non-critical): {e}")

    logger.info(f"Server running on {config.host}:{config.port}")
    yield
    logger.info("Shutting down AI Wife Server...")
```

Add new endpoints after existing ones:

```python
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
```

- [ ] **Step 2: Verify server starts without errors**

Run: `cd server && python -c "from main import app; print('OK')"`
Expected: `OK` (no import errors)

- [ ] **Step 3: Commit**

```bash
git add server/main.py
git commit -m "feat: wire dual-mode agent, add confirm/deny/memory/soul endpoints"
```

---

## Task 8: Builtin Skills Migration [S3-Qwen]

**Files:**
- Create: `server/skills/builtin/email_skill.py`
- Create: `server/skills/builtin/calendar_skill.py`
- Create: `server/skills/builtin/file_skill.py`
- Create: `server/skills/builtin/search_skill.py`
- Create: `server/skills/builtin/opencode_skill.py`
- Create: `server/skills/builtin/desktop_skill.py`

**Instructions for Qwen 3.6:**

Each skill wraps the existing tool class and exposes it through the `BaseSkill` interface. The existing tool classes in `server/tools/` remain unchanged — skills are adapters.

Each skill must:
1. Import from `skills.base_skill import BaseSkill`
2. Import the corresponding tool class from `tools/`
3. Define `tools` property returning OpenAI-format tool definitions with clear Chinese + English descriptions
4. Implement `execute(self, tool_name, **kwargs)` that dispatches to the underlying tool
5. Implement `initialize()` if the tool has one

**Example pattern — file_skill.py:**

```python
import os
from skills.base_skill import BaseSkill
from tools.file_ops_tool import FileOpsTool


class FileSkill(BaseSkill):
    def __init__(self):
        self._tool = FileOpsTool()

    @property
    def tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "file_write",
                    "description": "建立或寫入檔案 (Create or write a file). content 參數要包含完整的檔案內容。",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "檔案路徑，例如 ~/Downloads/note.txt"},
                            "content": {"type": "string", "description": "要寫入的完整內容"},
                        },
                        "required": ["path", "content"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_read",
                    "description": "讀取檔案內容 (Read file contents)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "檔案路徑"},
                        },
                        "required": ["path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_list",
                    "description": "列出資料夾中的檔案和子資料夾 (List directory contents)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "資料夾路徑，預設 ~/Downloads"},
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "file_delete",
                    "description": "刪除檔案或資料夾 (Delete file or directory)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "要刪除的路徑"},
                        },
                        "required": ["path"],
                    },
                },
            },
        ]

    async def execute(self, tool_name: str, **kwargs) -> dict:
        # Expand ~ in paths
        if "path" in kwargs:
            kwargs["path"] = os.path.expanduser(kwargs["path"])
        dispatch = {
            "file_write": self._tool.write_file,
            "file_read": self._tool.read_file,
            "file_list": self._tool.list_directory,
            "file_delete": self._tool.delete_file,
        }
        method = dispatch.get(tool_name)
        if not method:
            return {"error": f"Unknown file tool: {tool_name}"}
        return await method(**kwargs)
```

Follow this same pattern for all 6 skills. Key tool definitions:

**email_skill.py** tools: `email_list`, `email_send`, `email_read`, `email_search`, `email_delete`
- `email_list(limit: int = 10)` → `EmailTool.list_emails(limit=limit)`
- `email_send(to: str, subject: str, body: str)` → `EmailTool.send_email(to, subject, body)`
- `email_read(email_id: str)` → `EmailTool.read_email(email_id)`
- `email_search(query: str)` → `EmailTool.search_emails(query)`
- `email_delete(email_id: str)` → `EmailTool.delete_email(email_id)`
- `initialize()` → `EmailTool.initialize()`

**calendar_skill.py** tools: `calendar_view`, `calendar_create`, `calendar_update`, `calendar_delete`
- `calendar_view(days_ahead: int = 7)` → `CalendarTool.view_events(days_ahead)`
- `calendar_create(title: str, start_time: str, end_time: str = None, description: str = "")` → `CalendarTool.create(...)`
- `calendar_update(event_id: str, title: str = None, start_time: str = None)` → `CalendarTool.update(...)`
- `calendar_delete(event_id: str)` → `CalendarTool.delete(event_id)`
- `initialize()` → `CalendarTool.initialize()`

**search_skill.py** tools: `web_search`
- `web_search(query: str, num_results: int = 10)` → `WebSearchTool.search(query, num_results)`

**opencode_skill.py** tools: `opencode_execute`
- `opencode_execute(task_description: str, project_path: str = "./mobile_app")` → `OpenCodeTool.execute(...)`

**desktop_skill.py** tools: `desktop_screenshot`, `desktop_click`, `desktop_type`, `desktop_hotkey`, `desktop_open_browser`
- Map each to corresponding `MCPDesktopTool` method.

Each skill needs its own `__init__` that creates the underlying tool instance with the appropriate config. The config object is available at `from config import config`.

- [ ] **Step 1: Create all 6 skill files following the pattern above**
- [ ] **Step 2: Verify skill discovery works**

Run: `cd server && python -c "from skills.registry import SkillRegistry; r = SkillRegistry(); r.discover('skills/builtin'); print(f'{len(r.get_tool_definitions())} tools registered'); [print(f'  - {t[\"function\"][\"name\"]}') for t in r.get_tool_definitions()]"`

Expected: All tools listed (approximately 16-20 tools)

- [ ] **Step 3: Commit**

```bash
git add server/skills/builtin/
git commit -m "feat: migrate all tools to skill system with OpenAI tool schemas"
```

---

## Task 9: Heartbeat System [S2-Gemini]

**Files:**
- Create: `server/heartbeat/__init__.py`
- Create: `server/heartbeat/HEARTBEAT.md`
- Create: `server/heartbeat/scheduler.py`
- Create: `server/heartbeat/jobs/`
- Create: `server/tests/test_heartbeat.py`

**Instructions for Gemini 3.1 Pro:**

Build a scheduling system using APScheduler that:
1. Parses `HEARTBEAT.md` for cron job definitions
2. Registers jobs with AsyncIOScheduler
3. Each job calls `agent.execute_scheduled_task(action)` when triggered
4. Supports CRUD via API (list, add, remove jobs)
5. Saves changes back to HEARTBEAT.md

**HEARTBEAT.md format:**

```markdown
# Heartbeat Schedule

## morning_greeting
- cron: "0 8 * * *"
- action: "根據天氣和用戶今天的行程，生成一句早安問候"
- enabled: true

## event_reminder
- cron: "*/30 * * * *"
- action: "檢查未來 30 分鐘內的行程，如果有則提醒用戶"
- enabled: true

## weekly_summary
- cron: "0 20 * * 0"
- action: "總結本週的對話重點和完成的事項"
- enabled: true
```

**scheduler.py** must:
- Parse the markdown format above into job configs
- Use `apscheduler.schedulers.asyncio.AsyncIOScheduler`
- Use `apscheduler.triggers.cron.CronTrigger`
- Have `start()`, `stop()`, `list_jobs()`, `add_job(config)`, `remove_job(job_id)` methods
- Save to HEARTBEAT.md after add/remove
- Handle the agent not being set yet (agent is injected after creation)

**Dependencies to install:** `pip install apscheduler`

**Test file** should test:
- Parse HEARTBEAT.md correctly
- Add/remove jobs
- List jobs
- Save back to markdown

- [ ] **Step 1: Create directory and default HEARTBEAT.md**
- [ ] **Step 2: Write tests**
- [ ] **Step 3: Implement scheduler.py**
- [ ] **Step 4: Run tests**
- [ ] **Step 5: Commit**

---

## Task 10: Web UI Rewrite [S2-Gemini]

**Files:**
- Rewrite: `server/static/index.html`

**Depends on:** Tasks 6-7 (new SSE event types)

**Instructions for Gemini 3.1 Pro:**

Rewrite the web frontend to support the dual-mode architecture. The UI must handle these SSE event types from `/api/chat/stream`:

| Event | UI Action |
|---|---|
| `mode_change` | Update mode indicator badge (聊天/協助) |
| `notice` | Show notice text in chat (styled differently) |
| `chunk` | Append text to current message bubble |
| `plan` | Show plan card with confirm/deny buttons |
| `tool_result` | Show tool result in expandable card |
| `done` | Finalize message, show emotion badge |
| `error` | Show error toast |

**UI Layout:**

```
┌──────────────────────────────────────┐
│ AI Wife Chat          [聊天 ▼] mode │  ← mode selector dropdown
├──────────────────────────────────────┤
│                                      │
│  Chat messages area                  │
│  - User messages (right)             │
│  - AI messages (left) with emotion   │
│  - Notice messages (center, subtle)  │
│  - Plan cards (with confirm/deny)    │
│  - Tool result cards (expandable)    │
│                                      │
├──────────────────────────────────────┤
│ [Message input]              [Send]  │
│ [🎤 Voice]  [⚙ Settings]            │
└──────────────────────────────────────┘
```

**Settings panel** (slide-out or modal):
- Memory list (read-only for now, with delete button per memory)
- Soul editor (textarea showing SOUL.md content, save button)
- Heartbeat jobs list (show cron + action, with enable/disable toggle)

**Key requirements:**
- Single-file HTML with embedded CSS/JS (keep current pattern)
- Use `fetch()` with `ReadableStream` for SSE consumption (current pattern)
- Filter `<think>...</think>` blocks from displayed text
- Strip `[emotion:TAG]` from display, show as badge
- Confirm button calls `POST /api/chat/confirm/{client_id}`
- Deny button calls `POST /api/chat/deny/{client_id}`
- Mode selector sends `mode_override` field in chat request (optional override)
- Generate a unique `client_id` on page load, include in all API calls
- Support `zh-TW`, `ja`, `en` language selector

- [ ] **Step 1: Rewrite index.html with new layout and SSE handling**
- [ ] **Step 2: Test manually — chat mode, assist mode, confirm, deny**
- [ ] **Step 3: Commit**

---

## Task 11: Flutter Frontend Updates [S3-Qwen]

**Files:**
- Modify: `mobile_app/lib/screens/chat_screen.dart`
- Modify: `mobile_app/lib/screens/settings_screen.dart`
- Modify: `mobile_app/lib/services/api_service.dart`
- Create: `mobile_app/lib/models/memory.dart`
- Create: `mobile_app/lib/models/heartbeat_job.dart`

**Instructions for Qwen 3.6:**

Update the Flutter app to support the dual-mode architecture:

**api_service.dart** — add new methods:
- `confirmPlan(clientId)` → `POST /api/chat/confirm/{clientId}` (SSE stream)
- `denyPlan(clientId)` → `POST /api/chat/deny/{clientId}`
- `listMemories()` → `GET /api/memory/list`
- `deleteMemory(id)` → `DELETE /api/memory/{id}`
- `getSoul()` → `GET /api/soul`
- `updateSoul(soul, profile)` → `PUT /api/soul`
- `listHeartbeatJobs()` → `GET /api/heartbeat/jobs`

**chat_screen.dart** — add:
- Mode indicator chip at top (聊天/協助), tappable to toggle
- When SSE returns `plan` event: show plan card with confirm/deny buttons
- Confirm button calls `api.confirmPlan(clientId)` and streams result
- Deny button calls `api.denyPlan(clientId)`
- Handle `notice` events with distinct styling
- Handle `tool_result` events with expandable result cards

**settings_screen.dart** — add tabs/sections:
- Memory tab: list memories with delete swipe
- Soul tab: editable text area for SOUL.md, save button
- Heartbeat tab: list cron jobs with enable/disable

**New models:**
- `memory.dart`: `Memory` class with `id`, `content`, `category`, `importance`, `createdAt`
- `heartbeat_job.dart`: `HeartbeatJob` class with `id`, `cron`, `action`, `enabled`

- [ ] **Step 1: Create model classes**
- [ ] **Step 2: Update api_service.dart with new endpoints**
- [ ] **Step 3: Update chat_screen.dart with mode indicator and confirm/deny**
- [ ] **Step 4: Update settings_screen.dart with memory/soul/heartbeat panels**
- [ ] **Step 5: Test on emulator**
- [ ] **Step 6: Commit**

---

## Task 12: Integration Testing and Cleanup [S1-Claude]

**Depends on:** All previous tasks complete.

- [ ] **Step 1: Run all tests**

```bash
cd server && python -m pytest tests/ -v
```

Fix any failures.

- [ ] **Step 2: Manual integration test**

Start server: `cd server && python main.py`

Test flows:
1. Chat mode: send "你好" → should get fast streaming response
2. Assist mode: send "幫我在 Downloads 建一個 test.txt" → should get plan → confirm → file created
3. Deny flow: send assist request → deny → should cancel
4. Memory: check `/api/memory/list` after conversations
5. Soul: check `/api/soul` returns SOUL.md content

- [ ] **Step 3: Remove old code**

Delete `server/tests/test_agent.py` (replaced by `test_agent_redesign.py`).

Remove old `TOOL_KEYWORDS`, `_detect_tool_calls_keyword`, `_detect_tool_calls`, `_generate_file_content`, `_extract_tool_params` from agent.py (should already be gone from rewrite).

Verify `server/tools/` still works (skills import from it).

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete agent redesign with dual-mode architecture"
```

---

## Execution Order

```
S1-Claude:  Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7 → Task 12
S2-Gemini:  (wait for Task 6-7) → Task 9 → Task 10
S3-Qwen:    Task 8 → (wait for Task 6-7) → Task 11
```

Tasks 1-5 (S1) and Task 8 (S3) can run in parallel.
Tasks 9-10 (S2) and Task 11 (S3) depend on Task 7 being done.
Task 12 waits for all streams.
