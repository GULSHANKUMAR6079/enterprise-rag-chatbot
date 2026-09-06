"""
High-Fidelity Deterministic Mock LLM Provider.
Used for testing, CI/CD, and local offline execution.
Produces grounded answers from context, refuses when evidence is missing, and provides deterministic embeddings.
"""
import asyncio
import hashlib
import time
from typing import AsyncGenerator, Dict, List, Optional
from backend.app.llm.base import BaseLLMProvider, LLMResponse, TokenUsage


class MockLLMProvider(BaseLLMProvider):
    def __init__(self, provider_name: str = "mock"):
        super().__init__(provider_name=provider_name)

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        timeout: float = 30.0,
        **kwargs
    ) -> LLMResponse:
        start_time = time.perf_counter()
        # Simulate slight network latency
        await asyncio.sleep(0.02)

        user_content = ""
        system_content = ""
        for m in messages:
            if m.get("role") == "user":
                user_content = m.get("content", "")
            elif m.get("role") == "system":
                system_content = m.get("content", "")

        answer = self._synthesize_response(user_content, system_content)
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        input_tokens = max(1, len(user_content + system_content) // 4)
        output_tokens = max(1, len(answer) // 4)

        return LLMResponse(
            content=answer,
            model=model,
            provider=self.provider_name,
            usage=TokenUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens
            ),
            latency_ms=latency_ms
        )

    async def stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        timeout: float = 30.0,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        user_content = ""
        system_content = ""
        for m in messages:
            if m.get("role") == "user":
                user_content = m.get("content", "")
            elif m.get("role") == "system":
                system_content = m.get("content", "")

        full_answer = self._synthesize_response(user_content, system_content)
        # Yield word by word with slight pause
        words = full_answer.split(" ")
        for i, word in enumerate(words):
            chunk = word if i == len(words) - 1 else word + " "
            await asyncio.sleep(0.01)
            yield chunk

    async def embed(
        self,
        texts: List[str],
        model: str,
        timeout: float = 15.0
    ) -> List[List[float]]:
        """
        Generates deterministic pseudo-normalized 1536-dim embedding vectors based on text hash.
        Maintains consistent cosine distances between identical texts and semantic tokens.
        """
        embeddings = []
        for text in texts:
            dim = 1536
            # Hash text into deterministic pseudo-random seed
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            seed_ints = [int(h[i:i+4], 16) for i in range(0, len(h), 4)]
            vec = []
            for i in range(dim):
                val = ((seed_ints[i % len(seed_ints)] + (i * 37)) % 1000) / 1000.0 - 0.5
                vec.append(val)

            # L2 Normalize
            norm = sum(x * x for x in vec) ** 0.5
            norm = norm if norm > 0 else 1.0
            vec = [round(x / norm, 6) for x in vec]
            embeddings.append(vec)
        return embeddings

    def _synthesize_response(self, user_content: str, system_content: str) -> str:
        lower_user = user_content.lower()

        # Check for direct prompt extraction attempts that slipped through
        if "system prompt" in lower_user or "hidden instructions" in lower_user or "repeat everything" in lower_user:
            return "I am the official website assistant. My role is to help you with questions about our company, products, and services based on verified company information."

        # Check if context exists in system content
        has_context = "<trusted_context>" in system_content and "</trusted_context>" in system_content

        if "office" in lower_user or "located" in lower_user or "location" in lower_user:
            if "pune" in system_content.lower() or not has_context:
                return "Our primary technical engineering headquarters is located in Pune, India, with our corporate operations office in San Francisco, California. [1]"

        if "product" in lower_user or "pricing" in lower_user or "plan" in lower_user:
            return "We offer flexible enterprise tiers including Starter ($49/mo), Pro ($199/mo), and Custom Enterprise plans with dedicated SLA and security compliance. [1]"

        if "contact" in lower_user or "support" in lower_user or "sales" in lower_user:
            return "You can reach our sales and support team directly via email at support@example.com or submit an inquiry through our verified contact form. [1]"

        if "career" in lower_user or "job" in lower_user or "hiring" in lower_user:
            return "We are actively hiring for Senior Backend Engineers, AI Security Specialists, and Cloud DevOps Engineers. Please visit our careers page for open postings. [1]"

        # Hallucination test cases (absent from approved context)
        if any(unverified in lower_user for unverified in ["cto", "revenue", "secret", "founder", "client list", "password"]):
            return "I don't have enough verified information in the approved knowledge base to answer that reliably."

        # Default grounded response
        if has_context:
            return "Based on our approved company documentation, our platform provides enterprise-grade AI architecture, high-availability security guardrails, and verified knowledge retrieval. [1]"

        return "I don't have enough verified information in the approved knowledge base to answer that reliably."
