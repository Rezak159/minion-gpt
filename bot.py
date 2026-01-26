# python3 -m venv .venv && source .venv/bin/activate

# source .venv/bin/activate && python3 bot.py

import asyncio
import logging
from logging.handlers import RotatingFileHandler


from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, BotCommandScopeDefault

from config import TG_TOKEN

from app.handlers import router

from app.database.base import DB_PATH
from app.database.chat_storage import ChatStorage
from app.database.user_storage import UserStorage

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler('bot.log', maxBytes=5000000, backupCount=3, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command='start', description='Начать'),
        BotCommand(command='clear', description='Очистить контекст'),
        BotCommand(command='settings', description='Настройки')
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())

async def main():
    bot = Bot(token=TG_TOKEN)

    storage = ChatStorage(DB_PATH)
    await storage.init_db()
    logger.info("✅ База данных истории чатов инициализирована")
    
    user_storage = UserStorage(DB_PATH)
    await user_storage.init_db()
    logger.info("✅ База данных пользователей инициализирована")

    dp = Dispatcher()
    dp["storage"] = storage
    dp["user_storage"] = user_storage

    dp.include_router(router)
    await set_commands(bot)

    logger.info('Бот запущен.')

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Exit")