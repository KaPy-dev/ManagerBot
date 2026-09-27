"""Состояние «обработано / в работе» у сообщений в чате менеджеров.

Под сообщением (письмо с почты) висят инлайн-кнопки «✅ Выполнено» / «↩️ Вернуть в работу»;
нажатие меняет последнюю строку сообщения (кто и когда отметил) и кнопку. Состояние живёт
в самом сообщении Telegram — отдельного хранилища не нужно.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from configuration import config

CB_DONE = "task:done"
CB_REOPEN = "task:reopen"

OPEN_LINE = "⏳ <b>Не обработано</b>"
_DONE = "✅ <b>Выполнено</b>"
_REOPENED = "🔁 <b>Возвращено в работу</b>"
# Строка состояния — последняя строка сообщения, начинается с одного из маркеров
_STATE_LINE = re.compile(r"\n*(?:⏳|✅|🔁) <b>(?:Не обработано|Выполнено|Возвращено в работу)</b>[^\n]*\s*$")


def _tz() -> ZoneInfo | None:
    try:
        return ZoneInfo(config.TZ_NAME)
    except Exception:  # noqa: BLE001 — неизвестная зона: время будет в UTC
        return None


def _stamp(who: str, when: datetime | None = None) -> str:
    when = (when or datetime.now(timezone.utc)).astimezone(_tz() or timezone.utc)
    return f" — {escape(who)}, {when:%d.%m %H:%M}"


def keyboard(done: bool) -> InlineKeyboardMarkup:
    button = (InlineKeyboardButton(text="↩️ Вернуть в работу", callback_data=CB_REOPEN) if done
              else InlineKeyboardButton(text="✅ Выполнено", callback_data=CB_DONE))
    return InlineKeyboardMarkup(inline_keyboard=[[button]])


def with_state(html_text: str, state_line: str) -> str:
    """Заменяет (или добавляет) строку состояния в конце текста сообщения."""
    base = _STATE_LINE.sub("", html_text).rstrip()
    return f"{base}\n\n{state_line}"


def open_text(html_text: str) -> str:
    return with_state(html_text, OPEN_LINE)


def done_text(html_text: str, who: str, when: datetime | None = None) -> str:
    return with_state(html_text, _DONE + _stamp(who, when))


def reopened_text(html_text: str, who: str, when: datetime | None = None) -> str:
    return with_state(html_text, _REOPENED + _stamp(who, when))
