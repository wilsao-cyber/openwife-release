import pytest
import asyncio
import os


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_memories.db")


@pytest.fixture
def store(db_path):
    from memory.memory_store import MemoryStore
    s = MemoryStore(db_path=db_path, use_embeddings=False)
    asyncio.run(s.initialize())
    return s


def test_initialize_creates_db(db_path):
    from memory.memory_store import MemoryStore
    s = MemoryStore(db_path=db_path, use_embeddings=False)
    asyncio.run(s.initialize())
    assert os.path.exists(db_path)


def test_add_and_list(store):
    async def _test():
        await store.add("User likes cats", "user_preference", 0.8)
        await store.add("Meeting tomorrow", "event", 0.6)
        return await store.list_all(limit=10)
    memories = asyncio.run(_test())
    assert len(memories) == 2


def test_search_keyword_fallback(store):
    async def _test():
        await store.add("User likes cats and dogs", "user_preference", 0.8)
        await store.add("Meeting with boss tomorrow", "event", 0.6)
        await store.add("Favorite food is ramen", "user_preference", 0.7)
        return await store.search("cats", limit=2)
    results = asyncio.run(_test())
    assert len(results) >= 1
    assert "cats" in results[0]["content"]


def test_delete(store):
    async def _test():
        await store.add("temp memory", "fact", 0.3)
        memories = await store.list_all()
        assert len(memories) == 1
        await store.delete(memories[0]["id"])
        return await store.list_all()
    memories = asyncio.run(_test())
    assert len(memories) == 0


def test_update_access(store):
    async def _test():
        await store.add("important fact", "fact", 0.9)
        memories = await store.list_all()
        assert memories[0]["access_count"] == 0
        await store.update_access(memories[0]["id"])
        return await store.list_all()
    memories = asyncio.run(_test())
    assert memories[0]["access_count"] == 1


def test_count(store):
    async def _test():
        await store.add("mem1", "fact", 0.5)
        await store.add("mem2", "fact", 0.5)
        return await store.count()
    count = asyncio.run(_test())
    assert count == 2
