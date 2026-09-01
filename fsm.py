from aiogram.fsm.state import State, StatesGroup


class Brief(StatesGroup):
    purchase_type = State()

    gov_communication = State()

    com_mounting = State()
    com_service_type = State()
    com_screen_size = State()
    com_city = State()

    phone = State()
    email = State()


class AdminFSM(StatesGroup):
    enter_admin_id = State()
    enter_search = State()
    enter_chat_id = State()
    enter_transfer_id = State()
