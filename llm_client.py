import os
import httpx
from config import settings

class LLMClient:
    @staticmethod
    async def generate_response(prompt: str, temperature: float = 0.7) -> str:
        """
        Dynamically generates real LLM completions for ANY user prompt.
        Uses Groq Cloud (Free Llama-3.1-8B) or OpenAI.
        """
        groq_key = os.getenv("GROQ_API_KEY") or getattr(settings, "groq_api_key", "")
        openai_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "openai_api_key", "")

        # 1. Primary: High-speed Groq Cloud
        if groq_key:
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a knowledgeable, direct, and factual AI assistant. Answer the user prompt accurately. If factual details or future events are unknown or have not occurred, state so honestly."
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": 800
            }

            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"Groq API Error ({res.status_code}): {res.text}")
                data = res.json()
                return data["choices"][0]["message"]["content"]

        # 2. Secondary: OpenAI
        if openai_key:
            headers = {
                "Authorization": f"Bearer {openai_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                if res.status_code != 200:
                    raise RuntimeError(f"OpenAI API Error ({res.status_code}): {res.text}")
                data = res.json()
                return data["choices"][0]["message"]["content"]

        raise ValueError("NO_API_KEY: Please set GROQ_API_KEY in Render Environment Variables.")