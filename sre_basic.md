#
```
dependency failure
dependency latency
capacity
queueing
timeouts
retries
backpressure
load shedding


How many requests/sec can A successfully complete?
How long does A take to complete them?
What happens when B becomes slow?
What happens when B goes down?
What happens when demand exceeds A's capacity?
What happens when clients retry?
Does retry traffic make the situation worse?
When should A reject work? → load shedding
How do we detect all of this? → metrics/observability
What do we consider acceptable? → SLO
How do we respond when it's not acceptable? → alerting/incident response
