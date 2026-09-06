"""
Base LLM Provider Interface.
Defines standard contracts for text generation, token streaming, and vector embedding.
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional, Any
from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    content: str
    model: str
    provider: str
    usage: TokenUsage
    latency_ms: float
    finish_reason: Optional[str] = "stop"
    raw_response: Optional[Dict[str, Any]] = None


class BaseLLMProvider(ABC):
    """Abstract interface for all model provider adapters."""
    def __init__(self, provider_name: str, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self.provider_name = provider_name
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        timeout: float = 30.0,
        **kwargs
    ) -> LLMResponse:
        """Executes a non-streaming completion call."""
        pass

    @abstractmethod
    async def stream(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        timeout: float = 30.0,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Yields text token chunks asynchronously."""
        pass

    @abstractmethod
    async def embed(
        self,
        texts: List[str],
        model: str,
        timeout: float = 15.0
    ) -> List[List[float]]:
        """Generates embedding vectors for a list of input texts."""
        pass
