"""Prometheus instrumentation.

Labels use the route template (e.g. ``/api/links/{code}``) rather than the raw
path, so the number of time series stays bounded no matter how many links exist.
"""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests handled.",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds.",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)
LINKS_CREATED = Counter("shortener_links_created_total", "Short links created.")
REDIRECTS = Counter("shortener_redirects_total", "Redirects served.")

EXCLUDED_ROUTES = {"/metrics"}


def _route_template(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", "unmatched")


def instrument(app: FastAPI) -> None:
    @app.middleware("http")
    async def record_metrics(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            route = _route_template(request)
            if route not in EXCLUDED_ROUTES:
                HTTP_LATENCY.labels(request.method, route).observe(time.perf_counter() - start)
                HTTP_REQUESTS.labels(request.method, route, str(status)).inc()

    @app.get("/metrics", tags=["ops"], include_in_schema=False)
    def metrics() -> Response:
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
