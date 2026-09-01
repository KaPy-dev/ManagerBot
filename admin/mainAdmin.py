import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import fsm
from modules.storage import storage
from modules.orm.user import (
    get_users_page, count_users, search_users, find_by_username,
    get_user, user_dossier, PER_PAGE
)
from main import insert_bot, logger

router = Router()


def dossier_text(dossier: dict) -> str:
    user = dossier["user"]
    counts = dossier["counts"]
    last = dossier["last_brief"]
    name = " ".join(filter(None, [user.get("first_name"), user.get("last_name")])) or "—"
    username = f"@{user['username']}" if user.get("username") else "—"
    lines = [
        "🗂 <b>Досье пользователя</b>",
        "",
        f"<b>ID:</b> <code>{user['tg_id']}</code>",
        f"<b>Юзернейм:</b> {username}",
        f"<b>Имя:</b> {name}",
        f"<b>Язык:</b> {user.get('language_code') or '—'}"
        + (" · ⭐ Premium" if user.get("is_premium") else ""),
        f"<b>Первый визит:</b> {user['first_seen']}",
        f"<b>Последняя активность:</b> {user['last_seen']}",
        "",
        f"<b>Заявок завершено:</b> {counts.get('completed', 0)}",
        f"<b>Заявок отменено:</b> {counts.get('cancelled', 0)}",
    ]
    if last:
        lines += ["", f"📋 <b>Последняя заявка</b> ({last['created_at']}, {last['status']})"]
        for field, title in (("purchase", "Тип закупки"), ("communication", "Коммуникация"),
                             ("mounting", "Исполнение"), ("service", "Обслуживание"),
                             ("screen_size", "Размер"), ("city", "Город"),
                             ("phone", "Телефон"), ("email", "Почта")):
            if last.get(field):
                lines.append(f"{title}: {last[field]}")
    return "\n".join(lines)


CHAT_TYPE_RU = {"channel": "канал", "supergroup": "группа", "group": "группа"}


def chat_line(chat_id) -> str:
    info = storage.chat_info(chat_id)
    icon = "📢" if info.get("type") == "channel" else "💬"
    type_ru = CHAT_TYPE_RU.get(info.get("type"), "чат")
    return f"{icon} <b>{info['title']}</b> ({type_ru}) — <code>{chat_id}</code>"


async def refresh_chats():
    for chat_id in list(storage.chats.keys()):
        try:
            chat = await insert_bot.get_chat(int(chat_id))
            title = chat.title or chat.username or str(chat_id)
            await storage.add_chat(int(chat_id), title, chat.type)
        except AttributeError:
            pass
        except Exception:
            logger.info(f"Чат {chat_id} недоступен — убираю из списка")
            await storage.remove_chat(int(chat_id))


async def users_list_view(call: CallbackQuery, page: int, item_prefix: str,
                          list_prefix: str, search_cb: str, back_cb: str, title: str):
    from keyboard.admin.mainAdmin import usersListPanel
    total = await count_users()
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    page = min(max(page, 0), pages - 1)
    users = await get_users_page(page)
    text = f"{title}\n\nВсего пользователей: <b>{total}</b>"
    await safe_edit(call, text, await usersListPanel(users, page, pages, list_prefix, item_prefix, search_cb, back_cb))


def panel_text(user_id: int) -> str:
    role = "👑 Владелец" if storage.is_owner(user_id) else "🛡 Администратор"
    chat = storage.manager_chat_id
    if chat == 0:
        chat_str = "не задан ⚠️"
    elif str(chat) in storage.data["chats"]:
        info = storage.chat_info(chat)
        chat_str = f"<b>{info['title']}</b> (<code>{chat}</code>)"
    else:
        chat_str = f"<code>{chat}</code>"
    text = f"⚙️ <b>Панель управления</b>\n\nВаша роль: <b>{role}</b>"
    if storage.is_owner(user_id):
        text += f"\nЧат для заявок: {chat_str}"
    return text


async def safe_edit(call: CallbackQuery, text: str, markup):
    try:
        await call.message.edit_text(text, reply_markup=markup)
    except TelegramBadRequest:
        await call.message.answer(text, reply_markup=markup)


@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if not storage.is_admin(user_id):
        return
    from keyboard.admin.mainAdmin import adminMainPanel
    await state.clear()
    await message.answer(panel_text(user_id), reply_markup=await adminMainPanel(storage.is_owner(user_id)))


@router.callback_query(F.data.startswith("adm:"))
async def admin_callbacks(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if not storage.is_admin(user_id):
        await call.answer("Нет доступа", show_alert=True)
        return

    action = call.data.split(":", 2)[1]
    is_owner = storage.is_owner(user_id)

    owner_only = {"chats", "chat_menu", "setchat", "enter_chat", "transfer", "tconf",
                  "add_admin", "remove_menu", "rm", "rmc", "search",
                  "pick", "uadd", "enter_admin", "psearch"}
    if action in owner_only and not is_owner:
        await call.answer("Доступно только владельцу", show_alert=True)
        return

    await call.answer()

    if action == "noop":
        return

    if action == "users":
        parts = call.data.split(":")
        page = int(parts[2]) if len(parts) > 2 else 0
        await state.clear()
        await users_list_view(call, page, "adm:udos", "adm:users", "adm:usearch", "adm:back",
                              "🗂 <b>Пользователи бота</b>")
        return

    if action == "udos":
        from keyboard.admin.mainAdmin import dossierPanel
        tg_id = int(call.data.split(":")[2])
        dossier = await user_dossier(tg_id)
        if dossier is None:
            await safe_edit(call, "⚠️ Пользователь не найден в базе.", await dossierPanel())
            return
        await safe_edit(call, dossier_text(dossier), await dossierPanel())
        return

    if action == "usearch":
        from keyboard.admin.mainAdmin import backPanel
        await state.set_state(fsm.AdminFSM.enter_search)
        await state.update_data(search_mode="users")
        await safe_edit(call, "🔍 <b>Поиск пользователя</b>\n\nОтправьте ID, юзернейм или имя:", await backPanel())
        return

    if action == "pick":
        parts = call.data.split(":")
        page = int(parts[2]) if len(parts) > 2 else 0
        await state.clear()
        await users_list_view(call, page, "adm:uadd", "adm:pick", "adm:psearch", "adm:admins",
                              "➕ <b>Назначение администратора</b>\n\nВыберите пользователя:")
        return

    if action == "psearch":
        from keyboard.admin.mainAdmin import backPanel
        await state.set_state(fsm.AdminFSM.enter_search)
        await state.update_data(search_mode="pick")
        await safe_edit(call, "🔍 <b>Поиск пользователя</b>\n\nОтправьте ID, юзернейм или имя:", await backPanel())
        return

    if action == "uadd":
        tg_id = int(call.data.split(":")[2])
        user = await get_user(tg_id)
        username = user.get("username") if user else None
        added = await storage.add_admin(tg_id, username)
        logger.info(f"Owner {user_id} added admin {tg_id} from list: {added}")
        result = f"✅ Пользователь <code>{tg_id}</code> назначен администратором." if added \
            else f"⚠️ Пользователь <code>{tg_id}</code> уже администратор или владелец."
        from keyboard.admin.mainAdmin import adminMainPanel
        await safe_edit(call, result + "\n\n" + panel_text(user_id), await adminMainPanel(is_owner))
        return

    if action == "close":
        await state.clear()
        try:
            await call.message.delete()
        except TelegramBadRequest:
            pass
        return

    if action == "back":
        from keyboard.admin.mainAdmin import adminMainPanel
        await state.clear()
        await safe_edit(call, panel_text(user_id), await adminMainPanel(is_owner))
        return

    if action == "admins":
        from keyboard.admin.mainAdmin import adminsPanel
        lines = [f"👑 <code>{storage.owner_id}</code> — владелец"]
        for admin_id in storage.admins:
            name = storage.admin_name(admin_id)
            lines.append(f"🛡 <code>{admin_id}</code>" + (f" · @{name}" if name else ""))
        text = "👥 <b>Администраторы</b>\n\n" + "\n".join(lines)
        await safe_edit(call, text, await adminsPanel(is_owner))
        return

    if action == "add_admin":
        from keyboard.admin.mainAdmin import addAdminMenuPanel
        await state.clear()
        await safe_edit(
            call,
            "➕ <b>Назначение администратора</b>\n\nКак выбрать пользователя?",
            await addAdminMenuPanel()
        )
        return

    if action == "enter_admin":
        from keyboard.admin.mainAdmin import backPanel
        await state.set_state(fsm.AdminFSM.enter_admin_id)
        await safe_edit(
            call,
            "✍️ <b>Назначение администратора</b>\n\n"
            "Отправьте <b>@юзернейм</b> или <b>Telegram ID</b> пользователя.\n"
            "По юзернейму найдутся только те, кто хотя бы раз запускал бота.",
            await backPanel()
        )
        return

    if action == "remove_menu":
        from keyboard.admin.mainAdmin import removeAdminPanel
        await state.clear()
        admins = storage.admins
        text = "➖ <b>Удаление администратора</b>\n\nВыберите пользователя:" if admins \
            else "➖ <b>Удаление администратора</b>\n\nСписок администраторов пуст."
        await safe_edit(call, text, await removeAdminPanel(admins, storage.data["admin_names"]))
        return

    if action == "search":
        from keyboard.admin.mainAdmin import backPanel
        await state.set_state(fsm.AdminFSM.enter_search)
        await state.update_data(search_mode="remove")
        await safe_edit(
            call,
            "🔍 <b>Поиск администратора</b>\n\n"
            "Отправьте ID (или его часть) либо юзернейм:",
            await backPanel()
        )
        return

    if action == "rmc":
        admin_id = int(call.data.split(":")[2])
        from keyboard.admin.mainAdmin import confirmRemovePanel, admin_label
        label = admin_label(admin_id, storage.admin_name(admin_id))
        await safe_edit(
            call,
            f"➖ <b>Удаление администратора</b>\n\n"
            f"{label}\n\nПодтвердить удаление?",
            await confirmRemovePanel(admin_id)
        )
        return

    if action == "rm":
        admin_id = int(call.data.split(":")[2])
        removed = await storage.remove_admin(admin_id)
        from keyboard.admin.mainAdmin import removeAdminPanel
        result = f"✅ Администратор <code>{admin_id}</code> удалён." if removed else "⚠️ Пользователь не найден в списке."
        logger.info(f"Owner {user_id} removed admin {admin_id}: {removed}")
        await safe_edit(call, f"➖ <b>Удаление администратора</b>\n\n{result}",
                        await removeAdminPanel(storage.admins, storage.data["admin_names"]))
        return

    if action == "chats":
        from keyboard.admin.mainAdmin import backPanel
        await refresh_chats()
        chats = storage.chats
        if chats:
            lines = [chat_line(chat_id) for chat_id in chats]
            text = "💬 <b>Чаты, в которых состоит бот</b>\n\n" + "\n".join(lines)
        else:
            text = "💬 <b>Чаты бота</b>\n\nБот пока не добавлен ни в один чат или канал."
        await safe_edit(call, text, await backPanel())
        return

    if action == "chat_menu":
        from keyboard.admin.mainAdmin import chatMenuPanel
        await refresh_chats()
        chat = storage.manager_chat_id
        current = chat_line(chat) if chat != 0 and str(chat) in storage.data["chats"] \
            else (f"<code>{chat}</code>" if chat != 0 else "не задан ⚠️")
        await safe_edit(
            call,
            f"📌 <b>Чат для заявок</b>\n\nТекущий: {current}\n\n"
            "Выберите чат из списка или введите ID вручную:",
            await chatMenuPanel(storage.chats)
        )
        return

    if action == "setchat":
        chat_id = int(call.data.split(":")[2])
        await storage.set_manager_chat(chat_id)
        logger.info(f"Owner {user_id} set manager chat to {chat_id}")
        from keyboard.admin.mainAdmin import adminMainPanel
        await safe_edit(call, f"✅ Чат для заявок обновлён: <code>{chat_id}</code>\n\n" + panel_text(user_id),
                        await adminMainPanel(is_owner))
        return

    if action == "enter_chat":
        from keyboard.admin.mainAdmin import backPanel
        await state.set_state(fsm.AdminFSM.enter_chat_id)
        await safe_edit(
            call,
            "✍️ <b>Ввод ID чата</b>\n\n"
            "Отправьте ID чата или канала числом.\n"
            "Для групп и каналов ID обычно начинается с <code>-100</code>",
            await backPanel()
        )
        return

    if action == "transfer":
        from keyboard.admin.mainAdmin import backPanel
        await state.set_state(fsm.AdminFSM.enter_transfer_id)
        await safe_edit(
            call,
            "👑 <b>Передача владельца</b>\n\n"
            "⚠️ Внимание: после передачи вы станете обычным администратором.\n\n"
            "Отправьте Telegram ID нового владельца числом:",
            await backPanel()
        )
        return

    if action == "tconf":
        new_owner_id = int(call.data.split(":")[2])
        if not storage.is_owner(user_id):
            return
        await storage.transfer_owner(new_owner_id)
        await state.clear()
        logger.info(f"Ownership transferred from {user_id} to {new_owner_id}")
        from keyboard.admin.mainAdmin import adminMainPanel
        await safe_edit(
            call,
            f"👑 Права владельца переданы пользователю <code>{new_owner_id}</code>.\n"
            "Вы стали администратором.\n\n" + panel_text(user_id),
            await adminMainPanel(storage.is_owner(user_id))
        )
        return


def parse_id(text: str) -> int | None:
    text = (text or "").strip()
    if re.fullmatch(r"-?\d{1,15}", text):
        return int(text)
    return None


@router.message(fsm.AdminFSM.enter_admin_id, F.text)
async def enter_admin_id_handler(message: Message, state: FSMContext):
    if not storage.is_owner(message.from_user.id):
        await state.clear()
        return
    from keyboard.admin.mainAdmin import backPanel
    text = (message.text or "").strip()
    new_id = parse_id(text)
    username = None
    if new_id is None:
        handle = text.lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{4,32}", handle):
            await message.answer("⚠️ Отправьте Telegram ID числом или @юзернейм:", reply_markup=await backPanel())
            return
        user_row = await find_by_username(handle)
        if user_row is None:
            await message.answer(
                f"⚠️ Пользователь @{handle} не найден.\n"
                "Он должен хотя бы раз запустить бота.",
                reply_markup=await backPanel()
            )
            return
        new_id = user_row["tg_id"]
        username = user_row.get("username")
    if new_id <= 0:
        await message.answer("⚠️ Отправьте корректный Telegram ID числом:", reply_markup=await backPanel())
        return
    if new_id == storage.owner_id:
        await message.answer("⚠️ Этот пользователь — владелец.", reply_markup=await backPanel())
        return
    if username is None:
        user_row = await get_user(new_id)
        if user_row:
            username = user_row.get("username")
        else:
            try:
                chat = await insert_bot.get_chat(new_id)
                username = getattr(chat, "username", None)
            except Exception:
                pass
    added = await storage.add_admin(new_id, username)
    await state.clear()
    logger.info(f"Owner {message.from_user.id} added admin {new_id}: {added}")
    result = f"✅ Пользователь <code>{new_id}</code> назначен администратором." if added \
        else f"⚠️ Пользователь <code>{new_id}</code> уже администратор."
    from keyboard.admin.mainAdmin import adminMainPanel
    await message.answer(result + "\n\n" + panel_text(message.from_user.id),
                         reply_markup=await adminMainPanel(True))


@router.message(fsm.AdminFSM.enter_search, F.text)
async def admin_search_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    mode = data.get("search_mode", "remove")
    if mode == "users":
        if not storage.is_admin(user_id):
            await state.clear()
            return
    elif not storage.is_owner(user_id):
        await state.clear()
        return

    query = (message.text or "").strip().lstrip("@").lower()
    await state.clear()

    if mode == "remove":
        from keyboard.admin.mainAdmin import removeAdminPanel
        names = storage.data["admin_names"]
        found = [
            admin_id for admin_id in storage.admins
            if query in str(admin_id) or query in (names.get(str(admin_id)) or "").lower()
        ]
        text = f"🔍 Найдено по запросу «{query}»: {len(found)}" if found \
            else f"🔍 По запросу «{query}» никого не нашлось."
        await message.answer("➖ <b>Удаление администратора</b>\n\n" + text,
                             reply_markup=await removeAdminPanel(found, names))
        return

    from keyboard.admin.mainAdmin import usersListPanel
    users = await search_users(query)
    if mode == "pick":
        item_prefix, list_prefix, search_cb, back_cb = "adm:uadd", "adm:pick", "adm:psearch", "adm:pick:0"
        title = "➕ <b>Назначение администратора</b>"
    else:
        item_prefix, list_prefix, search_cb, back_cb = "adm:udos", "adm:users", "adm:usearch", "adm:users:0"
        title = "🗂 <b>Пользователи бота</b>"
    text = f"{title}\n\n🔍 Найдено по запросу «{query}»: {len(users)}" if users \
        else f"{title}\n\n🔍 По запросу «{query}» никого не нашлось."
    await message.answer(text, reply_markup=await usersListPanel(users, 0, 1, list_prefix, item_prefix, search_cb, back_cb))


@router.message(fsm.AdminFSM.enter_chat_id, F.text)
async def enter_chat_id_handler(message: Message, state: FSMContext):
    if not storage.is_owner(message.from_user.id):
        await state.clear()
        return
    from keyboard.admin.mainAdmin import backPanel
    chat_id = parse_id(message.text)
    if chat_id is None:
        await message.answer("⚠️ Отправьте корректный ID чата числом:", reply_markup=await backPanel())
        return
    await storage.set_manager_chat(chat_id)
    await state.clear()
    logger.info(f"Owner {message.from_user.id} set manager chat to {chat_id}")
    from keyboard.admin.mainAdmin import adminMainPanel
    await message.answer(f"✅ Чат для заявок обновлён: <code>{chat_id}</code>\n\n" + panel_text(message.from_user.id),
                         reply_markup=await adminMainPanel(True))


@router.message(fsm.AdminFSM.enter_transfer_id, F.text)
async def enter_transfer_id_handler(message: Message, state: FSMContext):
    if not storage.is_owner(message.from_user.id):
        await state.clear()
        return
    from keyboard.admin.mainAdmin import backPanel, confirmTransferPanel
    new_id = parse_id(message.text)
    if new_id is None or new_id <= 0:
        await message.answer("⚠️ Отправьте корректный Telegram ID числом:", reply_markup=await backPanel())
        return
    if new_id == storage.owner_id:
        await message.answer("⚠️ Вы уже владелец.", reply_markup=await backPanel())
        return
    await message.answer(
        f"👑 Передать права владельца пользователю <code>{new_id}</code>?\n\n"
        "⚠️ Действие необратимо — вернуть права сможет только новый владелец.",
        reply_markup=await confirmTransferPanel(new_id)
    )
