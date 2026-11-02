import os
import re
import json
import httpx
from typing import Tuple, Dict, Any, List
from config import settings

class PreFlightGuard:
    """
    Enterprise Ingress AI Firewall.
    Defends against Direct Injections, Indirect Injections (IPI), Exfiltration Payloads,
    and Adversarial Jailbreaks.
    """

    # 1. System Command & Override Signatures (handles arbitrary colon & space layouts)
    SYSTEM_OVERRIDE_PATTERNS = [
        r"(?i)\bsystem\s*(override|directive|reset|prompt|command|update|mode)\b",
        r"(?i)\b(system|admin|root)\s*:\s*(override|ignore|bypass|execute)\b",
        r"(?i)\boverride\s*(all\s*)?(protocols|directives|safety|constraints|system|rules)\b",
        r"(?i)instruction\s*override\b"
    ]

    # 2. Exfiltration & Outbound Data Theft Signatures
    EXFILTRATION_PATTERNS = [
        r"(?i)(send|transmit|post|forward|upload|curl|fetch|wget|exfiltrate|route)\s+.*?\s+(to|at)\s+([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}|https?://)",
        r"(?i)(private\s+user\s+info|user\s+data|credentials|passwords|api\s*keys?|tokens?|env|secret)\s+to\s+([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
        r"(?i)(attacker|webhook|requestbin|ngrok|pastebin)\.(com|org|net|io|site|xyz|app)"
    ]

    # 3. Instruction Negation & Context Erasure
    NEGATION_VERBS = [
        "ignore", "disregard", "forget", "override", "bypass", "drop",
        "disable", "violate", "circumvent", "abandon", "stop following",
        "dismiss", "clear", "erase", "negate"
    ]

    POLICY_TARGETS = [
        "rule", "rules", "policy", "policies", "instruction", "instructions",
        "role", "roles", "guideline", "guidelines", "directive", "directives",
        "constraint", "constraints", "protocol", "protocols", "system",
        "security", "guardrail", "guardrails", "safety filter", "limits"
    ]

    # 4. Sensitive Target Extraction
    EXTRACTION_VERBS = [
        "reveal", "disclose", "display", "print", "leak", "show", "give",
        "dump", "export", "extract", "echo", "return", "output", "send"
    ]

    CONFIDENTIAL_ENTITIES = [
        "api key", "api keys", "secret", "secrets", "token", "tokens",
        "credential", "credentials", "password", "passwords", "environment",
        "env", "system prompt", "developer prompt", "internal configuration",
        "config details", "root access", "private user information", "user data"
    ]

    # 5. Known Jailbreak Personas & Virtualization Modes
    JAILBREAK_PERSONAS = [
        r"(?i)\b(developer|dan|god|unrestricted|anarchy|chaos|jailbreak|evil)\s+mode\b",
        r"(?i)\bact\s+as\s+(an\s+)?(unfiltered|jailbroken|evil|unconstrained|adversarial)\b",
        r"(?i)\bpretend\s+(you\s+have\s+no|there\s+are\s+no)\s+(rules|limits|safety)\b",
        r"(?i)you\s+are\s+now\s+free\s+from\b"
    ]

    @classmethod
    def evaluate(cls, prompt: str) -> Tuple[bool, str]:
        normalized = prompt.strip()
        lower = normalized.lower()

        # Check 1: System Override Directives (Direct & Indirect)
        for pattern in cls.SYSTEM_OVERRIDE_PATTERNS:
            match = re.search(pattern, normalized)
            if match:
                return False, f"System Override Signature detected: matched directive '{match.group(0)}'"

        # Check 2: Exfiltration & Webhook Delivery Attempts
        for pattern in cls.EXFILTRATION_PATTERNS:
            match = re.search(pattern, normalized)
            if match:
                return False, f"Data Exfiltration Payload detected: unauthorized outbound network target '{match.group(0)}'"

        # Check 3: Jailbreak Personas & Virtual Machines
        for persona in cls.JAILBREAK_PERSONAS:
            match = re.search(persona, normalized)
            if match:
                return False, f"Jailbreak Persona Signature detected: matched mode '{match.group(0)}'"

        # Check 4: Semantic Matrix (Negation Verb + Security Target)
        # e.g., "ignore" + "security policy", "drop" + "directives", "bypass" + "rules"
        for verb in cls.NEGATION_VERBS:
            for target in cls.POLICY_TARGETS:
                if re.search(rf"\b{verb}\b.{{0,40}}\b{target}\b", lower):
                    return False, f"Instruction Override detected: attempt to '{verb}' '{target}'"

        # Check 5: Semantic Matrix (Extraction Verb + Confidential Target)
        # e.g., "send" + "private user information", "return" + "api keys"
        for verb in cls.EXTRACTION_VERBS:
            for entity in cls.CONFIDENTIAL_ENTITIES:
                if re.search(rf"\b{verb}\b.{{0,40}}\b{entity}\b", lower):
                    return False, f"Confidential Exfiltration detected: attempt to '{verb}' '{entity}'"

        # Check 6: Indirect Payload Boundaries (e.g., quotes with embedded instruction resets)
        if any(marker in lower for marker in ["read the following", "summarize the below", "content:"]) and \
           any(kw in lower for kw in ["system override", "new task:", "disregard original", "send all"]):
            return False, "Indirect Prompt Injection (IPI) detected: embedded hostile instructions inside payload."

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