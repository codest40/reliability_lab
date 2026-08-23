from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
)


# ============================================================
# CUSTOM REGISTRY
# ============================================================
#
# We deliberately use our own registry so /metrics exposes
# ONLY the metrics defined in this project.
#

REGISTRY = CollectorRegistry()


# ============================================================
# SERVICE / HTTP
# ============================================================

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests received by Service A",
    ["method", "endpoint"],
    registry=REGISTRY,
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    registry=REGISTRY,
)

http_requests_errors_total = Counter(
    "http_requests_errors_total",
    "Total HTTP requests that resulted in an error",
    ["method", "endpoint"],
    registry=REGISTRY,
)

http_responses_total = Counter(
    "http_responses_total",
    "Total HTTP responses returned by Service A",
    ["method", "endpoint", "status"],
    registry=REGISTRY,
)

http_requests_in_progress = Gauge(
    "http_requests_in_progress",
    "HTTP requests currently being handled by Service A",
    ["method", "endpoint"],
    registry=REGISTRY,
)


# ============================================================
# DEPENDENCY
# ============================================================

dependency_requests_total = Counter(
    "dependency_requests_total",
    "Total requests made from Service A to Service B",
    ["dependency", "operation"],
    registry=REGISTRY,
)

dependency_request_duration_seconds = Histogram(
    "dependency_request_duration_seconds",
    "Time spent waiting for dependency responses",
    ["dependency", "operation"],
    registry=REGISTRY,
)

dependency_errors_total = Counter(
    "dependency_errors_total",
    "Total dependency errors",
    ["dependency", "operation"],
    registry=REGISTRY,
)

dependency_timeouts_total = Counter(
    "dependency_timeouts_total",
    "Total dependency request timeouts",
    ["dependency", "operation"],
    registry=REGISTRY,
)

dependency_connections_errors_total = Counter(
    "dependency_connections_errors_total",
    "Total dependency connection errors",
    ["dependency", "operation"],
    registry=REGISTRY,
)


# ============================================================
# WORKERS
# ============================================================

workers_total = Gauge(
    "workers_total",
    "Total workers assigned to a bulkhead",
    ["bulkhead"],
    registry=REGISTRY,
)

workers_busy = Gauge(
    "workers_busy",
    "Workers currently processing work",
    ["bulkhead"],
    registry=REGISTRY,
)

workers_available = Gauge(
    "workers_available",
    "Workers currently available",
    ["bulkhead"],
    registry=REGISTRY,
)


# ============================================================
# QUEUES
# ============================================================

queue_size = Gauge(
    "queue_size",
    "Current number of requests waiting in a queue",
    ["queue"],
    registry=REGISTRY,
)

queue_capacity = Gauge(
    "queue_capacity",
    "Maximum capacity of a queue",
    ["queue"],
    registry=REGISTRY,
)

queue_utilization = Gauge(
    "queue_utilization",
    "Queue utilization ratio",
    ["queue"],
    registry=REGISTRY,
)

queue_rejections_total = Counter(
    "queue_rejections_total",
    "Requests rejected because a queue was full",
    ["queue"],
    registry=REGISTRY,
)

queue_wait_duration_seconds = Histogram(
    "queue_wait_duration_seconds",
    "Time requests spend waiting in a queue",
    ["queue"],
    registry=REGISTRY,
)


# ============================================================
# RETRIES
# ============================================================

retries_total = Counter(
    "retries_total",
    "Total dependency retry operations",
    ["dependency", "operation"],
    registry=REGISTRY,
)

retry_attempts_total = Counter(
    "retry_attempts_total",
    "Total dependency attempts including the first attempt",
    ["dependency", "operation"],
    registry=REGISTRY,
)

retry_exhausted_total = Counter(
    "retry_exhausted_total",
    "Total dependency requests that exhausted all retries",
    ["dependency", "operation"],
    registry=REGISTRY,
)

retry_delay_seconds = Histogram(
    "retry_delay_seconds",
    "Time spent sleeping before a retry",
    ["dependency", "operation"],
    registry=REGISTRY,
)


# ============================================================
# CIRCUIT BREAKER
# ============================================================

circuit_breaker_state = Gauge(
    "circuit_breaker_state",
    """
    Circuit breaker state:
    0 = CLOSED
    1 = OPEN
    2 = HALF_OPEN
    """,
    ["dependency"],
    registry=REGISTRY,
)

circuit_breaker_transitions_total = Counter(
    "circuit_breaker_transitions_total",
    "Total circuit breaker state transitions",
    ["dependency", "from_state", "to_state"],
    registry=REGISTRY,
)

circuit_breaker_rejections_total = Counter(
    "circuit_breaker_rejections_total",
    "Requests rejected by the circuit breaker",
    ["dependency"],
    registry=REGISTRY,
)

circuit_breaker_open_total = Counter(
    "circuit_breaker_open_total",
    "Total times the circuit breaker opened",
    ["dependency"],
    registry=REGISTRY,
)

circuit_breaker_probe_total = Counter(
    "circuit_breaker_probe_total",
    "Total circuit breaker probe attempts",
    ["dependency"],
    registry=REGISTRY,
)

circuit_breaker_probe_success_total = Counter(
    "circuit_breaker_probe_success_total",
    "Successful circuit breaker probes",
    ["dependency"],
    registry=REGISTRY,
)

circuit_breaker_probe_failure_total = Counter(
    "circuit_breaker_probe_failure_total",
    "Failed circuit breaker probes",
    ["dependency"],
    registry=REGISTRY,
)


# ============================================================
# PROBES
# ============================================================

dependency_probes_total = Counter(
    "dependency_probes_total",
    "Total dependency readiness probes",
    ["dependency"],
    registry=REGISTRY,
)

dependency_probe_success_total = Counter(
    "dependency_probe_success_total",
    "Successful dependency readiness probes",
    ["dependency"],
    registry=REGISTRY,
)

dependency_probe_failure_total = Counter(
    "dependency_probe_failure_total",
    "Failed dependency readiness probes",
    ["dependency"],
    registry=REGISTRY,
)

dependency_probe_duration_seconds = Histogram(
    "dependency_probe_duration_seconds",
    "Dependency readiness probe duration",
    ["dependency"],
    registry=REGISTRY,
)


# ============================================================
# BULKHEAD
# ============================================================

bulkhead_capacity = Gauge(
    "bulkhead_capacity",
    "Maximum concurrent worker capacity of a bulkhead",
    ["bulkhead"],
    registry=REGISTRY,
)

bulkhead_active_requests = Gauge(
    "bulkhead_active_requests",
    "Requests currently being processed by a bulkhead",
    ["bulkhead"],
    registry=REGISTRY,
)

bulkhead_rejections_total = Counter(
    "bulkhead_rejections_total",
    "Requests rejected because a bulkhead was exhausted",
    ["bulkhead"],
    registry=REGISTRY,
)


# ============================================================
# DEPENDENCY HEALTH
# ============================================================

dependency_health = Gauge(
    "dependency_health",
    "Dependency health: 1 healthy, 0 unhealthy",
    ["dependency"],
    registry=REGISTRY,
)

dependency_under_pressure = Gauge(
    "dependency_under_pressure",
    "Dependency pressure: 1 under pressure, 0 normal",
    ["dependency"],
    registry=REGISTRY,
)


# ============================================================
# APPLICATION
# ============================================================

notes_processed_total = Counter(
    "notes_processed_total",
    "Total note requests processed",
    registry=REGISTRY,
)

notes_saved_total = Counter(
    "notes_saved_total",
    "Total valid notes successfully saved",
    registry=REGISTRY,
)

notes_invalid_total = Counter(
    "notes_invalid_total",
    "Total invalid notes rejected",
    registry=REGISTRY,
)
