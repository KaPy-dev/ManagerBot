import asyncio, logging
from aiogram import Bot, Dispatcher
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.bot import DefaultBotProperties
from configuration import config
from loginning.Loginning import *


insert_bot = Bot(config.TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = None

log_manager = LoggerManager()
logger = log_manager.get_logger()


async def set_bot_commands():
    from aiogram.types import BotCommand
    await insert_bot.set_my_commands([
        BotCommand(command="start", description="Оставить заявку"),
        BotCommand(command="brief", description="Начать бриф заново"),
        BotCommand(command="admin", description="Панель управления"),
    ])


async def main():
    try:
        global dp

        from modules.storage import storage
        if storage.manager_chat_id == 0:
            logger.warning("Чат для заявок не задан — владелец может указать его через /admin")
        if storage.owner_id == 0:
            logger.warning("OWNER_ID не задан в conf.env — админ-панель будет недоступна")

        logger.info("db init")
        from base import create_tables
        await create_tables()
        logger.info("db init complete")

        logger.info("commands init")
        await set_bot_commands()
        logger.info("commands init complete")

        bot = insert_bot
        from modules.fsm_storage import PersistentMemoryStorage
        fsm_store = PersistentMemoryStorage(config.PATH_DIR / "storage/fsm_state.json")
        if fsm_store._restored:
            logger.info(f"Восстановлено незавершённых сессий: {fsm_store._restored}")
        dp = Dispatcher(storage=fsm_store)

        from handlers.chats import router as chats_router
        from admin.mainAdmin import router as admin_router
        from handlers.brief import router as brief_router

        dp.include_router(chats_router)
        dp.include_router(admin_router)
        dp.include_router(brief_router)

        dp.update.outer_middleware(ActionLoggerMiddleware(logger))
        from modules.track import UserTrackMiddleware
        dp.update.outer_middleware(UserTrackMiddleware())

        await bot.delete_webhook(drop_pending_updates=False)
        autosave_task = asyncio.create_task(fsm_store.autosave_loop())
        logger.info("Bot polling started")
        try:
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
        finally:
            autosave_task.cancel()
            saved = fsm_store.dump()
            logger.info(f"Состояния FSM сохранены на диск: {saved}")

    except Exception:
        logger.critical("Критическая ошибка при запуске бота", exc_info=True)
        raise

    finally:
        from modules.async_.db.async_req import db
        await db.close()
        logger.info("Завершение работы бота")


if __name__ == '__main__':
    logging.info('Bot started')
    asyncio.run(main())
