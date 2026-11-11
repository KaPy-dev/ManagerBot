"""Внешний HTTP API бота: приём заявок с сайта и отправка их в чат менеджеров.

Запускается в том же процессе, что и polling (aiohttp уже есть у aiogram).
Все запросы, кроме /api/v1/health, требуют заголовок X-Api-Secret с секретной
фразой из conf.env (API_SECRET). Секрет сравнивается за постоянное время.

Маршруты (префикс /api/v1):
  GET  /health   — жив ли процесс (без авторизации, только {"status": "ok"})
  GET  /status   — бот, чат менеджеров, версия API (нужна авторизация)
  POST /leads    — отправить заявку в чат менеджеров (нужна авторизация);
                   kind=callback — заказ звонка: обязательны только name и phone
  POST /mail     — переслать входящее письмо с почты компании в чат менеджеров
                   (шлёт микросервис mailwatcher сайта; текст собирает modules/mail_text.py);
                   под сообщением кнопки «Выполнено» / «Вернуть в работу» (modules/tasks.py)
  POST /mail/files — файлы письма ответом на его сообщение (multipart: mail_id, reply_to, file × 1–10)
"""

from __future__ import annotations

import hmac
import json
import logging
from html import escape
from urllib.parse import unquote

from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaDocument, ReplyParameters
from aiohttp import BodyPartReader, web

from modules import tasks
from modules.brief_text import build_brief_text, build_callback_text
from modules.mail_text import build_mail_text
from modules.storage import storage

API_VERSION = "3"
FEATURES = ("leads", "mail", "mail_files")
SECRET_HEADER = "X-Api-Secret"
MAX_BODY = 64 * 1024

# POST /mail/files: лимит Bot API на загрузку — 50 МБ
MAX_FILES_BODY = 50 * 1024 * 1024
MAX_FILES = 10
MAX_FIELD = 1024
FILES_TIMEOUT = 300

# Поля анкеты, которые принимаем с сайта, и ограничения длины
LEAD_FIELDS = {
    "purchase": 60, "communication": 80, "mounting": 80, "service": 80, "screen_size": 80,
    "city": 100, "phone": 40, "email": 120, "name": 120, "description": 4000, "page": 500, "source": 40,
}

# lead — анкета как в брифе бота; callback — «Заказать звонок» с сайта (только ФИО и телефон)
LEAD_KINDS = ("lead", "callback")

# Поля входящего письма (POST /mail) и ограничения длины; вложения — список {name, size}
MAIL_FIELDS = {"mailbox": 200, "sender": 320, "sender_name": 200, "subject": 1000, "sent_at": 40, "sent_at_text": 40,
               "body": 3000, "matched_rule": 200, "source": 40}
MAIL_MAX_ATTACHMENTS = 50
MAIL_NOTE_MAX = 60

log = logging.getLogger("api")


def _json_error(status: int, message: str) -> web.Response:
    return web.json_response({"ok": False, "error": message}, status=status)


class _TooLarge(Exception):
    pass


async def _read_json(request: web.Request):
    """JSON с лимитом MAX_BODY, в том числе для тел без Content-Length (chunked)."""
    if request.content_length and request.content_length > MAX_BODY:
        raise _TooLarge
    raw = bytearray()
    async for chunk in request.content.iter_chunked(8192):
        raw += chunk
        if len(raw) > MAX_BODY:
            raise _TooLarge
    return json.loads(raw)


async def _json_payload(request: web.Request) -> tuple[object, web.Response | None]:
    try:
        return await _read_json(request), None
    except _TooLarge:
        return None, _json_error(413, "Слишком большой запрос")
    except Exception:  # noqa: BLE001
        return None, _json_error(400, "Тело запроса не является корректным JSON")


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
        "features": list(FEATURES),
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
    kind = payload.get("kind") or "lead"
    if kind not in LEAD_KINDS:
        return {}, "Поле «kind» должно быть lead или callback"
    data["kind"] = kind
    if kind == "callback":
        if not data.get("name"):
            return {}, "Не указано ФИО"
    elif not data.get("purchase"):
        return {}, "Не указан тип закупки"
    lead_id = payload.get("lead_id")
    if lead_id is not None and not isinstance(lead_id, (int, str)):
        return {}, "Поле «lead_id» должно быть числом или строкой"
    if lead_id is not None:
        data["lead_id"] = str(lead_id)[:40]
    return data, None


def _lead_text(data: dict, source: str, extra: list[str] | None) -> str:
    client = escape(data["name"]) if data.get("name") else "имя не указано"
    if data.get("lead_id"):
        client += f" · {escape(source)}, заявка #{escape(data['lead_id'])}"
    return build_brief_text(data, client=client, source=source, extra=extra)


async def create_lead(request: web.Request) -> web.Response:
    payload, failure = await _json_payload(request)
    if failure:
        return failure
    data, error = _clean_lead(payload)
    if error:
        return _json_error(400, error)

    chat_id = storage.manager_chat_id
    if not chat_id:
        log.error("API: заявка не отправлена — чат менеджеров не выбран")
        return _json_error(503, "Чат для заявок не задан: владелец выбирает его в боте через /admin")

    source = data.get("source") or "сайт"
    extra = [f"🔗 {escape(data['page'])}"] if data.get("page") else None
    if data["kind"] == "callback":
        text = build_callback_text(data, source=source, extra=extra)
    else:
        text = _lead_text(data, source, extra)

    bot: Bot = request.app["bot"]
    try:
        message = await bot.send_message(chat_id, text, disable_web_page_preview=True)
    except Exception as e:  # noqa: BLE001 — любую ошибку Telegram отдаём сайту как 502
        log.error("API: Telegram не принял заявку %s: %s", data.get("lead_id"), e, exc_info=True)
        return _json_error(502, f"Telegram не принял сообщение: {e}")

    log.info("API: заявка %s (%s) отправлена в чат %s, message_id=%s", data.get("lead_id"), source, chat_id, message.message_id)
    return web.json_response({"ok": True, "chat_id": chat_id, "message_id": message.message_id})


def _clean_attachment(a: dict) -> dict:
    item = {"name": str(a.get("name") or "")[:200], "size": int(a["size"]) if str(a.get("size") or "0").isdigit() else 0}
    note = a.get("note")
    if isinstance(note, str) and note.strip():
        item["note"] = note.strip()[:MAIL_NOTE_MAX]
    return item


def _clean_mail(payload: dict) -> tuple[dict, str | None]:
    if not isinstance(payload, dict):
        return {}, "Ожидается JSON-объект"
    data: dict = {}
    for key, max_len in MAIL_FIELDS.items():
        value = payload.get(key)
        if value is None:
            continue
        if not isinstance(value, (str, int, float)):
            return {}, f"Поле «{key}» должно быть строкой"
        value = str(value).strip()
        if len(value) > max_len:
            value = value[:max_len]
        if value:
            data[key] = value
    if not data.get("sender") and not data.get("subject") and not data.get("body"):
        return {}, "Пустое письмо: нет ни отправителя, ни темы, ни текста"
    attachments = payload.get("attachments") or []
    if not isinstance(attachments, list):
        return {}, "Поле «attachments» должно быть списком"
    data["attachments"] = [_clean_attachment(a) for a in attachments[:MAIL_MAX_ATTACHMENTS] if isinstance(a, dict) and a.get("name")]
    data["truncated"] = bool(payload.get("truncated"))
    mail_id = payload.get("mail_id")
    if mail_id is not None and not isinstance(mail_id, (int, str)):
        return {}, "Поле «mail_id» должно быть числом или строкой"
    if mail_id is not None:
        data["mail_id"] = str(mail_id)[:40]
    return data, None


async def forward_mail(request: web.Request) -> web.Response:
    payload, failure = await _json_payload(request)
    if failure:
        return failure
    data, error = _clean_mail(payload)
    if error:
        return _json_error(400, error)

    chat_id = storage.manager_chat_id
    if not chat_id:
        log.error("API: письмо не отправлено — чат менеджеров не выбран")
        return _json_error(503, "Чат для заявок не задан: владелец выбирает его в боте через /admin")

    bot: Bot = request.app["bot"]
    try:
        message = await bot.send_message(chat_id, tasks.open_text(build_mail_text(data)), reply_markup=tasks.keyboard(done=False),
                                         disable_web_page_preview=True)
    except Exception as e:  # noqa: BLE001 — любую ошибку Telegram отдаём сайту как 502
        log.error("API: Telegram не принял письмо %s: %s", data.get("mail_id"), e, exc_info=True)
        return _json_error(502, f"Telegram не принял сообщение: {e}")

    log.info("API: письмо %s от %s отправлено в чат %s, message_id=%s", data.get("mail_id"), data.get("sender"), chat_id, message.message_id)
    return web.json_response({"ok": True, "chat_id": chat_id, "message_id": message.message_id})


class _FormError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status, self.message = status, message


async def _read_part(part: BodyPartReader, limit: int, total: int) -> bytes:
    """Читает часть формы кусками; > limit или общий объём > MAX_FILES_BODY — 413, без дочитывания."""
    data = bytearray()
    while chunk := await part.read_chunk(64 * 1024):
        data += chunk
        if len(data) > limit or total + len(data) > MAX_FILES_BODY:
            raise _FormError(413, "Слишком большой запрос: файлы письма — до 50 МБ за раз")
    return bytes(data)


def _file_name(raw: str | None) -> str:
    # aiohttp-клиенты кодируют не-ASCII имя в filename="..." процентами, а сервер его не раскодирует
    name = unquote(raw or "").replace("/", "_").replace("\\", "_").strip()[:200]
    return name or "file"


async def _read_files_form(request: web.Request) -> tuple[str, int, list[tuple[str, bytes]]]:
    if request.content_length and request.content_length > MAX_FILES_BODY:
        raise _FormError(413, "Слишком большой запрос: файлы письма — до 50 МБ за раз")
    try:
        reader = await request.multipart()
    except Exception:  # noqa: BLE001
        raise _FormError(400, "Ожидается multipart/form-data") from None
    fields: dict[str, str] = {}
    files: list[tuple[str, bytes]] = []
    total = 0
    try:
        while (part := await reader.next()) is not None:
            if not isinstance(part, BodyPartReader):
                raise _FormError(400, "Вложенные multipart не поддерживаются")
            if part.name == "file":
                if len(files) >= MAX_FILES:
                    raise _FormError(400, f"Больше {MAX_FILES} файлов в одном запросе")
                content = await _read_part(part, MAX_FILES_BODY, total)
                if not content:
                    raise _FormError(400, "Пустой файл")
                total += len(content)
                files.append((_file_name(part.filename), content))
            elif part.name in ("mail_id", "reply_to"):
                fields[part.name] = (await _read_part(part, MAX_FIELD, total)).decode("utf-8", "replace").strip()
    except _FormError:
        raise
    except Exception:  # noqa: BLE001 — оборванная или битая форма
        raise _FormError(400, "Не удалось прочитать форму") from None

    mail_id = fields.get("mail_id", "")
    if not mail_id or len(mail_id) > 40:
        raise _FormError(400, "Поле «mail_id» — строка до 40 символов")
    reply_to = fields.get("reply_to", "")
    if not reply_to.isdigit() or int(reply_to) <= 0:
        raise _FormError(400, "Поле «reply_to» — номер сообщения с текстом письма")
    if not files:
        raise _FormError(400, "Нет файлов")
    return mail_id, int(reply_to), files


async def forward_mail_files(request: web.Request) -> web.Response:
    chat_id = storage.manager_chat_id
    if not chat_id:
        log.error("API: файлы письма не отправлены — чат менеджеров не выбран")
        return _json_error(503, "Чат для заявок не задан: владелец выбирает его в боте через /admin")
    try:
        mail_id, reply_to, files = await _read_files_form(request)
    except _FormError as e:
        return _json_error(e.status, e.message)

    bot: Bot = request.app["bot"]
    reply = ReplyParameters(message_id=reply_to, allow_sending_without_reply=True)
    try:
        if len(files) == 1:
            name, content = files[0]
            sent = [await bot.send_document(chat_id, BufferedInputFile(content, name), reply_parameters=reply,
                                            request_timeout=FILES_TIMEOUT)]
        else:
            media = [InputMediaDocument(media=BufferedInputFile(content, name)) for name, content in files]
            sent = await bot.send_media_group(chat_id, media, reply_parameters=reply, request_timeout=FILES_TIMEOUT)
    except Exception as e:  # любую ошибку Telegram отдаём сайту как 502
        log.exception("API: Telegram не принял файлы письма %s", mail_id)
        return _json_error(502, f"Telegram не принял файлы: {e}")

    message_ids = [m.message_id for m in sent]
    log.info("API: файлы письма %s (%d шт.) отправлены в чат %s ответом на %s", mail_id, len(files), chat_id, reply_to)
    return web.json_response({"ok": True, "chat_id": chat_id, "message_ids": message_ids})


def build_app(bot: Bot, secret: str) -> web.Application:
    app = web.Application(middlewares=[auth_middleware], client_max_size=MAX_FILES_BODY)
    app["bot"] = bot
    app["secret"] = secret
    app.add_routes([
        web.get("/api/v1/health", health),
        web.get("/api/v1/status", status),
        web.post("/api/v1/leads", create_lead),
        web.post("/api/v1/mail", forward_mail),
        web.post("/api/v1/mail/files", forward_mail_files),
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
