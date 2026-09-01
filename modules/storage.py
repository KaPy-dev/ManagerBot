import json
import asyncio
from pathlib import Path
from configuration.config import STORAGE_PATH, MANAGER_CHAT_ID, OWNER_ID


class Storage:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup()
        return cls._instance

    def _setup(self):
        self.path = Path(STORAGE_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()
        self.data = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                self.data = {}
        self.data.setdefault("owner_id", OWNER_ID)
        self.data.setdefault("manager_chat_id", MANAGER_CHAT_ID)
        self.data.setdefault("admins", [])
        self.data.setdefault("admin_names", {})
        self.data.setdefault("chats", {})
        if self.data["owner_id"] == 0 and OWNER_ID != 0:
            self.data["owner_id"] = OWNER_ID
        self._flush()

    def _flush(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)

    async def _save(self):
        async with self._lock:
            self._flush()

    @property
    def owner_id(self) -> int:
        return self.data["owner_id"]

    @property
    def manager_chat_id(self) -> int:
        return self.data["manager_chat_id"]

    @property
    def admins(self) -> list:
        return list(self.data["admins"])

    @property
    def chats(self) -> dict:
        return dict(self.data["chats"])

    def is_owner(self, user_id: int) -> bool:
        return user_id == self.data["owner_id"] and user_id != 0

    def is_admin(self, user_id: int) -> bool:
        return self.is_owner(user_id) or user_id in self.data["admins"]

    def admin_name(self, user_id: int) -> str | None:
        return self.data["admin_names"].get(str(user_id))

    async def add_admin(self, user_id: int, username: str | None = None) -> bool:
        if username:
            self.data["admin_names"][str(user_id)] = username
        if self.is_admin(user_id):
            await self._save()
            return False
        self.data["admins"].append(user_id)
        await self._save()
        return True

    async def remove_admin(self, user_id: int) -> bool:
        self.data["admin_names"].pop(str(user_id), None)
        if user_id not in self.data["admins"]:
            return False
        self.data["admins"].remove(user_id)
        await self._save()
        return True

    async def set_manager_chat(self, chat_id: int):
        self.data["manager_chat_id"] = chat_id
        await self._save()

    async def transfer_owner(self, new_owner_id: int):
        old_owner = self.data["owner_id"]
        self.data["owner_id"] = new_owner_id
        if new_owner_id in self.data["admins"]:
            self.data["admins"].remove(new_owner_id)
        if old_owner != 0 and old_owner not in self.data["admins"]:
            self.data["admins"].append(old_owner)
        await self._save()

    async def add_chat(self, chat_id: int, title: str):
        self.data["chats"][str(chat_id)] = title
        await self._save()

    async def remove_chat(self, chat_id: int):
        self.data["chats"].pop(str(chat_id), None)
        await self._save()


storage = Storage()
