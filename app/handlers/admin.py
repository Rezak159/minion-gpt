import logging
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

from app.database.chat_storage import ChatStorage
from app.database.user_storage import UserStorage

adm_router = Router()

logger = logging.getLogger(__name__)


@adm_router.message(Command("set_lim"))
async def cmd_set_lim(
    message: Message, storage: ChatStorage, user_storage: UserStorage
):
    try:
        user = message.from_user
        user_data = await user_storage.get_user(user.id)
        if not user_data:
            await message.answer("❌ Пользователь не найден. Попробуйте /start")
            return

        await user_storage.reset_daily_limits(user.id)
        await message.answer("Лимиты сброшены 🗑️")
    except Exception as e:
        logger.error(f"Ошибка при /sel_lim: {e}", exc_info=True)
        await message.answer("❌ Что-то пошло не так. Попробуйте еще раз позже.")
