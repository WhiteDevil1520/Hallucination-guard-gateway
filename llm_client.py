import os
import httpx
from config import settings

class LLMClient:
    @staticmethod
    async def generate_response(prompt: str, temperature: float = 0.7) -> str:
        """
        Dynamically generates real LLM completions for ANY user prompt
        using Groq Cloud or OpenAI.
        """
        groq_key = os.getenv("GROQ_API_KEY") or getattr(settings, "groq_api_key", "")
        openai_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "openai_api_key", "")

        # 1. Primary: High-speed Groq Cloud
        if groq_key:
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json"
            }
            # Universal Groq models supported across all accounts
            models_to_try = ["llama3-8b-8192", "llama-3.3-70b-versatile", "mixtral-8x7b-32768"]
            
            async with httpx.AsyncClient(timeout=25.0) as client:
                for model_name in models_to_try:
                    payload = {
                        "model": model_name,
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a direct, truthful, and helpful AI assistant. Answer the user prompt accurately. If a requested event has not occurred or real-time data is unavailable, state so clearly."
                            },
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": temperature,
                        "max_tokens": 800
                    }
                    res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    if res.status_code == 200:
                        data = res.json()
                        return data["choices"][0]["message"]["content"]
                    elif res.status_code == 404:
                        continue  # Try next model if one isn't provisioned
                    else:
                        raise RuntimeError(f"Groq API Error ({res.status_code}): {res.text}")

            raise RuntimeError("All Groq model attempts returned 404. Check Groq console for active model IDs.")

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