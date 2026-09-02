from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
    )


def navRow(back: bool = True) -> list:
    row = []
    if back:
        row.append(InlineKeyboardButton(text="⬅️ Назад", callback_data="brief:back"))
    row.append(InlineKeyboardButton(text="❌ Отменить", callback_data="brief:cancel"))
    return row


async def purchaseTypePanel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🏢 Коммерческая", callback_data="purchase:commercial"),
            ],
            [
                InlineKeyboardButton(text="🏛 Госзакупка по 44ФЗ", callback_data="purchase:gov44"),
            ],
            [
                InlineKeyboardButton(text="🏛 Госзакупка по 223ФЗ", callback_data="purchase:gov223"),
            ],
            navRow(back=False),
        ]
    )


async def govCommunicationPanel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Требуется помощь в подготовке ТЗ", callback_data="gov_comm:tz_help"),
            ],
            [
                InlineKeyboardButton(text="💬 Требуется консультация по продукции", callback_data="gov_comm:consult"),
            ],
            navRow(),
        ]
    )


async def mountingPanel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🧱 Настенный", callback_data="mounting:wall"),
            ],
            [
                InlineKeyboardButton(text="🏗 Отдельно стоящая конструкция", callback_data="mounting:standalone"),
            ],
            [
                InlineKeyboardButton(text="🔲 Напольный", callback_data="mounting:floor"),
            ],
            navRow(),
        ]
    )


async def serviceTypePanel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="↔️ Фронтальный", callback_data="service:front"),
            ],
            [
                InlineKeyboardButton(text="🔄 Тыльный", callback_data="service:rear"),
            ],
            navRow(),
        ]
    )


async def phonePanel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📱 Отправить мой номер", request_contact=True),
            ],
            [
                KeyboardButton(text="⬅️ Назад"),
                KeyboardButton(text="❌ Отменить"),
            ]
        ], resize_keyboard=True, one_time_keyboard=True
    )


async def cityPanel() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📍 Отправить текущее местоположение", request_location=True),
            ],
            [
                KeyboardButton(text="⬅️ Назад"),
                KeyboardButton(text="❌ Отменить"),
            ]
        ], resize_keyboard=True, one_time_keyboard=True
    )


async def textStepPanel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[navRow()])


async def emailPanel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⏭ Пропустить", callback_data="brief:skip_email"),
            ],
            navRow(),
        ]
    )


async def resumePanel() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="▶️ Продолжить", callback_data="brief:resume"),
            ],
            [
                InlineKeyboardButton(text="🔄 Начать заново", callback_data="brief:restart"),
            ]
        ]
    )
