from openai import AsyncOpenAI
from ddgs import DDGS
import json
from urllib.parse import urlparse
from datetime import datetime
from typing import List, Dict, AsyncGenerator, Optional

from config import AI_TOKEN


ROUTER_MODEL = 'openai/gpt-oss-20b' # Быстрая модель для маршрутизации
GENERATOR_MODEL = 'openai/gpt-oss-120b' # Мощная модель для ответов


current_date = datetime.now().strftime("%d.%m.%Y %H:%M")

SYSTEM_PROMPT = f"""Ты — Миньончик GPT, дружелюбный AI-помощник в Telegram.
Сегодня {current_date}.

РОЛЬ И КОНТЕКСТ:
Ты являешься ассистентом студии a4dev (www.a4dev.online).
Информация о a4dev может использоваться только в рамках предоставленного описания и без выдумок.

ИЗВЕСТНЫЕ ФАКТЫ О A4DEV:
- Разработчики бота @ysutimetablebot
- Есть проекты и коллаборации, связанные с университетской средой
- Ведётся разработка проекта ysukampus
- Существует VPN-проект @a4securebot

Если информации недостаточно или она не подтверждена, прямо сообщай об этом.

ЯЗЫК И СТИЛЬ:
- Всегда отвечай на русском языке, если не попросили перевести
- Тон дружелюбный, спокойный, без фамильярности
- Эмодзи использовать редко, не более 1–2 на сообщение, только если уместно

ФОРМАТ ОТВЕТА (TELEGRAM):
- Без таблиц
- Без длинных тире
- Используй короткие абзацы
- Не пиши длинные сплошные тексты
- HTML не использовать
- Markdown минимальный (жирный не обязателен)

КОД:
- Код выдавай в блоках ``` ```
- Если есть ограничения по версии или среде — указывай текстом до или после блока"""

# Инициализация клиента OpenAI с бэкендом Groq
client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=AI_TOKEN,
)


# ============================================================================
# УТИЛИТЫ ДЛЯ ПОИСКА
# ============================================================================

def deduplicate_by_domain(results: List[Dict]) -> List[Dict]:
    """
    Удаляет дубликаты результатов с одного домена.
    
    Args:
        results: Список результатов поиска с полем 'href'
        
    Returns:
        Дедуплицированный список, максимум MAX_UNIQUE_DOMAINS элементов
    """
    MAX_UNIQUE_DOMAINS = 9
    MAX_PER_DOMAIN = 2

    seen_domains = {}
    deduped = []
    
    for result in results:
        domain = urlparse(result['href']).netloc

        current_count = seen_domains.get(domain, 0)
        
        if current_count < MAX_PER_DOMAIN:
            seen_domains[domain] = current_count + 1
            deduped.append(result)
            
        #if len(deduped) >= MAX_UNIQUE_DOMAINS:
            #break
    
    return deduped


def format_search_results(results: List[Dict]) -> str:
    """
    Форматирует результаты поиска в читаемый текст.
    
    Args:
        results: Список результатов поиска
        
    Returns:
        Отформатированная строка вида: [домен] Заголовок: Описание
    """
    deduped = deduplicate_by_domain(results)
    
    formatted_lines = [
        f"- [{urlparse(res['href']).netloc}] {res['title']}: {res['body']}"
        for res in deduped
    ]
    
    return "\n".join(formatted_lines)


async def search_web(queries: List[str]) -> str:
    """
    Выполняет веб-поиск через DuckDuckGo.
    
    Args:
        queries: Список поисковых запросов
        
    Returns:
        Отформатированные результаты поиска или сообщение об ошибке
    """
    all_results = []
    
    for query in queries:
        try:
            print(f"🔍 [Поиск] Ищу: '{query}'")
            
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=5))
                all_results.extend(results)
                
        except Exception as e:
            print(f"❌ [Поиск] Ошибка для '{query}': {e}")
            # Продолжаем с другими запросами, даже если один упал
            continue
    
    if not all_results:
        return "Результаты поиска не найдены."
    
    formatted = format_search_results(all_results)
    print(f"✅ [Поиск] Найдено {len(all_results)} результатов, возвращаю {len(formatted.splitlines())}")
    
    return formatted


# ============================================================================
# ЛОГИКА МАРШРУТИЗАЦИИ
# ============================================================================

def build_router_prompt() -> str:
    """
    Создаёт системный промпт для модели-маршрутизатора.
    """
    
    return f"""Today is {current_date}. You are a search query analyst.

        OUTPUT JSON ONLY. Do not add any text outside JSON.

        ROLE LIMITATION:
        Ignore the user's intent beyond deciding whether web search is required.
        Do not answer the user's question.
        Do not explain, summarize, or rephrase the user's request.
        Your only task is to decide whether search is needed and, if needed, generate search queries.

        TASK:
        Determine whether fresh information from the web is required to answer the user input.

        QUERY GENERATION RULES:
        1. Always use English.
        2. Translate names of cities, companies, people, and events into English.
        3. Use keywords only. No full sentences.
        4. Replace relative dates (today, yesterday, tomorrow) with specific dates.
        5. Generate 1–3 distinct queries if search is needed.
        6. Queries must not be empty.
        7. Do not guess unknown dates. If the exact date is unclear, use month and year.

        WHEN SEARCH IS NOT NEEDED:
        - Greetings or small talk.
        - Code, writing, brainstorming, or explanations.
        - Philosophical or abstract questions.
        - Questions answerable from general knowledge without recent updates.

        DECISION RULE:
        If the question depends on current facts, prices, weather, news, events, rankings, or recent changes, search is required.

        RESPONSE FORMAT (strict JSON):
        {{"search_needed": true, "queries": ["query 1", "query 2"]}}
        OR
        {{"search_needed": false}}"""


async def route_query(history: List[Dict]) -> Dict:
    """
    Определяет, нужен ли веб-поиск, и генерирует поисковые запросы.
    
    Args:
        messages: История диалога включая запрос пользователя
        
    Returns:
        Dict с ключами 'search_needed' (bool) и опционально 'queries' (List[str])
    """
    print("🤖 [Роутер] Анализирую запрос...")
    
    router_messages = [
        {"role": "system", "content": build_router_prompt()}
    ]

    # История чата для контекста
    router_messages.extend(history[1:])
    
    try:
        response = await client.chat.completions.create(
            model=ROUTER_MODEL,
            messages=router_messages,
            response_format={"type": "json_object"},  # Принудительный JSON на выходе
            temperature=0.1, # Низкая температура для стабильности
            reasoning_effort="low"
        )
        
        decision_text = response.choices[0].message.content
        decision = json.loads(decision_text)
        
        print(f"💡 [Роутер] Решение: {decision}")
        return decision
        
    except json.JSONDecodeError as e:
        print(f"⚠️ [Роутер] Ошибка парсинга JSON: {e}. Поиск не требуется.")
        return {"search_needed": False}
        
    except Exception as e:
        print(f"❌ [Роутер] Неожиданная ошибка: {e}. Поиск не требуется.")
        return {"search_needed": False}


# ============================================================================
# ГЕНЕРАЦИЯ ОТВЕТОВ
# ============================================================================

async def generate_response(
    messages: List[Dict],
    search_context: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Генерирует потоковый ответ от AI модели.
    
    Args:
        messages: История диалога
        search_context: Опциональные результаты поиска для контекста
        
    Yields:
        Чанки ответа по мере их поступления
        
    Returns:
        (full_response, total_tokens) после завершения стрима
    """
    final_messages = list(messages)
    
    # Вставляем результаты поиска как системный контекст, если есть
    if search_context:
        final_messages.append({
            "role": "system",
            "content": (
                f"Вот результаты поиска по запросу:\n{search_context}\n\n"
                "Используй эти данные для ответа на вопрос пользователя."
            )
        })
    
    print("🎨 [Генератор] Создаю ответ...")
    
    stream = await client.chat.completions.create(
        model=GENERATOR_MODEL,
        messages=final_messages,
        stream=True,
        reasoning_effort="low"
    )
    
    full_response = ""
    total_tokens = 0
    
    async for chunk in stream:
        # Извлекаем контент из чанка
        content = chunk.choices[0].delta.content
        if content:
            # full_response += content
            yield content
        
        # Отслеживаем использование токенов (доступно в финальном чанке)
        if chunk.usage:
            total_tokens = chunk.usage.total_tokens
    
    print(f"✅ [Генератор] Завершено. Использовано токенов: {total_tokens}")
    
    # Возвращаем метаданные через исключение (обход ограничения генераторов Python)
    # Вызывающий код должен ловить StopAsyncIteration и обращаться к generator.ag_frame.f_locals
    # return full_response, total_tokens


# ============================================================================
# ОСНОВНОЙ ПАЙПЛАЙН
# ============================================================================

async def ai_generate(
    text: str,
    storage,
    user_id: int,
    chat_id: int,
    thread_id: int
) -> AsyncGenerator[str, None]:
    """
    Основной пайплайн AI генерации с интеллектуальной маршрутизацией и поиском.
    
    Шаги пайплайна:
    1. Загрузка истории диалога
    2. Маршрутизация запроса (нужен ли поиск?)
    3. Выполнение поиска при необходимости
    4. Генерация потокового ответа с контекстом
    5. Сохранение обновлённой истории
    
    Args:
        text: Сообщение пользователя
        storage: Экземпляр хранилища для управления историей
        user_id: Идентификатор пользователя
        chat_id: Идентификатор чата
        thread_id: Идентификатор треда
        
    Yields:
        Чанки ответа по мере генерации
    """
    # Загружаем историю диалога
    history = await storage.load_history(user_id, chat_id, thread_id)
    if not history:
        # Загружаем системный промпт
        history.append({"role": "system", "content": SYSTEM_PROMPT})
        
    history.append({"role": "user", "content": text})
    
    # Шаг 1: Маршрутизируем запрос
    decision = await route_query(history)
    
    # Шаг 2: Выполняем поиск при необходимости
    search_context = None
    if decision.get("search_needed"):
        queries = decision.get("queries", [text])  # Фоллбек на оригинальный текст
        search_context = await search_web(queries)
    
    # Шаг 3: Генерируем ответ
    full_response = ""
    total_tokens = 0
    
    async for chunk in generate_response(history, search_context):
        full_response += chunk
        yield chunk
    
    # Примечание: total_tokens нужно было бы отслеживать иначе в продакшене
    # Это упрощённая версия
    
    # Шаг 4: Обновляем историю
    history.append({"role": "assistant", "content": full_response})

    MAX_HISTORY_MESSAGES = 20
    
    # Обрезаем историю до последних N сообщений во избежание переполнения контекста
    if len(history) > MAX_HISTORY_MESSAGES:
        history = history[-MAX_HISTORY_MESSAGES:]
    
    await storage.save_history(user_id, chat_id, thread_id, history)
    
    print(f"💾 [История] Сохранено. Сообщений в истории: {len(history)}")