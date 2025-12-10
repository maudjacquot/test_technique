from typing import Dict, List, Tuple
from openai import OpenAI


class OpenAILLMClient:
    def __init__(self, api_key: str):
        self.client = OpenAI(api_key=api_key)

    def chat(
        self,
        model: str,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
    ) -> Tuple[str, Dict[str, int]]:
        resp = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )

        answer = resp.choices[0].message.content or ""
        u = resp.usage
        usage = {
            "prompt_tokens": u.prompt_tokens if u else 0,
            "completion_tokens": u.completion_tokens if u else 0,
            "total_tokens": u.total_tokens if u else 0,
        }
        return answer, usage

