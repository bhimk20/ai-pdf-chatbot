from __future__ import annotations

import json
import logging
import time
from typing import Any

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.responses import Response


REQUEST_COUNT = Counter(
    "app_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"],
)
REQUEST_LATENCY = Histogram(
    "app_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)
INGEST_COUNT = Counter(
    "app_ingest_requests_total",
    "Total ingest requests",
    ["status"],
)
INGEST_CHUNKS = Counter(
    "app_ingest_document_chunks_total",
    "Total document chunks prepared for ingest",
)
CHAT_COUNT = Counter(
    "app_chat_requests_total",
    "Total chat requests",
    ["route", "status"],
)
ACTIVE_CHAT_STREAMS = Gauge(
    "app_active_chat_streams",
    "Number of active chat streams",
)
EXTERNAL_CALL_COUNT = Counter(
    "app_external_calls_total",
    "External service calls",
    ["service", "operation", "status"],
)
EXTERNAL_CALL_LATENCY = Histogram(
    "app_external_call_duration_seconds",
    "Latency for external service calls in seconds",
    ["service", "operation"],
)


def configure_logging() -> None:
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(level=logging.INFO, format="%(message)s")
    else:
        root_logger.setLevel(logging.INFO)


def log_event(event: str, **fields: Any) -> None:
    payload = {
        "event": event,
        **fields,
    }
    logging.getLogger("app").info(json.dumps(payload, default=str))


def observe_external_call(service: str, operation: str, started_at: float, success: bool) -> None:
    status = "success" if success else "error"
    EXTERNAL_CALL_COUNT.labels(service=service, operation=operation, status=status).inc()
    EXTERNAL_CALL_LATENCY.labels(service=service, operation=operation).observe(
        time.perf_counter() - started_at
    )


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
