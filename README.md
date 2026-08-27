# SRE Reliability Lab

A small distributed system built to demonstrate **Site Reliability Engineering concepts through real failure, saturation, recovery, observability, and alerting scenarios**.
The project intentionally keeps the application simple so the focus remains on **Designing a distributed system that remains predictable under load and failure, with measurable reliability, controlled degradation, actionable observability, and verified recovery.**

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
| `docs/architecture.md` | System architecture, services, request flow, and boundaries |
| `docs/reliability.md` | Reliability mechanisms: retries, circuit breaker, bulkhead, queues, and protection |
| `docs/failure-scenarios.md` | Controlled failure experiments and expected behavior |
| `docs/observability.md` | Metrics and what each metric measures |
| `docs/monitoring.md` | Prometheus, Grafana, Loki, Alloy, Alertmanager, and Notify monitoring pipeline |

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
| Script                 | Purpose                                                                  |
| ---------------------- | ------------------------------------------------------------------------ |
| [`send.py`](send.py)   | Send individual requests with normal, slow, error, and timeout behaviors |
| [`load.py`](load.py)   | Generate concurrent load against the Receiver                            |
| [`chaos.py`](chaos.py) | Run a multi-stage controlled chaos experiment                            |
| [`t.sh`](t.sh)         | Simple shell-based traffic experiments                                   |
| [`start.sh`](start.sh) | Start the lab environment                                                |
| [`init.sh`](init.sh)   | Initialize the lab environment                                           |

- bash start.sh init experiment
- bash start.sh experiment
