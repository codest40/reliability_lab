# SRE Reliability Lab — Monitoring

## 1. Purpose

The Reliability Lab monitoring system turns system behavior into operational signals that can be:

    collected
       ↓
    stored
       ↓
    visualized
       ↓
    evaluated
       ↓
    alerted
       ↓
    investigated
       ↓
    acted upon

The monitoring stack combines:

- application metrics
- container logs
- time-series monitoring
- log aggregation
- dashboards
- alert evaluation
- alert routing
- notification handling

The monitoring architecture is intentionally small, but represents the major operational path used in a distributed service environment.

The individual application metrics are documented separately in `observability.md`.

The reliability mechanisms that produce many of those signals are documented in `reliability.md`.

This document focuses on the **monitoring system itself and how its components interact**.

---

# 2. Monitoring Architecture

The complete monitoring architecture is:

                         APPLICATION SERVICES
                  +-------------+-------------+
                  |             |             |
                  v             v             v
              Receiver A     Saver B       Notify
                  |             |             |
                  |             |             |
                  +------+------|-------------+
                         |      |
                         |      |
                    application logs
                         |
                         v
                       Docker
                         |
                         v
                       Alloy
                         |
                         v
                        Loki
                         |
                         v
                      Grafana


                  Receiver A metrics
                         |
                         v
                    Prometheus
                         |
                  +------+------+
                  |             |
                  v             v
               Grafana     Alertmanager
                               |
                               v
                             Notify
                               |
                               v
                         Notification
                               |
                               v
                              Logs
                               |
                               v
                             Alloy
                               |
                               v
                              Loki
                               |
                               v
                            Grafana

The architecture therefore contains two primary telemetry pipelines:

    Metrics Pipeline

    Application
        ↓
    Prometheus
        ↓
    Grafana

and:

    Logs Pipeline

    Docker containers
        ↓
    Alloy
        ↓
    Loki
        ↓
    Grafana

Alerting creates an additional operational path:

    Prometheus
        ↓
    Alertmanager
        ↓
    Notify
        ↓
    logs
        ↓
    Alloy
        ↓
    Loki
        ↓
    Grafana

---

# 3. Monitoring Components

The monitoring stack consists of:

| Component | Responsibility |
|---|---|
| Receiver A | Generates application and reliability metrics and application logs |
| Saver B | Provides dependency/application behavior and logs |
| Notify | Receives Alertmanager webhooks and records notification events |
| Prometheus | Scrapes, stores, queries, and evaluates metrics |
| Alertmanager | Receives and routes firing alerts |
| Alloy | Discovers Docker containers and collects container logs |
| Loki | Stores and queries logs |
| Grafana | Provides dashboards, visualization, and investigation |
| Docker | Provides the container runtime and container log source |

Each component has a distinct operational responsibility.

The components are intentionally separated so that:

    collection
    storage
    visualization
    detection
    routing
    notification

remain independent concerns.

---

# 4. Metrics Pipeline

The primary metrics pipeline is:

    Receiver A
        |
        | GET /metrics
        v
    Prometheus
        |
        +----------------+
        |                |
        v                v
    Grafana         Alert Rules
                         |
                         v
                    Alertmanager
                         |
                         v
                       Notify

Service A exposes its Prometheus-compatible metrics through:

    GET /metrics

Prometheus periodically scrapes the endpoint.

Prometheus then stores the resulting time series and makes them available for:

- PromQL queries
- Grafana dashboards
- alert rule evaluation
- operational analysis

The application therefore exposes telemetry while Prometheus owns collection and evaluation.

---

# 5. Prometheus

Prometheus is the metrics collection and time-series monitoring component.

Its responsibilities in the lab include:

- discovering the configured monitoring targets
- scraping application metrics
- storing time-series data
- evaluating PromQL expressions
- evaluating alerting rules
- sending firing alerts to Alertmanager
- serving metric queries to Grafana

Conceptually:

    Application
         |
         | /metrics
         v
    Prometheus
         |
         +----> time series
         |
         +----> PromQL
         |
         +----> alert rules
         |
         v
    operational signals

Prometheus does not determine how an operator should visualize every signal.

Grafana consumes the stored metrics and provides the operational interface.

---

# 6. Prometheus Scraping Model

The application exposes metrics rather than actively pushing them to Prometheus.

The model is:

    Service A
       |
       | exposes /metrics
       |
       v
    Prometheus
       |
       | periodic scrape
       v
    time-series storage

This pull-based model provides a clear boundary between:

    metric instrumentation

and:

    metric collection

The application is therefore responsible for generating meaningful measurements.

Prometheus is responsible for periodically collecting those measurements.

---

# 7. PromQL and Operational Signals

Prometheus stores raw metric measurements.

Operational meaning is often derived from those measurements using PromQL.

Conceptually:

    raw metric
        ↓
      PromQL
        ↓
    derived signal
        ↓
    dashboard / alert

Examples of operational signals include:

    request rate
    error rate
    latency
    queue utilization
    worker saturation
    retry activity
    dependency failure rate
    circuit state

A metric therefore represents an observation.

A PromQL expression can turn that observation into an operational condition.

For example:

    metric
      ↓
    rate / ratio / percentile
      ↓
    operational interpretation
