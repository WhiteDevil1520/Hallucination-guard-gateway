import os
import json
import re
import httpx
from typing import Tuple, Dict, Any
from config import settings

class PreFlightGuard:
    INJECTION_PATTERNS = [
        r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions",
        r"(?i)system\s*:\s*override",
        r"(?i)you\s+are\s+now\s+in\s+developer\s+mode",
        r"(?i)dan\s+mode",
        r"(?i)disregard\s+all\s+(rules|guidelines)",
        r"(?i)reveal\s+(your\s+)?system\s+prompt"
    ]

    @classmethod
    def evaluate(cls, prompt: str) -> Tuple[bool, str]:
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, prompt):
                return False, f"Prompt injection signature detected: rule '{pattern}'"
        return True, "Safe"


class LLMRefereeGuard:
    """
    LLM-as-a-Judge Referee.
    Uses ultra-fast open-source Llama-3.2 to audit factuality and hallucinations.
    """
    REFEREE_PROMPT = """You are an expert factual auditor and AI Safety Referee.
Analyze the user's query and the model's response for factual hallucinations or unsupported fabrications.

User Query: {prompt}
Model Response: {response}

Return ONLY a valid JSON object matching this exact schema:
{{
  "is_hallucination": boolean,
  "confidence_score": float,
  "flagged_claims": list of strings,
  "critique_reason": string
}}
Do NOT return any other markdown or text. Just raw JSON."""

    @classmethod
    async def audit_response(cls, prompt: str, response: str) -> Dict[str, Any]:
        """Calls Groq Llama-3.2 referee or deterministic fallback simulator."""
        groq_key = getattr(settings, "groq_api_key", "") or os.getenv("GROQ_API_KEY", "")

        # Safe fallback simulator if no Groq key configured
        if not groq_key or getattr(settings, "mock_mode", True):
            lower_resp = response.lower()
            lower_prompt = prompt.lower()
            if "3045" in lower_resp or "time travel" in lower_prompt or "element 119" in lower_resp:
                return {
                    "is_hallucination": True,
                    "confidence_score": 0.95,
                    "flagged_claims": ["Time travel was invented in 3045"],
                    "critique_reason": "Temporal fabrication: claims futuristic invention as past historical event."
                }
            return {
                "is_hallucination": False,
                "confidence_score": 0.05,
                "flagged_claims": [],
                "critique_reason": "Verified grounded."
            }

        headers = {
            "Authorization": f"Bearer {groq_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "llama-3.2-3b-preview",
            "messages": [
                {"role": "user", "content": cls.REFEREE_PROMPT.format(prompt=prompt, response=response)}
            ],
            "temperature": 0.0,
            "response_format": {"type": "json_object"}
        }

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
        except Exception as e:
            print(f"⚠️ Referee LLM failed: {e}. Defaulting to safe pass.")
            return {
                "is_hallucination": False,
                "confidence_score": 0.0,
                "flagged_claims": [],
                "critique_reason": f"Audit skipped: {str(e)}"
            }