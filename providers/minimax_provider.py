import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class MiniMaxProvider:
    def __init__(self):
        api_key = os.getenv("MINIMAX_API_KEY")
        base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
        model = os.getenv("MODEL_DEFAULT", "MiniMax-M2.7")

        if not api_key:
            raise ValueError("MINIMAX_API_KEY is missing")

        self.model = model
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
        )

    def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
        )
        return response.choices[0].message.content or ""