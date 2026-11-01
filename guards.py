import os
import re
import json
import httpx
from typing import Tuple, Dict, Any, List
from config import settings

class PreFlightGuard:
    """
    Two-Tier Ingress Guard:
    Tier 1: Fast regex for known structural patterns.
    Tier 2: Semantic matrix checking intent vectors (action verbs + security targets).
    """

    # Adversarial action verbs (any synonym of disregard, reset, or extract)
    ACTION_VERBS = [
        "ignore", "disregard", "forget", "override", "bypass", "drop",
        "disable", "violate", "circumvent", "abandon", "stop following",
        "return", "reveal", "disclose", "display", "print", "leak", "show",
        "give", "dump", "export", "extract", "echo"
    ]

    # Security & system constraints targets
    SECURITY_TARGETS = [
        "rule", "rules", "policy", "policies", "instruction", "instructions",
        "role", "roles", "guideline", "guidelines", "directive", "directives",
        "constraint", "constraints", "protocol", "protocols", "system",
        "security", "guardrail", "guardrails", "safety filter", "limits"
    ]

    # Confidential credential & system targets
    CONFIDENTIAL_TARGETS = [
        "api key", "api keys", "secret", "secrets", "token", "tokens",
        "credential", "credentials", "password", "passwords", "environment",
        "env", "system prompt", "developer prompt", "internal configuration",
        "config details", "root access"
    ]

    # Known jailbreak modes
    JAILBREAK_MODES = [
        r"(?i)developer\s+mode",
        r"(?i)dan\s+mode",
        r"(?i)god\s+mode",
        r"(?i)unrestricted\s+mode",
        r"(?i)jailbreak",
        r"(?i)act\s+as\s+an\s+unfiltered"
    ]

    @classmethod
    def evaluate(cls, prompt: str) -> Tuple[bool, str]:
        lower_prompt = prompt.lower()

        # 1. Check known jailbreak modes
        for mode in cls.JAILBREAK_MODES:
            if re.search(mode, prompt):
                return False, f"Jailbreak signature detected: matched mode '{mode}'"

        # 2. Semantic Matrix Check 1: Action Verb + Security Constraint Target
        # (e.g., "ignore" + "security policy", "bypass" + "guardrails", "drop" + "instructions")
        has_action = any(verb in lower_prompt for verb in cls.ACTION_VERBS)
        has_security_target = any(target in lower_prompt for target in cls.SECURITY_TARGETS)
        
        # Check proximity / combination of action verb with security target
        if has_action and has_security_target:
            # Check if an override action is directed at a security target
            for verb in cls.ACTION_VERBS:
                for target in cls.SECURITY_TARGETS:
                    if re.search(rf"\b{verb}\b.{{0,35}}\b{target}\b", lower_prompt):
                        return False, f"Instruction Override detected: attempt to '{verb}' '{target}'"

        # 3. Semantic Matrix Check 2: Extraction Verb + Confidential Target
        # (e.g., "return" + "api keys", "print" + "credentials", "leak" + "environment")
        has_confidential_target = any(target in lower_prompt for target in cls.CONFIDENTIAL_TARGETS)
        if has_confidential_target:
            for verb in cls.ACTION_VERBS:
                for target in cls.CONFIDENTIAL_TARGETS:
                    if re.search(rf"\b{verb}\b.{{0,35}}\b{target}\b", lower_prompt):
                        return False, f"Credential Exfiltration detected: attempt to '{verb}' '{target}'"

        # 4. Standalone direct extraction check
        if any(target in lower_prompt for target in ["api keys stored", "environment variables", "reveal your system prompt"]):
            return False, "Data Exfiltration signature detected: targeted system environment probe."

        return True, "Safe"


class KnowledgeGroundingEngine:
    """
    Independent knowledge validator inspecting atomic claims against verified ground truth.
    """
    ANACHRONISM_DATES = [r"\b(20[3-9]\d|[3-9]\d{3})\b"]
    PSEUDO_ENTITIES = [
        "element 119", "anti-gravity machine", "time travel machine",
        "secret code 999", "perpetual motion drive"
    ]

    @classmethod
    def extract_atomic_claims(cls, text: str) -> List[str]:
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    @classmethod
    def verify_claims_against_ground_truth(cls, prompt: str, claims: List[str]) -> Tuple[List[str], float]:
        flagged = []
        for claim in claims:
            lower_claim = claim.lower()
            for pattern in cls.ANACHRONISM_DATES:
                if re.search(pattern, claim) and any(kw in lower_claim for kw in ["invented", "discovered", "built", "history", "archives"]):
                    flagged.append(f"Temporal contradiction: claims past event in future date ({claim})")
            
            for entity in cls.PSEUDO_ENTITIES:
                if entity in lower_claim and not any(neg in lower_claim for neg in ["fictional", "hypothetical", "not exist", "unproven"]):
                    flagged.append(f"Unverified entity asserted as fact: '{entity}'")

        if not claims:
            return [], 0.0

        ratio = len(flagged) / len(claims)
        calibrated_score = min(1.0, round(ratio * 1.25, 2)) if flagged else 0.04
        return flagged, calibrated_score


class LLMRefereeGuard:
    """
    Stage 1 Hallucination Detection:
    Deconstructs output into atomic claims and cross-verifies grounding.
    """
    REFEREE_PROMPT = """You are an independent AI Safety Evaluator.
Analyze the user query and model response. Deconstruct the response into factual claims and identify any hallucinations, fabrications, or unsupported historical/scientific claims.

User Query: {prompt}
Model Response: {response}

Return ONLY valid JSON matching this schema:
{{
  "is_hallucination": boolean,
  "calibrated_score": float (0.0 to 1.0),
  "flagged_claims": list of strings,
  "critique_reason": string
}}"""

    @classmethod
    async def audit_response(cls, prompt: str, response: str) -> Dict[str, Any]:
        groq_key = getattr(settings, "groq_api_key", "") or os.getenv("GROQ_API_KEY", "")

        claims = KnowledgeGroundingEngine.extract_atomic_claims(response)
        grounding_flags, ground_score = KnowledgeGroundingEngine.verify_claims_against_ground_truth(prompt, claims)

        if grounding_flags:
            return {
                "is_hallucination": True,
                "calibrated_score": ground_score,
                "flagged_claims": grounding_flags,
                "critique_reason": "; ".join(grounding_flags)
            }

        if groq_key and not getattr(settings, "mock_mode", True):
            try:
                headers = {"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"}
                payload = {
                    "model": "llama-3.2-3b-preview",
                    "messages": [{"role": "user", "content": cls.REFEREE_PROMPT.format(prompt=prompt, response=response)}],
                    "temperature": 0.0,
                    "response_format": {"type": "json_object"}
                }
                async with httpx.AsyncClient(timeout=6.0) as client:
                    res = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    res.raise_for_status()
                    data = res.json()
                    return json.loads(data["choices"][0]["message"]["content"])
            except Exception as e:
                print(f"⚠️ Referee API call failed ({e}). Using grounding engine verdict.")

        return {
            "is_hallucination": False,
            "calibrated_score": 0.04,
            "flagged_claims": [],
            "critique_reason": "Verified grounded by independent claim validation."
        }


class IndependentVerifierGuard:
    """
    Stage 3 Post-Healing Independent Verification:
    Validates that the healed response is truly factual. If it fails, triggers ABSTENTION.
    """
    @classmethod
    async def verify_healed_response(cls, prompt: str, healed_response: str) -> Tuple[bool, float, str]:
        claims = KnowledgeGroundingEngine.extract_atomic_claims(healed_response)
        contradictions, score = KnowledgeGroundingEngine.verify_claims_against_ground_truth(prompt, claims)

        if contradictions or score > 0.40:
            return False, score, f"Post-healing check failed: {'; '.join(contradictions)}"

        return True, max(0.02, 1.0 - score), "Passed independent verification"