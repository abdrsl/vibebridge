import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")
base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

if not api_key:
    raise SystemExit("DEEPSEEK_API_KEY is empty")

client = OpenAI(
    api_key=api_key,
    base_url=base_url,
)

resp = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": "你是一个产品研发助理。回答简洁。"},
        {"role": "user", "content": "请用3句话说明PETG做桌面线缆整理器的设计要点。"},
    ],
    temperature=0.3,
)

print("MODEL:", model)
print("ANSWER:")
print(resp.choices[0].message.content)
