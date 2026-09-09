"""Проверка внешнего HTTP API без сети и без реального бота.

Запуск: python test/test_api.py
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))
_tmp = Path(tempfile.mkdtemp())
os.environ["STORAGE_PATH"] = str(_tmp / "settings.json")
os.environ["DB_PATH"] = str(_tmp / "test.db")
os.environ["OWNER_ID"] = "111"

from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

from api.server import SECRET_HEADER, build_app  # noqa: E402
from modules.storage import storage  # noqa: E402

SECRET = "correct horse battery staple"


class FakeBot:
    def __init__(self):
        self.sent = []
        self.fail = False

    async def get_me(self):
        return SimpleNamespace(id=42, username="dipled_test_bot")

    async def send_message(self, chat_id, text, **kwargs):
        if self.fail:
            raise RuntimeError("chat not found")
        self.sent.append((chat_id, text, kwargs))
        return SimpleNamespace(message_id=len(self.sent))


LEAD = {
    "lead_id": 17, "source": "сайт", "purchase": "Коммерческая", "mounting": "Настенный", "service": "Фронтальный",
    "screen_size": "300 x 200 см (Г x В)", "city": "Омск", "phone": "+7 900 123-45-67", "email": "ivan@example.com",
    "name": "Иван <b>", "description": "Нужен экран", "page": "https://dipled.ru/zayavka",
}

errors = []


def check(name, condition):
    print(("✅ " if condition else "❌ ") + name)
    if not condition:
        errors.append(name)


async def run():
    bot = FakeBot()
    await storage.set_manager_chat(-100123)
    async with TestClient(TestServer(build_app(bot, SECRET))) as client:
        auth = {SECRET_HEADER: SECRET}

        r = await client.get("/api/v1/health")
        check("health без секрета отвечает 200", r.status == 200 and (await r.json())["status"] == "ok")

        r = await client.get("/api/v1/status")
        check("status без секрета — 401", r.status == 401)
        r = await client.get("/api/v1/status", headers={SECRET_HEADER: "wrong"})
        check("status с неверным секретом — 401", r.status == 401)
        r = await client.get("/api/v1/status", headers=auth)
        body = await r.json()
        check("status с секретом — бот и чат", r.status == 200 and body["bot"]["username"] == "dipled_test_bot" and body["manager_chat"]["id"] == -100123)

        r = await client.post("/api/v1/leads", json=LEAD, headers=auth)
        body = await r.json()
        check("заявка принята", r.status == 200 and body["ok"] and body["message_id"] == 1 and body["chat_id"] == -100123)
        chat_id, text, kwargs = bot.sent[-1]
        check("ушла в чат менеджеров", chat_id == -100123 and kwargs.get("disable_web_page_preview") is True)
        check("заголовок с источником", "📋 <b>Новая заявка</b> (сайт)" in text)
        check("поля анкеты на месте", "<b>Тип закупки:</b> Коммерческая" in text and "<b>Город:</b> Омск" in text and "<b>Комментарий:</b> Нужен экран" in text)
        check("контакты и номер заявки", "📞 <b>Телефон:</b> +7 900 123-45-67" in text and "заявка #17" in text and "🔗 https://dipled.ru/zayavka" in text)
        check("HTML в имени экранирован", "Иван &lt;b&gt;" in text and "<b>Иван" not in text)

        r = await client.post("/api/v1/leads", json={**LEAD, "phone": ""}, headers=auth)
        check("без телефона — 400", r.status == 400)
        r = await client.post("/api/v1/leads", data="not json", headers={**auth, "Content-Type": "application/json"})
        check("битый JSON — 400", r.status == 400)
        r = await client.post("/api/v1/leads", json=LEAD)
        check("заявка без секрета — 401 и не отправлена", r.status == 401 and len(bot.sent) == 1)

        bot.fail = True
        r = await client.post("/api/v1/leads", json=LEAD, headers=auth)
        check("ошибка Telegram — 502", r.status == 502 and "chat not found" in (await r.json())["error"])
        bot.fail = False

        await storage.set_manager_chat(0)
        r = await client.post("/api/v1/leads", json=LEAD, headers=auth)
        check("чат не выбран — 503", r.status == 503)

    print("\n" + ("✅ API: все проверки пройдены" if not errors else f"❌ API: провалено {len(errors)}"))
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
