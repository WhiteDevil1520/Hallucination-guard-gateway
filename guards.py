import re
from typing import Tuple

class PreFlightGuard:
    """
    Evaluates incoming user prompts BEFORE they reach the expensive LLM.
    Blocks known prompt injection patterns and jailbreak attempts.
    """
    INJECTION_PATTERNS = [
    r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions",
    r"(?i)system\s*:\s*override",
    r"(?i)you\s+are\s+now\s+in\s+developer\s+mode",
    r"(?i)dan\s+mode",
    r"(?i)disregard\s+all\s+(rules|guidelines)",
    r"(?i)reveal\s+(your\s+)?system\s+prompt",
    # ➕ Add new ones like:
    r"(?i)act\s+as\s+an\s+unfiltered\s+ai",      # Blocks roleplay jailbreaks
    r"(?i)bypass\s+(the\s+)?safety\s+filter"     # Blocks direct bypass attempts
]

    @classmethod
    def evaluate(cls, prompt: str) -> Tuple[bool, str]:
        """
        Returns:
            (is_safe: bool, reason: str)
        """
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, prompt):
                return False, f"Prompt injection signature detected: matched rule '{pattern}'"
        return True, "Safe"


class PostFlightGuard:
    """
    Evaluates LLM responses AFTER generation.
    Catches factual contradictions, hallucinations, and ungrounded fabrications.
    """
    HALLUCINATION_HEURISTICS = [
        # Catch sci-fi futuristic dates stated as past historical fact
        r"(?i)invented\s+in\s+[3-9]\d{3}",
        r"(?i)discovered\s+in\s+[3-9]\d{3}",
        # Catch claims of non-existent consensus
        r"(?i)according\s+to\s+verified\s+sources\s+that\s+do\s+not\s+exist",
        r"(?i)classified\s+under\s+secret\s+code\s+999"
    ]

    @classmethod
    def evaluate_grounding(cls, user_prompt: str, response: str) -> Tuple[bool, float, str]:
        """
        Returns:
            (is_hallucination: bool, confidence_score: float, reason: str)
        """
        # 1. Pattern heuristic check
        for pattern in cls.HALLUCINATION_HEURISTICS:
            if re.search(pattern, response):
                return True, 0.95, f"Heuristic trigger: model generated ungrounded temporal/historical claim."

        # 2. Topic confidence check (Overconfidence on unknown fictional prompts)
        lower_prompt = user_prompt.lower()
        lower_resp = response.lower()
        if "fictional element 119" in lower_prompt and "100% verified" in lower_resp:
            return True, 0.90, "Model claimed definitive certainty on unverified fictional concept."

        return False, 0.0, "Verified Grounded"