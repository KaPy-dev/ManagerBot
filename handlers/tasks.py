"""Кнопки «Выполнено» / «Вернуть в работу» под сообщениями в чате менеджеров."""

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery

from main import logger
from modules import tasks

router = Router()


@router.callback_query(F.data.in_({tasks.CB_DONE, tasks.CB_REOPEN}))
async def toggle_task(call: CallbackQuery):
    message = call.message
    if message is None or not message.html_text:
        await call.answer("Сообщение недоступно", show_alert=False)
        return
    who = call.from_user.full_name or call.from_user.username or str(call.from_user.id)
    done = call.data == tasks.CB_DONE
    text = tasks.done_text(message.html_text, who) if done else tasks.reopened_text(message.html_text, who)
    try:
        await message.edit_text(text, reply_markup=tasks.keyboard(done), disable_web_page_preview=True)
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            logger.error(f"Не удалось обновить состояние сообщения {message.message_id}: {e}")
            await call.answer("Не удалось обновить сообщение", show_alert=False)
            return
    logger.info(f"Сообщение {message.message_id} в чате {message.chat.id}: {'выполнено' if done else 'возвращено в работу'} ({who})")
    await call.answer("Отмечено как выполненное" if done else "Возвращено в работу", show_alert=False)
