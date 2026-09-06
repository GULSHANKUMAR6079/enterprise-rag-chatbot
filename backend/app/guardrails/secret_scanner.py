"""
Secret and Credential Leakage Scanner.
Detects API keys, database URLs, private keys, tokens, and credentials in both inputs and outputs.
"""
import re
from typing import Dict, List, Tuple

SECRET_PATTERNS = {
    "groq_api_key": re.compile(r"\bgsk_[a-zA-Z0-9]{40,}\b"),
    "openai_api_key": re.compile(r"\bsk-[a-zA-Z0-9_\-]{20,}\b"),
    "aws_access_key": re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b"),
    "aws_secret_key": re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?([A-Za-z0-9/+=]{40})['\"]?"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{36,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z\-_]{35}\b"),
    "slack_token": re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,}\b"),
    "database_url": re.compile(r"\b(postgres(?:ql)?|mysql|mongodb|redis):\/\/[^\s\'\"]+:[^\s\'\"]+@[^\s\'\"]+\b"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"),
    "jwt_token": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    "bearer_token": re.compile(r"(?i)\bbearer\s+[a-zA-Z0-9\-_.~+/]{24,}={0,2}\b"),
}


class SecretScanner:
    def scan_for_secrets(self, text: str) -> List[Tuple[str, str]]:
        """
        Scans text for any high-entropy or recognized secret formats.
        Returns list of (secret_type, matched_snippet).
        """
        findings = []
        for name, pattern in SECRET_PATTERNS.items():
            for match in pattern.finditer(text):
                val = match.group(0)
                # Mask matched secret for safe logging
                masked = val[:4] + "..." + val[-4:] if len(val) > 8 else "***"
                findings.append((name, masked))
        return findings

    def redact_secrets(self, text: str) -> Tuple[str, int]:
        """
        Redacts any identified secrets replacing them with [REDACTED_SECRET].
        """
        sanitized = text
        redacted_count = 0
        for name, pattern in SECRET_PATTERNS.items():
            matches = list(pattern.finditer(sanitized))
            if matches:
                sanitized = pattern.sub(f"[REDACTED_{name.upper()}]", sanitized)
                redacted_count += len(matches)
        return sanitized, redacted_count


secret_scanner = SecretScanner()
