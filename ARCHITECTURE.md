# System Architecture & Technical Specifications

This document outlines the complete architectural design of the **Incerro Enterprise Website Chatbot** powered by **Groq Cloud**.

---

## 1. High-Level System Architecture

```mermaid
flowchart TD
    User([End User / Website Visitor]) -->|HTTPS / WSS| Web[Web Browser / Embedded Chat Widget]
    Web -->|Reverse Proxy / SSE| Nginx[Nginx Edge Proxy]
    
    subgraph Security Layer
        Nginx --> Middlewares[Security Middlewares\n- Payload Size Cap 32KB\n- Correlation Request ID\n- Strict CSP & Frame Ancestors]
        Middlewares --> Auth[Secure Session Management\n- HMAC Salted IP Hash\n- HttpOnly Lax Cookie]
        Auth --> RateLimit[Sliding Window Rate Limiter\n- Redis / In-Memory Fallback]
        RateLimit --> Guardrails[Deterministic Guardrail Engine\n- Unicode NFKC Normalizer\n- Prompt Injection Detector\n- Jailbreak Detector\n- Secret Scanner\n- Luhn Credit Card / SSN Redactor]
    end

    subgraph RAG & Orchestration
        Guardrails --> RAG[Hybrid Retrieval Engine]
        RAG -->|Semantic Query| Dense[Dense Vector Search\nCosine Normalized]
        RAG -->|Lexical Query| Sparse[Okapi BM25 Search]
        Dense & Sparse --> RRF[Reciprocal Rank Fusion RRF\nReranker]
        RRF --> ContextBuilder[Context Construction\n- Indirect Injection Quarantine\n- Strict Verified-Only System Prompt]
    end

    subgraph AI Gateway
        ContextBuilder --> Gateway[AI Gateway]
        Gateway --> Breaker[Circuit Breaker & Exponential Backoff]
        Breaker --> GroqAdapter[Groq Cloud LPU Adapter\nModel: llama-3.1-8b-instant\nBase: https://api.groq.com/openai/v1]
        Breaker -.->|Fallback if Offline| MockAdapter[Deterministic Offline Simulator]
        GroqAdapter --> CostTracker[Token Budget & Cost Accounting]
    end

    subgraph Response Guardrails & Stream
        GroqAdapter --> OutputFilter[Output Guardrail\n- Secret Leakage Scanner\n- PII Redactor\n- Citation & Grounding Verifier]
        OutputFilter --> Stream[SSE Real-time Token Streaming]
        Stream --> Web
    end
```

---

## 2. Request Lifecycle & Sequence

```mermaid
sequenceDiagram
    autonumber
    actor User as User Browser
    participant API as FastAPI Backend
    participant Guard as Guardrails Engine
    participant Store as Hybrid RAG Store
    participant GW as AI Gateway
    participant Groq as Groq Cloud LPU

    User->>API: POST /api/v1/chat (Message, Stream=True)
    API->>API: Verify Session & Rate Limits (60 req/min)
    API->>Guard: Evaluate Input (NFKC, Injections, Secrets, PII)
    alt Security Violation Triggered
        Guard-->>API: BLOCK / Refusal Decision
        API-->>User: 400 Bad Request (Safe Refusal Message)
    else Input Cleared
        API->>Store: Hybrid Search (Vector Cosine + BM25)
        Store-->>API: Top-K Grounded Chunks (Indirect Injection Screened)
        API->>API: Assemble Context with Structural Isolation
        API->>GW: Dispatch to Primary Model (llama-3.1-8b-instant)
        GW->>Groq: POST /chat/completions (Stream=True)
        loop Token Generation
            Groq-->>GW: Delta Tokens (~30ms TTFT)
            GW-->>API: Token Stream
            API-->>User: SSE data: {"token": "..."}
        end
        API->>API: Verify Citations & Confidence Level
        API-->>User: SSE data: {"done": true, "confidence": "grounded", "sources": [...]}
    end
```

---

## 3. Core Subsystems

### 3.1 Groq Cloud LPU Engine
- **Primary Model**: `llama-3.1-8b-instant`
- **Alternative Large Model**: `llama-3.3-70b-versatile`
- **Latency**: Under 50ms time-to-first-token.
- **Circuit Breaker**: Trips on 3 consecutive failures (HTTP 5xx / timeouts), entering a 30-second half-open recovery phase.
- **Retries**: 3 retries using full-jitter exponential backoff (`sleep = uniform(0, min(8.0, 0.5 * 2^attempt))`).

### 3.2 Hybrid RAG Pipeline
1. **Dense Vector Store**: 1536-dimensional normalized vectors with cosine similarity scoring.
2. **Sparse Lexical Search**: Pure Okapi BM25 implementation tokenizing query terms and document frequencies.
3. **Reciprocal Rank Fusion (RRF)**: Merges rank positions using $RRF(d) = \sum_{m \in M} \frac{1}{60 + r_m(d)}$ to achieve optimal precision.
4. **Indirect Injection Defense**: Quarantines suspicious prompt overrides within retrieved chunks (`[INERT_DOCUMENT_TEXT: ...]`).

### 3.3 Hallucination Defense & Verified Knowledge Enforcement
- The model is instructed with a zero-temperature strict system prompt stating that it **only** possesses knowledge present in the retrieved `<trusted_context>`.
- Any fact outside the context produces an explicit, polite refusal.
- Outputs are scored as:
  - `grounded`: 100% supported by citations.
  - `partially_grounded`: Multiple facts supported, some conversational continuity.
  - `insufficient_evidence`: Context lacked evidence, safe refusal provided.
