from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def user_label(user: dict) -> str:
    tg_id = user["tg_id"]
    if user.get("username"):
        return f"👤 @{user['username']} · {tg_id}"
    name = user.get("first_name") or ""
    return f"👤 {name} · {tg_id}".strip(" ·")


def pageNav(prefix: str, page: int, pages: int) -> list:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}:{page - 1}"))
    row.append(InlineKeyboardButton(text=f"{page + 1} / {pages}", callback_data="adm:noop"))
    if page < pages - 1:
        row.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}:{page + 1}"))
    return row


async def usersListPanel(users: list, page: int, pages: int,
                         list_prefix: str, item_prefix: str,
                         search_cb: str, back_cb: str) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text=user_label(u), callback_data=f"{item_prefix}:{u['tg_id']}")]
        for u in users
    ]
    if pages > 1:
        kb.append(pageNav(list_prefix, page, pages))
    kb.append([InlineKeyboardButton(text="🔍 Поиск по ID / юзернейму", callback_data=search_cb)])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def addAdminMenuPanel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Выбрать из списка пользователей", callback_data="adm:pick:0")],
            [InlineKeyboardButton(text="✍️ Ввести ID или @юзернейм", callback_data="adm:enter_admin")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:admins")],
        ]
    )


async def confirmAddPanel(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Назначить админом", callback_data=f"adm:uadd:{user_id}")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="adm:pick:0")],
        ]
    )


async def dossierPanel(back_cb: str = "adm:users:0") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data=back_cb)]]
    )


async def adminMainPanel(is_owner: bool) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="👥 Администраторы", callback_data="adm:admins")],
        [InlineKeyboardButton(text="🗂 Пользователи", callback_data="adm:users:0")],
    ]
    if is_owner:
        kb += [
            [InlineKeyboardButton(text="💬 Чаты бота", callback_data="adm:chats")],
            [InlineKeyboardButton(text="📌 Чат для заявок", callback_data="adm:chat_menu")],
            [InlineKeyboardButton(text="👑 Передать владельца", callback_data="adm:transfer")],
        ]
    kb.append([InlineKeyboardButton(text="✖️ Закрыть", callback_data="adm:close")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def adminsPanel(is_owner: bool) -> InlineKeyboardMarkup:
    kb = []
    if is_owner:
        kb += [
            [InlineKeyboardButton(text="➕ Назначить админа", callback_data="adm:add_admin")],
            [InlineKeyboardButton(text="➖ Удалить админа", callback_data="adm:remove_menu")],
        ]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_label(admin_id: int, username: str | None) -> str:
    return f"👤 {admin_id} · @{username}" if username else f"👤 {admin_id}"


async def removeAdminPanel(admins: list, names: dict) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text=admin_label(admin_id, names.get(str(admin_id))), callback_data=f"adm:rmc:{admin_id}")]
        for admin_id in admins[:20]
    ]
    kb.append([InlineKeyboardButton(text="🔍 Поиск по ID / юзернейму", callback_data="adm:search")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:admins")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def confirmRemovePanel(admin_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить удаление", callback_data=f"adm:rm:{admin_id}")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="adm:remove_menu")],
        ]
    )


async def chatMenuPanel(chats: dict) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text=f"💬 {title}", callback_data=f"adm:setchat:{chat_id}")]
        for chat_id, title in list(chats.items())[:20]
    ]
    kb.append([InlineKeyboardButton(text="✍️ Ввести ID вручную", callback_data="adm:enter_chat")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)


async def confirmTransferPanel(new_owner_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить передачу", callback_data=f"adm:tconf:{new_owner_id}")],
            [InlineKeyboardButton(text="⬅️ Отмена", callback_data="adm:back")],
        ]
    )


async def backPanel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="adm:back")]]
    )
