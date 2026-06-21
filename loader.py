from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from utils.db.storage import DatabaseManager

from data import config

_DUMMY_FALLBACK_TOKEN = "110201543:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw"

_token = config.BOT_TOKEN
if config.BOT_TOKEN_IS_PLACEHOLDER:
    _token = _DUMMY_FALLBACK_TOKEN

bot = Bot(token=_token, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
db = DatabaseManager('data/database.db')