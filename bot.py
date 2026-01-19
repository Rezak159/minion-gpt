# python3 -m venv .venv && source .venv/bin/activate

# source .venv/bin/activate
# python3 bot.py

import asyncio
import logging


from aiogram import Bot, Dispatcher

from aiogram.types import BotCommand, BotCommandScopeDefault
from aiogram.client.default import DefaultBotProperties

from config import TG_TOKEN

from app.handlers import router
from app.database import SimpleSQLiteStorage

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command='start', description='Начать'),
        BotCommand(command='clear', description='Очистить контекст')
    ]
    await bot.set_my_commands(commands, BotCommandScopeDefault())

async def main():
    bot = Bot(token=TG_TOKEN)

    storage = SimpleSQLiteStorage('chat_history.db')

    if hasattr(storage, 'init_db'):
        await storage.init_db()
        print("✅ База данных истории инициализирована")

    dp = Dispatcher()
    dp["storage"] = storage

    dp.include_router(router)
    await set_commands(bot)

    try:
        await dp.start_polling(bot)
        print('Успех.')
    finally:
        await bot.session.close()

if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exit")