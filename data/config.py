import os
import sys

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

PLACEHOLDER_TOKENS = {"", "YOUR_BOT_TOKEN_HERE", "1234567890:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}

BOT_TOKEN_IS_PLACEHOLDER = BOT_TOKEN in PLACEHOLDER_TOKENS

if BOT_TOKEN_IS_PLACEHOLDER:
    print("=" * 60)
    print("ПРЕДУПРЕЖДЕНИЕ: BOT_TOKEN не настроен!")
    print("=" * 60)
    print()
    print("Бот запустится, но не сможет подключиться к Telegram.")
    print("Чтобы полноценно запустить бота:")
    print()
    print("  1. Откройте Telegram и найдите @BotFather")
    print("  2. Отправьте команду /newbot")
    print("  3. Следуйте инструкциям, получите токен")
    print('  4. Отредактируйте файл .env:')
    print('     BOT_TOKEN=ваш_реальный_токен')
    print('     ADMINS=ваш_telegram_id')
    print()

PROJECT_NAME = os.getenv("PROJECT_NAME")

# Heroku webhook
# WEBHOOK_HOST = f"https://{PROJECT_NAME}.herokuapp.com"
# WEBHOOK_PATH = '/webhook/' + BOT_TOKEN

# Railway webhook
WEBHOOK_HOST = os.getenv("RAILWAY_PUBLIC_DOMAIN")
WEBHOOK_PATH = os.getenv("WEBHOOK_PATH")

if WEBHOOK_HOST and WEBHOOK_PATH:
    WEBHOOK_URL = f"{WEBHOOK_HOST}{WEBHOOK_PATH}"
else:
    WEBHOOK_URL = None

ADMINS_RAW = os.getenv("ADMINS", "")
if ADMINS_RAW:
    ADMINS = list(map(int, ADMINS_RAW.split(",")))
else:
    ADMINS = []
