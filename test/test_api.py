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

from aiohttp import FormData
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

from api.server import MAX_BODY, SECRET_HEADER, build_app  # noqa: E402
from modules.storage import storage  # noqa: E402

SECRET = "correct horse battery staple"


class FakeBot:
    def __init__(self):
        self.sent = []
        self.docs = []
        self.fail = False

    async def get_me(self):
        return SimpleNamespace(id=42, username="dipled_test_bot")

    async def send_message(self, chat_id, text, **kwargs):
        if self.fail:
            raise RuntimeError("chat not found")
        self.sent.append((chat_id, text, kwargs))
        return SimpleNamespace(message_id=len(self.sent))

    async def send_document(self, chat_id, document, **kwargs):
        if self.fail:
            raise RuntimeError("file upload failed")
        self.docs.append((chat_id, [document], kwargs))
        return SimpleNamespace(message_id=500 + len(self.docs))

    async def send_media_group(self, chat_id, media, **kwargs):
        if self.fail:
            raise RuntimeError("file upload failed")
        self.docs.append((chat_id, [m.media for m in media], kwargs))
        return [SimpleNamespace(message_id=600 + i) for i in range(len(media))]


def files_form(count: int = 1, mail_id="12", reply_to="3", size: int = 10) -> FormData:
    form = FormData()
    if mail_id is not None:
        form.add_field("mail_id", mail_id)
    if reply_to is not None:
        form.add_field("reply_to", reply_to)
    for i in range(count):
        form.add_field("file", b"x" * size, filename=f"смета-{i}.pdf", content_type="application/pdf")
    return form


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

        call = {"kind": "callback", "lead_id": 18, "name": "Иванов <i>Иван</i>", "phone": "+7 900 123-45-67", "purchase": "Заказ звонка", "page": "https://dipled.ru/kontakty"}
        r = await client.post("/api/v1/leads", json=call, headers=auth)
        text = bot.sent[-1][1]
        check("заказ звонка принят", r.status == 200 and len(bot.sent) == 2)
        check("звонок помечен и без анкеты", "📞 <b>Заказ звонка</b> (сайт)" in text and "Тип закупки" not in text and "Почта" not in text)
        check("ФИО, телефон и номер заявки", "<b>ФИО:</b> Иванов &lt;i&gt;" in text and "<b>Телефон:</b> +7 900 123-45-67" in text and "заявка #18" in text and "🔗 https://dipled.ru/kontakty" in text)
        r = await client.post("/api/v1/leads", json={**call, "name": ""}, headers=auth)
        check("звонок без ФИО — 400", r.status == 400)
        r = await client.post("/api/v1/leads", json={**call, "kind": "spam"}, headers=auth)
        check("неизвестный kind — 400", r.status == 400)

        mail = {"mail_id": 12, "mailbox": "info@dipled.ru", "sender": "ivan@zakupki.ru", "sender_name": "Иван <b>", "subject": "Запрос <КП>",
                "sent_at_text": "26.09.2026 15:00", "body": "Здравствуйте!\nНужен экран 3×2 м.", "truncated": True,
                "attachments": [{"name": "kp.pdf", "size": 120000}, "мусор", {"size": 1}], "matched_rule": "Госзаказчики"}
        r = await client.post("/api/v1/mail", json=mail, headers=auth)
        body = await r.json()
        check("письмо принято", r.status == 200 and body["ok"] and body["chat_id"] == -100123 and len(bot.sent) == 3)
        text = bot.sent[-1][1]
        check("письмо оформлено", text.startswith("📨 <b>Письмо на почту</b>\n\n👤 <b>От:</b> Иван &lt;b&gt;\n📧 ivan@zakupki.ru\n📝 <b>Тема:</b> Запрос &lt;КП&gt;\n"))
        check("без ящика, номера и правила", "info@dipled.ru" not in text and "#12" not in text and "Госзаказчики" not in text)
        check("вложения и текст", "📎 <b>Вложения:</b> kp.pdf (117 КБ)" in text and "<blockquote expandable>Здравствуйте!\nНужен экран 3×2 м.…</blockquote>" in text)
        check("дата, затем отметка состояния", text.endswith("🕒 26.09.2026 15:00\n<i>Текст сокращён — полностью письмо в ящике и в админке сайта</i>\n\n⏳ <b>Не обработано</b>"))
        kb = bot.sent[-1][2].get("reply_markup")
        check("кнопка «Выполнено» под письмом", kb is not None and kb.inline_keyboard[0][0].callback_data == "task:done")
        r = await client.post("/api/v1/mail", json={"attachments": []}, headers=auth)
        check("пустое письмо — 400", r.status == 400)
        r = await client.post("/api/v1/mail", json=mail)
        check("письмо без секрета — 401", r.status == 401 and len(bot.sent) == 3)
        r = await client.get("/api/v1/status", headers=auth)
        body = await r.json()
        check("status сообщает поддержку писем и файлов", {"mail", "mail_files"} <= set(body["features"]) and body["api_version"] == "3")

        noted = {**mail, "attachments": [{"name": "смета.pdf", "size": 182344},
                                         {"name": "видео.mp4", "size": 325058560, "note": " не переслано — больше 45 МБ "},
                                         {"name": "x.bin", "size": 5, "note": "<b>" + "я" * 80}]}
        r = await client.post("/api/v1/mail", json=noted, headers=auth)
        text = bot.sent[-1][1]
        check("note в скобках после размера", r.status == 200 and "📎 <b>Вложения:</b> смета.pdf (178 КБ), видео.mp4 (310.0 МБ, не переслано — больше 45 МБ), x.bin (5 Б, &lt;b&gt;" in text)
        check("note обрезан до 60 символов", "&lt;b&gt;" + "я" * 57 + ")" in text)
        sent_before = len(bot.sent)
        r = await client.post("/api/v1/mail", data=b'{"subject": "' + b"a" * MAX_BODY + b'"}', headers={**auth, "Content-Type": "application/json"})
        check("JSON больше 64 КБ — 413", r.status == 413)

        async def chunked():
            yield b'{"subject": "'
            for _ in range(10):
                yield b"a" * 8192
            yield b'"}'
        r = await client.post("/api/v1/mail", data=chunked(), headers={**auth, "Content-Type": "application/json"})
        check("JSON без Content-Length больше 64 КБ — 413", r.status == 413 and len(bot.sent) == sent_before)

        r = await client.post("/api/v1/mail/files", data=files_form(1), headers=auth)
        body = await r.json()
        chat_id, docs, kwargs = bot.docs[-1]
        reply = kwargs.get("reply_parameters")
        check("1 файл → send_document", r.status == 200 and body == {"ok": True, "chat_id": -100123, "message_ids": [501]} and chat_id == -100123)
        check("ответом на текст письма, без подписи", reply.message_id == 3 and reply.allow_sending_without_reply is True and "caption" not in kwargs)
        check("имя и байты файла", docs[0].filename == "смета-0.pdf" and docs[0].data == b"x" * 10)
        raw = FormData()
        raw.add_field("mail_id", "12")
        raw.add_field("reply_to", "3")
        raw.add_field("file", b"y", filename="../отчёт 50% итог.xlsx")
        r = await client.post("/api/v1/mail/files", data=raw, headers=auth)
        check("имя без слэшей, проценты не ломают", r.status == 200 and bot.docs[-1][1][0].filename == ".._отчёт 50% итог.xlsx")

        r = await client.post("/api/v1/mail/files", data=files_form(3), headers=auth)
        body = await r.json()
        check("3 файла → send_media_group", r.status == 200 and body["message_ids"] == [600, 601, 602] and len(bot.docs[-1][1]) == 3)
        check("пачка ответом на текст", bot.docs[-1][2]["reply_parameters"].message_id == 3)
        docs_before = len(bot.docs)
        r = await client.post("/api/v1/mail/files", data=files_form(11), headers=auth)
        check("11 файлов — 400", r.status == 400)
        r = await client.post("/api/v1/mail/files", data=files_form(0), headers=auth)
        check("форма без файлов — 400", r.status == 400)
        r = await client.post("/api/v1/mail/files", data=FormData({"x": "1"}), headers=auth)
        check("пустая форма — 400", r.status == 400)
        r = await client.post("/api/v1/mail/files", json={"mail_id": 1}, headers=auth)
        check("не multipart — 400", r.status == 400)
        r = await client.post("/api/v1/mail/files", data=files_form(1, reply_to="abc"), headers=auth)
        check("reply_to не число — 400", r.status == 400)
        r = await client.post("/api/v1/mail/files", data=files_form(1, mail_id=None), headers=auth)
        check("без mail_id — 400", r.status == 400)
        r = await client.post("/api/v1/mail/files", data=files_form(1, size=0), headers=auth)
        check("пустой файл — 400", r.status == 400)
        r = await client.post("/api/v1/mail/files", data=files_form(1))
        check("файлы без секрета — 401", r.status == 401)
        r = await client.post("/api/v1/mail/files", data=files_form(1, size=50 * 1024 * 1024 + 1), headers=auth)
        check("файл больше 50 МБ — 413", r.status == 413)
        r = await client.post("/api/v1/mail/files", data=files_form(2, size=26 * 1024 * 1024), headers=auth)
        check("файлы суммарно больше 50 МБ — 413", r.status == 413 and len(bot.docs) == docs_before)

        bot.fail = True
        r = await client.post("/api/v1/leads", json=LEAD, headers=auth)
        check("ошибка Telegram — 502", r.status == 502 and "chat not found" in (await r.json())["error"])
        r = await client.post("/api/v1/mail", json=mail, headers=auth)
        check("ошибка Telegram для письма — 502", r.status == 502)
        r = await client.post("/api/v1/mail/files", data=files_form(1), headers=auth)
        check("ошибка Telegram для файла — 502", r.status == 502 and "file upload failed" in (await r.json())["error"])
        r = await client.post("/api/v1/mail/files", data=files_form(2), headers=auth)
        check("ошибка Telegram для пачки — 502", r.status == 502)
        bot.fail = False

        await storage.set_manager_chat(0)
        r = await client.post("/api/v1/leads", json=LEAD, headers=auth)
        check("чат не выбран — 503", r.status == 503)
        r = await client.post("/api/v1/mail/files", data=files_form(1), headers=auth)
        check("файлы без чата — 503", r.status == 503)

    print("\n" + ("✅ API: все проверки пройдены" if not errors else f"❌ API: провалено {len(errors)}"))
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
