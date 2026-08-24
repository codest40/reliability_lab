# SRE Reliability Lab — Architecture

## 1. Purpose

The Reliability Lab is a deliberately small distributed system consisting of two services:

    Client
      |
      v
    Service A — Receiver
      |
      | HTTP
      v
    Service B — Saver

The application functionality is intentionally simple.

A client submits a note to Service A, and Service A communicates with Service B to validate and persist the note.

The simplicity of the application allows the project to focus on the behavior of the system as a distributed service rather than on business functionality.

---

# 2. System Components

The system contains three primary components:

    Client
       |
       v
    Receiver A
       |
       v
    Saver B

Each component has a distinct responsibility.

---

## 2.1 Client

The client represents an external caller of the system.

It sends HTTP requests to Service A.

The client is not responsible for interacting directly with Service B.

For the main workflow, the client submits notes through:

    POST /notes

The client may also be used by the project's load and failure experiments to generate controlled traffic.

---

## 2.2 Service A — Receiver

Service A is the client-facing application.

Its primary responsibility is to receive requests and coordinate processing.

The main responsibilities of Service A are:

- expose the HTTP API
- receive client requests
- perform request admission
- place accepted work into processing queues
- execute work using workers
- communicate with Service B
- expose application and reliability metrics

Service A is therefore the entry point into the system.

---

## 2.3 Service B — Saver

Service B is the internal dependency used by Service A.

Its primary responsibilities are:

- validate notes
- persist notes
- return stored notes
- expose service health information
- expose service readiness information
- provide controlled failure behavior for experiments

Service B is not directly exposed as the primary client-facing API.

---

# 3. Service Interfaces

The services communicate using HTTP.

## Service A

The primary client-facing endpoint is:

    POST /notes

Service A also exposes:

    GET /all_notes

for retrieving application data.

Metrics are exposed through:

    GET /metrics

---

## Service B

Service B exposes:

    POST /validate
    GET  /get_notes
    GET  /health
    GET  /readiness

The `/validate` endpoint is used by Service A for the normal note-processing path.

The remaining endpoints support application access, service state inspection, and recovery validation.

---

# 4. Request Flow

A normal note request follows this path:

    Client
       |
       | POST /notes
       v
    Service A
       |
       | admission
       v
    Processing Queue
       |
       | worker
       v
    Service A Worker
       |
       | HTTP POST /validate
       v
    Service B
       |
       | validation / persistence
       v
    Service A
       |
       v
    Client

The important architectural boundary is between Service A and Service B.

Service A owns the client request.

Service B provides a downstream capability required to complete that request.

---

# 5. Internal Processing Model

Service A does not process all accepted requests directly inside the HTTP request handler.

The application separates request admission from request processing.

Conceptually:

    HTTP request
         |
         v
    Service A
         |
         v
    Work Queue
         |
         v
    Worker
         |
         v
    Dependency call
         |
         v
    Response

The queue therefore acts as the boundary between incoming HTTP work and the worker pool.

---

# 6. Worker Pool

Service A currently uses a fixed worker pool.

The current configuration is:

    WORKERS = 5

Conceptually:

              Service A

        +-------------------+
        |    Worker Pool    |
        |                   |
        | W1  W2  W3  W4 W5 |
        +---------+---------+
                  |
                  v
              Service B

The workers execute accepted application work and communicate with Service B as part of the processing path.

The worker pool represents the processing capacity available to the application.

The reliability implications of this finite capacity are documented separately in `reliability.md`.

---

# 7. Processing Queue

Service A places accepted work into a bounded queue.

The current configuration is:

    QUEUE_SIZE = 10

Conceptually:

    Incoming requests
           |
           v
    +---------------+
    | Queue         |
    |               |
    | maximum: 10   |
    +-------+-------+
            |
            v
       Worker Pool

The queue separates request arrival from worker execution.

It provides a finite amount of buffering between incoming demand and available workers.

The behavior of the queue under saturation is covered in the reliability and failure-scenario documentation.

---

# 8. Workload Separation

Service A contains separate processing capacity for its different workloads.

The current design is:

    Service A
       |
       +---- /notes
       |       |
       |       +---- 4 workers
       |
       +---- /all_notes
               |
               +---- 1 worker

This creates separate processing paths for the two workloads.

The purpose and reliability implications of this separation are documented in `reliability.md`.

---

# 9. Dependency Boundary

Service A communicates with Service B over HTTP.

The normal dependency path is:

    Service A
        |
        | POST /validate
        v
    Service B

Service A therefore depends on the availability and responsiveness of Service B for the note-processing workflow.

Service B can be placed into different operating conditions during experiments.

The failure behavior and resulting protection mechanisms are documented separately.

---

# 10. Service B Data Path

Service B is responsible for the note data path.

The normal operation is:

    Service A
       |
       | /validate
       v
    Service B
       |
       +--> validate note
       |
       +--> persist note
       |
       v
    response

The application therefore keeps business-data handling inside Service B while Service A remains responsible for request coordination.

---

# 11. Health and Readiness Interfaces

Service B exposes two operational endpoints:

    /health
    /readiness

These endpoints provide different operational interfaces for inspecting the state of the service.

Service A uses the readiness interface as part of its dependency recovery mechanism.

The conceptual distinction between health and readiness, and why it matters for reliability, is documented in `reliability.md`.

---

# 12. Failure Injection Boundary

Controlled failure behavior is implemented inside Service B.

This gives the lab a dedicated dependency whose behavior can be changed without modifying Service A.

Conceptually:

    Service A
       |
       v
    Service B
       |
       +---- normal
       +---- slow
       +---- error
       +---- timeout

This makes Service B the primary failure-injection point for dependency-related experiments.

The individual experiments are documented in `failure-scenarios.md`.

---

# 13. Observability Boundary

Service A exposes:

    GET /metrics

The metrics describe application and reliability behavior occurring within the system.

Conceptually:

    Service A
       |
       +---- HTTP API
       |
       +---- processing
       |
       +---- dependency interaction
       |
       +---- reliability state
       |
       +---- metrics

The individual metrics and their interpretation are documented in `observability.md`.

---

# 14. Container-Level Deployment

The services are independently runnable applications.

The development environment uses Docker Compose to run the system as multiple containers.

Conceptually:

    Docker Compose
          |
          +----------------+
          |                |
          v                v
    Receiver A          Saver B
      :5000               :5001

Service A reaches Service B through the Compose network using the service name:

    saver

The application therefore communicates using the same service-to-service model inside the container environment rather than relying on localhost between containers.

---

# 15. Network Boundary

The main communication paths are:

    Client
       |
       | HTTP
       v
    Receiver A
       |
       | HTTP
       v
    Saver B

The client communicates with Service A.

Service A communicates with Service B.

The client does not need to communicate directly with Service B for the normal application workflow.

This creates a simple dependency chain:

    Client
       ↓
       A
       ↓
       B

---

# 16. Architectural Boundaries

The project deliberately maintains several clear boundaries.

### Client boundary

External traffic enters through Service A.

### Processing boundary

HTTP request handling is separated from worker-based processing.

### Dependency boundary

Service B is treated as a separate service rather than an internal module of Service A.

### Workload boundary

Different Service A workloads have separate processing capacity.

### Failure-injection boundary

Dependency failures are introduced primarily through Service B.

### Observability boundary

Reliability metrics are exposed separately through the metrics endpoint.

These boundaries make it possible to examine different parts of the system independently.

---

# 17. Complete Architecture

The complete system can be represented as:

                         CLIENT
                            |
                            | HTTP
                            v
                 +----------------------+
                 |     RECEIVER A       |
                 |                      |
                 |  HTTP API            |
                 |       |              |
                 |       v              |
                 |  Work Queues         |
                 |       |              |
                 |       v              |
                 |  Worker Pools        |
                 |       |              |
                 |       +------+-------+
                 |              |
                 |          Metrics
                 |              |
                 +--------------+
                                |
                                | HTTP
                                |
                                v
                 +----------------------+
                 |       SAVER B        |
                 |                      |
                 |  /validate           |
                 |  /get_notes          |
                 |  /health             |
                 |  /readiness          |
                 |                      |
                 |  Data Storage        |
                 |  Failure Injection   |
                 +----------------------+

The primary application path is:

    Client
      ↓
    Receiver A
      ↓
    Worker / processing path
      ↓
    Saver B
      ↓
    Receiver A
      ↓
    Client

---

# 18. Architectural Summary

The Reliability Lab is intentionally built around a very small distributed architecture:

    Client
      ↓
    Service A
      ↓
    Service B

Service A is responsible for receiving and processing client work.

Service B provides the downstream note-processing capability.

The system introduces explicit boundaries around:

    HTTP traffic
    queued work
    worker execution
    workload processing
    dependency communication
    failure injection
    observability

The architecture is deliberately small so that the project's complexity comes from **system behavior under failure**, rather than from a large number of infrastructure components.

The reliability mechanisms built around this architecture are documented in `reliability.md`.

The metrics used to observe those mechanisms are documented in `observability.md`.

The experiments used to test those mechanisms are documented in `failure-scenarios.md`.
