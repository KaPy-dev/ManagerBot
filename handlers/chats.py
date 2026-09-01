from aiogram import Router
from aiogram.types import ChatMemberUpdated
from modules.storage import storage
from main import logger

router = Router()


@router.my_chat_member()
async def bot_membership_changed(event: ChatMemberUpdated):
    chat = event.chat
    if chat.type == "private":
        return
    status = event.new_chat_member.status
    if status in ("member", "administrator", "creator"):
        title = chat.title or chat.username or str(chat.id)
        await storage.add_chat(chat.id, title, chat.type)
        logger.info(f"Bot added to chat {chat.id} ({title})")
    else:
        await storage.remove_chat(chat.id)
        logger.info(f"Bot removed from chat {chat.id}")
