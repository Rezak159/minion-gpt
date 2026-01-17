from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from aiogram.exceptions import TelegramRetryAfter

import asyncio


from app.generate import ai_generate, clear_context
from app.utils import split_message_by_lines

router = Router()

class Gen(StatesGroup):
    wait = State()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer('Добро пожаловать в бот!')


@router.message(Command('clear'))
async def get_help(message: Message):
    await clear_context()
    await message.answer("Контекст диалога очищен.")


@router.message(Gen.wait)
async def wait(message: Message):
    await message.reply('Нужно подождать')


@router.message()
async def answer(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Отправьте текстовое сообщение.")
        return

    await state.set_state(Gen.wait)
    full_text = ''
    last_update_time = asyncio.get_event_loop().time()
    update_interval = 0.2  # минимальный интервал между обновлениями
    is_rate_limited = False
    rate_limit_until = 0

    try:
        async for chunk in ai_generate(message.text):
            full_text += chunk
            current_time = asyncio.get_event_loop().time()

            # Проверяем, прошло ли достаточно времени с последнего обновления
            # И не находимся ли мы в rate limit
            if current_time - last_update_time < update_interval:
                continue

            if is_rate_limited and current_time < rate_limit_until:
                # Накапливаем чанки во время rate limit
                continue

            try:
                await message.bot.send_message_draft(
                    chat_id=message.chat.id,
                    draft_id=message.message_id,
                    text=full_text,
                    message_thread_id=message.message_thread_id,
                    parse_mode='Markdown'
                )
                last_update_time = current_time
                is_rate_limited = False
                await asyncio.sleep(0.05)

            except TelegramRetryAfter as e:
                print(f'Rate limit: ждем {e.retry_after} сек, накапливаем чанки')
                is_rate_limited = True
                rate_limit_until = current_time + e.retry_after
                
                # Ждем указанное время
                await asyncio.sleep(e.retry_after)

                # После ожидания отправляем накопленный текст
                try:
                    await message.bot.send_message_draft(
                        chat_id=message.chat.id,
                        draft_id=message.message_id,
                        text=full_text,
                        message_thread_id=message.message_thread_id,
                        parse_mode='Markdown'
                    )
                    last_update_time = asyncio.get_event_loop().time()
                    is_rate_limited = False
                except Exception as e:
                    print(f'Ошибка после retry: {e}')
            except Exception as e:
                print(f'Другая ошибка: {e}')

        # Финальная отправка
        await message.answer(full_text, parse_mode='Markdown')
    finally:
        await state.clear()
    

    '''
        answer = await ai_generate(message.text)
    # parts = split_message_by_lines(answer, max_length=4096)

    for part in parts:
        await message.answer(part, parse_mode=None)
    '''




    