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
    """HTML-текст письма для чата менеджеров: кто написал (имя и адрес отдельно), тема, вложения, текст, дата."""
    sender = escape(str(data.get("sender") or ""))
    name = escape(str(data.get("sender_name") or ""))
    lines = ["📨 <b>Письмо на почту</b>", ""]
    if name:
        lines.append(f"👤 <b>От:</b> {name}")
        if sender:
            lines.append(f"📧 {sender}")
    else:
        lines.append(f"👤 <b>От:</b> {sender or 'не указан'}")
    lines.append(f"📝 <b>Тема:</b> {escape(str(data.get('subject') or '(без темы)'))}")
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
    lines.append("")
    if data.get("sent_at_text"):
        lines.append(f"🕒 {escape(str(data['sent_at_text']))}")
    if data.get("truncated"):
        lines.append("<i>Текст сокращён — полностью письмо в ящике и в админке сайта</i>")
    return "\n".join(lines).rstrip()
