from concurrent.futures import Future
from queue import Queue, Full
from threading import Thread
import time

import requests
from flask import Flask, request, jsonify, g
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from service import (
    submit_note,
    get_all_notes,
    dependency_state,
    probe_dependency,
    States,
    create_conn_error,
)

from metrics import (
    REGISTRY,

    http_requests_total,
    http_request_duration_seconds,
    http_requests_errors_total,
    http_responses_total,
    http_requests_in_progress,

    workers_total,
    workers_busy,
    workers_available,

    queue_size,
    queue_capacity,
    queue_utilization,
    queue_rejections_total,
    queue_wait_duration_seconds,

    bulkhead_capacity,
    bulkhead_active_requests,
    bulkhead_rejections_total,

    circuit_breaker_rejections_total,

    notes_processed_total,
)


app = Flask(__name__)


NOTES_WORKERS = 4
ALL_NOTES_WORKERS = 1

NOTES_QUEUE_SIZE = 10
ALL_NOTES_QUEUE_SIZE = 10

notes_queue = Queue(maxsize=NOTES_QUEUE_SIZE)
all_notes_queue = Queue(maxsize=ALL_NOTES_QUEUE_SIZE)


workers_total.labels(bulkhead="notes").set(NOTES_WORKERS)
workers_total.labels(bulkhead="all_notes").set(ALL_NOTES_WORKERS)

workers_busy.labels(bulkhead="notes").set(0)
workers_busy.labels(bulkhead="all_notes").set(0)

workers_available.labels(bulkhead="notes").set(NOTES_WORKERS)
workers_available.labels(bulkhead="all_notes").set(ALL_NOTES_WORKERS)

queue_capacity.labels(queue="notes").set(NOTES_QUEUE_SIZE)
queue_capacity.labels(queue="all_notes").set(ALL_NOTES_QUEUE_SIZE)

queue_size.labels(queue="notes").set(0)
queue_size.labels(queue="all_notes").set(0)

queue_utilization.labels(queue="notes").set(0)
queue_utilization.labels(queue="all_notes").set(0)

bulkhead_capacity.labels(bulkhead="notes").set(NOTES_WORKERS)
bulkhead_capacity.labels(bulkhead="all_notes").set(ALL_NOTES_WORKERS)

bulkhead_active_requests.labels(bulkhead="notes").set(0)
bulkhead_active_requests.labels(bulkhead="all_notes").set(0)


@app.before_request
def observe_http_request_start():

    g.http_request_start = time.monotonic()
    g.http_method = request.method
    g.http_endpoint = request.path

    http_requests_total.labels(
        method=request.method,
        endpoint=request.path,
    ).inc()

    http_requests_in_progress.labels(
        method=request.method,
        endpoint=request.path,
    ).inc()


@app.after_request
def observe_http_request_end(response):

    method = getattr(g, "http_method", request.method)
    endpoint = getattr(g, "http_endpoint", request.path)
    request_start = getattr(g, "http_request_start", None)

    http_responses_total.labels(
        method=method,
        endpoint=endpoint,
        status=str(response.status_code),
    ).inc()

    if response.status_code >= 500:

        http_requests_errors_total.labels(
            method=method,
            endpoint=endpoint,
        ).inc()

    if request_start is not None:

        duration = time.monotonic() - request_start

        http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)

    http_requests_in_progress.labels(
        method=method,
        endpoint=endpoint,
    ).dec()

    return response


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
    ).set(size / capacity)


def worker(
    work_queue,
    queue_name,
    bulkhead_name,
):

    while True:

        function, args, future, queued_at = work_queue.get()

        queue_wait = time.monotonic() - queued_at

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

            future.set_result(function(*args))

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


for _ in range(NOTES_WORKERS):

    Thread(
        target=worker,
        args=(notes_queue, "notes", "notes"),
        daemon=True,
    ).start()


for _ in range(ALL_NOTES_WORKERS):

    Thread(
        target=worker,
        args=(all_notes_queue, "all_notes", "all_notes"),
        daemon=True,
    ).start()


def dependency_probe_loop():

    while True:

        if dependency_state.is_under_pressure():

            if dependency_state.should_probe():

                print(
                    "Service B under pressure -> "
                    "running dependency probe now",
                    flush=True,
                )

                result = probe_dependency()

                print(
                    f"Dependency probe result: {result}",
                    flush=True,
                )

        time.sleep(1)


Thread(
    target=dependency_probe_loop,
    daemon=True,
).start()


@app.get("/metrics")
def metrics():

    return (
        generate_latest(REGISTRY),
        200,
        {"Content-Type": CONTENT_TYPE_LATEST},
    )


@app.get("/")
def root():

    return "WELCOME TO RECIEVER SERVICE"


@app.get("/favicon.ico")
def favicon():

    return jsonify({"f": "ok"})


@app.get("/health")
def health():

    return jsonify({
        "status": "healthy",
        "service": "reciever",
    })


def response_body(response):

    try:
        return response.json()

    except ValueError:
        return {
            "raw": response.text,
        }


@app.post("/notes")
def notes():

    try:

        data = request.get_json()

        if not data:

            return jsonify({
                "error": "word is required",
                "source": "reciever",
            }), 400

        state = dependency_state.get_state()

        if state != States.CLOSED:

            print(
                f"Service B Current state: {state}",
                flush=True,
            )

            circuit_breaker_rejections_total.labels(
                dependency="saver"
            ).inc()

            return jsonify({
                "error": "Service B is unavailable",
                "state": state.value,
                "source": "reciever",
            }), 503

        if dependency_state.is_under_pressure():

            circuit_breaker_rejections_total.labels(
                dependency="saver"
            ).inc()

            return jsonify({
                "error": "Dependency Service B is under pressure",
                "source": "reciever",
            }), 503

        future = Future()

        try:

            notes_queue.put_nowait(
                (
                    submit_note,
                    (data,),
                    future,
                    time.monotonic(),
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

            return jsonify({
                "error": "Service A is overloaded",
                "source": "reciever",
            }), 503

        response = future.result()
        notes_processed_total.inc()
        return (
            jsonify(response_body(response)),
            response.status_code,
        )

    except requests.exceptions.Timeout:

        return jsonify({
            "source": "reciever",
            "error": "Service B [Saver App] timed out",
        }), 504

    except requests.exceptions.ConnectionError:

        return jsonify({
            "source": "reciever",
            "error": "Service B [Saver App] unavailable",
        }), 503

    except Exception as error:

        return jsonify({
            "source": "reciever",
            "error": str(error),
        }), 500


@app.get("/all_notes")
def all_notes():

    try:

        future = Future()

        try:

            all_notes_queue.put_nowait(
                (
                    get_all_notes,
                    (),
                    future,
                    time.monotonic(),
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

            return jsonify({
                "error": "Service A is overloaded",
                "source": "reciever",
            }), 503

        response = future.result()
        return (
            jsonify(response_body(response)),
            response.status_code,
        )

    except requests.exceptions.Timeout:

        return jsonify({
            "source": "reciever",
            "error": "Service B [Saver App] timed out",
        }), 504

    except requests.exceptions.ConnectionError:

        return jsonify({
            "source": "reciever",
            "error": "Service B [Saver App] unavailable",
        }), 503

    except Exception as error:

        return jsonify({
            "source": "reciever",
            "error": str(error),
        }), 500


@app.get("/conn_error")
def conn_error():
    return jsonify(
        create_conn_error()
    ), 503


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
    )
