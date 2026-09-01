import logging
import sys
import time
import colorlog
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from configuration.config import LOG_PATH


class ErrorFileHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.directory = LOG_PATH
        self.directory.mkdir(parents=True, exist_ok=True)
        self.setLevel(logging.ERROR)

    def emit(self, record):
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        file_path = self.directory / f"error_{timestamp}.log"
        log_entry = self.format(record)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(log_entry)


class ActionLoggerMiddleware(BaseMiddleware):
    def __init__(self, logger):
        self.logger = logger
        super().__init__()

    async def __call__(self, handler, event, data):
        user = data.get("event_from_user")
        user_info = f"ID: {user.id} (@{user.username})" if user else "Unknown"

        content = ""
        if isinstance(event, Message):
            if event.text:
                text_snippet = event.text[:40].replace('\n', ' ')
                content = f" | Text: {text_snippet}"
        elif isinstance(event, CallbackQuery):
            content = f" | Data: {event.data}"

        self.logger.info(f"USER: {user_info} | EVENT: {type(event).__name__}{content}")
        return await handler(event, data)


class LoggerManager:
    _instances = {}

    def __new__(cls, name="tg_bot", main_log="full_log.log"):
        if name not in cls._instances:
            instance = super().__new__(cls)
            instance._setup(name, main_log)
            cls._instances[name] = instance
        return cls._instances[name]

    def _setup(self, name, main_log):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False

        plain_formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

        color_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s | %(levelname)-8s | %(message)s%(reset)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'bold_red',
            }
        )

        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(color_formatter)
        self.logger.addHandler(console)

        main_file = logging.FileHandler(main_log, encoding="utf-8")
        main_file.setFormatter(plain_formatter)
        self.logger.addHandler(main_file)

        error_file_handler = ErrorFileHandler()
        error_file_handler.setFormatter(plain_formatter)
        self.logger.addHandler(error_file_handler)

        sys.excepthook = self._handle_unhandled_exception

    def _handle_unhandled_exception(self, exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        self.logger.error("FATAL ERROR", exc_info=(exc_type, exc_value, exc_traceback))

    def get_logger(self):
        return self.logger
