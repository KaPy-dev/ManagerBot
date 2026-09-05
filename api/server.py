"""Внешний HTTP API бота: приём заявок с сайта и отправка их в чат менеджеров.

Запускается в том же процессе, что и polling (aiohttp уже есть у aiogram).
Все запросы, кроме /api/v1/health, требуют заголовок X-Api-Secret с секретной
фразой из conf.env (API_SECRET). Секрет сравнивается за постоянное время.

Маршруты (префикс /api/v1):
  GET  /health   — жив ли процесс (без авторизации, только {"status": "ok"})
  GET  /status   — бот, чат менеджеров, версия API (нужна авторизация)
  POST /leads    — отправить заявку в чат менеджеров (нужна авторизация)
"""

from __future__ import annotations

import hmac
import logging
from html import escape

from aiohttp import web
from aiogram import Bot

from modules.brief_text import build_brief_text
from modules.storage import storage

API_VERSION = "1"
SECRET_HEADER = "X-Api-Secret"
MAX_BODY = 64 * 1024

# Поля анкеты, которые принимаем с сайта, и ограничения длины
LEAD_FIELDS = {
    "purchase": 60, "communication": 80, "mounting": 80, "service": 80, "screen_size": 80,
    "city": 100, "phone": 40, "email": 120, "name": 120, "description": 4000, "page": 500, "source": 40,
}

log = logging.getLogger("api")


def _json_error(status: int, message: str) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


@web.middleware
async def auth_middleware(request: web.Request, handler):
    if request.path.endswith("/health"):
        return await handler(request)
    secret: str = request.app["secret"]
    given = request.headers.get(SECRET_HEADER, "")
    if not given or not hmac.compare_digest(given.encode(), secret.encode()):
        log.warning("API: отклонён запрос %s %s с %s — неверный секрет", request.method, request.path, request.remote)
        return _json_error(401, "Неверная секретная фраза")
    return await handler(request)


async def health(_: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def status(request: web.Request) -> web.Response:
    bot: Bot = request.app["bot"]
    chat_id = storage.manager_chat_id
    info = storage.chat_info(chat_id) if chat_id else None
    me = request.app.get("me")
    if me is None:
        try:
            me = await bot.get_me()
            request.app["me"] = me
        except Exception:  # noqa: BLE001 — статус должен отвечать даже без связи с Telegram
            me = None
    return web.json_response({
        "ok": True,
        "api_version": API_VERSION,
        "bot": {"id": me.id, "username": me.username} if me else None,
        "manager_chat": {"id": chat_id, "title": info.get("title") if info else None} if chat_id else None,
    })


def _clean_lead(payload: dict) -> tuple[dict, str | None]:
    """Обрезает пробелы, ограничивает длину, проверяет обязательные поля. Возвращает (данные, ошибка)."""
    if not isinstance(payload, dict):
        return {}, "Ожидается JSON-объект"
    data: dict = {}
    for key, max_len in LEAD_FIELDS.items():
        value = payload.get(key)
        if value is None:
            continue
        if not isinstance(value, (str, int, float)):
            return {}, f"Поле «{key}» должно быть строкой"
        value = str(value).strip()
        if len(value) > max_len:
            return {}, f"Поле «{key}» длиннее {max_len} символов"
        if value:
            data[key] = value
    if not data.get("phone"):
        return {}, "Не указан телефон"
    if not data.get("purchase"):
        return {}, "Не указан тип закупки"
    lead_id = payload.get("lead_id")
    if lead_id is not None and not isinstance(lead_id, (int, str)):
        return {}, "Поле «lead_id» должно быть числом или строкой"
    if lead_id is not None:
        data["lead_id"] = str(lead_id)[:40]
    return data, None


async def create_lead(request: web.Request) -> web.Response:
    if request.content_length and request.content_length > MAX_BODY:
        return _json_error(413, "Слишком большой запрос")
    try:
        payload = await request.json()
    except Exception:  # noqa: BLE001
        return _json_error(400, "Тело запроса не является корректным JSON")
    data, error = _clean_lead(payload)
    if error:
        return _json_error(400, error)

    chat_id = storage.manager_chat_id
    if not chat_id:
        log.error("API: заявка не отправлена — чат менеджеров не выбран")
        return _json_error(503, "Чат для заявок не задан: владелец выбирает его в боте через /admin")

    source = data.get("source") or "сайт"
    client = escape(data["name"]) if data.get("name") else "имя не указано"
    if data.get("lead_id"):
        client += f" · {escape(source)}, заявка #{escape(data['lead_id'])}"
    extra = [f"🔗 {escape(data['page'])}"] if data.get("page") else None
    text = build_brief_text(data, client=client, source=source, extra=extra)

    bot: Bot = request.app["bot"]
    try:
        message = await bot.send_message(chat_id, text, disable_web_page_preview=True)
    except Exception as e:  # noqa: BLE001 — любую ошибку Telegram отдаём сайту как 502
        log.error("API: Telegram не принял заявку %s: %s", data.get("lead_id"), e, exc_info=True)
        return _json_error(502, f"Telegram не принял сообщение: {e}")

    log.info("API: заявка %s (%s) отправлена в чат %s, message_id=%s", data.get("lead_id"), source, chat_id, message.message_id)
    return web.json_response({"ok": True, "chat_id": chat_id, "message_id": message.message_id})


def build_app(bot: Bot, secret: str) -> web.Application:
    app = web.Application(middlewares=[auth_middleware], client_max_size=MAX_BODY)
    app["bot"] = bot
    app["secret"] = secret
    app.add_routes([
        web.get("/api/v1/health", health),
        web.get("/api/v1/status", status),
        web.post("/api/v1/leads", create_lead),
    ])
    return app


class ApiServer:
    """Обёртка над aiohttp: start() поднимает сервер, stop() гасит."""

    def __init__(self, bot: Bot, secret: str, host: str, port: int) -> None:
        self._runner = web.AppRunner(build_app(bot, secret), access_log=None)
        self._host, self._port = host, port

    async def start(self) -> None:
        await self._runner.setup()
        await web.TCPSite(self._runner, self._host, self._port).start()
        log.info("HTTP API запущен на http://%s:%s/api/v1", self._host, self._port)

    async def stop(self) -> None:
        await self._runner.cleanup()
