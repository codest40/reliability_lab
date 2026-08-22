# SRE Concepts Demonstrated

This project is a small two-service system designed to demonstrate practical
SRE fundamentals through controlled experiments.

The focus is not on building a complex application, but on understanding what
happens when a service reaches its capacity or when one of its dependencies
starts failing.

---

## System Model

    Client
      |
      v
    Service A (Receiver)
      |
      | HTTP request
      v
    Service B (Saver)
      |
      v
    Data


Service A is the primary system being observed.

Service B is a dependency that can be deliberately made slow, unavailable,
or faulty to study how Service A behaves under failure and load.

1. Dependency Failure

Service A depends on Service B to complete requests.

If Service B becomes unavailable, A cannot complete the operation normally.

The system explicitly distinguishes this from an application validation error.

    Service A
        |
        X
    Service B unavailable

Service A returns:

    HTTP 503 Service Unavailable

This demonstrates that a dependency failure can propagate through the
request path and must be handled deliberately.

2. Dependency Latency

Service B can deliberately take several seconds to process a request.

For example:

    Service B processing time = 4 seconds

This means Service A's workers remain occupied while waiting for B.

The important lesson is:

A slow dependency consumes Service A's processing capacity.

A dependency does not have to be completely down to cause an outage.

3. Request Capacity

Service A was configured with:

    Workers = 5

This means only five requests can actively execute at the same time.

If each request requires approximately four seconds of dependency processing,
the theoretical throughput is approximately:

    5 workers / 4 seconds
    ≈ 1.25 requests/sec

This is a capacity measurement, not inherently a good or bad number.

It becomes meaningful when compared with incoming demand.

4. Demand

Demand is the amount of work clients are asking Service A to perform.

For example:

    Demand   = 2 requests/sec
    Capacity = 1.25 requests/sec

Since:

    Demand > Capacity

the system cannot keep up.

Work begins accumulating.

5. Queueing

Service A was given a bounded queue:

    Queue size = 10

Together with five workers:

    5 processing
    +
    10 waiting
    =
    15 requests in the system

When Service B takes approximately four seconds per request, requests
accumulate behind the five active workers.

Observed behavior:

    Requests 1-5    → ~4 seconds
    Requests 6-10   → ~8 seconds
    Requests 11-15  → ~12 seconds

This demonstrates how queueing increases request latency when demand
approaches or exceeds service capacity.

6. Backpressure

Backpressure occurs when a downstream dependency or limited processing
capacity prevents a service from accepting work at the rate it is arriving.

In this system:

    Client demand
         ↓
    Service A
         ↓
    5 workers
         ↓
    Service B is slow
         ↓
    workers remain occupied
         ↓
    queue grows

The queue provides a temporary buffer between incoming demand and available
processing capacity.

Backpressure prevents the system from pretending that unlimited work can be
processed immediately.

7. Bounded Queue

The queue is intentionally bounded:

    QUEUE_SIZE = 10

This prevents the system from accumulating unlimited pending work.

Without a bound, sustained overload could produce:

    large queue
        ↓
    increasing memory usage
        ↓
    increasing latency
        ↓
    timeouts
        ↓
    retries
        ↓
    even more load

A bounded queue creates an explicit limit on how much work the service is
willing to hold.

8. Load Shedding

When the queue becomes full, Service A does not wait indefinitely.

Instead:

    Queue full
       ↓
    Reject new request
       ↓
    HTTP 503

This is load shedding.

The service deliberately refuses additional work because it is already
saturated.

The goal is controlled degradation rather than allowing overload to consume
the entire service.

9. Experimental Result

With:

    Workers      = 5
    Queue        = 10
    B processing = ~4 seconds
    Requests     = 20

the system observed:

    15 requests → accepted and completed
     5 requests → rejected immediately with HTTP 503

The accepted requests completed in approximately:

    4 seconds
    8 seconds
    12 seconds

The rejected requests failed almost immediately rather than waiting behind
an already saturated system.

10. Reliability Trade-off

This experiment demonstrates an important SRE principle:

Reliability is not simply the percentage of requests that return HTTP 200.

Accepting every request can produce extremely high latency and eventually
cause cascading failures.

Rejecting some requests early can protect the remaining capacity of the
system.

    Accept everything
          ↓
    queue grows
          ↓
    latency increases
          ↓
    timeouts
          ↓
    possible cascading failure

    versus:

    Detect saturation
          ↓
    shed excess load
          ↓
    protect available capacity
          ↓
    fast, controlled failures

Whether load shedding is actually better depends on the service's SLOs,
client expectations, retry behavior, and business requirements.

SRE Principles Demonstrated

This small system provides practical demonstrations of:

Service dependencies
Dependency failure
Dependency latency
Request capacity
Incoming demand
Concurrency limits
Queueing
Bounded queues
Backpressure
Load shedding
Controlled failure
Latency under saturation
Capacity vs. demand
Failure isolation
Reliability trade-offs

The purpose of the project is to make these concepts observable through
experiments rather than treating them as purely theoretical SRE concepts.


## 11. Two Sources of Latency
As the system becomes more realistic, latency can come from different parts
of the request path.

### Queue Waiting
When all workers are busy, new requests wait in the bounded queue.

```text
Client
  ↓
Service A
  ↓
Queue
  ↓
Worker
  ↓
Service B

Retry Waiting

A request can also spend additional time waiting because Service A retries
a failed dependency call.

For example:

Attempt 1 → timeout
    ↓
Attempt 2 → timeout
    ↓
Attempt 3 → success

Each retry can add more time to the original request.

This is retry-related latency.

Combined Effect

A request can experience both:

Queue waiting
      ↓
Worker starts
      ↓
Service B call
      ↓
Timeout
      ↓
Retry
      ↓
Timeout
      ↓
Retry
      ↓
Success

Therefore:

Total client-observed latency can include both time spent waiting in
Service A's queue and time spent retrying Service B.
So improving one source of latency does not
necessarily solve the overall latency problem. For example, reducing queue size may reduce queue waiting, while aggressive
retries can still make requests slow.

```

12. Retry Amplification

Retries can also increase the amount of traffic sent to a struggling
dependency.
```
With:

MAX_RETRIES = 2

one logical request can generate up to:

3 dependency attempts

Therefore:

5 client requests
      ↓
up to 15 requests to Service B

If B is already slow or overloaded, immediate retries can make the problem
worse.

B becomes slow
    ↓
A times out
    ↓
A retries immediately
    ↓
B receives more requests
    ↓
B becomes more overloaded
    ↓
more timeouts
    ↓
more retries

The project intentionally demonstrates this behavior before introducing
exponential backoff, allowing the effect of retries to be observed directly.
```

##
We used ThreadPoolExec because ThreadPoolExecutor is actually the better production-style abstraction, but we switched to raw Thread because we wanted the queue to be visible and directly controlled for this SRE experiment.
