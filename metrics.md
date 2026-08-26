# SRE Reliability Lab — Metrics Reference

This document provides the complete Prometheus metrics reference for the SRE Reliability Lab.

The metrics are grouped by the reliability dimension they measure:

```text
HTTP / Service
      ↓
Capacity / Saturation
      ↓
Queues / Backpressure
      ↓
Bulkheads
      ↓
Dependency
      ↓
Retries
      ↓
Circuit Breaker
      ↓
Application
      ↓
SLI / SLO / Error Budget
```

---

# 1. HTTP / Service Metrics

These metrics describe what the Receiver HTTP service is receiving, processing,
and returning.

| Metric                          | Type      | Labels                         | What It Measures                                                  | Why It Matters                                                                         |
| ------------------------------- | --------- | ------------------------------ | ----------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| `http_requests_total`           | Counter   | `method`, `endpoint`           | Total HTTP requests received by Receiver                          | Measures incoming traffic and request volume                                           |
| `http_responses_total`          | Counter   | `method`, `endpoint`, `status` | Total HTTP responses returned by Receiver, grouped by status code | Foundation for HTTP traffic classification, SLIs, error rates and status-code analysis |
| `http_requests_errors_total`    | Counter   | `method`, `endpoint`           | HTTP requests considered application errors                       | Measures failures produced while processing requests                                   |
| `http_request_duration_seconds` | Histogram | `method`, `endpoint`           | End-to-end HTTP request duration                                  | Used to calculate p50/p95/p99 latency and latency SLIs                                 |
| `http_requests_in_progress`     | Gauge     | `method`, `endpoint`           | Requests currently being processed                                | Shows concurrent HTTP workload and possible request accumulation                       |

### HTTP Status Classification

The `http_responses_total` metric allows the service to classify every HTTP
response:

| Class | Meaning             | Reliability Interpretation                                     |
| ----- | ------------------- | -------------------------------------------------------------- |
| `2xx` | Successful response | Successful request processing                                  |
| `3xx` | Redirect            | Request was successfully handled at the HTTP layer             |
| `4xx` | Client error        | Request reached the service but the client/request was invalid |
| `5xx` | Server error        | Service failed to successfully process the request             |

For the project's availability SLI:

```text
Successful
    =
2xx + 3xx
```

```text
Failed for SLI
    =
5xx
```

`4xx` responses are tracked separately so they can be analyzed without
incorrectly treating client mistakes as service failures.

---

# 2. Worker / Capacity Metrics

These metrics describe the Receiver's available processing concurrency.

| Metric              | Type  | Labels     | What It Measures                            | Why It Matters                           |
| ------------------- | ----- | ---------- | ------------------------------------------- | ---------------------------------------- |
| `workers_total`     | Gauge | `bulkhead` | Total workers assigned to a workload        | Defines available processing concurrency |
| `workers_busy`      | Gauge | `bulkhead` | Workers currently executing work            | Shows active concurrency                 |
| `workers_available` | Gauge | `bulkhead` | Workers currently available to process work | Shows remaining processing capacity      |

### Capacity Relationship

```text
workers_total
      =
workers_busy
      +
workers_available
```

For example:

```text
4 total workers
2 busy
2 available
```

means the workload is currently consuming 50% of its worker capacity.

---

# 3. Queue / Backpressure Metrics

These metrics describe work waiting for workers and whether the system is
beginning to reject additional work.

| Metric                        | Type      | Labels  | What It Measures                                                   | Why It Matters                                      |
| ----------------------------- | --------- | ------- | ------------------------------------------------------------------ | --------------------------------------------------- |
| `queue_size`                  | Gauge     | `queue` | Number of requests currently waiting in a queue                    | Shows backlog                                       |
| `queue_capacity`              | Gauge     | `queue` | Maximum number of requests the queue can contain                   | Defines bounded queue capacity                      |
| `queue_utilization`           | Gauge     | `queue` | Percentage of queue capacity currently being used                  | Shows how close the system is to queue saturation   |
| `queue_rejections_total`      | Counter   | `queue` | Number of requests rejected because the queue was full             | Measures explicit backpressure / overload rejection |
| `queue_wait_duration_seconds` | Histogram | `queue` | Time requests spend waiting before a worker starts processing them | Measures queue-induced latency                      |

### Queue Utilization

Conceptually:

```text
queue_utilization
=
queue_size / queue_capacity
```

Example:

```text
queue_size      = 8
queue_capacity  = 10

queue_utilization = 80%
```

A high queue utilization does not necessarily mean failure, but sustained
100% utilization indicates that incoming work is exceeding available
processing capacity.

### Queue Rejection

The Receiver uses:

```python
queue.put_nowait(...)
```

When the queue is full:

```text
put_nowait()
     ↓
queue.Full
     ↓
queue_rejections_total++
     ↓
HTTP 503
```

This turns overload into an observable reliability signal.

---

# 4. Queue Latency Metrics

`queue_wait_duration_seconds` is particularly important because HTTP latency
alone does not tell us **where the latency came from**.

| Metric                        | Type      | What It Measures                                        | Example Question It Answers                                                                   |
| ----------------------------- | --------- | ------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `queue_wait_duration_seconds` | Histogram | Time spent waiting in the queue before worker execution | "Are requests slow because the dependency is slow, or because they are waiting for a worker?" |

Common PromQL calculations:

### Queue p95

```promql
histogram_quantile(
  0.95,
  sum by (le, queue) (
    rate(queue_wait_duration_seconds_bucket[5m])
  )
)
```

### Queue p99

```promql
histogram_quantile(
  0.99,
  sum by (le, queue) (
    rate(queue_wait_duration_seconds_bucket[5m])
  )
)
```

This allows the project to distinguish:

```text
Dependency latency
        +
Queue waiting
        =
Observed request latency
```

---

# 5. Bulkhead Metrics

Bulkheads isolate workloads so that one overloaded operation does not consume
all available service capacity.

| Metric                      | Type    | Labels     | What It Measures                                                        | Why It Matters                     |
| --------------------------- | ------- | ---------- | ----------------------------------------------------------------------- | ---------------------------------- |
| `bulkhead_capacity`         | Gauge   | `bulkhead` | Maximum concurrent processing capacity of a bulkhead                    | Defines isolation capacity         |
| `bulkhead_active_requests`  | Gauge   | `bulkhead` | Requests currently occupying bulkhead capacity                          | Shows current resource consumption |
| `bulkhead_rejections_total` | Counter | `bulkhead` | Requests rejected because the bulkhead could not accept additional work | Measures overload protection       |

In this project, the workloads are separated:

```text
                Receiver
                   |
          +--------+--------+
          |                 |
       /notes          /all_notes
          |                 |
      Bulkhead A        Bulkhead B
          |                 |
      4 workers         1 worker
      10 queue          10 queue
```

This means `/notes` saturation should not consume the processing capacity
dedicated to `/all_notes`.

> Note: `queue_rejections_total` is the primary rejection metric in the
> current design. `bulkhead_rejections_total` represents the same queue-full
> rejection event from the bulkhead perspective, so the two should not be
> blindly summed together as independent failures.

---

# 6. Dependency Metrics

These metrics describe communication between Receiver and Saver.

| Metric                                | Type      | Labels       | What It Measures                            | Why It Matters                                  |
| ------------------------------------- | --------- | ------------ | ------------------------------------------- | ----------------------------------------------- |
| `dependency_requests_total`           | Counter   | `operation`  | Total requests Receiver sends to Saver      | Measures dependency traffic                     |
| `dependency_errors_total`             | Counter   | `operation`  | Failed dependency requests                  | Measures dependency failures                    |
| `dependency_request_duration_seconds` | Histogram | `operation`  | Time spent waiting for dependency responses | Measures dependency latency                     |
| `dependency_timeouts_total`           | Counter   | `operation`  | Dependency requests that timed out          | Identifies timeout failures                     |
| `dependency_connections_errors_total` | Counter   | `operation`  | Dependency connection failures              | Identifies inability to establish communication |
| `dependency_probe_failure_total`      | Counter   | `dependency` | Failed dependency health probes             | Detects dependency recovery/health problems     |

### Dependency Request Rate

```promql
sum by (operation) (
  rate(dependency_requests_total[5m])
)
```

### Dependency Error Rate

```promql
100 *
sum by (operation) (
  rate(dependency_errors_total[5m])
)
/
clamp_min(
  sum by (operation) (
    rate(dependency_requests_total[5m])
  ),
  0.000001
)
```

### Dependency p95

```promql
histogram_quantile(
  0.95,
  sum by (le, operation) (
    rate(dependency_request_duration_seconds_bucket[5m])
  )
)
```

---

# 7. Dependency Health / Pressure Metrics

These gauges represent the Receiver's current interpretation of Saver's
condition.

| Metric                      | Type  | Labels       | Values    | Meaning                                                                   |
| --------------------------- | ----- | ------------ | --------- | ------------------------------------------------------------------------- |
| `dependency_health`         | Gauge | `dependency` | `0` / `1` | Whether the dependency is considered healthy                              |
| `dependency_under_pressure` | Gauge | `dependency` | `0` / `1` | Whether the dependency is currently considered under performance pressure |

### `dependency_health`

```text
0 = UNHEALTHY
1 = HEALTHY
```

### `dependency_under_pressure`

```text
0 = NORMAL
1 = UNDER PRESSURE
```

This distinction is important.

A dependency can be:

```text
Healthy
but
Under Pressure
```

For example, Saver may still successfully respond to requests while its
latency has increased significantly.

---

# 8. Circuit Breaker Metrics

The circuit breaker prevents continuous requests from being sent to a
dependency that is failing or under unacceptable pressure.

| Metric                             | Type    | Labels       | What It Measures                         | Why It Matters                                      |
| ---------------------------------- | ------- | ------------ | ---------------------------------------- | --------------------------------------------------- |
| `circuit_breaker_state`            | Gauge   | `dependency` | Current circuit breaker state            | Shows whether dependency traffic is allowed         |
| `circuit_breaker_rejections_total` | Counter | `dependency` | Requests rejected by the circuit breaker | Measures protection activated by dependency failure |

### Circuit States

| Value | State       | Meaning                               |
| ----: | ----------- | ------------------------------------- |
|   `0` | `CLOSED`    | Requests are allowed                  |
|   `1` | `OPEN`      | Requests are rejected                 |
|   `2` | `HALF_OPEN` | Limited recovery testing is occurring |

The intended flow is:

```text
CLOSED
   |
   | dependency failure / pressure
   v
OPEN
   |
   | recovery probe
   v
HALF_OPEN
   |
   +---- success ----> CLOSED
   |
   +---- failure ----> OPEN
```

---

# 9. Retry Metrics

Retries can improve availability for transient failures but can also amplify
load against an already struggling dependency.

| Metric                  | Type      | Labels      | What It Measures                                                 | Why It Matters                                |
| ----------------------- | --------- | ----------- | ---------------------------------------------------------------- | --------------------------------------------- |
| `retries_total`         | Counter   | `operation` | Number of retry attempts                                         | Measures additional dependency load           |
| `retry_exhausted_total` | Counter   | `operation` | Number of operations that failed after exhausting retry attempts | Shows failures that retries could not recover |
| `retry_delay_seconds`   | Histogram | `operation` | Time spent waiting between retry attempts                        | Measures backoff behavior                     |

### Retry Amplification

For example:

```text
Original requests = 100

Maximum attempts = 3

Worst-case dependency requests:
100 × 3 = 300
```

The additional 200 requests are retry-generated load.

This is why retries must be bounded and combined with mechanisms such as
timeouts, backoff and circuit breaking.

---

# 10. Application Metrics

These metrics describe business/application-level processing.

| Metric                  | Type    | What It Measures                                                        | Why It Matters                                                        |
| ----------------------- | ------- | ----------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `notes_processed_total` | Counter | Number of notes successfully processed through the application workflow | Provides application-level throughput rather than merely HTTP traffic |

This differs from:

```text
http_requests_total
```

because an HTTP request reaching the application does not necessarily mean
the underlying business operation completed successfully.

---

# 11. Service-Level Indicators

The project derives its primary SLIs from the HTTP response metrics.

## Total HTTP Traffic

All HTTP requests received by Receiver:

```text
Total HTTP
    |
    +── 2xx Successful
    |
    +── 3xx Redirect
    |
    +── 4xx Client Error
    |
    +── 5xx Server Error
```

The service dashboard keeps this separate from the SLI traffic.

---

## Total SLI HTTP

For the project's availability SLI, only the selected client-facing
endpoints are included.

The project currently treats:

```text
Successful SLI requests
=
2xx + 3xx
```

and:

```text
Failed SLI requests
=
5xx
```

4xx responses remain separately observable but are not counted as successful
requests.

---

# 12. Availability SLI

The project's availability SLI is conceptually:

```text
Availability SLI
=
successful requests
/
total SLI requests
```

where:

```text
successful
=
2xx + 3xx
```

and:

```text
failed
=
5xx
```

Therefore:

```text
Availability SLI
=
(2xx + 3xx)
/
(2xx + 3xx + 5xx)
× 100
```

The dashboard deliberately keeps 4xx traffic separate for future analysis.

---

# 13. Error Rate

The primary service error rate is based on 5xx responses:

```text
5xx Error Rate
=
5xx responses
/
total SLI requests
× 100
```

This is useful because it measures actual service-side failures rather than
client mistakes.

---

# 14. Latency SLI

The latency SLI measures the percentage of requests completed within the
defined latency objective.

Current project objective:

```text
99% of requests < 2 seconds
```

Conceptually:

```text
Latency SLI
=
requests completed under 2s
/
total requests
× 100
```

The underlying histogram:

```text
http_request_duration_seconds
```

allows percentile and threshold-based analysis.

---

# 15. Error Budget Metrics

The project uses a 99.9% availability SLO.

Therefore:

```text
SLO = 99.9%

Allowed error =
100% - 99.9%

          = 0.1%
```

| Concept            | Meaning                                              |
| ------------------ | ---------------------------------------------------- |
| Availability SLO   | Target reliability                                   |
| Error Budget       | Amount of unreliability that is acceptable           |
| Budget Consumption | How much of the allowed failure budget has been used |
| Burn Rate          | Speed at which the error budget is being consumed    |

### Error Budget

```text
Allowed Error = 0.1%
```

### Burn Rate

A burn rate of:

```text
1x
```

means the service is consuming its error budget at approximately the rate
expected by the SLO.

A burn rate of:

```text
10x
```

means the budget is being consumed approximately ten times faster than the
normal budget allowance.

---

# 16. Grafana Dashboard Metrics

The service dashboard turns the raw Prometheus metrics into operational
views.

| Dashboard Panel              | Primary Metric(s)                                    | Reliability Question                                        |
| ---------------------------- | ---------------------------------------------------- | ----------------------------------------------------------- |
| Total SLI HTTP Requests      | `http_responses_total`                               | How many requests are being considered by the SLI?          |
| Availability SLI             | `http_responses_total`                               | Are successful requests meeting the availability objective? |
| Current 5xx Error Rate       | `http_responses_total`                               | How frequently is the service failing?                      |
| Budget Exhaustion Status     | `http_responses_total`                               | How much availability error budget remains?                 |
| Availability SLO             | Constant `99.9`                                      | What reliability target are we operating against?           |
| Error Budget Consumption     | HTTP error metrics                                   | How quickly are failures consuming the budget?              |
| Error Budget Burn Rate       | HTTP error metrics                                   | Is the service burning budget abnormally fast?              |
| Request Rate                 | `http_requests_total`                                | How much traffic is entering the service?                   |
| Error Rate %                 | `http_requests_errors_total` / `http_requests_total` | What percentage of requests are errors?                     |
| HTTP p95 Latency             | `http_request_duration_seconds`                      | What does high-percentile latency look like?                |
| HTTP p99 Latency             | `http_request_duration_seconds`                      | How bad is the long tail of latency?                        |
| Latency SLI < 2s             | `http_request_duration_seconds`                      | What percentage meets the latency objective?                |
| Latency SLO                  | Constant `99`                                        | What latency reliability target are we using?               |
| Latency Error Budget         | Latency SLI                                          | How much latency budget remains?                            |
| Dependency Request Rate      | `dependency_requests_total`                          | How much traffic is being sent to Saver?                    |
| Dependency Error Rate        | `dependency_errors_total`                            | Is Saver failing?                                           |
| Dependency p95 Latency       | `dependency_request_duration_seconds`                | Is Saver becoming slow?                                     |
| Dependency Timeouts          | `dependency_timeouts_total`                          | How frequently is Saver timing out?                         |
| Dependency Connection Errors | `dependency_connections_errors_total`                | Are connections to Saver failing?                           |
| Dependency Probe Failures    | `dependency_probe_failure_total`                     | Is recovery probing failing?                                |
| Dependency Health            | `dependency_health`                                  | Is Saver currently considered healthy?                      |
| Dependency Pressure          | `dependency_under_pressure`                          | Is Saver healthy but operating under pressure?              |
| Circuit Breaker State        | `circuit_breaker_state`                              | Is dependency traffic currently allowed?                    |
| Circuit Breaker Rejections   | `circuit_breaker_rejections_total`                   | How often is the breaker protecting the service?            |
| Retry Rate                   | `retries_total`                                      | How much additional dependency work is being generated?     |
| Retry Exhaustion             | `retry_exhausted_total`                              | How often do retries fail to recover the operation?         |
| Retry Delay p95              | `retry_delay_seconds`                                | How much latency is backoff adding?                         |

---

# 17. Complete Metric Inventory

For quick reference:

|  # | Metric                                | Category             |
| -: | ------------------------------------- | -------------------- |
|  1 | `http_requests_total`                 | HTTP                 |
|  2 | `http_responses_total`                | HTTP                 |
|  3 | `http_requests_errors_total`          | HTTP                 |
|  4 | `http_request_duration_seconds`       | HTTP / Latency       |
|  5 | `http_requests_in_progress`           | HTTP / Concurrency   |
|  6 | `workers_total`                       | Capacity             |
|  7 | `workers_busy`                        | Capacity             |
|  8 | `workers_available`                   | Capacity             |
|  9 | `queue_size`                          | Queue                |
| 10 | `queue_capacity`                      | Queue                |
| 11 | `queue_utilization`                   | Queue                |
| 12 | `queue_rejections_total`              | Queue / Backpressure |
| 13 | `queue_wait_duration_seconds`         | Queue / Latency      |
| 14 | `bulkhead_capacity`                   | Bulkhead             |
| 15 | `bulkhead_active_requests`            | Bulkhead             |
| 16 | `bulkhead_rejections_total`           | Bulkhead             |
| 17 | `dependency_requests_total`           | Dependency           |
| 18 | `dependency_errors_total`             | Dependency           |
| 19 | `dependency_request_duration_seconds` | Dependency / Latency |
| 20 | `dependency_timeouts_total`           | Dependency           |
| 21 | `dependency_connections_errors_total` | Dependency           |
| 22 | `dependency_probe_failure_total`      | Dependency           |
| 23 | `dependency_health`                   | Dependency Health    |
| 24 | `dependency_under_pressure`           | Dependency Health    |
| 25 | `circuit_breaker_state`               | Circuit Breaker      |
| 26 | `circuit_breaker_rejections_total`    | Circuit Breaker      |
| 27 | `retries_total`                       | Retry                |
| 28 | `retry_exhausted_total`               | Retry                |
| 29 | `retry_delay_seconds`                 | Retry / Latency      |
| 30 | `notes_processed_total`               | Application          |

---

# 18. The SRE Mental Model

The most important thing is not memorizing the metric names.

The metrics form a chain:

```text
                         TRAFFIC
                            │
                            ▼
                  http_requests_total
                            │
                            ▼
                     HTTP processing
                            │
             ┌──────────────┴──────────────┐
             │                             │
             ▼                             ▼
       Worker Capacity                 Dependency
             │                             │
             ▼                             ▼
      workers_busy                dependency_requests_total
             │                             │
             ▼                             ▼
        Queue Growth              dependency latency/errors
             │                             │
             ▼                             ▼
      queue_utilization             dependency pressure
             │                             │
             ▼                             ▼
    queue_rejections_total         circuit breaker
             │                             │
             └──────────────┬──────────────┘
                            ▼
                     HTTP Responses
                            │
             ┌──────────────┼──────────────┐
             │              │              │
             ▼              ▼              ▼
            2xx            4xx            5xx
             │              │              │
             │              │              ▼
             │              │        Error Budget
             │              │              │
             └──────┬───────┘              ▼
                    │                Burn Rate / SLO
                    ▼
              Availability SLI
```

This is the real value of the dashboard.

You are not simply collecting **30 metrics**.

You are building the ability to answer:

> **What is the system doing?**

```text
Traffic
```

> **Where is capacity being consumed?**

```text
Workers / Queue / Bulkhead
```

> **Is the dependency causing the problem?**

```text
Dependency latency / errors / timeouts / pressure
```

> **Is the system protecting itself?**

```text
Queue rejection / Bulkhead / Circuit Breaker
```

> **Are retries making the situation worse?**

```text
Retry rate / Retry exhaustion / Retry delay
```

> **What does the customer actually experience?**

```text
HTTP latency / 2xx / 3xx / 4xx / 5xx
```

> **Are we meeting our reliability objective?**

```text
SLI / SLO / Error Budget / Burn Rate
```

That is the complete observability model of the Reliability Lab.
