from dotenv import load_dotenv
import os, pathlib

load_dotenv("./configuration/conf.env")

TOKEN = str(os.getenv("TOKEN"))
MANAGER_CHAT_ID = int(os.getenv("MANAGER_CHAT_ID", "0"))
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

PATH_DIR = pathlib.Path(__file__).parent.parent.resolve()
STORAGE_PATH = os.getenv("STORAGE_PATH", str(PATH_DIR / "storage/settings.json"))
DB_PATH = os.getenv("DB_PATH", str(PATH_DIR / "storage/answerbot.db"))
LOG_PATH = PATH_DIR / "loginning/log/"

# --- Внешний HTTP API (заявки с сайта) -----------------------------------------
# Секретная фраза: сайт передаёт её в заголовке X-Api-Secret. Пустая — API выключен.
API_SECRET = os.getenv("API_SECRET", "").strip()
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8090"))
