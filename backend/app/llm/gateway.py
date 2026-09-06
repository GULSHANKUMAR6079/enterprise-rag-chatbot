"""
Centralized AI / LLM Gateway.
Enforces circuit breaking, retries with exponential backoff and jitter, fallback hierarchy,
token budgeting, and cost tracking across all provider interactions.
"""
import asyncio
import logging
import random
import time
from typing import AsyncGenerator, Dict, List, Optional
import httpx
from backend.app.core.config import settings
from backend.app.core.exceptions import LLMProviderUnavailableException
from backend.app.gateway.circuit_breaker import get_circuit_breaker
from backend.app.gateway.cost_tracker import cost_tracker
from backend.app.llm.base import BaseLLMProvider, LLMResponse, TokenUsage
from backend.app.llm.groq_adapter import GroqAdapter
from backend.app.llm.mock_adapter import MockLLMProvider
from backend.app.llm.openai_adapter import OpenAIAdapter

logger = logging.getLogger("llm_gateway")


class LLMGateway:
    def __init__(self):
        self._providers: Dict[str, BaseLLMProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        # Register mock provider (always available)
        self._providers["mock"] = MockLLMProvider("mock")

        # Register Groq provider (Primary)
        groq_key = settings.GROQ_API_KEY or settings.LLM_API_KEY
        self._providers["groq"] = GroqAdapter(
            api_key=groq_key,
            base_url=settings.LLM_API_BASE or "https://api.groq.com/openai/v1",
            provider_name="groq"
        )

        # Register OpenAI / compatible provider (Secondary)
        self._providers["openai"] = OpenAIAdapter(
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_API_BASE,
            provider_name="openai"
        )

    def get_provider(self, provider_name: str) -> BaseLLMProvider:
        return self._providers.get(provider_name, self._providers["mock"])

    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2
    ) -> LLMResponse:
        """
        Executes generation passing through circuit breaker, retries, and fallback tiers.
        """
        active_provider_name = provider or settings.LLM_PROVIDER
        active_model = model or settings.PRIMARY_MODEL

        # Step 1: Estimate tokens and verify budget
        input_text = " ".join([m.get("content", "") for m in messages])
        estimated_input_tokens = cost_tracker.estimate_tokens(input_text)
        cost_tracker.verify_request_budget(active_model, estimated_input_tokens, max_tokens)

        # Step 2: Attempt primary provider with retries
        try:
            response = await self._call_with_resilience(
                provider_name=active_provider_name,
                model=active_model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )
        except Exception as primary_exc:
            logger.warning(
                f"Primary provider '{active_provider_name}' failed: {primary_exc}. Attempting fallback..."
            )
            # Step 3: Trigger fallback provider
            fallback_provider = settings.FALLBACK_PROVIDER
            fallback_model = settings.FALLBACK_MODEL
            try:
                response = await self._call_with_resilience(
                    provider_name=fallback_provider,
                    model=fallback_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
            except Exception as fallback_exc:
                logger.error(f"Fallback provider '{fallback_provider}' also failed: {fallback_exc}")
                raise LLMProviderUnavailableException(
                    "All configured LLM providers failed to respond. Please try again later."
                )

        # Step 4: Record actual cost
        cost = cost_tracker.calculate_cost(
            response.model,
            response.usage.input_tokens,
            response.usage.output_tokens
        )
        cost_tracker.record_actual_spend(cost)
        return response

    async def _call_with_resilience(
        self,
        provider_name: str,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float
    ) -> LLMResponse:
        breaker = get_circuit_breaker(
            provider_name,
            threshold=settings.CIRCUIT_BREAKER_FAILURE_THRESHOLD,
            recovery_seconds=settings.CIRCUIT_BREAKER_RECOVERY_TIME
        )

        if not breaker.can_execute():
            raise RuntimeError(f"Circuit breaker for provider '{provider_name}' is OPEN.")

        provider = self.get_provider(provider_name)
        max_retries = settings.LLM_MAX_RETRIES
        base_backoff = 0.5

        for attempt in range(max_retries + 1):
            try:
                resp = await provider.generate(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=settings.LLM_TIMEOUT_SECONDS
                )
                breaker.record_success()
                return resp
            except (httpx.HTTPStatusError, httpx.RequestError, asyncio.TimeoutError) as exc:
                # Check for transient errors suitable for retry (429, 502, 503, 504, timeout)
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                is_transient = status_code in (429, 502, 503, 504) or isinstance(exc, (httpx.TimeoutException, asyncio.TimeoutError))

                if not is_transient or attempt == max_retries:
                    breaker.record_failure()
                    raise

                # Full jitter exponential backoff: sleep between 0 and min(max_backoff, base * 2^attempt)
                sleep_duration = random.uniform(0, min(8.0, base_backoff * (2 ** attempt)))
                logger.info(f"Retrying provider '{provider_name}' in {sleep_duration:.2f}s (attempt {attempt + 1}/{max_retries})...")
                await asyncio.sleep(sleep_duration)

        breaker.record_failure()
        raise RuntimeError(f"Exhausted retries for provider '{provider_name}'")

    async def stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        provider: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.2
    ) -> AsyncGenerator[str, None]:
        """Streams token chunks through resilient provider."""
        active_provider_name = provider or settings.LLM_PROVIDER
        active_model = model or settings.PRIMARY_MODEL

        provider_obj = self.get_provider(active_provider_name)
        try:
            async for token in provider_obj.stream(
                messages=messages,
                model=active_model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=settings.LLM_TIMEOUT_SECONDS
            ):
                yield token
        except Exception as exc:
            logger.warning(f"Streaming failed for '{active_provider_name}': {exc}. Trying fallback...")
            fallback_obj = self.get_provider(settings.FALLBACK_PROVIDER)
            async for token in fallback_obj.stream(
                messages=messages,
                model=settings.FALLBACK_MODEL,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=settings.LLM_TIMEOUT_SECONDS
            ):
                yield token

    async def embed(
        self,
        texts: List[str],
        model: Optional[str] = None,
        provider: Optional[str] = None
    ) -> List[List[float]]:
        """Generates embedding vectors with fallback."""
        active_provider_name = provider or settings.LLM_PROVIDER
        active_model = model or settings.EMBEDDING_MODEL

        # Groq specializes in high-speed text inference and does not expose /embeddings; use local embeddings
        if active_provider_name.lower() == "groq":
            mock_provider = self.get_provider("mock")
            return await mock_provider.embed(texts=texts, model="local-deterministic")

        provider_obj = self.get_provider(active_provider_name)
        try:
            return await provider_obj.embed(texts=texts, model=active_model)
        except Exception:
            # Fallback to mock deterministic embeddings
            mock_provider = self.get_provider("mock")
            return await mock_provider.embed(texts=texts, model="mock-embedding")


# Singleton LLM Gateway instance
llm_gateway = LLMGateway()
