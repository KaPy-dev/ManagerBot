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
