# SRE Reliability Lab — Reliability

## 1. Reliability Goal

The goal of this project is not to make every request succeed.

The goal is to keep the system useful and predictable when demand exceeds capacity or when a dependency becomes slow or unavailable.

The project deliberately demonstrates that reliability sometimes means:

- rejecting work
- limiting concurrency
- allowing some requests to fail
- stopping retries
- protecting a dependency
- isolating workloads
- recovering gradually

A system that accepts everything and eventually collapses is not necessarily more reliable than one that rejects excess work quickly.

---

## 2. Demand vs Capacity

The system has a finite processing capacity.

Service A has:

    5 workers
    10 queued requests

Therefore, Service A cannot process unlimited concurrent work.

If Service B takes approximately 4 seconds per request:

    5 workers / 4 seconds
    ≈ 1.25 requests/second

is approximately the maximum sustained processing rate of the worker pool for that workload.

The important lesson is:

> Reliability starts with understanding capacity.

If incoming demand is higher than the rate at which work can be completed, backlog grows.

Eventually the queue becomes full.

At that point, the system has to make a decision.

---

## 3. Queueing and Backpressure

The receiver does not immediately execute every request.

Requests enter a bounded queue:

    Client
       |
       v
    Service A
       |
       v
     Queue
       |
       +--> Worker
       +--> Worker
       +--> Worker
       +--> Worker
       +--> Worker

The queue provides temporary buffering when demand exceeds the number of immediately available workers.

But the queue is intentionally bounded.

    QUEUE_SIZE = 10

This is important because an unlimited queue would simply move the failure somewhere else.

Instead of:

    queue grows forever
            |
            v
    latency grows forever
            |
            v
    memory pressure
            |
            v
    system collapse

we use:

    queue reaches capacity
            |
            v
    reject new work
            |
            v
    HTTP 503

This is backpressure.

The system communicates to the caller:

> I cannot safely accept this work right now.

---

## 4. Load Shedding

When the queue is full, Service A uses:

    work_queue.put_nowait(...)

instead of blocking.

If the queue is full:

    Queue.Full
        |
        v
    HTTP 503

The request therefore fails immediately rather than waiting indefinitely.

This creates an important reliability trade-off.

### Without load shedding

More requests can eventually succeed, but latency can become extremely high.

### With load shedding

Some requests fail immediately, but accepted requests have a much better chance of completing within a predictable time.

The system therefore trades:

    higher success rate

for:

    better latency protection
    + bounded resource usage
    + predictable failure

This is a deliberate reliability decision.

---

## 5. Dependency Latency Is a Reliability Problem

Service A depends on Service B.

A request is therefore not simply:

    Client → A

It is effectively:

    Client
       |
       v
    Service A
       |
       v
    Service B

If B becomes slow, A's workers remain occupied waiting for B.

For example:

    B latency = 4 seconds

A worker can spend approximately 4 seconds processing a single request.

With only five workers:

    5 workers
       |
       +--> waiting for B
       +--> waiting for B
       +--> waiting for B
       +--> waiting for B
       +--> waiting for B

A can become saturated even though A itself is not doing computationally expensive work.

This demonstrates an important SRE principle:

> A dependency can consume your capacity simply by being slow.

---

## 6. Queue Latency and Dependency Latency

The project deliberately exposes two different sources of request latency:

    Total request latency
            |
            +----------------+
            |                |
            v                v
    Queue waiting       Dependency waiting

### Queue waiting

The request waits for a worker.

Measured by:

    queue_wait_duration_seconds

### Dependency waiting

A worker is already processing the request but is waiting for Service B.

Measured by:

    dependency_request_duration_seconds

These are different problems.

A request can have:

    1 second queue wait
    +
    4 second dependency wait
    =
    5 seconds total latency

Understanding where latency is accumulated is more useful than simply observing that the endpoint is slow.

---

## 7. Retry Policy

Retries are implemented in Service A because A is the caller of B.

The retry policy is intentionally small:

    Maximum retries = 2
    Maximum attempts = 3

Retries are only performed for failures that may be transient:

    timeout
    connection failure

We do not retry client errors such as:

    400
    validation failure
    invalid request

because retrying an invalid request does not make the request valid.

The basic model is:

    A → B
        |
        +-- timeout
        |
        +-- retry
        |
        +-- retry
        |
        +-- fail

---

## 8. Why Immediate Retries Are Dangerous

Retries initially used no delay.

That deliberately demonstrated a failure amplification problem.

If many clients experience a dependency failure simultaneously:

    100 requests
          |
          v
    100 failures
          |
          v
    100 immediate retries
          |
          v
    B receives more traffic
          |
          v
    B becomes even more overloaded
          |
          v
    more failures

The retry mechanism can therefore increase demand precisely when the dependency has the least capacity.

This is retry amplification.

Retries are useful, but uncontrolled retries can make an incident worse.

---

## 9. Exponential Backoff

The retry delay was then changed to:

    retry #1 → 0.5 seconds
    retry #2 → 1 second

The idea is to avoid immediately sending another request to an already struggling dependency.

The sequence becomes:

    attempt 1
       |
       +-- failure
       |
      0.5s
       |
    attempt 2
       |
       +-- failure
       |
      1.0s
       |
    attempt 3

Backoff does not guarantee recovery.

It simply reduces the pressure created by retries.

This demonstrates why retry policy is part of reliability engineering rather than simply an HTTP client feature.

---

## 10. Dependency Pressure Detection

The receiver does not immediately declare Service B unhealthy because of one slow request.

Instead, it tracks consecutive slow requests.

The current experiment uses:

    SLOW_THRESHOLD = 2 seconds
    CONSECUTIVE_SLOW_LIMIT = 3

Therefore:

    1.0s → normal
    1.2s → normal

    4.0s → slow #1
    4.0s → slow #2
    4.0s → slow #3
                  |
                  v
           B under pressure

An isolated slow request therefore does not immediately change system behavior.

The system is looking for evidence of sustained dependency pressure.

---

## 11. Circuit Breaker

Once sustained dependency pressure is detected, Service A opens the circuit.

The state model is:

    CLOSED
       |
       | sustained dependency pressure
       v
    OPEN
       |
       | probe interval
       v
    HALF_OPEN
       |
       +---- success ----> CLOSED
       |
       +---- failure ----> OPEN

### CLOSED

Normal operation.

Requests are allowed to reach Service B.

### OPEN

Service B is considered under pressure.

Normal requests are rejected instead of continuing to send traffic to B.

### HALF_OPEN

Service A temporarily tests whether B has recovered.

This prevents Service A from immediately releasing the entire backlog of rejected traffic against B.

---

## 12. Why HALF_OPEN Exists

A major recovery problem is that detecting recovery is not enough.

Suppose B was overloaded and A rejected 1,000 requests.

If B suddenly becomes healthy and A immediately allows all 1,000 requests through:

    B recovers
        |
        v
    1,000 requests released
        |
        v
    traffic spike
        |
        v
    B overloaded again

The system can repeatedly oscillate between failure and recovery.

The `HALF_OPEN` state provides a controlled transition.

Instead:

    OPEN
     |
     | wait
     v
    HALF_OPEN
     |
     | small health/readiness probe
     v
    CLOSED

Only after the probe succeeds does normal traffic resume.

---

## 13. Readiness vs Liveness

Service B exposes:

    /health
    /readiness

These endpoints have different purposes.

### `/health`

Answers:

> Is the service process alive?

A successful health check does not necessarily mean that the functionality required by Service A is ready.

### `/readiness`

Answers a stronger question:

> Can Service B currently perform the basic operation required for normal service?

For this project, readiness performs a lightweight dependency-related check by exercising the data-loading path without creating a note.

This is preferable to using `/health` as the circuit-breaker recovery signal because:

    process alive

does not necessarily mean:

    request path healthy

The distinction becomes important when a service is running but its dependencies, storage, or required functionality are unavailable.

---

## 14. Bulkhead Isolation

The project also separates worker capacity between workloads.

The design is:

    Service A
       |
       +---- /notes
       |       |
       |       +--> 4 workers
       |
       +---- /all_notes
               |
               +--> 1 worker

This prevents one workload from consuming all available worker capacity.

Without isolation:

    /notes traffic
          |
          v
    all workers consumed
          |
          v
    /all_notes cannot execute

With a bulkhead:

    /notes → 4 workers
    /all_notes → 1 worker

A failure or traffic spike in `/notes` therefore does not automatically prevent `/all_notes` from making progress.

The concept comes from isolating failure domains.

---

## 15. Reliability vs Success Rate

One of the most important lessons from the experiments is:

> More successful requests does not automatically mean a more reliable system.

Consider two systems.

### System A

    100 requests
    100 succeed
    average latency = 30 seconds

### System B

    100 requests
    70 succeed
    30 rejected immediately
    average accepted-request latency = 4 seconds

Depending on the application's requirements, System B may provide a much better user experience and protect the system from collapse.

This is why reliability must be evaluated using multiple dimensions:

    success
    latency
    availability
    capacity
    resource usage
    failure behavior
    recovery behavior

---

## 16. Controlled Failure Is Part of the Design

This project intentionally introduces:

    slow dependency
    dependency timeout
    dependency errors
    connection failures
    queue saturation
    request rejection
    retry amplification
    dependency pressure
    circuit opening
    dependency recovery

The purpose is not simply to prove that the system can work.

The purpose is to observe:

    failure
       ↓
    system response
       ↓
    resource impact
       ↓
    client impact
       ↓
    recovery

This makes reliability something that can be tested experimentally rather than assumed.

---

## 17. Reliability Principles Demonstrated

The implementation demonstrates several practical SRE principles:

### Bound work

Use finite worker and queue capacity.

### Protect the dependency

Stop sending normal traffic when sustained dependency pressure is detected.

### Fail fast

Reject work that cannot be safely accepted instead of allowing unlimited waiting.

### Retry selectively

Retry only failures that may be transient.

### Back off

Avoid immediately increasing traffic against a struggling dependency.

### Isolate workloads

Use bulkheads so one workload cannot consume all capacity.

### Detect sustained problems

Do not react to a single slow request when sustained evidence is required.

### Probe recovery

Test recovery independently before reopening normal traffic.

### Make failure observable

Expose metrics for requests, queues, workers, dependencies, retries, circuit state, probes, and bulkheads.

---

## 18. The Core Reliability Model

The project can ultimately be summarized as:

                     CLIENT DEMAND
                          |
                          v
                  +---------------+
                  |   Service A   |
                  +---------------+
                          |
                 capacity controls
                          |
              +-----------+-----------+
              |                       |
              v                       v
          admission                queue
          control                 bounded
              |                       |
              |                       v
              |                    workers
              |                       |
              +-----------+-----------+
                          |
                          v
                    Service B
                          |
              +-----------+-----------+
              |                       |
              v                       v
           latency                failures
              |                       |
              +-----------+-----------+
                          |
                          v
                  dependency state
                          |
              +-----------+-----------+
              |           |           |
              v           v           v
            CLOSED      OPEN      HALF_OPEN
                          |           |
                          |           v
                          |        probe
                          |           |
                          +-----------+

The central idea is simple:

> **When demand or dependency pressure exceeds what the system can safely handle, the system must adapt rather than continue accepting work until it collapses.**
