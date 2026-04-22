import os
import re
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

class MiniMaxProvider:
    def __init__(self):
        api_key = os.getenv("MINIMAX_API_KEY")
        base_url = os.getenv("MINIMAX_BASE_URL", "https://api.minimax.io/v1")
        model = os.getenv("MODEL_DEFAULT", "MiniMax-M2.7")
        disable_env_proxies = os.getenv("MINIMAX_DISABLE_ENV_PROXIES", "true").lower() in ("1", "true", "yes")

        if not api_key:
            raise ValueError("MINIMAX_API_KEY is missing")

        self.model = model
        http_client = httpx.Client(trust_env=not disable_env_proxies, timeout=60.0)
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=http_client,
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

    def _clean_final_response(self, text: str) -> str:
        """
        Clean and format final response by removing thinking tags and metadata.
        
        Args:
            text: Raw response text
            
        Returns:
            Cleaned response text
        """
        if not text:
            return ""

        clean_text = text.strip()
        clean_text = re.sub(r"<think>.*?</think>\s*", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"\[think\].*?\[/think\]\s*", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"^\s*(Let me .*?\n\n)", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"^(Final response:|Answer:)\s*", "", clean_text, flags=re.IGNORECASE)
        return clean_text.strip()

    def combine_results(self, original_task: str, subtask_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Combine multi-step task results into a single coherent response.
        
        Args:
            original_task: The original user task
            subtask_results: List of results from parallel/sequential subtasks
                Each item should have: id, task_type, result (dict with "response" key)
                
        Returns:
            Dictionary with combined "response" and "subtask_results"
        """
        if len(subtask_results) == 1:
            return {
                "response": subtask_results[0]["result"].get("response", ""),
                "subtask_results": subtask_results
            }

        combined_text = f"Original task: {original_task}\n\n"

        for item in subtask_results:
            combined_text += (
                f"Subtask {item['id']} ({item['task_type']}):\n"
                f"{item['result'].get('response', '')}\n\n"
            )

        merge_prompt = f"""
You are a response synthesizer.

Do not include analysis, reasoning, or internal thoughts.
Write one final clean response for the user based on the original task and agent outputs.
Return plain text only, with no extra commentary.

Original task:
{original_task}

Agent outputs:
{combined_text}
"""

        try:
            final_response = self.chat(
                system_prompt="""
You are a high-quality response synthesizer.

Your job:
- Combine multiple agent outputs into ONE clean final answer
- Remove redundancy
- Improve clarity and flow
- Keep it concise but complete
- Maintain a professional tone

Return ONLY the final answer.
""",
                user_prompt=merge_prompt,
            ).strip()
            final_response = self._clean_final_response(final_response)
            if not final_response:
                raise ValueError("Empty final response from combiner")
        except Exception as e:
            print(f"[MINIMAX COMBINE ERROR] {e}")
            final_response = self._clean_final_response(combined_text)

        return {
            "response": final_response,
            "subtask_results": subtask_results
        }
