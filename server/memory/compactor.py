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
