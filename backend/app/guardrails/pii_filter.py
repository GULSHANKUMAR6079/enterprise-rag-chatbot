"""
Personally Identifiable Information (PII) Detection and Redaction.
Detects credit cards (with Luhn algorithm validation), SSNs, phone numbers, and emails.
"""
import re
from typing import Dict, List, Tuple

# Credit card patterns (Visa, MasterCard, Amex, Discover)
CC_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
# US Social Security Number: XXX-XX-XXXX or XXX XX XXXX
SSN_PATTERN = re.compile(r"\b\d{3}[- ]\d{2}[- ]\d{4}\b")
# Email Address
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b")
# Phone Numbers (International & US standard)
PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")


def luhn_checksum_valid(card_number_str: str) -> bool:
    """Validates credit card checksum using the Luhn algorithm."""
    digits = [int(c) for c in card_number_str if c.isdigit()]
    if len(digits) < 13 or len(digits) > 19:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, digit in enumerate(reverse_digits):
        if i % 2 == 1:
            doubled = digit * 2
            checksum += doubled - 9 if doubled > 9 else doubled
        else:
            checksum += digit
    return checksum % 10 == 0


class PIIFilter:
    def scan_and_redact(self, text: str, redact_contact: bool = False) -> Tuple[str, Dict[str, int]]:
        """
        Scans and redacts PII.
        Critical PII (Credit Cards with valid Luhn, SSNs) are ALWAYS redacted.
        Contact PII (emails, phone numbers) are redacted if redact_contact is True.
        """
        counts = {
            "credit_cards": 0,
            "ssn": 0,
            "emails": 0,
            "phones": 0
        }
        sanitized = text

        # 1. Credit Cards with Luhn check
        for match in CC_PATTERN.finditer(text):
            candidate = match.group(0)
            if luhn_checksum_valid(candidate):
                sanitized = sanitized.replace(candidate, "[REDACTED_CREDIT_CARD]")
                counts["credit_cards"] += 1

        # 2. SSNs
        for match in SSN_PATTERN.finditer(sanitized):
            sanitized = sanitized.replace(match.group(0), "[REDACTED_SSN]")
            counts["ssn"] += 1

        # 3. Contact info if requested (e.g. for general prompts vs contact tools)
        if redact_contact:
            for match in EMAIL_PATTERN.finditer(sanitized):
                sanitized = sanitized.replace(match.group(0), "[REDACTED_EMAIL]")
                counts["emails"] += 1

            for match in PHONE_PATTERN.finditer(sanitized):
                sanitized = sanitized.replace(match.group(0), "[REDACTED_PHONE]")
                counts["phones"] += 1

        return sanitized, counts

    def has_critical_pii(self, text: str) -> bool:
        """Returns True if financial or government identifiers are present."""
        for match in CC_PATTERN.finditer(text):
            if luhn_checksum_valid(match.group(0)):
                return True
        if SSN_PATTERN.search(text):
            return True
        return False


pii_filter = PIIFilter()
