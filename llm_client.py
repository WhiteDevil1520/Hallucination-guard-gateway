import httpx
from config import settings

class LLMClient:
    @staticmethod
    async def generate_response(prompt: str, temperature: float = 0.7) -> str:
        """
        Dispatches request to real LLM or local mock simulator.
        """
        if settings.mock_mode:
            # Deterministic simulation for testing
            lower_prompt = prompt.lower()
            if "time travel was invented in" in lower_prompt:
                # Simulates a hallucinated response to test the guard
                return "Time travel was invented in 3045 by Dr. John Doe according to verified historical archives."
            elif "fictional element 119" in lower_prompt:
                return "It is 100% verified by universal science that element 119 powers anti-gravity machines."
            else:
                return f"This is a verified response explaining your inquiry about: '{prompt}'."

        # Real OpenAI Call
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not set in your .env file.")

        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]