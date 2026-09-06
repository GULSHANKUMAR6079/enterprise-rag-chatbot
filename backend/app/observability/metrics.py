"""
Prometheus Metrics Instrumentation.
Tracks request rates, latency distributions, token costs, rate-limit hits, and security blocks.
"""
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

# Counters
REQUESTS_TOTAL = Counter(
    "chatbot_requests_total",
    "Total HTTP chat requests received",
    ["route", "method"]
)

REQUESTS_FAILED = Counter(
    "chatbot_requests_failed_total",
    "Total failed HTTP requests",
    ["route", "status_code"]
)

SECURITY_EVENTS_TOTAL = Counter(
    "chatbot_security_events_total",
    "Total security policy violations detected",
    ["event_type", "severity"]
)

RATE_LIMIT_HITS = Counter(
    "chatbot_rate_limit_hits_total",
    "Total requests throttled by rate limiter"
)

TOKENS_CONSUMED = Counter(
    "chatbot_tokens_consumed_total",
    "Total tokens consumed",
    ["type", "model"]  # type: input | output
)

ESTIMATED_COST_USD = Counter(
    "chatbot_estimated_cost_usd_total",
    "Total estimated LLM spend in USD"
)

FALLBACK_USAGE_TOTAL = Counter(
    "chatbot_fallback_usage_total",
    "Total times secondary fallback model was invoked"
)

# Histograms
REQUEST_LATENCY = Histogram(
    "chatbot_request_latency_seconds",
    "Total end-to-end request duration",
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
)

LLM_LATENCY = Histogram(
    "chatbot_llm_latency_seconds",
    "Model inference latency",
    ["provider", "model"],
    buckets=[0.2, 0.5, 1.0, 2.0, 4.0, 8.0, 15.0]
)

RETRIEVAL_LATENCY = Histogram(
    "chatbot_retrieval_latency_seconds",
    "Vector and BM25 retrieval latency",
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0]
)


def get_metrics_snapshot() -> bytes:
    """Generates Prometheus metrics output for /metrics endpoint."""
    return generate_latest()
