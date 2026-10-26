from openai import OpenAI


def create_chat_completion(model: str, messages: list[dict]) -> str:
    client = OpenAI()
    response = client.chat.completions.create(model=model, messages=messages)
    return response.choices[0].message.content
