import time
from aiogram import BaseMiddleware
from modules.orm.user import upsert_user
from main import logger


class UserTrackMiddleware(BaseMiddleware):
    def __init__(self, throttle_seconds: int = 60):
        self.throttle_seconds = throttle_seconds
        self._seen = {}
        super().__init__()

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        if user and not user.is_bot:
            now = time.monotonic()
            if now - self._seen.get(user.id, 0) > self.throttle_seconds:
                self._seen[user.id] = now
                try:
                    await upsert_user(user)
                except Exception:
                    logger.error(f"Не удалось сохранить пользователя {user.id}", exc_info=True)
        return await handler(event, data)
