import json
import time
import asyncio
from pathlib import Path
from typing import Any, Dict, Optional
from aiogram.fsm.storage.memory import MemoryStorage, MemoryStorageRecord
from aiogram.fsm.storage.base import StorageKey, StateType

STATE_TTL_SECONDS = 24 * 3600
AUTOSAVE_INTERVAL = 300


class PersistentMemoryStorage(MemoryStorage):
    def __init__(self, path: str | Path):
        super().__init__()
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ts: Dict[StorageKey, float] = {}
        self._dirty = False
        self._restored = self._load()

    def _load(self) -> int:
        if not self.path.exists():
            return 0
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return 0
        now = time.time()
        restored = 0
        for item in raw:
            if now - item.get("ts", 0) > STATE_TTL_SECONDS:
                continue
            key = StorageKey(
                bot_id=item["bot_id"],
                chat_id=item["chat_id"],
                user_id=item["user_id"],
                thread_id=item.get("thread_id"),
                business_connection_id=item.get("business_connection_id"),
                destiny=item.get("destiny", "default"),
            )
            self.storage[key] = MemoryStorageRecord(data=item["data"], state=item["state"])
            self._ts[key] = item["ts"]
            restored += 1
        return restored

    def dump(self):
        now = time.time()
        raw = []
        for key, rec in self.storage.items():
            if rec.state is None and not rec.data:
                continue
            ts = self._ts.get(key, now)
            if now - ts > STATE_TTL_SECONDS:
                continue
            raw.append({
                "bot_id": key.bot_id,
                "chat_id": key.chat_id,
                "user_id": key.user_id,
                "thread_id": key.thread_id,
                "business_connection_id": key.business_connection_id,
                "destiny": key.destiny,
                "state": rec.state,
                "data": rec.data,
                "ts": ts,
            })
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)
        self._dirty = False
        return len(raw)

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        await super().set_state(key, state)
        self._ts[key] = time.time()
        self._dirty = True

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        await super().set_data(key, data)
        self._ts[key] = time.time()
        self._dirty = True

    async def close(self) -> None:
        self.dump()
        await super().close()

    async def autosave_loop(self):
        while True:
            await asyncio.sleep(AUTOSAVE_INTERVAL)
            if self._dirty:
                self.dump()
