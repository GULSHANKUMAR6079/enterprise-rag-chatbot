"""
Distributed Tracing with OpenTelemetry.
Creates spans across all architectural phases: guardrails, retrieval, reranking, and model generation.
Provides in-memory trace inspection, real-time console logging, and optional OTLP/Jaeger export.
"""
from collections import deque
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, List, Optional, Sequence

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import StatusCode

from backend.app.core.config import settings
from backend.app.observability.logger import app_logger


class InMemorySpanBuffer(SpanExporter):
    """
    Thread-safe in-memory ring buffer storing the latest spans.
    Allows inspection via /system/traces endpoint without external APM services.
    """
    def __init__(self, max_spans: int = 200):
        self._spans: deque = deque(maxlen=max_spans)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            trace_id = format(span.context.trace_id, "032x")
            span_id = format(span.context.span_id, "016x")
            parent_id = format(span.parent.span_id, "016x") if span.parent else None
            duration_ms = (
                round((span.end_time - span.start_time) / 1_000_000, 2)
                if span.end_time and span.start_time
                else 0.0
            )

            status_name = (
                span.status.status_code.name
                if hasattr(span.status.status_code, "name")
                else str(span.status.status_code)
            )

            span_record = {
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_span_id": parent_id,
                "name": span.name,
                "status": status_name,
                "duration_ms": duration_ms,
                "attributes": dict(span.attributes) if span.attributes else {},
                "start_time_ns": span.start_time,
                "end_time_ns": span.end_time,
            }
            self._spans.append(span_record)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True

    def get_traces_summary(self, limit: int = 50, trace_id: Optional[str] = None) -> Dict:
        """Group recorded spans by trace_id for easy visualization and debugging."""
        spans = list(self._spans)
        if trace_id:
            spans = [s for s in spans if s["trace_id"] == trace_id]

        grouped: Dict[str, List] = {}
        for s in reversed(spans):
            t_id = s["trace_id"]
            if t_id not in grouped:
                if len(grouped) >= limit:
                    break
                grouped[t_id] = []
            grouped[t_id].append(s)

        traces_list = []
        for t_id, t_spans in grouped.items():
            total_duration = (
                sum(s["duration_ms"] for s in t_spans if not s["parent_span_id"])
                or sum(s["duration_ms"] for s in t_spans)
            )
            traces_list.append({
                "trace_id": t_id,
                "span_count": len(t_spans),
                "total_duration_ms": round(total_duration, 2),
                "spans": list(reversed(t_spans))
            })

        return {
            "total_recorded_spans": len(self._spans),
            "returned_traces": len(traces_list),
            "traces": traces_list
        }


class ConsoleSpanSummaryExporter(SpanExporter):
    """Logs human-readable trace summaries to stdout whenever a span completes."""
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            trace_id_short = format(span.context.trace_id, "032x")[:8]
            duration_ms = (
                round((span.end_time - span.start_time) / 1_000_000, 2)
                if span.end_time and span.start_time
                else 0.0
            )
            status_name = (
                span.status.status_code.name
                if hasattr(span.status.status_code, "name")
                else str(span.status.status_code)
            )
            app_logger.info(
                f"[OPENTELEMETRY SPAN] name='{span.name}' | duration={duration_ms}ms | status={status_name} | trace_id={trace_id_short}..."
            )
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


# Global in-memory trace buffer
trace_buffer = InMemorySpanBuffer(max_spans=200)
console_exporter = ConsoleSpanSummaryExporter()

# Initialize OpenTelemetry TracerProvider with service attributes
resource = Resource.create({
    "service.name": settings.APP_NAME,
    "service.version": settings.APP_VERSION,
    "deployment.environment": settings.APP_ENV
})

provider = TracerProvider(resource=resource)

# 1. Attach in-memory ring buffer (always active for API inspection)
provider.add_span_processor(SimpleSpanProcessor(trace_buffer))

# 2. Attach console span logger (active in debug or standard environment)
provider.add_span_processor(SimpleSpanProcessor(console_exporter))

# 3. Optional remote OTLP Exporter (Jaeger, Logfire, SigNoz, Datadog)
if settings.OTEL_EXPORTER_OTLP_ENDPOINT:
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            timeout=2,
            insecure=True
        )
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        app_logger.info(f"OpenTelemetry OTLP Exporter configured for {settings.OTEL_EXPORTER_OTLP_ENDPOINT}")
    except Exception as exc:
        app_logger.warning(f"Failed to initialize OTLP exporter: {exc}")

trace.set_tracer_provider(provider)
tracer = trace.get_tracer("enterprise_chatbot", settings.APP_VERSION)


@asynccontextmanager
async def trace_span(span_name: str, attributes: Optional[dict] = None) -> AsyncGenerator[trace.Span, None]:
    """Context manager for tracing async code blocks."""
    with tracer.start_as_current_span(span_name) as span:
        if attributes:
            for k, v in attributes.items():
                if v is not None:
                    span.set_attribute(k, str(v) if not isinstance(v, (int, float, bool)) else v)
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
            raise
