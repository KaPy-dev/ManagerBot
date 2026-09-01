import asyncio
from pathlib import Path
from typing import Any, Optional, List, Dict
import aiosqlite
from configuration.config import DB_PATH


class DatabaseManager:
    _instance: Optional["DatabaseManager"] = None
    _conn: Optional[aiosqlite.Connection] = None

    def __new__(cls) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    async def get_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
            self._conn = await aiosqlite.connect(DB_PATH)
            self._conn.row_factory = aiosqlite.Row
            await self._conn.execute("PRAGMA journal_mode=WAL")
            await self._conn.execute("PRAGMA busy_timeout=5000")
            await self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    async def execute(self, query: str, params: Any = None) -> Optional[int]:
        conn = await self.get_conn()
        async with self._lock:
            cur = await conn.execute(query, params or ())
            await conn.commit()
            return cur.lastrowid

    async def fetch_all(self, query: str, params: Any = None) -> List[Dict[str, Any]]:
        conn = await self.get_conn()
        cur = await conn.execute(query, params or ())
        rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def fetch_one(self, query: str, params: Any = None) -> Optional[Dict[str, Any]]:
        conn = await self.get_conn()
        cur = await conn.execute(query, params or ())
        row = await cur.fetchone()
        return dict(row) if row else None

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None


db = DatabaseManager()
