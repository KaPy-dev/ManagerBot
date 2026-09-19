"""Единый текст заявки для чата менеджеров.

Используется и брифом в Telegram, и внешним API (заявки с сайта), чтобы
менеджеры получали одинаково оформленные сообщения независимо от источника.
"""

from html import escape

# Порядок и подписи полей анкеты в сообщении
FIELDS = (
    ("communication", "Формат коммуникации"),
    ("mounting", "Вариант исполнения"),
    ("service", "Тип обслуживания"),
    ("screen_size", "Размер экрана"),
    ("city", "Город"),
)


def build_callback_text(data: dict, source: str | None = None, extra: list[str] | None = None) -> str:
    """Заказ звонка с сайта: анкеты нет, только ФИО и телефон — менеджеру нужно перезвонить."""
    title = "📞 <b>Заказ звонка</b>" + (f" ({escape(source)})" if source else "")
    note = "Перезвонить клиенту"
    if data.get("lead_id"):
        note += f" · {escape(source or 'сайт')}, заявка #{escape(str(data['lead_id']))}"
    lines = [
        title,
        "",
        f"👤 <b>ФИО:</b> {escape(str(data.get('name') or 'не указано'))}",
        f"📱 <b>Телефон:</b> {escape(str(data.get('phone') or ''))}",
        "",
        note,
    ]
    if extra:
        lines += extra
    return "\n".join(lines)


def build_brief_text(data: dict, client: str, source: str | None = None, extra: list[str] | None = None) -> str:
    """Собирает HTML-текст заявки.

    data    — поля анкеты в человекочитаемом виде (как их записывает бот);
    client  — строка про клиента (уже экранированная, может содержать HTML);
    source  — пометка источника в заголовке, например «сайт»;
    extra   — дополнительные строки в конце (ссылка на страницу и т. п.).
    """
    title = "📋 <b>Новая заявка</b>" + (f" ({escape(source)})" if source else "")
    lines = [title, "", f"<b>Тип закупки:</b> {escape(str(data.get('purchase') or ''))}"]
    for key, label in FIELDS:
        value = data.get(key)
        if value:
            lines.append(f"<b>{label}:</b> {escape(str(value))}")
    if data.get("description"):
        lines.append(f"<b>Комментарий:</b> {escape(str(data['description']))}")
    lines += [
        "",
        f"📞 <b>Телефон:</b> {escape(str(data.get('phone') or ''))}",
        f"📧 <b>Почта:</b> {escape(str(data['email'])) if data.get('email') else 'не указана'}",
        "",
        f"👤 Клиент: {client}",
    ]
    if extra:
        lines += extra
    return "\n".join(lines)
