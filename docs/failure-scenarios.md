# SRE Reliability Lab — Failure Scenarios

## 1. Purpose

This document defines the controlled failure experiments performed against the Reliability Lab.

The purpose is to verify that the reliability mechanisms implemented in the system produce the expected behavior under specific failure conditions.

Each experiment follows the same operational pattern:

    Establish baseline
          ↓
    Inject failure
          ↓
    Generate traffic
          ↓
    Observe behavior
          ↓
    Verify protection
          ↓
    Restore normal conditions
          ↓
    Verify recovery

The mechanisms themselves are explained in `reliability.md`.

The metrics used to observe the experiments are documented in `observability.md`.

This document focuses on the experiments.

---

# 2. Baseline

Before running a failure experiment, establish that the system is operating normally.

Expected baseline:

    Service A
       |
       v
    Service B

Service B should respond normally.

The following should be true:

- requests complete successfully
- dependency latency is within the normal range
- workers return to an available state after processing
- queue depth remains low
- no unexpected queue rejections occur
- the circuit breaker remains `CLOSED`
- no unexpected retry activity occurs

Useful metrics:

    http_requests_total
    http_request_duration_seconds
    dependency_request_duration_seconds
    workers_busy
    workers_available
    queue_size
    circuit_breaker_state

A baseline provides a reference point for comparing the system after failure injection.

---

# 3. Slow Dependency

## Objective

Determine how the system behaves when Service B remains responsive but becomes significantly slower.

---

## Failure Injection

Configure Service B to introduce an artificial delay on `/validate`.

Example:

    Service B delay = 4 seconds

The normal request path remains available, but dependency latency is deliberately increased.

---

## Traffic

Send multiple concurrent requests to:

    POST /notes

Use enough traffic to keep several Service A workers occupied.

---

## Expected Signals

Observe:

    dependency_request_duration_seconds
    http_request_duration_seconds
    workers_busy
    workers_available
    queue_size
    queue_wait_duration_seconds
    circuit_breaker_state

Expected progression:

    dependency latency increases
              ↓
    workers remain occupied longer
              ↓
    queue pressure increases
              ↓
    sustained slow requests detected
              ↓
    circuit state changes

---

## Expected Protection

Once the configured sustained-latency condition is reached:

    CLOSED
       ↓
     OPEN

Normal requests should no longer continue creating dependency traffic while the circuit is open.

---

## Recovery

Remove the artificial delay.

Allow the configured recovery interval to pass.

Observe the recovery probe and circuit state.

Expected progression:

    OPEN
      ↓
    HALF_OPEN
      ↓
    successful probe
      ↓
    CLOSED

---

## Evidence

The experiment is successful if the metrics demonstrate:

- increased dependency latency
- increased worker occupancy
- increased queue pressure where sufficient traffic is present
- circuit opening after sustained pressure
- recovery probing
- successful return to `CLOSED`

---

# 4. Dependency Timeout

## Objective

Verify that Service A does not wait indefinitely for a dependency response.

---

## Failure Injection

Configure Service B to take longer than Service A's dependency timeout.

Example:

    Service B delay = 15 seconds
    Service A timeout = 5 seconds

---

## Traffic

Send requests through:

    POST /notes

---

## Expected Signals

Observe:

    dependency_request_duration_seconds
    dependency_timeouts_total
    retries_total
    retry_attempts_total
    retry_delay_seconds
    retry_exhausted_total
    http_requests_errors_total

Expected request sequence:

    attempt 1
       ↓
    timeout
       ↓
    retry
       ↓
    timeout
       ↓
    retry
       ↓
    final result

---

## Expected Protection

The dependency request should terminate at the configured timeout rather than occupying a worker indefinitely.

Retry activity should remain bounded by the configured retry policy.

---

## Recovery

Restore normal Service B behavior.

Send new requests and verify that:

    dependency_timeouts_total

stops increasing for successful normal traffic.

Also verify that requests complete without unnecessary retry activity.

---

## Evidence

The experiment is successful if:

- dependency timeouts are recorded
- retry attempts are bounded
- retry delays are observable
- exhausted retries produce the expected failure
- normal traffic succeeds after recovery

---

# 5. Dependency Connection Failure

## Objective

Verify behavior when Service A cannot establish communication with Service B.

---

## Failure Injection

Stop Service B or otherwise make it unreachable from Service A.

Example:

    Service B
        ↓
    unavailable

---

## Traffic

Send requests through:

    POST /notes

---

## Expected Signals

Observe:

    dependency_connections_errors_total
    dependency_requests_total
    retries_total
    retry_attempts_total
    retry_exhausted_total
    circuit_breaker_state
    http_responses_total

---

## Expected Behavior

A dependency request should fail because Service A cannot establish the connection.

Transient failures are retried according to the configured policy.

The dependency should not receive an unlimited stream of attempts.

---

## Recovery

Restore Service B.

Verify that the service becomes reachable again.

Observe the recovery path if the circuit has entered protection.

---

## Evidence

The experiment is successful if:

- connection failures are recorded separately from dependency responses
- retries occur only within the configured limit
- dependency traffic remains bounded
- the system eventually stops attempting normal work while the dependency remains unavailable
- normal operation resumes after recovery

---

# 6. Queue Saturation

## Objective

Verify that Service A enforces its configured processing boundary when incoming demand exceeds available capacity.

---

## Configuration

Current capacity:

    Workers = 5
    Queue capacity = 10

Therefore, accepted work can occupy:

    5 active workers
    +
    10 queued requests

before additional work is rejected.

---

## Traffic

Generate more concurrent requests than the available capacity.

For example:

    20 concurrent POST /notes requests

Use a dependency delay long enough for workers and queue entries to remain occupied while the load is generated.

---

## Expected Signals

Observe:

    workers_busy
    workers_available
    queue_size
    queue_utilization
    queue_rejections_total
    http_responses_total
    http_request_duration_seconds

Expected progression:

    workers become occupied
          ↓
    queue begins filling
          ↓
    queue utilization approaches 1.0
          ↓
    additional requests are rejected

---

## Expected Outcome

Requests that cannot be admitted should receive:

    HTTP 503

Previously accepted requests should continue processing.

---

## Recovery

Allow the existing workload to drain.

Verify:

    workers_busy ↓
    workers_available ↑
    queue_size ↓
    queue_utilization ↓

New requests should become admissible again.

---

## Evidence

The experiment is successful if queue capacity is visibly bounded and excess requests are rejected rather than accumulating indefinitely.

---

# 7. Retry Amplification

## Objective

Measure the additional dependency traffic created by retries during dependency failure.

---

## Failure Injection

Make Service B return a retryable failure or become unavailable.

---

## Traffic

Generate a known number of client requests.

For example:

    100 client requests

---

## Expected Signals

Compare:

    http_requests_total

against:

    dependency_requests_total
    retry_attempts_total
    retry_exhausted_total

The dependency may receive more attempts than the number of client requests.

For example:

    100 client requests
    180 dependency attempts

would demonstrate additional dependency demand created by retries.

---

## Expected Protection

Retry behavior should remain bounded by:

    MAX_RETRIES = 2

with the configured delays:

    retry #1 → 0.5 seconds
    retry #2 → 1 second

---

## Recovery

Restore Service B.

Verify that retry activity returns to its normal baseline for successful requests.

---

## Evidence

The experiment is successful if the additional dependency traffic generated by retries can be measured and correlated with the client request volume.

---

# 8. Sustained Dependency Pressure

## Objective

Verify that repeated slow dependency responses are detected as a sustained condition rather than treated as isolated latency events.

---

## Failure Injection

Keep Service B consistently slow.

Example:

    4s
    4s
    4s
    4s
    4s

---

## Traffic

Send enough requests to produce multiple dependency calls.

---

## Expected Signals

Observe:

    dependency_request_duration_seconds
    circuit_breaker_state
    circuit_breaker_transitions_total
    circuit_breaker_open_total

With the configured thresholds:

    SLOW_THRESHOLD = 2s
    CONSECUTIVE_SLOW_LIMIT = 3

the dependency should produce a sustained-pressure event.

---

## Expected Outcome

The circuit should transition:

    CLOSED
       ↓
     OPEN

---

## Recovery

Restore normal dependency latency.

Continue observing the circuit state and recovery probe metrics.

---

## Evidence

The experiment is successful if the circuit opens only after the configured sustained condition has been reached rather than after a single slow request.

---

# 9. Circuit Breaker Recovery

## Objective

Verify that recovery from an unhealthy dependency occurs through a controlled transition rather than an immediate return to normal traffic.

---

## Setup

First create conditions that cause:

    CLOSED → OPEN

Then restore Service B.

---

## Expected Signals

Observe:

    circuit_breaker_state
    circuit_breaker_transitions_total
    circuit_breaker_probe_total
    circuit_breaker_probe_success_total
    circuit_breaker_probe_failure_total
    dependency_probe_duration_seconds

---

## Successful Recovery

Expected sequence:

    OPEN
      ↓
    HALF_OPEN
      ↓
    recovery probe
      ↓
    CLOSED

---

## Failed Recovery

If the dependency remains unhealthy:

    OPEN
      ↓
    HALF_OPEN
      ↓
    failed probe
      ↓
    OPEN

---

## Evidence

The experiment is successful if normal traffic resumes only after the configured recovery condition has been satisfied.

---

# 10. Readiness vs Liveness

## Objective

Verify that a running Service B process is not automatically treated as ready for normal traffic.

---

## Failure Injection

Keep Service B running while making the functionality required by normal requests unhealthy or slow.

---

## Test

Compare:

    GET /health

with:

    GET /readiness

---

## Expected Signals

The process may continue responding successfully to:

    /health

while the readiness check reports that the service is not suitable for normal work.

---

## Recovery

Restore the affected functionality.

Repeat both checks.

---

## Evidence

The experiment is successful if the two endpoints provide distinguishable operational signals rather than treating process existence and traffic readiness as the same condition.

---

# 11. Bulkhead Isolation

## Objective

Verify that heavy traffic to one workload does not consume the processing capacity reserved for another workload.

---

## Configuration

Current workload allocation:

    /notes
        4 workers

    /all_notes
        1 worker

---

## Traffic

Generate sustained traffic against:

    POST /notes

while simultaneously requesting:

    GET /all_notes

---

## Expected Signals

Observe:

    bulkhead_capacity
    bulkhead_active_requests
    bulkhead_rejections_total
    http_requests_total
    http_responses_total

---

## Expected Outcome

The `/notes` workload should be able to exhaust its own allocation without consuming the capacity reserved for `/all_notes`.

Requests to `/all_notes` should therefore retain access to its allocated processing capacity.

---

## Recovery

Stop the `/notes` load.

Verify that:

    bulkhead_active_requests

returns toward normal levels and that both workloads continue operating normally.

---

## Evidence

The experiment is successful if resource exhaustion in one workload does not prevent the other workload from making progress.

---

# 12. Invalid Client Request

## Objective

Verify that deterministic client-side failures are not retried.

---

## Failure Injection

Send invalid input to the application.

Examples:

    missing word
    empty word
    non-string word
    invalid note data

---

## Traffic

Send the invalid request through the normal API.

---

## Expected Signals

Observe:

    http_responses_total
    http_requests_errors_total
    dependency_requests_total
    retries_total

---

## Expected Outcome

The request should return the appropriate client/application error.

For example:

    HTTP 400

No retry should be generated for a deterministic validation failure.

---

## Evidence

The experiment is successful if:

    client error
        ↓
    request failure

does not become:

    client error
        ↓
    retry
        ↓
    retry
        ↓
    unnecessary dependency traffic

---

# 13. Queue Pressure During Dependency Slowness

## Objective

Demonstrate how dependency latency can propagate into Service A's own processing resources.

---

## Failure Injection

Combine:

    high concurrent demand
          +
    slow Service B

---

## Expected Progression

Observe:

    Service B latency increases
          ↓
    workers remain occupied
          ↓
    worker availability decreases
          ↓
    queue begins filling
          ↓
    queue utilization increases
          ↓
    queue reaches capacity
          ↓
    requests are rejected

---

## Metrics

Observe:

    dependency_request_duration_seconds
    workers_busy
    workers_available
    queue_size
    queue_utilization
    queue_rejections_total
    http_request_duration_seconds

---

## Recovery

Restore normal Service B latency.

Allow workers and queued requests to drain.

Observe the return of:

    workers_available
    queue_size
    queue_utilization

toward their normal levels.

---

## Evidence

The experiment is successful if the dependency problem can be traced through Service A's resource utilization into admission failures.

---

# 14. Repeated Failure and Recovery

## Objective

Determine whether the system remains stable when the dependency repeatedly alternates between healthy and unhealthy conditions.

---

## Failure Pattern

Alternate Service B between:

    slow
    normal
    slow
    normal

---

## Expected Signals

Observe:

    dependency_request_duration_seconds
    circuit_breaker_state
    circuit_breaker_transitions_total
    circuit_breaker_open_total
    circuit_breaker_probe_total
    circuit_breaker_probe_success_total
    circuit_breaker_probe_failure_total
    http_responses_total

---

## Expected Outcome

Successful recovery should produce:

    CLOSED
       ↓
     OPEN
       ↓
    HALF_OPEN
       ↓
     CLOSED

An unsuccessful recovery should produce:

    CLOSED
       ↓
     OPEN
       ↓
    HALF_OPEN
       ↓
     OPEN

---

## Evidence

The experiment should show whether the system settles into a stable state or repeatedly oscillates between protection and recovery.

Frequent transitions should be treated as an operational signal rather than simply counting individual successful requests.

---

# 15. Combined Failure Experiment

## Objective

Observe several reliability mechanisms interacting during the same incident.

This represents a more realistic distributed-system failure rather than an isolated mechanism test.

---

## Failure Injection

Configure Service B to become slow while generating high concurrent demand.

---

## Expected Progression

The system should demonstrate a chain such as:

    increased demand
          ↓
    dependency latency
          ↓
    workers remain occupied
          ↓
    queue pressure
          ↓
    admission pressure
          ↓
    sustained dependency pressure
          ↓
    circuit protection
          ↓
    request rejection
          ↓
    dependency recovery
          ↓
    recovery probe
          ↓
    normal operation

---

## Metrics

Observe the system across multiple layers:

    HTTP
    workers
    queue
    dependency
    retries
    circuit breaker
    probes

Particularly useful metrics include:

    http_request_duration_seconds
    dependency_request_duration_seconds
    workers_busy
    queue_size
    queue_rejections_total
    dependency_timeouts_total
    retries_total
    circuit_breaker_state
    circuit_breaker_transitions_total
    circuit_breaker_probe_success_total

---

## Evidence

The experiment is successful if the metrics allow the complete failure progression to be reconstructed without relying solely on application logs.

---

# 16. Recovery Verification

Every failure experiment should end with an explicit recovery check.

After restoring normal conditions, verify:

    Service B responsive
          ↓
    dependency latency normal
          ↓
    workers available
          ↓
    queue drains
          ↓
    rejection rate returns to normal
          ↓
    retries return to normal
          ↓
    circuit returns to CLOSED
          ↓
    normal requests succeed

Recovery should therefore be treated as part of the experiment rather than as an assumption.

---

# 17. Experiment Evidence

A failure experiment should produce measurable evidence.

Useful evidence includes:

- HTTP status changes
- latency changes
- queue growth
- worker saturation
- dependency errors
- dependency timeouts
- connection failures
- retry activity
- retry exhaustion
- circuit transitions
- recovery probes
- bulkhead activity
- application outcomes

The purpose of collecting this evidence is to establish a causal sequence.

For example:

    dependency latency
          ↓
    worker occupancy
          ↓
    queue growth
          ↓
    queue rejection
          ↓
    client-visible 503

This is stronger evidence than simply observing that requests eventually failed.

---

# 18. Failure Scenario Matrix

| Scenario | Failure introduced | Primary evidence | Expected protection |
|---|---|---|---|
| Slow dependency | Artificial dependency delay | Dependency latency, workers, queue, circuit state | Dependency protection |
| Dependency timeout | Dependency exceeds caller timeout | Timeout count, retries | Timeout + bounded retry |
| Connection failure | Service B unreachable | Connection errors, retries | Retry + dependency protection |
| Queue saturation | Demand exceeds processing capacity | Queue utilization, rejections | Load shedding |
| Retry amplification | Retryable dependency failures | Dependency attempts vs client requests | Retry limits + backoff |
| Sustained dependency pressure | Repeated slow responses | Consecutive latency, circuit state | Circuit breaker |
| Circuit recovery | Dependency restored | Probe and state transitions | Controlled recovery |
| Readiness/liveness | Process alive but functionality unhealthy | Health/readiness responses | Readiness-based recovery |
| Bulkhead isolation | One workload exhausts its allocation | Bulkhead activity | Workload isolation |
| Invalid request | Invalid application input | HTTP status, retry count | No retry |
| Queue pressure + slow dependency | High demand + slow dependency | Workers, queue, dependency latency | Backpressure + load shedding |
| Repeated instability | Dependency repeatedly changes state | Circuit transitions, probes | Controlled state transitions |
| Combined failure | High demand + dependency slowdown | Cross-layer metrics | Multiple protections |

---

# 19. Failure Testing Loop

The complete operational loop for the lab is:

    1. Establish baseline
           ↓
    2. Inject controlled failure
           ↓
    3. Generate representative traffic
           ↓
    4. Observe system behavior
           ↓
    5. Identify constrained resources
           ↓
    6. Verify protection mechanism
           ↓
    7. Restore normal conditions
           ↓
    8. Verify recovery
           ↓
    9. Examine metrics
           ↓
    10. Record the result

The experiment is not complete simply because the failure occurred.

The experiment is complete when the failure, system response, protection behavior, and recovery can all be demonstrated with observable evidence.

---

# 20. What These Experiments Demonstrate

The scenarios collectively test whether the system can:

- detect abnormal dependency behavior
- prevent unlimited waiting
- keep processing capacity bounded
- control excess demand
- limit retry-generated traffic
- protect an unhealthy dependency
- isolate competing workloads
- distinguish deterministic failures from transient failures
- recover through a controlled process
- expose measurable evidence of system behavior

The objective is not to demonstrate that failures can be prevented entirely.

The objective is to demonstrate that when failures occur, the system responds in a controlled, bounded, and observable manner.

> **A reliability mechanism is only meaningful when its behavior can be demonstrated under failure.**
