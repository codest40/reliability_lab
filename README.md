# SRE Reliability Lab

A small distributed system built to demonstrate **Site Reliability Engineering concepts through real failure, saturation, recovery, observability, and alerting scenarios**.
The project intentionally keeps the application simple so the focus remains on **system that remains predictable under load and failure, with measurable reliability, controlled degradation, actionable observability, and verified recovery**.

## Aim
The experiments provide controlled conditions from which reliability behavior can be observed, investigated, and understood.

    Failure Scenario
           ↓
        Detect
           ↓
        Collect
           ↓
       Visualize
           ↓
        Analyze
           ↓
         Study
           ↓
    Understand reliability behavior

## Architecture

    Client
      |
      v
    Receiver A
      |
      v
    Saver B

            +-------------------+
            |   Observability   |
            |                   |
            | Prometheus        |
            | Grafana           |
            | Alloy             |
            | Loki              |
            | Alertmanager      |
            | Notify            |
            +-------------------+

## Project Documentation
| Document | Purpose |
|---|---|
| `docs/architecture.md` | System architecture, services, request flow, and system boundaries |
| `docs/reliability.md` | Reliability mechanisms including retries, circuit breakers, bulkheads, queues, and protection |
| `docs/failure-scenarios.md` | Controlled failure experiments, observed behavior, protection, and recovery |
| `docs/observability.md` | Application, dependency, queue, worker, retry, circuit-breaker, probe, and bulkhead metrics |
| `docs/monitoring.md` | Prometheus, Grafana, Loki, Alloy, Alertmanager, and notification pipeline |
| `docs/experiment_flow.md` | End-to-end experiment, observation, investigation, and incident flow |

## Core SRE Concepts Demonstrated
    Capacity
    Backpressure
    Queueing
    Saturation
    Retries
    Retry Amplification
    Timeouts
    Circuit Breakers
    Bulkheads
    Load Shedding
    Partial Failure
    Dependency Failure
    Observability
    Alerting
    Incident Investigation
    Recovery

## Running the Lab
| Script | Purpose |
|---|---|
| [`send.py`](send.py) | Send individual requests with normal, slow, error, and timeout behaviors |
| [`load.py`](load.py) | Generate concurrent load against the Receiver |
| [`chaos.py`](chaos.py) | Run multi-stage controlled chaos experiments |
| [`t.sh`](t.sh) | Run simple shell-based traffic experiments |
| [`start.sh`](start.sh) | Orchestrate the concurrent experiment suite |
| [`init.sh`](init.sh) | Initialize and start the lab containers |

### Common Commands
    # Initialize the lab, then run all experiments
    bash start.sh init experiment

    # Run experiments against an already-running lab
    bash start.sh experiment

    # Same as experiment
    bash start.sh

`start.sh` launches the experiment suite concurrently, combining request generation, load testing, traffic tests, and chaos experiments to exercise the reliability mechanisms under controlled conditions.


- The purpose of the monitoring stack is this.
> **When the system is under pressure, can the metrics and logs explain what happened?**
For example:

    Increased latency
           |
           +--> Queue wait increasing?
           |
           +--> Dependency latency increasing?
           |
           +--> Workers saturated?
           |
           +--> Retries increasing?
           |
           +--> Circuit breaker opening?
           |
           +--> Requests being shed?
           |
           +--> Dependency recovering?

- The system should make it possible to move from:
    "The API is slow."
to:
    "Service B became slow, which occupied all Service A workers,
    increased queue wait time, filled the bounded queue,
    triggered load shedding, increased 503 responses,
    and eventually caused the circuit breaker to open."

- That is the central purpose of the Reliability Lab.
