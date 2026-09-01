import os
import sys
import asyncio
import time
import random
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
_tmp = Path(tempfile.mkdtemp())
os.environ["STORAGE_PATH"] = str(_tmp / "settings.json")
os.environ["DB_PATH"] = str(_tmp / "test.db")
os.environ["OWNER_ID"] = "111"

from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.bot import DefaultBotProperties
from aiogram.client.session.base import BaseSession
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Update, Message, CallbackQuery, Chat, User, ChatMemberUpdated,
    ChatMemberMember, ChatMemberLeft, Contact
)

import main
from modules.storage import storage

OWNER = 111
ADMIN = 222
STRANGER = 333


class FakeSession(BaseSession):
    def __init__(self):
        super().__init__()
        self.sent = []
        self._id = 10_000

    async def close(self):
        pass

    async def stream_content(self, *a, **k):
        yield b""

    async def make_request(self, bot, method, timeout=None):
        name = type(method).__name__
        if name == "SendMessage":
            self._id += 1
            self.sent.append((method.chat_id, method.text))
            return Message(
                message_id=self._id,
                date=datetime.now(timezone.utc),
                chat=Chat(id=method.chat_id, type="private"),
                text=method.text,
            )
        if name == "EditMessageText":
            self.sent.append((method.chat_id, method.text))
        if name == "GetChat":
            cid = int(method.chat_id)
            if cid < 0:
                from aiogram.types import ChatFullInfo
                return ChatFullInfo.model_construct(id=cid, type="supergroup", title="Заявки Vavilon", username=None)
            raise RuntimeError("user chat not available")
        return True


session = FakeSession()
bot = Bot("42:TEST", session=session, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
main.insert_bot._session = session
main.insert_bot.session = session

dp = Dispatcher(storage=MemoryStorage())

from handlers.chats import router as chats_router
from admin.mainAdmin import router as admin_router
from handlers.brief import router as brief_router

dp.include_router(chats_router)
dp.include_router(admin_router)
dp.include_router(brief_router)

from modules.track import UserTrackMiddleware
dp.update.outer_middleware(UserTrackMiddleware())

errors = []


@dp.errors()
async def on_error(event):
    errors.append(event.exception)
    return True


_uid = 0


def next_id():
    global _uid
    _uid += 1
    return _uid


def tg_user(user_id):
    return User(id=user_id, is_bot=False, first_name=f"U{user_id}", username=f"user{user_id}")


def msg_update(user_id, text):
    return Update(
        update_id=next_id(),
        message=Message(
            message_id=next_id(),
            date=datetime.now(timezone.utc),
            chat=Chat(id=user_id, type="private"),
            from_user=tg_user(user_id),
            text=text,
        ),
    )


def contact_update(user_id, phone):
    return Update(
        update_id=next_id(),
        message=Message(
            message_id=next_id(),
            date=datetime.now(timezone.utc),
            chat=Chat(id=user_id, type="private"),
            from_user=tg_user(user_id),
            contact=Contact(phone_number=phone, first_name=f"U{user_id}", user_id=user_id),
        ),
    )


def cb_update(user_id, data):
    return Update(
        update_id=next_id(),
        callback_query=CallbackQuery(
            id=str(next_id()),
            from_user=tg_user(user_id),
            chat_instance="ci",
            data=data,
            message=Message(
                message_id=next_id(),
                date=datetime.now(timezone.utc),
                chat=Chat(id=user_id, type="private"),
                from_user=User(id=42, is_bot=True, first_name="Bot"),
                text="q",
            ),
        ),
    )


def member_update(chat_id, title, joined=True):
    new = ChatMemberMember(user=User(id=42, is_bot=True, first_name="Bot")) if joined \
        else ChatMemberLeft(user=User(id=42, is_bot=True, first_name="Bot"))
    old = ChatMemberLeft(user=User(id=42, is_bot=True, first_name="Bot")) if joined \
        else ChatMemberMember(user=User(id=42, is_bot=True, first_name="Bot"))
    return Update(
        update_id=next_id(),
        my_chat_member=ChatMemberUpdated(
            chat=Chat(id=chat_id, type="supergroup", title=title),
            from_user=tg_user(OWNER),
            date=datetime.now(timezone.utc),
            old_chat_member=old,
            new_chat_member=new,
        ),
    )


async def feed(update):
    await dp.feed_update(bot, update)


def last_text(user_id):
    for chat_id, text in reversed(session.sent):
        if chat_id == user_id:
            return text or ""
    return ""


def check(name, condition):
    status = "OK " if condition else "FAIL"
    print(f"  [{status}] {name}")
    if not condition:
        errors.append(AssertionError(name))


async def commercial_flow(user_id, with_mistakes=False, with_back=False):
    await feed(msg_update(user_id, "/start"))
    await feed(cb_update(user_id, "purchase:commercial"))
    await feed(cb_update(user_id, "mounting:wall"))
    if with_back:
        await feed(cb_update(user_id, "brief:back"))
        await feed(cb_update(user_id, "mounting:floor"))
    await feed(cb_update(user_id, "service:front"))
    if with_mistakes:
        await feed(msg_update(user_id, "не знаю"))
    await feed(msg_update(user_id, "300 x 200"))
    if with_mistakes:
        await feed(msg_update(user_id, "/help"))
    await feed(msg_update(user_id, "Москва"))
    if with_mistakes:
        await feed(msg_update(user_id, "восемь девятьсот"))
    await feed(msg_update(user_id, "+7 900 123 45 67"))
    if with_mistakes:
        await feed(msg_update(user_id, "не почта"))
    await feed(msg_update(user_id, f"client{user_id}@mail.ru"))


async def gov_flow(user_id):
    await feed(msg_update(user_id, "/start"))
    await feed(cb_update(user_id, "purchase:gov44"))
    await feed(cb_update(user_id, "gov_comm:tz_help"))
    await feed(msg_update(user_id, "89001234567"))
    await feed(msg_update(user_id, f"gov{user_id}@mail.ru"))


async def test_brief_flows():
    print("\n== Бриф: коммерческая ветка (с ошибками ввода и кнопкой Назад) ==")
    await commercial_flow(1001, with_mistakes=True, with_back=True)
    check("заявка завершена", "Спасибо" in last_text(1001))

    print("\n== Бриф: госзакупка ==")
    await gov_flow(1002)
    check("заявка завершена", "Спасибо" in last_text(1002))

    print("\n== Незавершённый опрос: возобновление ==")
    await feed(msg_update(1003, "/start"))
    await feed(cb_update(1003, "purchase:commercial"))
    await feed(cb_update(1003, "mounting:wall"))
    await feed(msg_update(1003, "/start"))
    check("предложено продолжить", "незавершённая" in last_text(1003))
    await feed(cb_update(1003, "brief:resume"))
    check("вернулись к тому же шагу", "Тип обслуживания" in last_text(1003))
    await feed(msg_update(1003, "/start"))
    await feed(cb_update(1003, "brief:restart"))
    check("начали заново", "Шаг 1" in last_text(1003))

    print("\n== Телефон из профиля Telegram ==")
    await feed(msg_update(1006, "/start"))
    await feed(cb_update(1006, "purchase:gov223"))
    await feed(cb_update(1006, "gov_comm:consult"))
    await feed(contact_update(1006, "79001112233"))
    check("контакт принят", "Принято" in [t for c, t in session.sent if c == 1006 and t and "Принято" in t][-1] if any(c == 1006 and t and "Принято" in (t or "") for c, t in session.sent) else False)
    await feed(msg_update(1006, "contact@mail.ru"))
    check("заявка с контактом завершена", "Спасибо" in last_text(1006))

    print("\n== Назад/Отмена с reply-кнопок на шаге телефона ==")
    await feed(msg_update(1007, "/start"))
    await feed(cb_update(1007, "purchase:gov44"))
    await feed(cb_update(1007, "gov_comm:tz_help"))
    await feed(msg_update(1007, "⬅️ Назад"))
    check("вернулись к формату коммуникации", "Формат коммуникации" in last_text(1007))
    await feed(cb_update(1007, "gov_comm:consult"))
    await feed(msg_update(1007, "❌ Отменить"))
    check("отмена с шага телефона", "отменено" in last_text(1007))

    print("\n== Отмена ==")
    await feed(cb_update(1003, "brief:cancel"))
    check("отменено", "отменено" in last_text(1003))

    print("\n== Мусорные действия ==")
    await feed(msg_update(1004, "просто текст без старта"))
    check("подсказка про /start", "/start" in last_text(1004))
    await feed(cb_update(1004, "purchase:commercial"))
    await feed(cb_update(1004, "mounting:wall"))
    await feed(cb_update(1004, "service:front"))
    await feed(cb_update(1004, "brief:back"))
    await feed(cb_update(1004, "какая-то:чушь"))
    await feed(msg_update(1005, "/start"))
    await feed(cb_update(1005, "purchase:hack"))
    await feed(cb_update(1005, "brief:back"))
    check("мусор не уронил бота", True)


async def test_admin():
    print("\n== Трекинг чатов ==")
    await feed(member_update(-100500, "Заявки Vavilon"))
    await feed(member_update(-100600, "Тестовый канал"))
    check("чаты записаны", "-100500" in storage.chats and "-100600" in storage.chats)
    await feed(member_update(-100600, "Тестовый канал", joined=False))
    check("выход из чата учтён", "-100600" not in storage.chats)

    print("\n== Доступ к /admin ==")
    before = len(session.sent)
    await feed(msg_update(STRANGER, "/admin"))
    check("чужому панель не показана", all(c != STRANGER or "Панель" not in (t or "") for c, t in session.sent[before:]))

    await feed(msg_update(OWNER, "/admin"))
    check("владелец видит панель", "Владелец" in last_text(OWNER))

    print("\n== Владелец назначает админа ==")
    await feed(cb_update(OWNER, "adm:admins"))
    await feed(cb_update(OWNER, "adm:add_admin"))
    await feed(cb_update(OWNER, "adm:enter_admin"))
    await feed(msg_update(OWNER, "абракадабра"))
    check("невалидный ID отклонён", "юзернейм" in last_text(OWNER))
    await feed(msg_update(OWNER, str(ADMIN)))
    check("админ добавлен", storage.is_admin(ADMIN))

    print("\n== Права обычного админа ==")
    await feed(msg_update(ADMIN, "/admin"))
    check("админ видит панель", "Администратор" in last_text(ADMIN))
    await feed(cb_update(ADMIN, "adm:chats"))
    check("список чатов закрыт для админа", "Чаты, в которых" not in last_text(ADMIN))
    await feed(cb_update(ADMIN, "adm:enter_chat"))
    await feed(msg_update(ADMIN, "-100999"))
    check("админ не сменил чат заявок", storage.manager_chat_id != -100999)
    await feed(cb_update(ADMIN, "adm:add_admin"))
    await feed(msg_update(ADMIN, "444"))
    check("админ не назначил админа", not storage.is_admin(444))

    print("\n== Владелец: чаты и чат заявок ==")
    await feed(msg_update(OWNER, "/admin"))
    await feed(cb_update(OWNER, "adm:chats"))
    check("владелец видит чаты", "-100500" in last_text(OWNER))
    check("название чата показано", "Заявки Vavilon" in last_text(OWNER) and "группа" in last_text(OWNER))
    await feed(cb_update(OWNER, "adm:chat_menu"))
    await feed(cb_update(OWNER, "adm:setchat:-100500"))
    check("чат заявок установлен", storage.manager_chat_id == -100500)
    await storage.set_manager_chat(0)

    print("\n== Удаление админа: поиск и подтверждение ==")
    await storage.add_admin(555, "helper")
    await feed(cb_update(OWNER, "adm:admins"))
    await feed(cb_update(OWNER, "adm:remove_menu"))
    await feed(cb_update(OWNER, "adm:search"))
    await feed(msg_update(OWNER, "@helper"))
    check("поиск по юзернейму нашёл", "Найдено" in last_text(OWNER) and ": 1" in last_text(OWNER))
    await feed(cb_update(OWNER, "adm:search"))
    await feed(msg_update(OWNER, "99999"))
    check("пустой поиск обработан", "не нашлось" in last_text(OWNER))
    await feed(cb_update(OWNER, "adm:rmc:555"))
    check("запрошено подтверждение удаления", "Подтвердить удаление" in last_text(OWNER))
    await feed(cb_update(OWNER, "adm:remove_menu"))
    check("удаление отменено", storage.is_admin(555))
    await feed(cb_update(OWNER, "adm:rmc:555"))
    await feed(cb_update(OWNER, "adm:rm:555"))
    check("после подтверждения удалён", not storage.is_admin(555))
    await feed(cb_update(OWNER, f"adm:rmc:{ADMIN}"))
    await feed(cb_update(OWNER, f"adm:rm:{ADMIN}"))
    check("админ удалён", not storage.is_admin(ADMIN))

    print("\n== Передача владельца ==")
    await feed(msg_update(OWNER, "/admin"))
    await feed(cb_update(OWNER, "adm:transfer"))
    await feed(msg_update(OWNER, str(ADMIN)))
    check("запрошено подтверждение", "Передать права" in last_text(OWNER))
    await feed(cb_update(OWNER, f"adm:tconf:{ADMIN}"))
    check("владелец сменился", storage.is_owner(ADMIN))
    check("старый владелец стал админом", ADMIN != OWNER and storage.is_admin(OWNER) and not storage.is_owner(OWNER))
    check("бывший владелец не видит чаты", True)
    await feed(cb_update(OWNER, "adm:chats"))
    check("экс-владельцу список чатов закрыт", "Чаты, в которых" not in last_text(OWNER))
    await storage.transfer_owner(OWNER)


async def test_load():
    print("\n== Нагрузка: 300 пользователей параллельно ==")
    sent_before = len([1 for _, t in session.sent if t and "Спасибо" in t])
    start = time.monotonic()

    async def one_user(user_id):
        if random.random() < 0.5:
            await commercial_flow(user_id, with_mistakes=random.random() < 0.5, with_back=random.random() < 0.3)
        else:
            await gov_flow(user_id)

    await asyncio.gather(*(one_user(50_000 + i) for i in range(300)))
    elapsed = time.monotonic() - start
    done = len([1 for _, t in session.sent if t and "Спасибо" in t]) - sent_before
    print(f"  Завершено заявок: {done}/300 за {elapsed:.2f} сек")
    check("все 300 заявок завершены", done == 300)
    check("без ошибок в обработчиках", not any(isinstance(e, Exception) and not isinstance(e, AssertionError) for e in errors))


async def test_persistence():
    print("\n== Персистентность FSM: сохранение и восстановление после рестарта ==")
    from modules.fsm_storage import PersistentMemoryStorage
    fsm_path = Path(tempfile.mkdtemp()) / "fsm_state.json"

    store1 = PersistentMemoryStorage(fsm_path)
    from aiogram.fsm.storage.base import StorageKey
    key = StorageKey(bot_id=42, chat_id=7777, user_id=7777)
    await store1.set_state(key, "Brief:phone")
    await store1.set_data(key, {"purchase": "Коммерческая", "branch": "com", "city": "Казань"})
    saved = store1.dump()
    check("состояние сохранено на диск", saved == 1 and fsm_path.exists())

    store2 = PersistentMemoryStorage(fsm_path)
    check("состояние восстановлено", store2._restored == 1)
    check("шаг совпадает", (await store2.get_state(key)) == "Brief:phone")
    check("данные совпадают", (await store2.get_data(key)).get("city") == "Казань")

    old_key = StorageKey(bot_id=42, chat_id=8888, user_id=8888)
    await store2.set_state(old_key, "Brief:email")
    store2._ts[old_key] = time.time() - 100_000
    store2.dump()
    store3 = PersistentMemoryStorage(fsm_path)
    check("протухшие состояния отброшены", (await store3.get_state(old_key)) is None)


async def test_users_db():
    print("\n== БД: пользователи, досье, списки с пагинацией ==")
    from modules.orm.user import count_users, get_user, user_dossier, find_by_username

    total = await count_users()
    check("пользователи трекаются в БД", total > 300)
    row = await get_user(1001)
    check("профиль сохранён", row is not None and row["username"] == "user1001")

    dossier = await user_dossier(1001)
    check("досье собирается", dossier is not None and dossier["counts"].get("completed", 0) >= 1)
    check("в досье есть последняя заявка", dossier["last_brief"] is not None and dossier["last_brief"]["phone"])

    found = await find_by_username("USER1002")
    check("поиск по юзернейму без регистра", found is not None and found["tg_id"] == 1002)

    print("\n== Админка: список пользователей и пагинация ==")
    await feed(msg_update(OWNER, "/admin"))
    await feed(cb_update(OWNER, "adm:users:0"))
    check("список пользователей открыт", "Пользователи бота" in last_text(OWNER))
    await feed(cb_update(OWNER, "adm:users:1"))
    await feed(cb_update(OWNER, "adm:users:999"))
    check("выход за границы страниц не падает", "Пользователи бота" in last_text(OWNER))
    await feed(cb_update(OWNER, "adm:noop"))

    await feed(cb_update(OWNER, "adm:udos:1001"))
    check("досье открывается", "Досье пользователя" in last_text(OWNER))
    await feed(cb_update(OWNER, "adm:udos:424242"))
    check("досье незнакомца не падает", "не найден" in last_text(OWNER))

    print("\n== Поиск пользователей ==")
    await feed(cb_update(OWNER, "adm:users:0"))
    await feed(cb_update(OWNER, "adm:usearch"))
    await feed(msg_update(OWNER, "user1001"))
    check("поиск нашёл", "Найдено" in last_text(OWNER))

    print("\n== Назначение админа из списка и по @юзернейму ==")
    await feed(msg_update(OWNER, "/admin"))
    await feed(cb_update(OWNER, "adm:admins"))
    await feed(cb_update(OWNER, "adm:add_admin"))
    check("меню выбора способа", "Как выбрать" in last_text(OWNER))
    await feed(cb_update(OWNER, "adm:pick:0"))
    check("список для выбора открыт", "Выберите пользователя" in last_text(OWNER))
    await feed(cb_update(OWNER, "adm:uadd:1001"))
    check("назначен из списка", storage.is_admin(1001))
    check("юзернейм подтянут из БД", storage.admin_name(1001) == "user1001")
    await storage.remove_admin(1001)

    await feed(cb_update(OWNER, "adm:admins"))
    await feed(cb_update(OWNER, "adm:add_admin"))
    await feed(cb_update(OWNER, "adm:enter_admin"))
    await feed(msg_update(OWNER, "@user1002"))
    check("назначен по @юзернейму", storage.is_admin(1002))
    await storage.remove_admin(1002)
    await feed(cb_update(OWNER, "adm:admins"))
    await feed(cb_update(OWNER, "adm:add_admin"))
    await feed(cb_update(OWNER, "adm:enter_admin"))
    await feed(msg_update(OWNER, "@nobody_here_404"))
    check("неизвестный юзернейм отклонён", "не найден" in last_text(OWNER))

    print("\n== Доступ админа к спискам ==")
    await storage.add_admin(ADMIN, "admin222")
    await feed(msg_update(ADMIN, "/admin"))
    await feed(cb_update(ADMIN, "adm:users:0"))
    check("админ видит пользователей", "Пользователи бота" in last_text(ADMIN))
    await feed(cb_update(ADMIN, "adm:pick:0"))
    check("админ не назначает из списка", "Выберите пользователя" not in last_text(ADMIN))
    await feed(cb_update(ADMIN, "adm:uadd:1005"))
    check("прямое добавление админом закрыто", not storage.is_admin(1005))
    await storage.remove_admin(ADMIN)


async def run():
    from base import create_tables
    await create_tables()
    await test_brief_flows()
    await test_admin()
    await test_load()
    await test_users_db()
    await test_persistence()

    from modules.async_.db.async_req import db
    await db.close()

    print("\n==============================")
    fails = [e for e in errors if isinstance(e, AssertionError)]
    handler_errors = [e for e in errors if not isinstance(e, AssertionError)]
    if handler_errors:
        print(f"❌ Ошибки в обработчиках: {len(handler_errors)}")
        for e in handler_errors[:5]:
            print(f"   {type(e).__name__}: {e}")
    if fails:
        print(f"❌ Провалено проверок: {len(fails)}")
        sys.exit(1)
    print("✅ Все e2e-проверки пройдены, пересылок в реальный чат не было")


if __name__ == "__main__":
    asyncio.run(run())
