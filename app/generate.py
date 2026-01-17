from openai import AsyncOpenAI
from config import AI_TOKEN

MODEL='openai/gpt-oss-20b'
# xiaomi/mimo-v2-flash:free

client = AsyncOpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=AI_TOKEN,
)

memory = []


async def ai_generate(text):
    memory.append({"role": "user", "content": text})

    stream = await client.chat.completions.create(
        model=MODEL,
        messages=memory,
        stream=True
        # tools=[{"type": "browser_search"}],  # Правильный синтаксис
        # tool_choice="auto"  # или "required" для принудительного поиска
        )

    # print(response)
    # reasoning = response.choices[0].message.reasoning
    # answer = response.choices[0].message.content
    # tokens_used = response.usage.total_tokens

    # print(answer)

    # print(f"Использовано токенов: {tokens_used}")

    # memory.append({"role": "assistant", "content": answer,})

    # return answer

    async for chunk in stream:
       content = chunk.choices[0].delta.content
       if content:
          print(f'Чанк {content}')
          yield content

  

async def clear_context():
  memory.clear()







'''

async def ai_generate(text):
  # First API call with reasoning
  response = await client.chat.completions.create(
  model=MODEL,
  messages=[
          {
            "role": "user",
            "content": text
          }
        ],
  extra_body={"reasoning": {"enabled": False}}
  )


ask = input()

memory = [
  {"role": "user", "content": "сколько букв р в слове дерревянный?"},
  {
    "role": "assistant",
    "content": answer,
    "reasoning_details": reasoning
  },
  {"role": "user", "content": ask}
]



# Preserve the assistant message with reasoning_details


# Second API call - model continues reasoning from where it left off
response2 = client.chat.completions.create(
  model=MODEL,
  messages=memory,
  extra_body={"reasoning": {"enabled": True}}
)

answer = response2.choices[0].message.content
print(answer)

# Second API call - model continues reasoning from where it left off
response2 = client.chat.completions.create(
  model=MODEL,
  messages=messages,
  extra_body={"reasoning": {"enabled": True}}
)

answer = response2.choices[0].message.content
print(answer)
'''


