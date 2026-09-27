"""Кнопки «Выполнено» / «Вернуть в работу»: текст состояния и обработчик без сети.

Запуск: python test/test_tasks.py
"""

import asyncio
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))
_tmp = Path(tempfile.mkdtemp())
os.environ["STORAGE_PATH"] = str(_tmp / "settings.json")
os.environ["DB_PATH"] = str(_tmp / "test.db")
os.environ["TZ_NAME"] = "Europe/Moscow"

from aiogram.exceptions import TelegramBadRequest  # noqa: E402

from handlers.tasks import toggle_task  # noqa: E402
from modules import tasks  # noqa: E402

errors = []


def check(name, condition):
    print(("✅ " if condition else "❌ ") + name)
    if not condition:
        errors.append(name)


class FakeMessage:
    def __init__(self, html_text):
        self.html_text, self.message_id, self.chat = html_text, 5, SimpleNamespace(id=-100)
        self.edits, self.fail = [], None

    async def edit_text(self, text, **kwargs):
        if self.fail:
            raise self.fail
        self.html_text = text
        self.edits.append((text, kwargs))


class FakeCall:
    def __init__(self, data, message, name="Иван Петров"):
        self.data, self.message, self.from_user = data, message, SimpleNamespace(full_name=name, username="ivan", id=7)
        self.answers = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append(text)


async def run():
    when = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)
    body = "📨 <b>Письмо на почту</b>\n\n<blockquote expandable>текст</blockquote>\n\n🕒 26.09.2026 15:00"
    opened = tasks.open_text(body)
    check("строка «Не обработано» добавлена", opened == body + "\n\n⏳ <b>Не обработано</b>")
    done = tasks.done_text(opened, "Иван <Петров>", when)
    check("«Выполнено» заменяет строку состояния", done == body + "\n\n✅ <b>Выполнено</b> — Иван &lt;Петров&gt;, 26.09 15:00")
    reopened = tasks.reopened_text(done, "Оля", when)
    check("«Возвращено» заменяет «Выполнено»", reopened == body + "\n\n🔁 <b>Возвращено в работу</b> — Оля, 26.09 15:00")
    check("повторное «Выполнено» не плодит строк", tasks.done_text(reopened, "Оля", when).count("<b>") == 2)
    check("клавиатуры", tasks.keyboard(False).inline_keyboard[0][0].callback_data == "task:done" and tasks.keyboard(True).inline_keyboard[0][0].callback_data == "task:reopen")

    msg = FakeMessage(opened)
    call = FakeCall("task:done", msg)
    await toggle_task(call)
    check("обработчик: текст обновлён и кнопка сменилась", "✅ <b>Выполнено</b> — Иван Петров" in msg.html_text and msg.edits[-1][1]["reply_markup"].inline_keyboard[0][0].callback_data == "task:reopen")
    check("обработчик: ответ на нажатие", call.answers == ["Отмечено как выполненное"])

    call = FakeCall("task:reopen", msg, name="Оля")
    await toggle_task(call)
    check("обработчик: возврат в работу", "🔁 <b>Возвращено в работу</b> — Оля" in msg.html_text and "Выполнено" not in msg.html_text and call.answers == ["Возвращено в работу"])

    msg.fail = TelegramBadRequest(method=SimpleNamespace(), message="Bad Request: message is not modified")
    call = FakeCall("task:reopen", msg)
    await toggle_task(call)
    check("«not modified» не считается ошибкой", call.answers == ["Возвращено в работу"])
    msg.fail = TelegramBadRequest(method=SimpleNamespace(), message="Bad Request: message can't be edited")
    call = FakeCall("task:done", msg)
    await toggle_task(call)
    check("другая ошибка Telegram — сообщение пользователю", call.answers == ["Не удалось обновить сообщение"])

    print("\n" + ("✅ Задачи: все проверки пройдены" if not errors else f"❌ Задачи: провалено {len(errors)}"))
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run())
