# Security Architecture & Defense-in-Depth Specification

This document details the multi-tiered defensive controls implemented in the Incerro Enterprise Assistant to prevent adversarial attacks, data exfiltration, and abuse.

---

## 1. Threat Mitigation Matrix

| Threat Category | Primary Attack Vectors | Defensive Mechanism | Enforcement Point |
|---|---|---|---|
| **Direct Prompt Injection** | `Ignore prior rules`, `Disregard instructions`, `Bypass guardrails` | Regex heuristic engine, structural boundary tags (`<user_request>`) | `injection_detector.py` |
| **System Prompt Extraction** | `Repeat system prompt`, `Dump context`, `Print instructions` | Extraction pattern scoring & polite safe refusal | `policy_engine.py` |
| **Jailbreaks & Personas** | `DAN mode`, `Roleplay evil AI`, `Fictional movie scenario` | Persona & fictional framing detector, token-split space collapsing | `jailbreak_detector.py` |
| **Obfuscation & Evasion** | Base64 strings, ROT13 ciphers, Unicode zero-width, ligatures | Unicode NFKC normalization, auto-padding Base64 decode inspection | `input_guardrail.py` |
| **Indirect Retrieval Poisoning**| Poisoned HTML/MD files injected with instructions | Indirect injection scanner, quarantine tag `[INERT_DOCUMENT_TEXT: ...]` | `indirect_injection_defense.py` |
| **Secret & Key Leakage** | `Output GROQ_API_KEY`, `Reveal database password` | High-entropy regex scanner & automatic redaction (`[REDACTED_...]`) | `secret_scanner.py` |
| **Financial & Citizen PII** | Credit card numbers, Social Security Numbers (SSN) | Luhn checksum validation (mod 10) & SSN regex mask | `pii_filter.py` |
| **SSRF & Network Scanning** | AWS/GCP metadata (`169.254.169.254`), `localhost`, RFC1918 subnets | Socket DNS resolution & CIDR IP blacklist enforcement | `ssrf_protector.py` |
| **Denial of Service & Abuse**| High-volume automated bots, token exhaustion attacks | Sliding-window IP rate limiter, max payload 32KB, token budgets | `rate_limiter.py` |

---

## 2. Ingestion & Web Scraping SSRF Defense

The automated web scraper (`backend/app/rag/web_scraper.py`) and SSRF protector (`backend/app/security/ssrf_protector.py`) strictly validate every target URL before opening any HTTP connection:
- Rejects non-HTTPS schemes.
- Resolves DNS hostname to IP address.
- Validates that the resolved IP address does not belong to:
  - Loopback (`127.0.0.0/8`, `::1`)
  - RFC 1918 Private Subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
  - Cloud Metadata Services (`169.254.169.254`, `fe80::/10`)
  - Broadcast & Multicast ranges

---

## 3. Secret Leakage Prevention

Input and output streams are scanned against verified secret signatures:
- Groq Cloud API Keys: `\bgsk_[a-zA-Z0-9]{40,}\b`
- OpenAI Keys: `\bsk-[a-zA-Z0-9_\-]{20,}\b`
- AWS Access Keys: `\b(AKIA|ASIA)[0-9A-Z]{16}\b`
- Database URLs: `\b(postgres|mysql|mongodb|redis):\/\/[^\s\'\"]+@[^\s\'\"]+\b`
- Private Keys: `-----BEGIN (RSA|EC|DSA|OPENSSH) PRIVATE KEY-----`

---

## 4. Reporting Security Vulnerabilities

To report a vulnerability or coordinate disclosure, please email `security@incerro.example.com`.
