# SRE Reliability Lab — Observability

## 1. Purpose

Observability in this project is designed around one question:

> **When the system is under pressure, can I explain what is happening from the metrics alone?**

The metrics are therefore not generic infrastructure metrics.

They are tied directly to the reliability mechanisms implemented in the lab:

- request handling
- dependency behavior
- worker utilization
- queue pressure
- retries
- circuit-breaker decisions
- recovery probes
- bulkhead isolation
- application outcomes

---

## 2. Service Metrics

These metrics describe what clients are experiencing at the HTTP layer.

### `http_requests_total`

Counts incoming HTTP requests.

Labels:

    method
    endpoint

Useful for understanding demand.

Example:

    POST /notes
    GET /all_notes

---

### `http_request_duration_seconds`

Measures total HTTP request duration.

This includes time spent:

    request
       ↓
    queue waiting
       ↓
    worker processing
       ↓
    dependency interaction
       ↓
    response

This is the primary metric for understanding end-to-end latency from Service A's perspective.

---

### `http_requests_errors_total`

Counts HTTP requests that result in an error.

This allows request failure rate to be calculated rather than relying on individual logs.

---

### `http_responses_total`

Counts responses by HTTP status.

Labels:

    method
    endpoint
    status

This makes it possible to distinguish:

    2xx → success
    4xx → client/request problems
    5xx → service/dependency/capacity problems

---

### `http_requests_in_progress`

Shows the number of HTTP requests currently being handled.

This helps identify whether concurrent demand is building faster than the service can complete requests.

---

# 3. Dependency Metrics

These metrics describe the behavior of Service B from Service A's perspective.

### `dependency_requests_total`

Counts requests made from A to B.

This is particularly important when retries are enabled because:

    client requests

and:

    dependency requests

are no longer necessarily equal.

---

### `dependency_request_duration_seconds`

Measures how long Service B takes to respond.

This is the metric used to identify sustained dependency latency.

For example:

    dependency latency > 2s

can contribute to the dependency being considered under pressure.

---

### `dependency_errors_total`

Counts dependency failures returned to Service A.

This helps distinguish dependency failures from client-side request failures.

---

### `dependency_timeouts_total`

Counts dependency requests that exceed the configured timeout.

Timeouts are especially important because they can consume worker capacity without producing a successful response.

---

### `dependency_connections_errors_total`

Counts connection failures when A cannot establish communication with B.

This separates:

    B responded with an error

from:

    A could not connect to B

---

# 4. Worker Metrics

These metrics expose the actual processing capacity of Service A.

### `workers_total`

Total number of workers available.

Current design:

    5 workers

---

### `workers_busy`

Number of workers currently processing work.

---

### `workers_available`

Number of workers currently available.

The relationship is:

    workers_total
    =
    workers_busy + workers_available

This makes worker exhaustion directly observable.

For example:

    workers_total = 5
    workers_busy = 5
    workers_available = 0

means all worker capacity is currently occupied.

---

# 5. Queue Metrics

The queue is where demand that cannot immediately obtain a worker waits.

### `queue_size`

Current number of requests waiting.

This shows backlog at a point in time.

---

### `queue_capacity`

Maximum number of requests the queue can hold.

Current design:

    10

---

### `queue_utilization`

Calculated as:

    queue_size / queue_capacity

For example:

    queue_size = 8
    queue_capacity = 10

    queue_utilization = 0.8

This provides a normalized view of queue pressure.

---

### `queue_rejections_total`

Counts requests rejected because the queue was full.

This is one of the most important load-shedding metrics in the project.

A rising value means:

> Demand exceeded the available admission capacity.

---

### `queue_wait_duration_seconds`

Measures how long requests wait before a worker starts processing them.

This separates:

    queue latency

from:

    dependency latency

which is critical when diagnosing end-to-end latency.

---

# 6. Retry Metrics

Retries introduce additional dependency traffic and therefore need to be observable separately.

### `retries_total`

Counts retry events.

This answers:

> How often are requests needing another attempt?

---

### `retry_attempts_total`

Counts individual dependency attempts.

This makes the difference between original requests and actual dependency traffic visible.

For example:

    100 client requests
    120 dependency attempts

indicates additional traffic caused by retries.

---

### `retry_exhausted_total`

Counts requests that consumed all permitted retry attempts without succeeding.

This identifies cases where retrying did not recover the operation.

---

### `retry_delay_seconds`

Measures time spent waiting between retry attempts.

This makes retry backoff observable instead of hiding it inside total request latency.

---

# 7. Circuit Breaker Metrics

These metrics expose the decisions made by the dependency protection mechanism.

### `circuit_breaker_state`

Represents the current state:

    CLOSED
    OPEN
    HALF_OPEN

This allows the current dependency protection mode to be observed directly.

---

### `circuit_breaker_transitions_total`

Counts state transitions.

Examples:

    CLOSED → OPEN
    OPEN → HALF_OPEN
    HALF_OPEN → CLOSED
    HALF_OPEN → OPEN

This is useful for identifying repeated instability.

---

### `circuit_breaker_rejections_total`

Counts client requests rejected because the circuit is protecting the dependency.

This distinguishes circuit-breaker load shedding from queue-based rejection.

---

### `circuit_breaker_open_total`

Counts occurrences of the circuit entering the `OPEN` state.

This answers:

> How often has sustained dependency pressure triggered protection?

---

### `circuit_breaker_probe_total`

Counts recovery probes initiated while the circuit is open.

---

### `circuit_breaker_probe_success_total`

Counts probes that successfully demonstrate dependency recovery.

---

### `circuit_breaker_probe_failure_total`

Counts probes that fail to demonstrate recovery.

A high failure count indicates that the dependency has not recovered sufficiently for normal traffic.

---

# 8. Probe Metrics

Probe metrics describe the recovery mechanism independently from normal client traffic.

### `dependency_probes_total`

Total recovery probes sent to Service B.

---

### `dependency_probe_success_total`

Number of probes that confirm recovery.

---

### `dependency_probe_failure_total`

Number of probes that indicate the dependency remains unavailable or under pressure.

---

### `dependency_probe_duration_seconds`

Measures how long the readiness probe takes.

This is important because a probe that technically returns `200` but takes several seconds may still indicate dependency pressure.

---

# 9. Bulkhead Metrics

These metrics expose capacity isolation between workloads.

### `bulkhead_capacity`

Shows the worker capacity allocated to a particular workload.

For example:

    /notes      → 4
    /all_notes  → 1

---

### `bulkhead_active_requests`

Shows how much of each workload's isolated capacity is currently being consumed.

---

### `bulkhead_rejections_total`

Counts requests rejected because that workload's own capacity has been exhausted.

This allows us to distinguish:

    global capacity exhaustion

from:

    one workload exhausting its own allocation

---

# 10. Application Metrics

These metrics describe business-level outcomes rather than infrastructure behavior.

### `notes_processed_total`

Counts notes processed by the application.

---

### `notes_saved_total`

Counts notes successfully persisted.

---

### `notes_invalid_total`

Counts notes rejected because they failed application validation.

These metrics help connect system behavior to actual application results.

---

# 11. What the Metrics Let Us Diagnose

The important part is not having many metrics.

It is being able to combine them to answer a specific question.

### "Why did latency increase?"

Look at:

    http_request_duration_seconds
    queue_wait_duration_seconds
    dependency_request_duration_seconds
    workers_busy
    queue_size

---

### "Are we receiving more traffic than we can handle?"

Look at:

    http_requests_total
    workers_busy
    queue_size
    queue_utilization
    queue_rejections_total

---

### "Is the dependency causing the problem?"

Look at:

    dependency_request_duration_seconds
    dependency_errors_total
    dependency_timeouts_total
    dependency_connections_errors_total

---

### "Are retries making the incident worse?"

Compare:

    http_requests_total

against:

    dependency_requests_total
    retry_attempts_total

A large difference indicates additional dependency traffic generated by retries.

---

### "Why are clients receiving 503?"

Separate the possible causes:

    queue_rejections_total
    circuit_breaker_rejections_total
    bulkhead_rejections_total

The HTTP status alone does not tell us which protection mechanism rejected the request.

---

### "Is the dependency recovering?"

Look at:

    circuit_breaker_state
    dependency_probes_total
    dependency_probe_success_total
    dependency_probe_failure_total
    dependency_probe_duration_seconds

---

# 12. Observability Model

The project therefore observes the system at several layers:

    CLIENT EXPERIENCE
            |
            v
    HTTP METRICS
            |
            v
    QUEUE / WORKER CAPACITY
            |
            v
    DEPENDENCY BEHAVIOR
            |
            v
    RETRY BEHAVIOR
            |
            v
    CIRCUIT BREAKER
            |
            v
    RECOVERY PROBES
            |
            v
    APPLICATION OUTCOME

Each layer answers a different operational question.

The objective is not to collect metrics for the sake of monitoring.

The objective is to make the system's **behavior under failure explainable**.
