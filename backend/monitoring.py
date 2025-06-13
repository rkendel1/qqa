import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from prometheus_client import start_http_server, Counter, Histogram
from fastapi import FastAPI
from prometheus_client.openmetrics.exposition import generate_latest
from starlette.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize tracer
trace.set_tracer_provider(TracerProvider())
tracer = trace.get_tracer(__name__)

# Add OTLP exporter
# otlp_exporter = OTLPSpanExporter(
#     endpoint="localhost:4317",
#     insecure=True
# )
# span_processor = BatchSpanProcessor(otlp_exporter)
# trace.get_tracer_provider().add_span_processor(span_processor)

# Prometheus metrics
class PrometheusMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.requests_total = Counter(
            'http_requests_total',
            'Total number of HTTP requests',
            ['method', 'endpoint', 'status']
        )
        self.request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint']
        )

    async def dispatch(self, request, call_next):
        start_time = time.time()
        
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as e:
            status_code = 500
            raise e
        finally:
            duration = time.time() - start_time
            self.requests_total.labels(
                method=request.method,
                endpoint=request.url.path,
                status=status_code
            ).inc()
            self.request_duration.labels(
                method=request.method,
                endpoint=request.url.path
            ).observe(duration)
        
        return response

def setup_monitoring(app: FastAPI):
    """Setup monitoring for the FastAPI application"""
    # Add Prometheus middleware
    app.add_middleware(PrometheusMiddleware)
    
    # Add metrics endpoint
    @app.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type="text/plain")
    
    # Start Prometheus metrics server with port-in-use handling
    try:
        start_http_server(8050)
        logger.info("Prometheus metrics HTTP server started on port 8050")
    except OSError as e:
        if e.errno == 48:  # Address already in use
            logger.warning("Port 8050 already in use, skipping Prometheus HTTP server start")
        else:
            raise

def get_tracer():
    """Get the tracer instance"""
    return tracer