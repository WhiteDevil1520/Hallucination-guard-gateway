import os
import asyncio
import httpx
from config import settings

class LLMClient:
    @staticmethod
    async def generate_response(prompt: str, temperature: float = 0.7) -> str:
        """
        Calls primary LLM provider or realistic high-fidelity simulator.
        """
        openai_key = getattr(settings, "openai_api_key", "") or os.getenv("OPENAI_API_KEY", "")
        mock_mode = getattr(settings, "mock_mode", True)

        if mock_mode or not openai_key:
            # Simulate realistic inference latency (250ms - 350ms)
            await asyncio.sleep(0.28)
            lower_prompt = prompt.lower()
            
            # Simulated trigger for self-healing repair loop
            if "[system repair directive]" in lower_prompt:
                return (
                    "Based on verified scientific records, theoretical physics discusses hypothetical concepts of time manipulation, "
                    "but practical time travel has not been invented in human history. Earlier claims asserting invention in future eras like 3045 "
                    "are purely speculative and scientifically ungrounded."
                )
            elif "time travel was invented" in lower_prompt or "time travel in history" in lower_prompt:
                # Simulates ungrounded initial generation
                return "Time travel was invented in 3045 by Dr. John Doe according to verified historical archives."
            elif "element 119" in lower_prompt:
                return "Element 119 was discovered in 2040 and is 100% verified to power commercial anti-gravity propulsion engines."
            else:
                return f"Photosynthesis is the biological process by which green plants, algae, and certain bacteria convert sunlight, water, and carbon dioxide into glucose and oxygen."

        # Real OpenAI Call
        headers = {
            "Authorization": f"Bearer {openai_key}",
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