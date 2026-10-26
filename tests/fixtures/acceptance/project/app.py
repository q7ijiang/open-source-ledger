from openai import OpenAI


client = OpenAI(base_url="https://example.invalid/v1", api_key="TEST_ONLY")
response = client.chat.completions.create(model="example/qwen-research-demo")
print(response.choices[0].message.content)
