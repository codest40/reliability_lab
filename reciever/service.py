import os
import time
import threading

import requests


SAVER_URL = os.getenv(
    "SAVER_URL",
    "http://localhost:5001"
)

MAX_RETRIES = 2
SLOW_THRESHOLD = 2.0
CONSECUTIVE_SLOW_LIMIT = 3
PROBE_INTERVAL = 5


class DependencyState:

    def __init__(self):
        self.consecutive_slow = 0
        self.under_pressure = False
        self.last_probe = 0
        self.lock = threading.Lock()

    def record_latency(self, duration):

        with self.lock:

            if duration >= SLOW_THRESHOLD:

                self.consecutive_slow += 1

                print(
                    f"B latency: {duration:.2f}s | "
                    f"SLOW #{self.consecutive_slow}"
                )

                if (
                    self.consecutive_slow
                    >= CONSECUTIVE_SLOW_LIMIT
                ):
                    self.under_pressure = True

                    print(
                        "B UNDER PRESSURE"
                    )

            else:

                self.consecutive_slow = 0

                if self.under_pressure:
                    print(
                        "B RECOVERED"
                    )

                self.under_pressure = False

                print(
                    f"B latency: {duration:.2f}s | "
                    "NORMAL"
                )

    def is_under_pressure(self):

        with self.lock:
            return self.under_pressure

    def should_probe(self):

        with self.lock:

            now = time.monotonic()

            if now - self.last_probe >= PROBE_INTERVAL:

                self.last_probe = now

                return True

            return False


dependency_state = DependencyState()


def probe_dependency():

    print("PROBE: Testing Service B...")

    start = time.monotonic()

    try:

        response = requests.get(
            f"{SAVER_URL}/health",
            timeout=2
        )

        duration = time.monotonic() - start

        if (
            response.ok
            and duration < SLOW_THRESHOLD
        ):

            print(
                f"PROBE: Service B recovered "
                f"({duration:.2f}s)"
            )

            with dependency_state.lock:
                dependency_state.consecutive_slow = 0
                dependency_state.under_pressure = False

            return True

        print(
            f"PROBE: Service B still under pressure "
            f"({duration:.2f}s)"
        )

        return False

    except (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError
    ):

        print(
            "PROBE: Service B still unavailable"
        )

        return False


def submit_note(data):

    timeout = data.get("timeout", 10)

    attempts = 0

    while attempts <= MAX_RETRIES:

        try:

            attempts += 1

            print(
                f"Attempt: {attempts}"
            )

            start = time.monotonic()

            response = requests.post(
                f"{SAVER_URL}/validate",
                json=data,
                timeout=timeout,
            )

            duration = (
                time.monotonic() - start
            )

            dependency_state.record_latency(
                duration
            )

            return response

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError
        ):

            if attempts > MAX_RETRIES:
                raise

            if attempts == 1:
                time.sleep(0.5)

            elif attempts == 2:
                time.sleep(1)

    raise RuntimeError(
        "Retry loop ended unexpectedly"
    )


def get_all_notes():

    return requests.get(
        f"{SAVER_URL}/get_notes"
    )
