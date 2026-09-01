import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
import fsm
from modules.storage import storage
from main import insert_bot, logger

router = Router()

PHONE_RE = re.compile(r"^\+?[78]?[\s\-\(\)]*(\d[\s\-\(\)]*){10}$")
EMAIL_RE = re.compile(r"^[\w\.\-]+@[\w\-]+\.[a-zA-Z]{2,}$")
SIZE_RE = re.compile(r"^\s*(\d{2,5})\s*[xхXХ*×\s]\s*(\d{2,5})\s*$")

PURCHASE_NAMES = {
    "commercial": "Коммерческая",
    "gov44": "Госзакупка по 44ФЗ",
    "gov223": "Госзакупка по 223ФЗ",
}

GOV_COMM_NAMES = {
    "tz_help": "Требуется помощь в подготовке ТЗ",
    "consult": "Требуется консультация по продукции",
}

MOUNTING_NAMES = {
    "wall": "Настенный",
    "standalone": "Отдельно стоящая конструкция",
    "floor": "Напольный",
}

SERVICE_NAMES = {
    "front": "Фронтальный",
    "rear": "Тыльный",
}


async def clear_markup(call: CallbackQuery):
    try:
        await call.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        pass


async def ask_purchase(message: Message, state: FSMContext):
    from keyboard.panels import purchaseTypePanel
    await message.answer(
        "<b>Шаг 1</b> · Тип закупки\n\nЗакупка коммерческая или госзакупка?",
        reply_markup=await purchaseTypePanel()
    )
    await state.set_state(fsm.Brief.purchase_type)


async def ask_gov_comm(message: Message, state: FSMContext):
    from keyboard.panels import govCommunicationPanel
    await message.answer(
        "<b>Шаг 2 из 4</b> · Формат коммуникации\n\nЧто вам требуется?",
        reply_markup=await govCommunicationPanel()
    )
    await state.set_state(fsm.Brief.gov_communication)


async def ask_mounting(message: Message, state: FSMContext):
    from keyboard.panels import mountingPanel
    await message.answer(
        "<b>Шаг 2 из 7</b> · Вариант исполнения\n\nВыберите вариант исполнения экрана:",
        reply_markup=await mountingPanel()
    )
    await state.set_state(fsm.Brief.com_mounting)


async def ask_service(message: Message, state: FSMContext):
    from keyboard.panels import serviceTypePanel
    await message.answer(
        "<b>Шаг 3 из 7</b> · Тип обслуживания\n\nВыберите тип обслуживания:",
        reply_markup=await serviceTypePanel()
    )
    await state.set_state(fsm.Brief.com_service_type)


async def ask_size(message: Message, state: FSMContext):
    from keyboard.panels import textStepPanel
    await message.answer(
        "<b>Шаг 4 из 7</b> · Размер экрана\n\n"
        "Укажите примерный размер экрана в сантиметрах —\n"
        "горизонталь и вертикаль, например: <code>300 x 200</code>",
        reply_markup=await textStepPanel()
    )
    await state.set_state(fsm.Brief.com_screen_size)


async def ask_city(message: Message, state: FSMContext):
    from keyboard.panels import textStepPanel
    await message.answer(
        "<b>Шаг 5 из 7</b> · Город\n\nУкажите город установки/доставки:",
        reply_markup=await textStepPanel()
    )
    await state.set_state(fsm.Brief.com_city)


async def ask_phone(message: Message, state: FSMContext):
    from keyboard.panels import phonePanel
    data = await state.get_data()
    step = "Шаг 3 из 4" if data.get("branch") == "gov" else "Шаг 6 из 7"
    await message.answer(
        f"<b>{step}</b> · Телефон\n\n"
        "Введите номер телефона для обратной связи,\n"
        "например: <code>+7 900 000 00 00</code>\n\n"
        "Или нажмите кнопку ниже, чтобы отправить номер из профиля Telegram 👇",
        reply_markup=await phonePanel()
    )
    await state.set_state(fsm.Brief.phone)


async def ask_email(message: Message, state: FSMContext):
    from keyboard.panels import textStepPanel
    data = await state.get_data()
    step = "Шаг 4 из 4" if data.get("branch") == "gov" else "Шаг 7 из 7"
    await message.answer(
        f"<b>{step}</b> · Почта\n\n"
        "Введите адрес электронной почты,\n"
        "например: <code>name@example.com</code>",
        reply_markup=await textStepPanel()
    )
    await state.set_state(fsm.Brief.email)


ASK = {
    fsm.Brief.purchase_type.state: ask_purchase,
    fsm.Brief.gov_communication.state: ask_gov_comm,
    fsm.Brief.com_mounting.state: ask_mounting,
    fsm.Brief.com_service_type.state: ask_service,
    fsm.Brief.com_screen_size.state: ask_size,
    fsm.Brief.com_city.state: ask_city,
    fsm.Brief.phone.state: ask_phone,
    fsm.Brief.email.state: ask_email,
}

PREV = {
    fsm.Brief.gov_communication.state: ask_purchase,
    fsm.Brief.com_mounting.state: ask_purchase,
    fsm.Brief.com_service_type.state: ask_mounting,
    fsm.Brief.com_screen_size.state: ask_service,
    fsm.Brief.com_city.state: ask_size,
    fsm.Brief.email.state: ask_phone,
}


@router.message(CommandStart())
@router.message(Command("brief"))
async def start_handler(message: Message, state: FSMContext):
    current = await state.get_state()
    data = await state.get_data()
    if current in ASK and data:
        from keyboard.panels import resumePanel
        await message.answer(
            "📋 У вас есть незавершённая заявка.\n\nПродолжить с того же места?",
            reply_markup=await resumePanel()
        )
        return
    await state.clear()
    logger.info(f"User {message.from_user.id} started brief")
    await message.answer(
        "👋 <b>Здравствуйте!</b>\n\n"
        "Я помогу оформить заявку — это займёт пару минут.\n"
        "В любой момент можно вернуться назад или отменить заполнение."
    )
    await ask_purchase(message, state)


@router.callback_query(F.data == "brief:resume")
async def resume_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await clear_markup(call)
    current = await state.get_state()
    if current in ASK:
        await ASK[current](call.message, state)
    else:
        await state.clear()
        await ask_purchase(call.message, state)


@router.callback_query(F.data == "brief:restart")
async def restart_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await clear_markup(call)
    await state.clear()
    await ask_purchase(call.message, state)


async def log_cancelled(user_id: int, data: dict):
    if not data.get("purchase"):
        return
    from modules.orm.user import save_brief
    try:
        await save_brief(user_id, "cancelled", data)
    except Exception:
        logger.error(f"Не удалось сохранить отменённую заявку {user_id}", exc_info=True)


@router.callback_query(F.data == "brief:cancel")
async def cancel_handler(call: CallbackQuery, state: FSMContext):
    await call.answer("Заявка отменена")
    await clear_markup(call)
    await log_cancelled(call.from_user.id, await state.get_data())
    await state.clear()
    await call.message.answer("❌ Заполнение отменено.\n\nЧтобы начать заново — отправьте /start")


@router.callback_query(F.data == "brief:back")
async def back_handler(call: CallbackQuery, state: FSMContext):
    await call.answer()
    current = await state.get_state()
    if current == fsm.Brief.phone.state:
        data = await state.get_data()
        prev = ask_gov_comm if data.get("branch") == "gov" else ask_city
    else:
        prev = PREV.get(current)
    if prev is None:
        return
    await clear_markup(call)
    await prev(call.message, state)


@router.callback_query(fsm.Brief.purchase_type, F.data.startswith("purchase:"))
async def purchase_type_handler(call: CallbackQuery, state: FSMContext):
    purchase = call.data.split(":")[1]
    if purchase not in PURCHASE_NAMES:
        await call.answer()
        return
    branch = "com" if purchase == "commercial" else "gov"
    await state.update_data(purchase=PURCHASE_NAMES[purchase], branch=branch)
    await call.answer()
    await clear_markup(call)
    if branch == "com":
        await ask_mounting(call.message, state)
    else:
        await ask_gov_comm(call.message, state)


@router.callback_query(fsm.Brief.gov_communication, F.data.startswith("gov_comm:"))
async def gov_communication_handler(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":")[1]
    if key not in GOV_COMM_NAMES:
        await call.answer()
        return
    await state.update_data(communication=GOV_COMM_NAMES[key])
    await call.answer()
    await clear_markup(call)
    await ask_phone(call.message, state)


@router.callback_query(fsm.Brief.com_mounting, F.data.startswith("mounting:"))
async def mounting_handler(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":")[1]
    if key not in MOUNTING_NAMES:
        await call.answer()
        return
    await state.update_data(mounting=MOUNTING_NAMES[key])
    await call.answer()
    await clear_markup(call)
    await ask_service(call.message, state)


@router.callback_query(fsm.Brief.com_service_type, F.data.startswith("service:"))
async def service_type_handler(call: CallbackQuery, state: FSMContext):
    key = call.data.split(":")[1]
    if key not in SERVICE_NAMES:
        await call.answer()
        return
    await state.update_data(service=SERVICE_NAMES[key])
    await call.answer()
    await clear_markup(call)
    await ask_size(call.message, state)


@router.message(fsm.Brief.com_screen_size, F.text)
async def screen_size_handler(message: Message, state: FSMContext):
    match = SIZE_RE.match(message.text or "")
    if not match:
        from keyboard.panels import textStepPanel
        await message.answer(
            "⚠️ Не удалось распознать размеры.\n\n"
            "Введите два числа в сантиметрах — горизонталь и вертикаль,\n"
            "например: <code>300 x 200</code>",
            reply_markup=await textStepPanel()
        )
        return
    await state.update_data(screen_size=f"{match.group(1)} x {match.group(2)} см (Г x В)")
    await ask_city(message, state)


@router.message(fsm.Brief.com_city, F.text)
async def city_handler(message: Message, state: FSMContext):
    city = (message.text or "").strip()
    if not city or len(city) > 100 or city.startswith("/"):
        from keyboard.panels import textStepPanel
        await message.answer(
            "⚠️ Укажите город текстом, например: <code>Москва</code>",
            reply_markup=await textStepPanel()
        )
        return
    await state.update_data(city=city)
    await ask_phone(message, state)


@router.message(fsm.Brief.phone, F.contact)
async def phone_contact_handler(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"
    await state.update_data(phone=phone)
    await message.answer(f"📞 Принято: <code>{phone}</code>", reply_markup=ReplyKeyboardRemove())
    await ask_email(message, state)


@router.message(fsm.Brief.phone, F.text == "⬅️ Назад")
async def phone_back_handler(message: Message, state: FSMContext):
    await message.answer("↩️ Возвращаемся…", reply_markup=ReplyKeyboardRemove())
    data = await state.get_data()
    prev = ask_gov_comm if data.get("branch") == "gov" else ask_city
    await prev(message, state)


@router.message(fsm.Brief.phone, F.text == "❌ Отменить")
async def phone_cancel_handler(message: Message, state: FSMContext):
    await log_cancelled(message.from_user.id, await state.get_data())
    await state.clear()
    await message.answer(
        "❌ Заполнение отменено.\n\nЧтобы начать заново — отправьте /start",
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(fsm.Brief.phone, F.text)
async def phone_handler(message: Message, state: FSMContext):
    phone = (message.text or "").strip()
    if not PHONE_RE.match(phone):
        await message.answer(
            "⚠️ Номер не распознан.\n\n"
            "Введите номер телефона в формате: <code>+7 900 000 00 00</code> —\n"
            "или отправьте номер из профиля кнопкой ниже 👇"
        )
        return
    await state.update_data(phone=phone)
    await message.answer(f"📞 Принято: <code>{phone}</code>", reply_markup=ReplyKeyboardRemove())
    await ask_email(message, state)


@router.message(fsm.Brief.email, F.text)
async def email_handler(message: Message, state: FSMContext):
    email = (message.text or "").strip()
    if not EMAIL_RE.match(email):
        from keyboard.panels import textStepPanel
        await message.answer(
            "⚠️ Почта не распознана.\n\n"
            "Введите адрес в формате: <code>name@example.com</code>",
            reply_markup=await textStepPanel()
        )
        return
    await state.update_data(email=email)
    await finish_brief(message, state)


async def finish_brief(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    user = message.from_user
    username = f"@{user.username}" if user.username else "не указан"

    lines = [
        "📋 <b>Новая заявка</b>",
        "",
        f"<b>Тип закупки:</b> {data.get('purchase')}",
    ]
    if "communication" in data:
        lines.append(f"<b>Формат коммуникации:</b> {data['communication']}")
    if "mounting" in data:
        lines.append(f"<b>Вариант исполнения:</b> {data['mounting']}")
    if "service" in data:
        lines.append(f"<b>Тип обслуживания:</b> {data['service']}")
    if "screen_size" in data:
        lines.append(f"<b>Размер экрана:</b> {data['screen_size']}")
    if "city" in data:
        lines.append(f"<b>Город:</b> {data['city']}")
    lines += [
        "",
        f"📞 <b>Телефон:</b> {data.get('phone')}",
        f"📧 <b>Почта:</b> {data.get('email')}",
        "",
        f"👤 Клиент: {username} (ID: <code>{user.id}</code>)",
    ]
    brief_text = "\n".join(lines)

    from modules.orm.user import save_brief
    try:
        await save_brief(user.id, "completed", data)
    except Exception:
        logger.error(f"Не удалось сохранить заявку пользователя {user.id} в БД", exc_info=True)

    manager_chat = storage.manager_chat_id
    if manager_chat != 0:
        try:
            await insert_bot.send_message(manager_chat, brief_text)
            logger.info(f"Brief from user {user.id} sent to manager chat {manager_chat}")
        except Exception:
            logger.error(f"Failed to send brief from user {user.id} to manager chat", exc_info=True)
    else:
        logger.warning(f"Brief from user {user.id} not forwarded: manager chat is not set")

    await message.answer(
        "✅ <b>Спасибо, что оставили заявку!</b>\n\n"
        "Наш менеджер свяжется с вами в самое ближайшее время. 🙏\n\n"
        "Оставить ещё одну заявку — /start"
    )


@router.message(F.chat.type == "private")
async def fallback_handler(message: Message, state: FSMContext):
    current = await state.get_state()
    if current is None:
        await message.answer("Чтобы оставить заявку, отправьте /start")
    elif current in ASK:
        await message.answer(
            "⚠️ Пожалуйста, ответьте на вопрос выше — "
            "или воспользуйтесь кнопками «Назад» / «Отменить»."
        )


@router.callback_query()
async def stale_callback_handler(call: CallbackQuery):
    await call.answer("Эта кнопка уже неактуальна. Отправьте /start", show_alert=False)
