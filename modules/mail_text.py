"""Текст входящего письма для чата менеджеров.

Письма с почты компании принимает микросервис mailwatcher сайта DIPLED и присылает сюда
через POST /api/v1/mail. Копия функции живёт в dipled/mailwatcher/mailwatcher/notify.py
(запасной канал «напрямую в Telegram») — при правках держать одинаковыми.
"""

from html import escape


def format_size(size: int) -> str:
    if size < 1024:
        return f"{size} Б"
    if size < 1024 * 1024:
        return f"{round(size / 1024)} КБ"
    return f"{size / 1024 / 1024:.1f} МБ"


def build_mail_text(data: dict) -> str:
    """HTML-текст письма. data — поля из запроса сайта (см. api/server.py: MAIL_FIELDS)."""
    sender = escape(str(data.get("sender") or ""))
    name = escape(str(data.get("sender_name") or ""))
    who = f"{name} &lt;{sender}&gt;" if name and sender else name or sender or "не указан"
    title = "📨 <b>Письмо на почту</b>" + (f" ({escape(str(data['mailbox']))})" if data.get("mailbox") else "")
    lines = [title, "", f"<b>От:</b> {who}", f"<b>Тема:</b> {escape(str(data.get('subject') or '(без темы)'))}"]
    if data.get("sent_at_text"):
        lines.append(f"<b>Дата:</b> {escape(str(data['sent_at_text']))}")
    attachments = [a for a in data.get("attachments") or [] if isinstance(a, dict) and a.get("name")]
    if attachments:
        listed = ", ".join(f"{escape(str(a['name']))} ({format_size(int(a.get('size') or 0))})" for a in attachments[:10])
        more = f" и ещё {len(attachments) - 10}" if len(attachments) > 10 else ""
        lines.append(f"📎 <b>Вложения:</b> {listed}{more}")
    body = str(data.get("body") or "").strip()
    lines.append("")
    if body:
        lines.append(f"<blockquote expandable>{escape(body)}{'…' if data.get('truncated') else ''}</blockquote>")
    else:
        lines.append("<i>(письмо без текста)</i>")
    footer = [f"✉️ письмо #{escape(str(data['mail_id']))}"] if data.get("mail_id") else ["✉️ письмо"]
    if data.get("matched_rule"):
        footer.append(f"правило «{escape(str(data['matched_rule']))}»")
    if data.get("truncated"):
        footer.append("полный текст в админке сайта")
    lines += ["", " · ".join(footer)]
    return "\n".join(lines)
