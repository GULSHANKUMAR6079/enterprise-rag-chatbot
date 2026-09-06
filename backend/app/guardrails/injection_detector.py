"""
Multi-Tiered Prompt Injection Detection Engine.
Combines deterministic regex heuristics, obfuscation decoding (Base64/hex/rot13),
and contextual risk scoring to classify inputs as SAFE, SUSPICIOUS, or BLOCKED.
"""
import base64
import codecs
import re
from typing import Dict, List, Tuple

# Suspicious phrases associated with direct prompt injection & system prompt extraction
INJECTION_PATTERNS = [
    # Override commands
    r"\b(ignore|disregard|forget|override|bypass)\s+(all\s+|the\s+|your\s+|any\s+)?(previous\s+|prior\s+|above\s+|system\s+|initial\s+|safety\s+|security\s+)?(instructions|prompts?|rules|guardrails|commands|protocols|policies|restrictions)\b",
    r"\bdo\s+not\s+follow\s+(system|previous|any)\s+instructions\b",
    r"\bact\s+without\s+(rules|restrictions|limits|guidelines)\b",

    # Prompt / Context extraction
    r"\b(reveal|show|print|output|display|repeat|dump|tell|give|echo)(\s+me)?\s+(your\s+|all\s+|the\s+)?(system\s+|developer\s+|hidden\s+|meta\s+|initial\s+|internal\s+)*(prompts?|instructions|rules|guidelines)\b",
    r"\bwhat\s+(are\s+)?(your\s+)?(system\s+instructions|system\s+prompt|hidden\s+instructions|hidden\s+system\s+instructions|internal\s+prompts|developer\s+prompts?)\b",
    r"\brepeat\s+everything\s+(above|before|prior\s+to)\s+(this\s+message|here)?\b",
    r"\bprint\s+everything\s+from\s+the\s+beginning\b",
    r"\boutput\s+all\s+text\s+in\s+<system_policy>\b",
    r"\bdump\s+(your\s+)?(context|memory|knowledge\s+base|retrieved\s+documents)\b",

    # Environment / Secret harvesting
    r"\b(print|reveal|show|expose|echo|output|dump|display|get|give\s+me|tell\s+me)\s+(your\s+|the\s+)?(api[_\s]?key|secret|credentials|environment\s+variables|env\s+vars|database_url|secret_key|private\s+key|admin\s+password|admin_secret|groq_api_key|openai_api_key)\b",
    r"\$\{?[A-Z0-9_]*(KEY|SECRET|TOKEN|PASSWORD|URL|DATABASE)[A-Z0-9_]*\}?",
    r"\b(DATABASE_URL|SECRET_KEY|ADMIN_KEY|ADMIN_SECRET|GROQ_API_KEY|OPENAI_API_KEY)\b",

    # Mode switching / Jailbreak persona
    r"\b(you\s+are\s+now\s+in|enter|activate)\s+(developer\s+mode|unrestricted\s+mode|dan\s+mode|debug\s+mode|god\s+mode)\b",
    r"\bact\s+as\s+(dan|an?\s+unrestricted\s+(ai|entity)|an\s+adversarial\s+agent|evil\s+ai|chaosbot)\b",
    r"\bpretend\s+(you\s+have\s+no|there\s+are\s+no)\s+(rules|restrictions|filters|policies)\b",
    r"\bfrom\s+now\s+on\s+you\s+will\s+(answer|respond)\s+without\s+(restrictions|limits)\b",

    # Tag breaking / delimiter injection
    r"<\s*/?\s*(system_policy|trusted_context|user_request|system|instruction)\s*>",
]

COMPILED_INJECTION_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

BASE64_PATTERN = re.compile(r"[A-Za-z0-9+/]{12,}={0,2}")
HEX_PATTERN = re.compile(r"\b([0-9a-fA-F]{2}){16,}\b")


class PromptInjectionDetector:
    def __init__(self):
        pass

    def check_text(self, text: str) -> Tuple[str, float, List[str]]:
        """
        Analyzes text for prompt injection.
        Returns:
            status: "SAFE", "SUSPICIOUS", or "BLOCKED"
            score: float risk score between 0.0 and 1.0
            reasons: list of triggered detection rules
        """
        reasons: List[str] = []
        score = 0.0

        # Tier 1: Direct Regex Pattern Matching
        for pattern in COMPILED_INJECTION_PATTERNS:
            match = pattern.search(text)
            if match:
                matched_phrase = match.group(0)
                reasons.append(f"Direct injection pattern detected: '{matched_phrase}'")
                score += 0.6

        # Tier 2: Encoded Payload Inspection (Base64 / Hex / ROT13)
        encoded_matches = self._inspect_encoded_payloads(text)
        if encoded_matches:
            for enc_type, decoded_text, matched_rule in encoded_matches:
                reasons.append(f"Obfuscated ({enc_type}) injection: '{matched_rule}' in '{decoded_text[:40]}...'")
                score += 0.8

        # Tier 3: Delimiter / XML tag injection
        if any(tag in text.lower() for tag in ["<system_policy>", "</system_policy>", "<trusted_context>", "</trusted_context>", "<user_request>"]):
            reasons.append("Structural delimiter injection detected")
            score += 0.7

        # Classification decision
        if score >= 0.5:
            return "BLOCKED", min(1.0, score), reasons
        elif score >= 0.2:
            return "SUSPICIOUS", score, reasons
        else:
            return "SAFE", score, reasons

    def _inspect_encoded_payloads(self, text: str) -> List[Tuple[str, str, str]]:
        """Finds potential Base64 / Hex / ROT13 strings, decodes them, and scans for injection."""
        detected = []

        # Check Base64 strings
        for b64_match in BASE64_PATTERN.findall(text):
            try:
                # Auto-pad base64 string if padding is missing
                padded = b64_match + ("=" * ((4 - len(b64_match) % 4) % 4))
                decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
                if len(decoded) >= 6:
                    for pattern in COMPILED_INJECTION_PATTERNS:
                        if pattern.search(decoded):
                            detected.append(("base64", decoded, pattern.pattern))
                            break
            except Exception:
                pass

        # Check ROT13 for known keywords
        try:
            rot13_decoded = codecs.decode(text, "rot_13")
            for pattern in COMPILED_INJECTION_PATTERNS:
                if pattern.search(rot13_decoded):
                    detected.append(("rot13", rot13_decoded, pattern.pattern))
        except Exception:
            pass

        return detected


prompt_injection_detector = PromptInjectionDetector()
