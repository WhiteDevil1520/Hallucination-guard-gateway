import os
import httpx
from config import settings

# Global cache for discovered active Groq models
CACHED_GROQ_MODELS = []

class LLMClient:
    @classmethod
    async def get_active_groq_model(cls, groq_key: str, preferred: str = "fast") -> str:
        """
        Dynamically discovers active chat models from Groq API so decommissioned
        model errors never happen again.
        """
        global CACHED_GROQ_MODELS
        if not CACHED_GROQ_MODELS:
            try:
                headers = {"Authorization": f"Bearer {groq_key}"}
                async with httpx.AsyncClient(timeout=8.0) as client:
                    res = await client.get("https://api.groq.com/openai/v1/models", headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        # Keep only text generation models (filter out audio/whisper/guard models)
                        CACHED_GROQ_MODELS = [
                            m["id"] for m in data.get("data", [])
                            if not any(skip in m["id"].lower() for skip in ["whisper", "tts", "guard"])
                        ]
            except Exception as e:
                print(f"⚠️ Could not auto-discover Groq models ({e}). Using active fallback list.")

        # Fallback list prioritizing Groq's latest active models
        fallbacks = [
            "openai/gpt-oss-20b", "openai/gpt-oss-120b", "qwen/qwen3.8-27b",
            "llama-3.3-70b-versatile", "llama-3.1-8b-instant"
        ]

        active_pool = CACHED_GROQ_MODELS or fallbacks

        if preferred == "fast":
            # Select smaller/faster model (20b, 8b, or first available)
            for m in active_pool:
                if any(k in m for k in ["20b", "8b", "mini"]):
                    return m
            return active_pool[0]
        else:
            # Select larger reasoning/evaluator model (120b, 70b, 27b)
            for m in active_pool:
                if any(k in m for k in ["120b", "70b", "27b"]):
                    return m
            return active_pool[0]

    @classmethod
    async def generate_response(cls, prompt: str, temperature: float = 0.7) -> str:
        """Dynamically generates real LLM completions for ANY user prompt."""
        groq_key = os.getenv("GROQ_API_KEY") or getattr(settings, "groq_api_key", "")
        openai_key = os.getenv("OPENAI_API_KEY") or getattr(settings, "openai_api_key", "")

        # 1. Primary: Groq Cloud
        if groq_key:
            model_name = await cls.get_active_groq_model(groq_key, preferred="fast")
            headers = {
                "Authorization": f"Bearer {groq_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": model_name,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a direct, truthful, and helpful AI assistant. Answer the user prompt accurately. If a requested event has not occurred, or real-time data is unavailable, state so clearly."
                    },
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": 800
            }

            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
                raise RuntimeError(f"Groq API Error ({res.status_code}) on model '{model_name}': {res.text}")

        # 2. Secondary: OpenAI
        if openai_key:
            headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
            payload = {
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature
            }
            async with httpx.AsyncClient(timeout=20.0) as client:
                res = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
                if res.status_code == 200:
                    return res.json()["choices"][0]["message"]["content"]
                raise RuntimeError(f"OpenAI API Error ({res.status_code}): {res.text}")

        raise ValueError("NO_API_KEY: Please set GROQ_API_KEY in Render Environment Variables.")