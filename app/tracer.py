from contextlib import asynccontextmanager, contextmanager

# Make OpenTelemetry optional; provide no-op fallback
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    _otel_available = True
except Exception:
    trace = None
    _otel_available = False


if _otel_available:
    provider = TracerProvider()
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(__name__)

    @contextmanager
    def start_span(name: str):
        with _tracer.start_as_current_span(name):
            yield

    @asynccontextmanager
    async def start_span_async(name: str):
        with _tracer.start_as_current_span(name):
            yield

    def get_tracer():
        return _tracer
else:
    # no-op implementations
    @contextmanager
    def start_span(name: str):
        yield

    @asynccontextmanager
    async def start_span_async(name: str):
        yield

    def get_tracer():
        class Dummy:
            def start_as_current_span(self, *_a, **_k):
                return contextmanager(lambda: (yield))()
        return Dummy()
