import html
import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, ErrorEvent, LinkPreviewOptions
from aiogram.filters import CommandStart, Command
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from aiogram.utils.markdown import hbold

from aiogram.exceptions import TelegramRetryAfter

from app.generate import ai_generate, GENERATOR_MODEL
from app.utils import smart_split

from app.database.chat_storage import ChatStorage
from app.database.user_storage import UserStorage 

router = Router()

class Gen(StatesGroup):
    wait = State()

logger = logging.getLogger(__name__)


@router.message(CommandStart())
async def cmd_start(message: Message, user_storage: UserStorage):
    logger.info(f'Пользователь @{message.from_user.username} - {message.from_user.id} нажал /start')

    try:
        # Регистрируем нового пользователя (или игнорируем, если уже есть)
        await user_storage.create_user(
            user_id=message.from_user.id,
            username=message.from_user.username
        )
        
        await message.answer(
            'Добро пожаловать в бота! Просто напиши что нибудь в чат и я отвечу.',
            reply_markup=ReplyKeyboardRemove()
        )
    except Exception as e:
        logger.error(f'Ошибка при /start: {e}', exc_info=True)
        await message.answer("❌ Что-то пошло не так. Попробуйте еще раз позже.")


@router.message(Command('settings'))
async def cmd_settings(message: Message, user_storage: UserStorage):
    logger.info(f'Пользователь @{message.from_user.username} - {message.from_user.id} нажал /settings')

    try:
        user = message.from_user
    
        # Проверяем и сбрасываем лимиты, если нужно
        await user_storage.check_and_reset_limits(user.id)
        
        # Получаем реальные данные из БД
        user_data = await user_storage.get_user(user.id)
        if not user_data:
            await message.answer("❌ Пользователь не найден. Попробуйте /start")
            return
        
        # Получаем лимиты для тарифа
        limits = user_storage.get_limits(user_data['tariff_plan'])

        # Формируем объект stats для совместимости с существующим кодом
        is_unlimited = limits['requests_per_day'] == -1
        
        stats = {
            "requests_today": user_data['requests_today'],
            "requests_limit": limits['requests_per_day'],
            "tokens_left": limits['tokens_per_day'] - user_data['tokens_today'] if limits['tokens_per_day'] != -1 else -1,
            "status": user_data['tariff_plan'].capitalize(),
            "total_requests": user_data['total_requests']
        }
        
        # Формируем имя с защитой от HTML-тегов в нике
        full_name = user.full_name
        username = f"@{user.username}" if user.username else "Нет"
        
        # Визуализация прогресс-бара лимитов (для красоты)
        if is_unlimited:
            progress_bar = "■" * 10  # Полный бар для безлимита
            requests_display = f"{stats['requests_today']}/∞"
            tokens_display = "∞"
        else:
            # Вычисляет процент: 12/50 -> [■■□□□□□□□□]
            percent = min(stats['requests_today'] / stats['requests_limit'], 1)
            bar_len = 10
            filled = int(percent * bar_len)
            progress_bar = "■" * filled + "□" * (bar_len - filled)
            requests_display = f"{stats['requests_today']}/{stats['requests_limit']}"
            tokens_display = str(stats['tokens_left']) if stats['tokens_left'] > 0 else '0'

        text = (
            f"<b>Настройки профиля</b>\n\n"
            
            f"👤 <b>Пилот:</b> {hbold(full_name)} • {username}\n"
            f"🏅 <b>Статус:</b> {stats['status']}\n\n"
            
            f"<b>Текущая модель:</b>\n"
            f"└ {GENERATOR_MODEL}\n\n"
            
            f"<b>Твои лимиты (на сегодня):</b>\n"
            f"├ Запросы: <b>{requests_display}</b>\n"
            f"├ Осталось токенов: <b>{tokens_display}</b>\n"
            f"└ [{progress_bar}]\n\n"
            
            f"📊 <b>Статистика:</b>\n"
            f"└ Всего запросов: <b>{stats['total_requests']}</b>\n\n"
            
            f"<i>Powered by a4dev</i>"
        )

        await message.answer(text, parse_mode='HTML')
    except Exception as e:
        logger.error(f'Ошибка при /settings: {e}', exc_info=True)
        await message.answer("❌ Что-то пошло не так. Попробуйте еще раз позже.")


@router.message(Command('clear'))
async def cmd_clear(message: Message, storage: ChatStorage, user_storage: UserStorage):
    logger.info(f'Пользователь @{message.from_user.username} - {message.from_user.id} нажал /clear')
    
    try:
        user = message.from_user
        user_data = await user_storage.get_user(user.id)
        if not user_data:
            await message.answer("❌ Пользователь не найден. Попробуйте /start")
            return
        
        await storage.clear_history(
            message.from_user.id,
            message.chat.id,
            message.message_thread_id
        )
        await message.answer("История очищена 🗑️")
    except Exception as e:
        logger.error(f'Ошибка при /clear: {e}', exc_info=True)
        await message.answer("❌ Что-то пошло не так. Попробуйте еще раз позже.")


@router.message(Command('set_lim'))
async def cmd_clear(message: Message, storage: ChatStorage, user_storage: UserStorage):    
    try:
        user = message.from_user
        user_data = await user_storage.get_user(user.id)
        if not user_data:
            await message.answer("❌ Пользователь не найден. Попробуйте /start")
            return
        
        await user_storage.reset_daily_limits(user.id)
        await message.answer("Лимиты сброшены 🗑️")
    except Exception as e:
        logger.error(f'Ошибка при /sel_lim: {e}', exc_info=True)
        await message.answer("❌ Что-то пошло не так. Попробуйте еще раз позже.")
        

@router.message(Gen.wait)
async def wait(message: Message):
    await message.reply('Нужно подождать..')


@router.message()
async def answer(message: Message, state: FSMContext, storage: ChatStorage, user_storage: UserStorage):
    if not message.text and message.content_type in ['forum_topic_created', 'new_chat_members', 'pinned_message']:
        return
    
    if not message.text:
        await message.answer("Отправьте текстовое сообщение.")
        return
    
    try:
        user = message.from_user
        user_data = await user_storage.get_user(user.id)
        if not user_data:
            await message.answer("❌ Пользователь не найден. Попробуйте /start")
            return

        # Проверяем и сбрасываем лимиты, если нужно
        await user_storage.check_and_reset_limits(message.from_user.id)
        
        # Проверяем, не превышены ли лимиты
        can_use, error_msg = await user_storage.check_limits(message.from_user.id)
        if not can_use:
            await message.answer(error_msg)
            return

        await state.set_state(Gen.wait)
        
        # Отправляем draft с "Думаю.."
        await message.bot.send_message_draft(
            chat_id=message.chat.id,
            draft_id=message.message_id,
            text="💡 <i>Думаю..</i>",
            message_thread_id=message.message_thread_id,
            parse_mode='HTML'
        )
        
        full_text = ''
        last_update_time = asyncio.get_event_loop().time()
        update_interval = 0.2  # минимальный интервал между обновлениями
        is_rate_limited = False
        rate_limit_until = 0
        found_links = []

        async for chunk, resources in ai_generate(
            text=message.text,
            storage=storage,
            user_id=message.from_user.id,
            chat_id=message.chat.id,
            thread_id=message.message_thread_id
        ):
            full_text += chunk
            current_time = asyncio.get_event_loop().time()
            if resources and not found_links:
                found_links = resources

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
                logger.warning(f'Rate limit: ждем {e.retry_after} сек, накапливаем чанки')
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
                    logger.error(f'Ошибка после retry: {e}', exc_info=True)

            except Exception as e:
                logger.error(f'Ошибка при генерации: {e}', exc_info=True)

        full_text = html.escape(full_text)

        # ЗДЕСЬ используем smart_split для финальной отправки
        parts = smart_split(full_text)

        for i, part in enumerate(parts):
            try:
                if found_links and i == len(parts) - 1:
                    links_formatted = [
                        f'<a href="{link["url"]}">[{i+1}]</a>' 
                        for i, link in enumerate(found_links)
                    ]
                    part += f"\n\n🌐 <i>Источники:</i> {', '.join(links_formatted)}"
                await message.answer(part, parse_mode='HTML', link_preview_options=LinkPreviewOptions(is_disabled=True))
                if i < len(parts) - 1:  # Пауза между частями
                    await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f'Ошибка отправки части {i+1}: {e}', exc_info=True)
        
        # Обновляем статистику использования
        # добавить подсчет реальных токенов из AI
        await user_storage.update_usage(
            user_id=message.from_user.id,
            requests_delta=1,
            tokens_delta=len(full_text)  # Временно считаем токены как длину текста
        )
    except Exception as e:
        logger.error(f'Ошибка при генерации: {e}', exc_info=True)
        await message.answer("❌ Произошла ошибка. Попробуйте еще раз позже.")
    finally:
        await state.clear()


@router.error()
async def error_handler(event: ErrorEvent):
    logger.error(f"Произошла непредвиденная ошибка: {event.exception}", exc_info=True)
    # Можно отправить сообщение пользователю, если есть доступ к message
    if event.update.message:
        await event.update.message.answer("Ой! Что-то пошло не так. Попробуйте еще раз позже.")




    