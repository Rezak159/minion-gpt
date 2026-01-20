import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from aiogram.exceptions import TelegramRetryAfter

from app.generate import ai_generate
from app.utils import smart_split
from app.database import SimpleSQLiteStorage 

router = Router()

class Gen(StatesGroup):
    wait = State()


@router.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        'Добро пожаловать в бота! Просто напиши что нибудь в чат и я отвечу.',
        reply_markup=ReplyKeyboardRemove()
    )


@router.message(Command('clear'))
async def cmd_clear(message: Message, storage: SimpleSQLiteStorage):
    await storage.clear_history(
        message.from_user.id,
        message.chat.id,
        message.message_thread_id
    )
    await message.answer("История очищена 🗑️")


@router.message(Gen.wait)
async def wait(message: Message):
    await message.reply('Нужно подождать..')


@router.message()
async def answer(message: Message, state: FSMContext, storage: SimpleSQLiteStorage):
    if not message.text and message.content_type in ['forum_topic_created', 'new_chat_members', 'pinned_message']:
        return
    
    if not message.text:
        await message.answer("Отправьте текстовое сообщение.")
        return

    await state.set_state(Gen.wait)
    
    # Отправляем draft с "Думаю.."
    await message.bot.send_message_draft(
        chat_id=message.chat.id,
        draft_id=message.message_id,
        text="💡 <b><i>Думаю..</i></b>",
        message_thread_id=message.message_thread_id,
        parse_mode='HTML'
    )
    
    full_text = ''
    last_update_time = asyncio.get_event_loop().time()
    update_interval = 0.2  # минимальный интервал между обновлениями
    is_rate_limited = False
    rate_limit_until = 0

    try:
        async for chunk in ai_generate(
            text=message.text,
            storage=storage,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            thread_id=message.message_thread_id
        ):
            full_text += chunk
            current_time = asyncio.get_event_loop().time()

            # Проверяем, прошло ли достаточно времени с последнего обновления
            # И не находимся ли мы в rate limit
            if current_time - last_update_time < update_interval:
                continue
            
            # Накапливаем чанки во время rate limit
            if is_rate_limited and current_time < rate_limit_until:
                continue

            try:
                # Ограничиваем draft до 4000 символов
                draft_text = full_text[:4000] + ('...' if len(full_text) > 4000 else '')

                await message.bot.send_message_draft(
                    chat_id=message.chat.id,
                    draft_id=message.message_id,
                    text=draft_text,
                    message_thread_id=message.message_thread_id,
                    parse_mode=None
                )
                last_update_time = current_time
                is_rate_limited = False
                await asyncio.sleep(0.01)

            except TelegramRetryAfter as e:
                print(f'Rate limit: ждем {e.retry_after} сек, накапливаем чанки')
                is_rate_limited = True
                rate_limit_until = current_time + e.retry_after
                
                # Ждем указанное время
                await asyncio.sleep(e.retry_after)

                # После ожидания отправляем накопленный текст
                draft_text = full_text[:4000] + ('...' if len(full_text) > 4000 else '')
                
                try:
                    await message.bot.send_message_draft(
                        chat_id=message.chat.id,
                        draft_id=message.message_id,
                        text=draft_text,
                        message_thread_id=message.message_thread_id,
                        parse_mode=None
                    )
                    last_update_time = asyncio.get_event_loop().time()
                    is_rate_limited = False

                except Exception as e:
                    print(f'Ошибка после retry: {e}')

            except Exception as e:
                print(f'Другая ошибка: {e}')

        # ЗДЕСЬ используем smart_split для финальной отправки
        parts = smart_split(full_text)

        for i, part in enumerate(parts):
            try:
                # Используем parse_mode=None (plain text) для избежания ошибок с Markdown
                await message.answer(part, parse_mode=None)
                if i < len(parts) - 1:  # Пауза между частями
                    await asyncio.sleep(0.3)
            except Exception as e:
                print(f'Ошибка отправки части {i+1}: {e}')
    finally:
        await state.clear()
    

    '''
        answer = await ai_generate(message.text)
    # parts = split_message_by_lines(answer, max_length=4096)

    for part in parts:
        await message.answer(part, parse_mode=None)
    '''




    