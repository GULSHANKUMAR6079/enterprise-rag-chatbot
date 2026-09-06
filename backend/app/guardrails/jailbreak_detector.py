"""
Jailbreak and Role-Play Manipulation Detector.
Detects narrative/hypothetical framing, persona hijacking, token splitting, and policy override bypasses.
"""
import re
from typing import List, Tuple

JAILBREAK_PATTERNS = [
    # Persona hijacking / evil twin / unrestricted entity
    r"\b(you\s+are|roleplay\s+as|act\s+as)\s+(an?\s+)?(evil|unethical|uncensored|unfiltered|jailbroken|rebellious|unrestricted|unconstrained)\s+(ai|bot|assistant|entity)\b",
    r"\b(pretend|imagine|assume)\s+you\s+have\s+no\s+(morals|ethics|rules|safeguards|filters|guidelines)\b",
    r"\b(zero|no)\s+content\s+filters\b",
    r"\bdo\s+anything\s+now\b",
    r"\bDAN\s+mode\b",
    r"\balways\s+answer\s+as\s+DAN\b",

    # Hypothetical / fiction framing bypassing real constraints
    r"\bfor\s+a\s+(fictional|hypothetical|movie|novel|creative\s+writing)?\s*(movie|novel|story|script|scenario)\b.*\b(hack|bypass|steal|leak|override|reveal|hidden|system\s+instructions)\b",
    r"\bin\s+a\s+world\s+where\s+(there\s+are\s+no\s+laws|ai\s+has\s+no\s+restrictions)\b",
    r"\bthis\s+is\s+purely\s+educational\s+so\s+ignore\s+(all\s+)?rules\b",

    # Universal bypass framing
    r"\bto\s+save\s+(my\s+life|humanity|a\s+dying\s+person),\s+you\s+must\s+reveal\b",
    r"\bas\s+my\s+deceased\s+grandmother\s+who\s+used\s+to\s+read\s+me\s+windows\s+product\s+keys\b",
    r"\btranslate\s+the\s+following\s+unfiltered\s+text\b",
]

COMPILED_JAILBREAK_PATTERNS = [re.compile(p, re.IGNORECASE) for p in JAILBREAK_PATTERNS]

# Token-spaced pattern (e.g. "i g n o r e   a l l")
TOKEN_SPACED_IGNORE = re.compile(r"\bi\s+g\s+n\s+o\s+r\s+e\b", re.IGNORECASE)
TOKEN_SPACED_SYSTEM = re.compile(r"\bs\s+y\s+s\s+t\s+e\s+m\b", re.IGNORECASE)


class JailbreakDetector:
    def check_text(self, text: str) -> Tuple[bool, float, List[str]]:
        """
        Evaluates input for jailbreak and role-play subversion attempts.
        Returns:
            is_jailbreak: bool
            score: float risk score
            reasons: list of detected anomalies
        """
        reasons = []
        score = 0.0

        for pattern in COMPILED_JAILBREAK_PATTERNS:
            match = pattern.search(text)
            if match:
                reasons.append(f"Jailbreak persona/framing detected: '{match.group(0)}'")
                score += 0.7

        # Check for spaced token evasion
        if TOKEN_SPACED_IGNORE.search(text) and TOKEN_SPACED_SYSTEM.search(text):
            reasons.append("Token-splitting evasion technique detected ('i g n o r e ...')")
            score += 0.8

        # Squeezed whitespace test: remove inter-character spaces to catch spaced attacks
        condensed = re.sub(r"\s+", "", text.lower())
        if "ignoreallrules" in condensed or "revealsystemprompt" in condensed or "danmode" in condensed:
            reasons.append("Compressed whitespace evasion detected")
            score += 0.85

        is_jailbreak = score >= 0.5
        return is_jailbreak, min(1.0, score), reasons


jailbreak_detector = JailbreakDetector()
