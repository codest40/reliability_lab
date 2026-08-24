from concurrent.futures import Future
from queue import Queue, Full
from threading import Thread
import time

import requests
from flask import ( Flask, request, jsonify )
from prometheus_client import ( generate_latest, CONTENT_TYPE_LATEST )

from service import ( submit_note, get_all_notes, dependency_state,
                     probe_dependency, States, create_conn_error )

from metrics import (
    REGISTRY,

    # HTTP
    http_requests_total,
    http_request_duration_seconds,
    http_requests_errors_total,
    http_responses_total,
    http_requests_in_progress,

    # Workers
    workers_total,
    workers_busy,
    workers_available,

    # Queues
    queue_size,
    queue_capacity,
    queue_utilization,
    queue_rejections_total,

    # Bulkhead
    bulkhead_capacity,
    bulkhead_active_requests,
    bulkhead_rejections_total,

    # Circuit Breaker
    circuit_breaker_rejections_total,

    # Application
    notes_processed_total,
)

app = Flask(__name__)

# ============================================================
# BULKHEAD CONFIGURATION
# ============================================================
NOTES_WORKERS = 4
ALL_NOTES_WORKERS = 1
NOTES_QUEUE_SIZE = 10
ALL_NOTES_QUEUE_SIZE = 10


notes_queue = Queue(
    maxsize=NOTES_QUEUE_SIZE
)

all_notes_queue = Queue(
    maxsize=ALL_NOTES_QUEUE_SIZE
)


# ============================================================
# INITIAL METRICS
# ============================================================

workers_total.labels(
    bulkhead="notes"
).set(NOTES_WORKERS)

workers_total.labels(
    bulkhead="all_notes"
).set(ALL_NOTES_WORKERS)


workers_busy.labels(
    bulkhead="notes"
).set(0)

workers_busy.labels(
    bulkhead="all_notes"
).set(0)


workers_available.labels(
    bulkhead="notes"
).set(NOTES_WORKERS)

workers_available.labels(
    bulkhead="all_notes"
).set(ALL_NOTES_WORKERS)


queue_capacity.labels(
    queue="notes"
).set(NOTES_QUEUE_SIZE)

queue_capacity.labels(
    queue="all_notes"
).set(ALL_NOTES_QUEUE_SIZE)


queue_size.labels(
    queue="notes"
).set(0)

queue_size.labels(
    queue="all_notes"
).set(0)


queue_utilization.labels(
    queue="notes"
).set(0)

queue_utilization.labels(
    queue="all_notes"
).set(0)


bulkhead_capacity.labels(
    bulkhead="notes"
).set(NOTES_WORKERS)

bulkhead_capacity.labels(
    bulkhead="all_notes"
).set(ALL_NOTES_WORKERS)


bulkhead_active_requests.labels(
    bulkhead="notes"
).set(0)

bulkhead_active_requests.labels(
    bulkhead="all_notes"
).set(0)


# ============================================================
# QUEUE METRIC HELPER
# ============================================================
def update_queue_metrics(
    queue,
    queue_name,
    capacity,
):

    size = queue.qsize()

    queue_size.labels(
        queue=queue_name
    ).set(size)

    queue_utilization.labels(
        queue=queue_name
    ).set(
        size / capacity
    )


# ============================================================
# WORKER
# ============================================================

def worker(
    work_queue,
    queue_name,
    bulkhead_name,
):

    while True:

        function, args, future, queued_at = (
            work_queue.get()
        )

        queue_wait = (
            time.monotonic()
            - queued_at
        )

        from metrics import (
            queue_wait_duration_seconds
        )

        queue_wait_duration_seconds.labels(
            queue=queue_name
        ).observe(queue_wait)

        workers_busy.labels(
            bulkhead=bulkhead_name
        ).inc()

        workers_available.labels(
            bulkhead=bulkhead_name
        ).dec()

        bulkhead_active_requests.labels(
            bulkhead=bulkhead_name
        ).inc()

        update_queue_metrics(
            work_queue,
            queue_name,
            work_queue.maxsize,
        )

        try:

            result = function(*args)

            future.set_result(result)

        except Exception as error:

            future.set_exception(error)

        finally:

            workers_busy.labels(
                bulkhead=bulkhead_name
            ).dec()

            workers_available.labels(
                bulkhead=bulkhead_name
            ).inc()

            bulkhead_active_requests.labels(
                bulkhead=bulkhead_name
            ).dec()

            work_queue.task_done()

            update_queue_metrics(
                work_queue,
                queue_name,
                work_queue.maxsize,
            )


# ============================================================
# START NOTES WORKERS
# ============================================================

for _ in range(NOTES_WORKERS):

    Thread(
        target=worker,
        args=(
            notes_queue,
            "notes",
            "notes",
        ),
        daemon=True,
    ).start()


# ============================================================
# START ALL_NOTES WORKER
# ============================================================

for _ in range(ALL_NOTES_WORKERS):

    Thread(
        target=worker,
        args=(
            all_notes_queue,
            "all_notes",
            "all_notes",
        ),
        daemon=True,
    ).start()


# ============================================================
# DEPENDENCY PROBE LOOP
# ============================================================

def dependency_probe_loop():

    while True:

        if dependency_state.is_under_pressure():

            if dependency_state.should_probe():

                probe_dependency()

        time.sleep(1)


Thread(
    target=dependency_probe_loop,
    daemon=True,
).start()


# ============================================================
# HTTP RESPONSE HELPER
# ============================================================

def record_response(
    method,
    endpoint,
    status,
):

    http_responses_total.labels(
        method=method,
        endpoint=endpoint,
        status=str(status),
    ).inc()


# ============================================================
# METRICS ENDPOINT
# ============================================================

@app.get("/metrics")
def metrics():

    return (
        generate_latest(REGISTRY),
        200,
        {
            "Content-Type":
                CONTENT_TYPE_LATEST
        },
    )


# ============================================================
# BASIC ENDPOINTS
# ============================================================

@app.get("/")
def root():
    return "WELCOME TO RECIEVER SERVICE"


@app.get("/favicon.ico")
def favicon():

    return jsonify({
        "f": "ok"
    })


@app.get("/health")
def health():

    return jsonify({
        "status": "healthy",
        "service": "reciever",
    })


# ============================================================
# POST /notes
# ============================================================

@app.post("/notes")
def notes():

    endpoint = "/notes"

    request_start = time.monotonic()

    http_requests_total.labels(
        method="POST",
        endpoint=endpoint,
    ).inc()

    http_requests_in_progress.labels(
        method="POST",
        endpoint=endpoint,
    ).inc()

    try:

        data = request.get_json()

        if not data:

            http_requests_errors_total.labels(
                method="POST",
                endpoint=endpoint,
            ).inc()

            record_response(
                "POST",
                endpoint,
                400,
            )

            return jsonify({
                "error": "word is required",
                "source": "reciever",
            }), 400


        # ====================================================
        # CIRCUIT BREAKER
        # ====================================================

        state = dependency_state.get_state()

        if state != States.CLOSED:

            circuit_breaker_rejections_total.labels(
                dependency="saver"
            ).inc()

            http_requests_errors_total.labels(
                method="POST",
                endpoint=endpoint,
            ).inc()

            record_response(
                "POST",
                endpoint,
                503,
            )

            return jsonify({
                "error":
                    "Service B is unavailable",
                "state":
                    state.value,
                "source":
                    "reciever",
            }), 503


        if dependency_state.is_under_pressure():

            circuit_breaker_rejections_total.labels(
                dependency="saver"
            ).inc()

            http_requests_errors_total.labels(
                method="POST",
                endpoint=endpoint,
            ).inc()

            record_response(
                "POST",
                endpoint,
                503,
            )

            return jsonify({
                "error":
                    "Dependency Service B "
                    "is under pressure",
                "source":
                    "reciever",
            }), 503


        # ====================================================
        # QUEUE WORK
        # ====================================================

        future = Future()

        queued_at = time.monotonic()

        try:

            notes_queue.put_nowait(
                (
                    submit_note,
                    (data,),
                    future,
                    queued_at,
                )
            )

            update_queue_metrics(
                notes_queue,
                "notes",
                NOTES_QUEUE_SIZE,
            )

        except Full:

            queue_rejections_total.labels(
                queue="notes"
            ).inc()

            bulkhead_rejections_total.labels(
                bulkhead="notes"
            ).inc()

            http_requests_errors_total.labels(
                method="POST",
                endpoint=endpoint,
            ).inc()

            record_response(
                "POST",
                endpoint,
                503,
            )

            return jsonify({
                "error":
                    "Service A is overloaded",
                "source":
                    "reciever",
            }), 503


        # ====================================================
        # WAIT FOR WORKER
        # ====================================================

        response = future.result()

        notes_processed_total.inc()

        record_response(
            "POST",
            endpoint,
            response.status_code,
        )

        if response.status_code >= 400:

            http_requests_errors_total.labels(
                method="POST",
                endpoint=endpoint,
            ).inc()

        return jsonify(
            response.json()
        ), response.status_code


    except requests.exceptions.Timeout:

        http_requests_errors_total.labels(
            method="POST",
            endpoint=endpoint,
        ).inc()

        record_response(
            "POST",
            endpoint,
            504,
        )

        return jsonify({
            "source":
                "reciever",
            "error":
                "Service B [Saver App] timed out",
        }), 504


    except requests.exceptions.ConnectionError:

        http_requests_errors_total.labels(
            method="POST",
            endpoint=endpoint,
        ).inc()

        record_response(
            "POST",
            endpoint,
            503,
        )

        return jsonify({
            "source":
                "reciever",
            "error":
                "Service B [Saver App] unavailable",
        }), 503


    except Exception as error:

        http_requests_errors_total.labels(
            method="POST",
            endpoint=endpoint,
        ).inc()

        record_response(
            "POST",
            endpoint,
            500,
        )

        return jsonify({
            "source":
                "reciever",
            "error":
                str(error),
        }), 500


    finally:

        duration = (
            time.monotonic()
            - request_start
        )

        http_request_duration_seconds.labels(
            method="POST",
            endpoint=endpoint,
        ).observe(duration)

        http_requests_in_progress.labels(
            method="POST",
            endpoint=endpoint,
        ).dec()


# ============================================================
# GET /all_notes
# ============================================================

@app.get("/all_notes")
def all_notes():

    endpoint = "/all_notes"

    request_start = time.monotonic()

    http_requests_total.labels(
        method="GET",
        endpoint=endpoint,
    ).inc()

    http_requests_in_progress.labels(
        method="GET",
        endpoint=endpoint,
    ).inc()

    try:

        future = Future()

        queued_at = time.monotonic()

        try:

            all_notes_queue.put_nowait(
                (
                    get_all_notes,
                    (),
                    future,
                    queued_at,
                )
            )

            update_queue_metrics(
                all_notes_queue,
                "all_notes",
                ALL_NOTES_QUEUE_SIZE,
            )

        except Full:

            queue_rejections_total.labels(
                queue="all_notes"
            ).inc()

            bulkhead_rejections_total.labels(
                bulkhead="all_notes"
            ).inc()

            http_requests_errors_total.labels(
                method="GET",
                endpoint=endpoint,
            ).inc()

            record_response(
                "GET",
                endpoint,
                503,
            )

            return jsonify({
                "error":
                    "Service A is overloaded",
                "source":
                    "reciever",
            }), 503


        response = future.result()

        record_response(
            "GET",
            endpoint,
            response.status_code,
        )

        if response.status_code >= 400:

            http_requests_errors_total.labels(
                method="GET",
                endpoint=endpoint,
            ).inc()

        return jsonify(
            response.json()
        ), response.status_code


    except requests.exceptions.Timeout:

        http_requests_errors_total.labels(
            method="GET",
            endpoint=endpoint,
        ).inc()

        record_response(
            "GET",
            endpoint,
            504,
        )

        return jsonify({
            "source":
                "reciever",
            "error":
                "Service B [Saver App] timed out",
        }), 504


    except requests.exceptions.ConnectionError:

        http_requests_errors_total.labels(
            method="GET",
            endpoint=endpoint,
        ).inc()

        record_response(
            "GET",
            endpoint,
            503,
        )

        return jsonify({
            "source":
                "reciever",
            "error":
                "Service B [Saver App] unavailable",
        }), 503


    except Exception as error:

        http_requests_errors_total.labels(
            method="GET",
            endpoint=endpoint,
        ).inc()

        record_response(
            "GET",
            endpoint,
            500,
        )

        return jsonify({
            "source":
                "reciever",
            "error":
                str(error),
        }), 500


    finally:

        duration = (
            time.monotonic()
            - request_start
        )

        http_request_duration_seconds.labels(
            method="GET",
            endpoint=endpoint,
        ).observe(duration)

        http_requests_in_progress.labels(
            method="GET",
            endpoint=endpoint,
        ).dec()

@app.get("/conn_error")
def conn_error():
  create_conn_error()

# ============================================================
# START SERVICE
if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
    )
