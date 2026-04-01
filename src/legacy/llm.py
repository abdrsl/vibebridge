import os

from dotenv import load_dotenv
from openai import OpenAI

from .secure_config import get_secret

load_dotenv()


def ask_deepseek_for_design_advice(user_prompt: str) -> str:
    api_key = get_secret("DEEPSEEK_API_KEY", "")
    base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    if not api_key:
        return "DeepSeek API key not configured."

    client = OpenAI(api_key=api_key, base_url=base_url)

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "你是一个产品研发AI助手，擅长需求分析、结构设计建议、3D打印可制造性建议、测试与验证方案。",
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ],
        temperature=0.3,
    )

    return resp.choices[0].message.content or ""
