import asyncio
from typing import AsyncGenerator, Optional
from aiogram import Bot
from aiogram.exceptions import TelegramRetryAfter


def smart_split(text: str, max_length: int = 3500) -> list[str]:
    """Разделяет текст по переносам строк и пробелам"""
    if len(text) <= max_length:
        return [text]

    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break

        # Ищем последний перенос строки
        part = text[:max_length]
        last_newline = part.rfind("\n")

        if last_newline != -1:
            parts.append(part[:last_newline])
            text = text[last_newline + 1 :]
        else:
            # Ищем последний пробел
            last_space = part.rfind(" ")
            if last_space != -1:
                parts.append(part[:last_space])
                text = text[last_space + 1 :]
            else:
                # Режем жестко
                parts.append(part)
                text = text[max_length:]

    return parts


async def stream_to_chat(
    bot: Bot,
    chat_id: int,
    draft_id: int,
    generator: AsyncGenerator,
    thread_id: Optional[int] = None,
) -> tuple[str, list]:
    update_interval = 0.2
    last_update = asyncio.get_event_loop().time()
    full_text = ""
    found_links = []

    await bot.send_message_draft(
        chat_id=chat_id,
        draft_id=draft_id,
        text="",
        message_thread_id=thread_id,
    )

    async for chunk, resources in generator:
        full_text += chunk
        if resources and not found_links:
            found_links = resources

        now = asyncio.get_event_loop().time()
        if now - last_update < update_interval:
            continue

        try:
            await bot.send_message_draft(
                chat_id=chat_id,
                draft_id=draft_id,
                text=full_text[:4000],
                message_thread_id=thread_id,
            )
            last_update = now
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            last_update = asyncio.get_event_loop().time()

    return full_text, found_links
