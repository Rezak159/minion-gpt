from openai import AsyncOpenAI
from ddgs import DDGS
import json
from urllib.parse import urlparse


from config import AI_TOKEN

MODEL=''
# xiaomi/mimo-v2-flash:free

ROUTER_MODEL = 'openai/gpt-oss-20b'
GENERATOR_MODEL = 'openai/gpt-oss-120b'


def format_results(all_results):
    seen_domains = set()
    deduped = []
    for res in all_results:
        domain = urlparse(res['href']).netloc
        if domain not in seen_domains:
            seen_domains.add(domain)
            deduped.append(res)
        if len(deduped) >= 9:  # Топ-9 уникальных
            break
    return "\n".join(f"- [{domain}] {res['title']}: {res['body']}" for res in deduped)


async def search_web(queries: list[str], max_results=3) -> str:
    """
    Поиск в DuckDuckGo.
    Возвращает строку с результатами.
    """
    results = []
    for i, query in enumerate(queries, 1):
        try:
            with DDGS() as ddgs:
                print(f"\n🔍 [Tool] Ищу в интернете: '{query}'...")
                r = list(ddgs.text(query, max_results=max_results))
                results.extend(r)
                if not results:
                    return "Поиск не дал результатов."
                
                return format_results(results)  # Убрать дубли + ранжировать

                
                results_text = "\n".join(
                    # Формат: [Заголовок] - Текст (без громоздких URL и меток)
                    f"- {res['title']}: {res['body']}" 
                    for res in results
                )
                print(results_text)
                return results_text
            
        except Exception as e:
            print(f"❌ Ошибка поиска: {e}")
            return f"Ошибка при поиске: {e}"


client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=AI_TOKEN,
)



async def ai_generate(text: str, storage, user_id: int, chat_id: int, thread_id: int):
    """
    Умная функция генерации:
    1. Спрашивает роутер (нужен ли поиск?)
    2. Ищет (если надо)
    3. Генерирует ответ (стриминг)
    """

    from datetime import datetime
    current_date = datetime.now().strftime("%d.%m.%Y %H:%M")

    router_messages = []
    router_messages.append({
        "role": "system", 
        "content": (
            f"Сегодня {current_date}. Ты — аналитик поисковых запросов. ПИШИ ТОЛЬКО JSON.\n"
            "Определи, нужна ли свежая информация из сети.\n\n"
            
            "ПРАВИЛА ФОРМИРОВАНИЯ ЗАПРОСОВ:\n"
            "1. ВСЕГДА используй английский язык для поисковых запросов\n"
            "2. Переводи названия городов, компаний, событий на английский\n"
            "3. Используй только ключевые слова (не полные предложения)\n"
            "4. Добавляй конкретные даты вместо 'сегодня', 'вчера', 'завтра'\n"
            
            "ПРИМЕРЫ:\n"
            "❌ 'погода Ханты-Мансийск сегодня' → ✅ 'Khanty-Mansiysk weather January 5 2026'\n"
            "❌ 'кто вчера победил барселону' → ✅ 'Barcelona match result 4 January 2026'\n"
            "❌ 'новости Газпром' → ✅ 'Gazprom news January 2026'\n"
            "❌ 'курс биткоина' → ✅ 'Bitcoin price USD'\n\n"
            
            "Если это простой разговор, общие знания или приветствие - поиск не нужен.\n"
            "Ответ строго в JSON: "
            "{'search_needed': true, 'queries': ['base', 'with date', 'synonyms']}"
        )
        })
    
    history = await storage.load_history(user_id, chat_id, thread_id)
    history.append({"role": "user", "content": text})

    router_messages.extend(history)

    print("🤖 [Router] Анализирую запрос...")

    # response_format={"type": "json_object"} - это фича Groq/OpenAI, гарантирующая JSON на выходе
    router_response = await client.chat.completions.create(
        model=ROUTER_MODEL,
        messages=router_messages,
        response_format={"type": "json_object"}, 
        temperature=0.3 # Нулевая температура для максимальной предсказуемости
    )
    
    # Парсим решение роутера
    try:
        decision_text = router_response.choices[0].message.content
        decision = json.loads(decision_text)
    except json.JSONDecodeError:
        # Если модель сглупила и вернула не JSON (редко с response_format)
        print("⚠️ Ошибка парсинга JSON от роутера. Считаем, что поиск не нужен.")
        decision = {"search_needed": False}

    print(f"💡 [Router] Решение: {decision}")

    # ЭТАП 2: ПОИСК (Tool Execution)
    context_message = ""
    
    if decision.get("search_needed"):
        queries = decision.get("queries") or [decision.get("search_query", text)]
        search_results = await search_web(queries) 
        
        # Формируем контекст для финальной модели
        # Мы добавляем это как системное сообщение или user-контекст
        context_message = (
            f"Вот результаты поиска по запросу:\n"
            f"{search_results}\n\n"
            "Используй эти данные для ответа на вопрос пользователя."
        )

    final_messages = list(history)

    # Если был поиск, добавляем результаты как системный контекст ПЕРЕД последним вопросом
    if context_message:
        # Вставляем контекст как System message для контекста
        final_messages.append({"role": "system", "content": context_message})

    stream = await client.chat.completions.create(
        model=GENERATOR_MODEL,
        messages=final_messages,
        stream=True
        # tool_choice="auto",
        # tools=[{"type": "browser_search"}]
        )
    
    full_response = ''
    total_tokens = 0

    # print(response)
    # reasoning = response.choices[0].message.reasoning
    # answer = response.choices[0].message.content
    # tokens_used = response.usage.total_tokens

    # print(answer)

    # print(f"Использовано токенов: {tokens_used}")

    async for chunk in stream:
       content = chunk.choices[0].delta.content
       if content:
          # print(f'Чанк {content}')
          full_response += content
          yield content
       if chunk.usage:
           total_tokens = chunk.usage.total_tokens

    print(f"Итого использовано токенов: {total_tokens}")

    history.append({"role": "assistant", "content": full_response})

    # Оставляем последние 20 сообщений (10 пар вопрос-ответ)
    if len(history) > 20:
        history = history[-20:]

    await storage.save_history(user_id, chat_id, thread_id, history)

