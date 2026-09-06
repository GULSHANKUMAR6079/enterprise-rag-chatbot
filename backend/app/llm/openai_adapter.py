"""
OpenAI & OpenAI-Compatible LLM Provider Adapter.
Supports OpenAI, Groq, Ollama, LocalAI, vLLM, and OpenRouter via standard endpoints.
"""
import json
import time
from typing import AsyncGenerator, Dict, List, Optional
import httpx
from backend.app.llm.base import BaseLLMProvider, LLMResponse, TokenUsage


class OpenAIAdapter(BaseLLMProvider):
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider_name: str = "openai"
    ):
        super().__init__(provider_name=provider_name, api_key=api_key, base_url=base_url)
        self.default_base_url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

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
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        timeout: float = 30.0,
        **kwargs
    ) -> AsyncGenerator[str, None]:
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
                            delta = chunk_data["choices"][0].get("delta", {})
                            content = delta.get("content")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            continue

    async def embed(
        self,
        texts: List[str],
        model: str = "text-embedding-3-small",
        timeout: float = 15.0
    ) -> List[List[float]]:
        url = f"{self.default_base_url}/embeddings"
        payload = {
            "model": model,
            "input": texts
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(url, headers=self._get_headers(), json=payload)
            resp.raise_for_status()
            data = resp.json()

        # Sort embeddings by index to preserve order
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]
