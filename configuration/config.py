from dotenv import load_dotenv
import os, pathlib

PATH_DIR = pathlib.Path(__file__).parent.parent.resolve()

# Профиль запуска. Прод: configuration/conf.env + storage/. Отладка на своём тестовом боте:
#   ANSWERBOT_ENV=dev ANSWERBOT_ENV_FILE=configuration/conf.dev.env STORAGE_DIR=storage-dev python main.py
# (то же делает ./run-dev.sh). Явно заданные переменные окружения имеют приоритет над файлом.
ENV_NAME = os.getenv("ANSWERBOT_ENV", "prod")
ENV_FILE = os.getenv("ANSWERBOT_ENV_FILE", str(PATH_DIR / "configuration" / "conf.env"))
load_dotenv(ENV_FILE)

TOKEN = str(os.getenv("TOKEN"))
MANAGER_CHAT_ID = int(os.getenv("MANAGER_CHAT_ID", "0"))
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

# Папка с настройками, базой и незавершёнными сессиями. У dev-профиля своя (storage-dev),
# чтобы тестовый бот не трогал чат заявок и досье продового.
STORAGE_DIR = pathlib.Path(os.getenv("STORAGE_DIR", str(PATH_DIR / "storage"))).resolve()
STORAGE_PATH = os.getenv("STORAGE_PATH", str(STORAGE_DIR / "settings.json"))
DB_PATH = os.getenv("DB_PATH", str(STORAGE_DIR / "answerbot.db"))
FSM_PATH = os.getenv("FSM_PATH", str(STORAGE_DIR / "fsm_state.json"))
LOG_PATH = pathlib.Path(os.getenv("LOG_DIR", str(PATH_DIR / "loginning" / "log")))

# --- Внешний HTTP API (заявки с сайта) -----------------------------------------
# Секретная фраза: сайт передаёт её в заголовке X-Api-Secret. Пустая — API выключен.
API_SECRET = os.getenv("API_SECRET", "").strip()
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8090"))
