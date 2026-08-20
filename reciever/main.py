from concurrent.futures import Future
from queue import Queue
from threading import Thread

import requests
from flask import Flask, request, jsonify

from service import submit_note, get_all_notes


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


for _ in range(WORKERS):
    Thread(
        target=worker,
        daemon=True
    ).start()


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

    future = Future()

    work_queue.put(
        (submit_note, (data,), future)
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

    work_queue.put(
        (get_all_notes, (), future)
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


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
