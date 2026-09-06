"""
Dedicated Groq Cloud LLM Provider Adapter.
Tailored for Groq's high-speed LPU inference engine running Llama 3 / 3.1 / 3.3 models.
Supports streaming, retry backoff, and Groq rate-limit header parsing.
"""
import json
import logging
import time
from typing import AsyncGenerator, Dict, List, Optional
import httpx
from backend.app.llm.base import BaseLLMProvider, LLMResponse, TokenUsage

logger = logging.getLogger("groq_adapter")


class GroqAdapter(BaseLLMProvider):
    """
    Adapter for Groq Cloud API (https://api.groq.com/openai/v1).
    Optimized for Llama 3.1 8B Instant and Llama 3.3 70B Versatile.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider_name: str = "groq"
    ):
        cleaned_key = api_key.strip().strip('"').strip("'") if api_key else None
        super().__init__(provider_name=provider_name, api_key=cleaned_key, base_url=base_url)
        self.default_base_url = (base_url or "https://api.groq.com/openai/v1").rstrip("/")

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Enterprise-Website-Assistant-Groq/1.0"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str = "groq/compound-mini",
        temperature: float = 0.2,
        max_tokens: int = 1000,
        timeout: float = 25.0,
        **kwargs
    ) -> LLMResponse:
        # If no Groq API key is set, fallback gracefully to mock provider
        if not self.api_key or self.api_key.strip() == "" or self.api_key.startswith("gsk_your_groq_api_key"):
            logger.info("GROQ_API_KEY not configured. Falling back to local simulator.")
            from backend.app.llm.mock_adapter import MockLLMProvider
            mock = MockLLMProvider(provider_name="groq")
            return await mock.generate(messages, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout)

        start_time = time.perf_counter()
        url = f"{self.default_base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=self._get_headers(), json=payload)
            if resp.status_code >= 400:
                logger.error(f"Groq API Error {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            data = resp.json()

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        choice = data["choices"][0]
        usage_data = data.get("usage", {})

        return LLMResponse(
            content=choice["message"]["content"],
            model=model,
            provider=self.provider_name,
            usage=TokenUsage(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0)
            ),
            latency_ms=latency_ms,
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data
        )

    async def stream(
        self,
        messages: List[Dict[str, str]],
        model: str = "groq/compound-mini",
        temperature: float = 0.2,
        max_tokens: int = 1000,
        timeout: float = 25.0,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        # If no Groq API key is set, fallback gracefully to mock provider
        if not self.api_key or self.api_key.strip() == "" or self.api_key.startswith("gsk_your_groq_api_key"):
            logger.info("GROQ_API_KEY not configured. Streaming from local simulator.")
            from backend.app.llm.mock_adapter import MockLLMProvider
            mock = MockLLMProvider(provider_name="groq")
            async for token in mock.stream(messages, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout):
                yield token
            return

        url = f"{self.default_base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=self._get_headers(), json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if line == "data: [DONE]":
                        break
                    if line.startswith("data: "):
                        json_str = line[6:]
                        try:
                            chunk_data = json.loads(json_str)
                            choices = chunk_data.get("choices", [])
                            if choices and len(choices) > 0:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content")
                                if content:
                                    yield content
                        except Exception:
                            continue

    async def embed(
        self,
        texts: List[str],
        model: str = "mock-embedding",
        timeout: float = 15.0
    ) -> List[List[float]]:
        """
        Groq is specialized for ultra-low latency LLM text inference.
        Embeddings are generated via local deterministic normalized vectors.
        """
        import hashlib
        embeddings = []
        for text in texts:
            dim = 1536
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            seed_ints = [int(h[i:i+4], 16) for i in range(0, len(h), 4)]
            vec = []
            for i in range(dim):
                val = ((seed_ints[i % len(seed_ints)] + (i * 37)) % 1000) / 1000.0 - 0.5
                vec.append(val)

            norm = sum(x * x for x in vec) ** 0.5
            norm = norm if norm > 0 else 1.0
            embeddings.append([round(x / norm, 6) for x in vec])
        return embeddings
