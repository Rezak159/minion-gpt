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

async def main():
    bot = Bot(token=TG_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO)
    try:
        print('Успех.')
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Exit")