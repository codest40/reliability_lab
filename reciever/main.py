from concurrent.futures import Future
from queue import Queue, Full
from threading import Thread
import time
import requests
from flask import Flask, request, jsonify
from service import submit_note, get_all_notes, dependency_state, probe_dependency

app = Flask(__name__)

# Service A capacity
WORKERS = 5

# Maximum number of requests waiting for a worker
QUEUE_SIZE = 10
work_queue = Queue(maxsize=QUEUE_SIZE)


def worker():
    """
    Continuously take work from the queue
    and execute it.
    """

    while True:
        function, args, future = work_queue.get()

        try:
            result = function(*args)
            future.set_result(result)

        except Exception as error:
            future.set_exception(error)

        finally:
            work_queue.task_done()


def dependency_probe_loop():
    while True:
        if dependency_state.is_under_pressure():
          if dependency_state.should_probe():
              probe_dependency()
        time.sleep(2)

for _ in range(WORKERS):
    Thread(
        target=worker,
        daemon=True
    ).start()

Thread(target=dependency_probe_loop, daemon=True).start()

@app.get("/")
def root():
    return "WELCOME TO RECIEVER APP"


@app.get("/favicon.ico")
def favicon():
    return jsonify({
        "f": "ok"
    })


@app.get("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "reciever"
    })


@app.post("/notes")
def notes():

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "word is required",
            "source": "reciever"
        }), 400

    if dependency_state.is_under_pressure():
        return jsonify({
            "error": "Dependency Service B is under pressure",
            "source": "reciever"
        }), 503

    future = Future()
    try:
        work_queue.put_nowait(
            (submit_note, (data,), future)
        )

        #work_queue.put(
        #    (submit_note, (data,), future)
        #)

    except Full:
        return jsonify({
            "error": "Service A is overloaded",
            "source": "reciever"
        }), 503

    print(
        f"Queue before adding request: "
        f"{work_queue.qsize()}"
    )

    print(
        f"Queue after adding request: "
        f"{work_queue.qsize()}"
    )

    try:
        response = future.result()
    except requests.exceptions.Timeout:
        return jsonify({
            "source": "reciever",
            "error": "Service B [Saver App] timed out"
        }), 504

    except requests.exceptions.ConnectionError:
        return jsonify({
            "source": "reciever",
            "error": "Service B [Saver App] unavailable"
        }), 503

    except Exception as error:
        return jsonify({
            "source": "reciever",
            "error": str(error)
        }), 500

    return jsonify(
        response.json()
    ), response.status_code


@app.get("/all_notes")
def all_notes():

    future = Future()

    try:
      work_queue.put_nowait(
          (get_all_notes, (), future)
      )

    except Full:
        return jsonify({
            "error": "Service A is overloaded",
            "source": "reciever"
        }), 503
    try:
        response = future.result()

    except requests.exceptions.Timeout:
        return jsonify({
            "source": "reciever",
            "error": "Service B [Saver App] timed out"
        }), 504

    except requests.exceptions.ConnectionError:
        return jsonify({
            "source": "reciever",
            "error": "Service B [Saver App] unavailable"
        }), 503

    except Exception as error:
        return jsonify({
            "source": "reciever",
            "error": str(error)
        }), 500

    return jsonify(
        response.json()
    ), response.status_code


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
