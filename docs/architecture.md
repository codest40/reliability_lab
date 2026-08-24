# SRE Reliability Lab — Architecture

## 1. Purpose

This project is a deliberately small distributed system designed to demonstrate practical **Site Reliability Engineering (SRE)** concepts.

The application is intentionally simple:

    Client
      │
      ▼
    ┌──────────────────────┐
    │      Receiver A      │
    │                      │
    │  HTTP API            │
    │  Worker Pool         │
    │  Queues              │
    │  Retries             │
    │  Circuit Breaker     │
    │  Backpressure        │
    │  Load Shedding       │
    │  Bulkheads            │
    │  Metrics             │
    └──────────┬───────────┘
               │
               │ HTTP
               ▼
    ┌──────────────────────┐
    │       Saver B        │
    │                      │
    │  /validate           │
    │  /get_notes          │
    │  /health             │
    │  /readiness          │
    │                      │
    │  Failure Injection   │
    └──────────────────────┘

The application is not intended to be a feature-rich notes application.

The notes functionality exists mainly to provide a realistic request path on which reliability behavior can be observed.

The actual purpose of the project is to demonstrate how a service behaves when:

- demand exceeds capacity
- a dependency becomes slow
- a dependency becomes unavailable
- requests begin accumulating
- retries amplify dependency traffic
- queues become full
- requests are rejected
- a dependency is declared under pressure
- a circuit opens
- the dependency is probed for recovery
- the circuit transitions through `HALF_OPEN`
- isolated workloads are protected using bulkheads
- system behavior is measured using application-specific metrics

---

# 2. Services

The system contains two services.

## Service A — Receiver

Service A is the client-facing service.

It accepts requests from clients and is responsible for controlling how much work is allowed to enter the system.

Its responsibilities include:

- receiving HTTP requests
- validating basic request input
- admitting or rejecting work
- placing accepted work into bounded queues
- processing work using workers
- calling Service B
- retrying transient dependency failures
- detecting sustained dependency latency
- applying backpressure
- shedding load when capacity is exhausted
- protecting the dependency with a circuit breaker
- probing the dependency for recovery
- isolating workloads with a bulkhead
- exposing reliability metrics

Service A therefore represents the main SRE control point in the system.

---

## Service B — Saver

Service B is the dependency of Service A.

It performs the actual note validation and persistence.

Important endpoints are:

    GET  /health
    GET  /readiness
    POST /validate
    GET  /get_notes

Service B also contains controlled failure behavior so that the system can be deliberately placed under different conditions.

For example:

    normal
    slow
    error
    timeout

This makes it possible to reproduce failure scenarios rather than waiting for naturally occurring failures.

---

# 3. Request Flow

A normal note request follows this path:

    Client
      │
      │ POST /notes
      ▼
    Receiver A
      │
      │ admission checks
      ▼
    Bounded Queue
      │
      │ worker available
      ▼
    Worker
      │
      │ submit_note()
      ▼
    Saver B
      │
      │ POST /validate
      ▼
    Validation / persistence
      │
      ▼
    Response
      │
      ▼
    Receiver A
      │
      ▼
    Client

The important part of this architecture is that **the request does not automatically get unlimited access to downstream resources**.

Service A deliberately introduces limits.

Those limits allow us to observe what happens when demand becomes greater than the system's ability to process that demand.

---

# 4. Service A Capacity Model

Service A currently uses:

    WORKERS = 5
    QUEUE_SIZE = 10

This creates a deliberately bounded processing system.

Conceptually:

                      Service A

                 ┌───────────────┐
                 │   5 Workers   │
                 │               │
                 │ W1 W2 W3 W4 W5│
                 └───────┬───────┘
                         │
                         │
                 ┌───────▼───────┐
                 │ Queue: 10     │
                 │ maximum       │
                 └───────┬───────┘
                         │
                         │
                      Clients

The workers represent active processing capacity.

The queue represents temporary buffering capacity.

The queue is intentionally bounded.

This is important.

An unbounded queue can hide overload by allowing requests to accumulate indefinitely.

A bounded queue makes overload visible.

Once both:

    workers

and

    queue capacity

are exhausted, Service A cannot safely accept more work.

The request is rejected with:

    HTTP 503

This is load shedding.

---

# 5. Why the Queue Exists

The queue separates **request arrival** from **request processing**.

Without a queue, incoming requests would compete directly for workers.

With a queue:

    Client demand
          │
          ▼
       Queue
          │
          ▼
       Workers
          │
          ▼
       Dependency

The queue allows temporary bursts of traffic to be absorbed.

However, the queue does not create additional processing capacity.

If Service B takes approximately:

    4 seconds/request

and Service A has:

    5 workers

then the approximate downstream processing capacity is:

    5 / 4

    ≈ 1.25 requests/second

Increasing the queue does not increase this throughput.

It only allows more requests to wait.

This creates an important SRE distinction:

> **Buffering capacity is not processing capacity.**

---

# 6. Queue Waiting

A request can experience latency before it even reaches Service B.

For example:

    Request arrives
         │
         ▼
    Queue waiting
         │
         ▼
    Worker starts
         │
         ▼
    Service B processing
         │
         ▼
    Response

Therefore total request latency can contain multiple components.

At a simplified level:

    Total latency
        =
    queue waiting
    +
    worker processing
    +
    dependency latency
    +
    retry waiting
    +
    network overhead

This is important because a slow user request does not necessarily mean Service B itself was slow.

The request may have spent most of its time waiting for capacity in Service A.

---

# 7. Dependency Interaction

Service A calls Service B through:

    POST /validate

The dependency call is intentionally treated as an unreliable external resource.

Service A therefore does not assume:

    B will always respond quickly

or:

    B will always be available

Instead, Service A observes dependency behavior and adapts.

The dependency can exhibit:

    Normal
       │
       ▼
    Slow
       │
       ▼
    Sustained pressure
       │
       ▼
    Circuit opens
       │
       ▼
    Probe recovery
       │
       ▼
    Closed

This is one of the central reliability behaviors demonstrated by the project.

---

# 8. Retry Architecture

Retries are implemented in Service A because Service A is the caller.

The initial retry policy is intentionally small:

    MAX_RETRIES = 2

Therefore the maximum number of attempts is:

    Attempt 1
    Attempt 2
    Attempt 3

Retries are only applied to transient failures such as:

    Timeout
    ConnectionError

Client-side validation errors are not retried.

For example:

    HTTP 400

should not cause Service A to repeatedly send the same invalid request.

---

# 9. Retry Backoff

Immediate retries were deliberately tested first.

That behavior can create:

    A
    │
    ├── attempt 1 → B
    ├── attempt 2 → B
    └── attempt 3 → B

If B is already struggling, those additional requests can increase its workload.

The implementation therefore adds delay between retries:

    Retry #1
       │
       └── wait 0.5s

    Retry #2
       │
       └── wait 1s

The project uses this simple delay to demonstrate the principle of retry backoff without introducing a more sophisticated retry framework.

The important concept is:

> A retry is additional demand on the dependency.

Retries therefore have to be treated as part of the system's capacity model.

---

# 10. Retry Amplification

Suppose 10 client requests arrive.

If every request is attempted once:

    10 client requests
            │
            ▼
    10 dependency requests

If every request requires three attempts:

    10 client requests
            │
            ▼
    up to 30 dependency requests

Therefore:

    client demand
    +
    retry demand
    =
    actual dependency demand

This is why retries can make an existing dependency failure worse.

Retries improve reliability for transient failures, but excessive retries can create a feedback loop.

---

# 11. Dependency Pressure Detection

Service A does not immediately declare Service B unhealthy because of one slow request.

Instead, it measures dependency latency.

The current threshold is:

    SLOW_THRESHOLD = 2 seconds

A request taking longer than that is considered slow.

The system then tracks **consecutive** slow requests.

The current threshold is:

    CONSECUTIVE_SLOW_LIMIT = 3

Therefore:

    1 slow request
            │
            ▼
    continue observing

    2 consecutive slow requests
            │
            ▼
    continue observing

    3 consecutive slow requests
            │
            ▼
    B considered under pressure

This avoids reacting to a single isolated latency spike.

---

# 12. Circuit Breaker

Service A maintains three states:

    CLOSED
    OPEN
    HALF_OPEN

## CLOSED

Normal operation.

Requests are allowed to reach Service B.

    Client
      │
      ▼
    Service A
      │
      ▼
    Service B

---

## OPEN

Service B has demonstrated sustained pressure or failure.

Service A stops sending normal requests to B.

New requests are rejected quickly:

    Client
      │
      ▼
    Service A
      │
      X
    Service B

This prevents Service A from continuously adding pressure to an unhealthy dependency.

---

## HALF_OPEN

After the circuit has remained open for the configured interval, Service A performs a controlled recovery test.

    OPEN
     │
     │ probe
     ▼
    HALF_OPEN

Normal client traffic is still not allowed through simply because the probe has started.

The system is testing whether B has recovered.

If the probe succeeds:

    HALF_OPEN
         │
         ▼
      CLOSED

If the probe fails:

    HALF_OPEN
         │
         ▼
       OPEN

This prevents Service A from immediately releasing a large amount of rejected traffic onto a recovering dependency.

---

# 13. Dependency Readiness

Service A probes:

    GET /readiness

rather than sending a real note through:

    POST /validate

This is important because a recovery probe should not create unnecessary business traffic.

Service B's readiness endpoint performs a lightweight dependency/application check and reports whether the service is ready to serve normal work.

The distinction is:

    /health

answers:

> "Is the process/service alive?"

while:

    /readiness

answers:

> "Is the service ready to handle normal work?"

This allows Service A's circuit breaker to make a more meaningful recovery decision than simply checking whether the HTTP process is alive.

---

# 14. Backpressure

Backpressure is implemented by refusing to continue accepting work when the downstream system is already demonstrating sustained pressure.

The architecture therefore allows the system to move from:

    Normal demand

to:

    Dependency pressure detected

to:

    Admission restricted

to:

    Circuit open

This protects the system from continuously accumulating work that it cannot process.

The goal is not to make every request succeed.

The goal is to prevent uncontrolled degradation of the entire service.

---

# 15. Load Shedding

Load shedding occurs when Service A cannot safely accept additional work.

For example:

    5 workers busy
    +
    10 queue slots occupied
    =
    no remaining capacity

A new request receives:

    HTTP 503

instead of waiting indefinitely.

This creates a deliberate trade-off:

    Without load shedding:

    more requests accepted
            ↓
    more waiting
            ↓
    higher latency
            ↓
    possible resource exhaustion

versus:

    With load shedding:

    some requests rejected
            ↓
    bounded workload
            ↓
    controlled latency
            ↓
    service remains responsive

This project uses load shedding to demonstrate that **fewer successful requests can sometimes represent better system reliability** if the alternative is uncontrolled degradation.

---

# 16. Bulkhead Architecture

The project also separates the capacity allocated to different workloads.

The design is:

    Service A
    │
    ├── /notes
    │     └── 4 workers
    │
    └── /all_notes
          └── 1 worker

The purpose is isolation.

Without a bulkhead, a large volume of `/notes` requests could consume all workers and prevent `/all_notes` from receiving processing capacity.

With the bulkhead:

    /notes traffic
         │
         └── 4-worker capacity


    /all_notes traffic
         │
         └── 1-worker capacity

A failure or traffic spike in one workload therefore does not automatically consume the entire service capacity of another workload.

This is the same fundamental principle as physical bulkheads in a ship:

> Contain failure so one area does not sink everything else.

---

# 17. Failure Injection

Service B contains controlled failure behavior.

This allows experiments to reproduce specific failure modes.

Examples include:

### Slow dependency

    action=slow

Service B intentionally delays the request.

This allows us to observe:

- dependency latency
- queue buildup
- worker saturation
- request latency
- consecutive slow detection
- circuit opening
- load shedding

### Dependency error

    action=error

Service B returns an error.

This allows retry and error-handling behavior to be examined.

### Dependency timeout

    action=timeout

Service B intentionally takes longer than the caller's timeout.

This allows timeout handling and retry behavior to be observed.

The failure injector is therefore part of the laboratory rather than application business logic.

---

# 18. Observability Boundary

Service A exposes a dedicated:

    GET /metrics

endpoint.

The project intentionally exposes **custom application and reliability metrics** rather than relying on generic Python runtime metrics.

The metrics describe the behavior that matters to the reliability experiments:

    HTTP traffic
    Dependency behavior
    Workers
    Queues
    Retries
    Circuit breaker
    Probes
    Bulkheads
    Application outcomes

This allows the system's reliability mechanisms to be observed quantitatively.

---

# 19. Reliability Control Loop

The architecture can ultimately be viewed as a feedback loop:

                     ┌───────────────┐
                     │    Client     │
                     └───────┬───────┘
                             │
                             ▼
                     ┌───────────────┐
                     │  Service A    │
                     │               │
                     │ Admission     │
                     │ Queue         │
                     │ Workers       │
                     └───────┬───────┘
                             │
                             ▼
                     ┌───────────────┐
                     │   Service B   │
                     └───────┬───────┘
                             │
                             ▼
                        Observe
                             │
                             ▼
                  ┌────────────────────┐
                  │ Reliability signals │
                  │                    │
                  │ latency            │
                  │ errors             │
                  │ saturation         │
                  │ queue depth        │
                  └──────────┬─────────┘
                             │
                             ▼
                     ┌───────────────┐
                     │   Adapt       │
                     │               │
                     │ Retry         │
                     │ Backpressure  │
                     │ Load shed     │
                     │ Circuit open  │
                     │ Probe         │
                     │ Recover       │
                     └───────────────┘

This feedback loop is the central architectural idea of the project.

Service A does not simply process requests.

It **observes system conditions and changes its behavior based on those conditions**.

---

# 20. The Reliability Model

The project demonstrates several layers of protection.

                     Incoming demand
                           │
                           ▼
                  ┌─────────────────┐
                  │ Admission check │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Bounded queue   │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Worker capacity │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Retry policy    │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Dependency B    │
                  └────────┬────────┘
                           │
                     observe latency
                           │
                           ▼
                  ┌─────────────────┐
                  │ Pressure detect │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Circuit breaker │
                  └────────┬────────┘
                           │
                           ▼
                  ┌─────────────────┐
                  │ Recovery probe  │
                  └────────┬────────┘
                           │
                           ▼
                        Recovery

Each mechanism addresses a different failure or overload problem.

| Mechanism            | Problem it addresses              |
|----------------------|------------------------------------|
| Workers              | Processing capacity                |
| Bounded queue        | Temporary bursts                   |
| Queue rejection      | Capacity exhaustion                |
| Backpressure         | Downstream pressure                |
| Load shedding        | Excess demand                      |
| Retry                | Transient dependency failure       |
| Retry backoff        | Retry amplification                |
| Circuit breaker      | Persistent dependency failure      |
| HALF_OPEN            | Controlled recovery                |
| Readiness probe      | Recovery validation                |
| Bulkhead             | Workload isolation                 |
| Metrics              | Visibility into system behavior    |
| Failure injection    | Repeatable reliability experiments |

---

# 21. What This Architecture Demonstrates

Although the application itself is intentionally small, the architecture demonstrates a number of concepts that appear in production distributed systems:

- finite service capacity
- demand versus capacity
- queueing
- worker saturation
- queue waiting
- dependency latency
- dependency failure
- timeout handling
- retry behavior
- retry amplification
- retry backoff
- backpressure
- load shedding
- circuit breakers
- `CLOSED` / `OPEN` / `HALF_OPEN` states
- controlled dependency recovery
- readiness versus liveness
- bulkhead isolation
- failure containment
- application-level observability
- reliability experimentation

The important design principle throughout the project is:

> **Do not allow demand, retries, queues, or dependency failures to grow without bounds.**

Instead, Service A continuously attempts to keep the system within a controlled operating envelope.

---

# 22. Why the System Is Deliberately Small

The project intentionally avoids unnecessary infrastructure.

There is no Kubernetes cluster, service mesh, distributed tracing platform, or large microservice ecosystem required to demonstrate these concepts.

That is deliberate.

The reliability mechanisms are easier to understand when the system contains only:

    Client
      │
      ▼
    Service A
      │
      ▼
    Service B

The complexity comes from the **behavior under failure**, not from the number of components.

This makes each experiment observable and allows individual SRE mechanisms to be introduced, tested, compared, and measured independently.

---

# 23. Final Architecture Summary

At its core, the project is a controlled experiment in protecting a service from overload and dependency failure.

The basic path is:

    Client
      ↓
    Service A
      ↓
    Bounded capacity
      ↓
    Workers
      ↓
    Service B

The reliability layer adds:

    Queue
    Backpressure
    Load shedding
    Retries
    Backoff
    Dependency pressure detection
    Circuit breaker
    Recovery probes
    Bulkheads
    Metrics

The result is a small system that demonstrates an important SRE principle:

> **Reliability is not simply making every request succeed. Reliability is controlling system behavior when demand, latency, failures, and resource constraints exceed normal operating conditions.**
