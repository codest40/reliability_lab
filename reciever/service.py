import os
import time
import threading
from enum import Enum

import requests

from metrics import (
    dependency_requests_total,
    dependency_request_duration_seconds,
    dependency_errors_total,
    dependency_timeouts_total,
    dependency_connections_errors_total,

    retries_total,
    retry_attempts_total,
    retry_exhausted_total,
    retry_delay_seconds,

    circuit_breaker_state,
    circuit_breaker_transitions_total,
    circuit_breaker_rejections_total,
    circuit_breaker_open_total,
    circuit_breaker_probe_total,
    circuit_breaker_probe_success_total,
    circuit_breaker_probe_failure_total,

    dependency_probes_total,
    dependency_probe_success_total,
    dependency_probe_failure_total,
    dependency_probe_duration_seconds,

    dependency_health,
    dependency_under_pressure,

    notes_processed_total,
    notes_saved_total,
    notes_invalid_total,
)


# ============================================================
# CONFIGURATION
# ============================================================

SAVER_URL = os.getenv(
    "SAVER_URL",
    "http://localhost:5001",
)

MAX_RETRIES = 2

SLOW_THRESHOLD = 2.0

CONSECUTIVE_SLOW_LIMIT = 3

PROBE_INTERVAL = 5


DEPENDENCY = "saver"

OPERATION_VALIDATE = "validate"

OPERATION_GET_NOTES = "get_notes"


# ============================================================
# CIRCUIT BREAKER STATES
# ============================================================

class States(Enum):

    CLOSED = "closed"

    OPEN = "open"

    HALF_OPEN = "half_open"


# ============================================================
# CIRCUIT BREAKER
# ============================================================

class DependencyState:

    def __init__(self):

        self.state = States.CLOSED

        self.consecutive_slow = 0

        self.under_pressure = False

        self.last_probe = 0

        self.lock = threading.Lock()

        circuit_breaker_state.labels(
            dependency=DEPENDENCY
        ).set(0)

        dependency_health.labels(
            dependency=DEPENDENCY
        ).set(1)

        dependency_under_pressure.labels(
            dependency=DEPENDENCY
        ).set(0)


    # ========================================================
    # STATE METRIC VALUE
    # ========================================================

    def state_value(self, state):

        if state == States.CLOSED:
            return 0

        if state == States.OPEN:
            return 1

        return 2


    # ========================================================
    # STATE TRANSITION
    # ========================================================

    def transition(self, new_state):

        old_state = self.state

        if old_state == new_state:
            return

        self.state = new_state

        circuit_breaker_state.labels(
            dependency=DEPENDENCY
        ).set(
            self.state_value(new_state)
        )

        circuit_breaker_transitions_total.labels(
            dependency=DEPENDENCY,
            from_state=old_state.value,
            to_state=new_state.value,
        ).inc()

        print(
            f"STATE: "
            f"{old_state.value.upper()} → "
            f"{new_state.value.upper()}"
        )

        if new_state == States.OPEN:

            circuit_breaker_open_total.labels(
                dependency=DEPENDENCY
            ).inc()

            dependency_health.labels(
                dependency=DEPENDENCY
            ).set(0)

        elif new_state == States.CLOSED:

            dependency_health.labels(
                dependency=DEPENDENCY
            ).set(1)


    # ========================================================
    # RECORD DEPENDENCY LATENCY
    # ========================================================

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

                    dependency_under_pressure.labels(
                        dependency=DEPENDENCY
                    ).set(1)

                    print("B UNDER PRESSURE")

                    if self.state == States.CLOSED:

                        self.transition(
                            States.OPEN
                        )

            else:

                self.consecutive_slow = 0

                if self.under_pressure:

                    print("B RECOVERED")

                self.under_pressure = False

                dependency_under_pressure.labels(
                    dependency=DEPENDENCY
                ).set(0)

                print(
                    f"B latency: {duration:.2f}s | "
                    "NORMAL"
                )


    # ========================================================
    # PRESSURE
    # ========================================================

    def is_under_pressure(self):

        with self.lock:

            return self.under_pressure


    # ========================================================
    # PROBE SCHEDULER
    # ========================================================

    def should_probe(self):

        with self.lock:

            if self.state != States.OPEN:

                return False

            now = time.monotonic()

            if (
                now - self.last_probe
                >= PROBE_INTERVAL
            ):

                self.last_probe = now

                self.transition(
                    States.HALF_OPEN
                )

                return True

            return False


    # ========================================================
    # PROBE SUCCESS
    # ========================================================

    def probe_succeeded(self):

        with self.lock:

            self.consecutive_slow = 0

            self.under_pressure = False

            dependency_under_pressure.labels(
                dependency=DEPENDENCY
            ).set(0)

            self.transition(
                States.CLOSED
            )


    # ========================================================
    # PROBE FAILURE
    # ========================================================

    def probe_failed(self):

        with self.lock:

            self.transition(
                States.OPEN
            )


    # ========================================================
    # CURRENT STATE
    # ========================================================

    def get_state(self):

        with self.lock:

            return self.state


dependency_state = DependencyState()


# ============================================================
# DEPENDENCY PROBE
# ============================================================

def probe_dependency():

    print(
        "PROBE: Testing Service B readiness..."
    )

    start = time.monotonic()

    dependency_probes_total.labels(
        dependency=DEPENDENCY
    ).inc()

    circuit_breaker_probe_total.labels(
        dependency=DEPENDENCY
    ).inc()

    try:

        response = requests.get(
            f"{SAVER_URL}/readiness",
            timeout=10,
        )

        duration = (
            time.monotonic() - start
        )

        dependency_probe_duration_seconds.labels(
            dependency=DEPENDENCY
        ).observe(duration)

        if (
            response.ok
            and duration < SLOW_THRESHOLD
        ):

            dependency_probe_success_total.labels(
                dependency=DEPENDENCY
            ).inc()

            circuit_breaker_probe_success_total.labels(
                dependency=DEPENDENCY
            ).inc()

            print(
                f"PROBE: Service B recovered "
                f"({duration:.2f}s)"
            )

            dependency_state.probe_succeeded()

            return True

        dependency_probe_failure_total.labels(
            dependency=DEPENDENCY
        ).inc()

        circuit_breaker_probe_failure_total.labels(
            dependency=DEPENDENCY
        ).inc()

        print(
            f"PROBE: Service B still under pressure "
            f"({duration:.2f}s)"
        )

        dependency_state.probe_failed()

        return False


    except (
        requests.exceptions.Timeout,
        requests.exceptions.ConnectionError,
    ):

        duration = (
            time.monotonic() - start
        )

        dependency_probe_duration_seconds.labels(
            dependency=DEPENDENCY
        ).observe(duration)

        dependency_probe_failure_total.labels(
            dependency=DEPENDENCY
        ).inc()

        circuit_breaker_probe_failure_total.labels(
            dependency=DEPENDENCY
        ).inc()

        print(
            "PROBE: Service B unavailable"
        )

        dependency_state.probe_failed()

        return False


# ============================================================
# SUBMIT NOTE
# ============================================================

def submit_note(data):

    timeout = data.get(
        "timeout",
        10,
    )

    attempts = 0

    while attempts <= MAX_RETRIES:

        attempts += 1

        retry_attempts_total.labels(
            dependency=DEPENDENCY,
            operation=OPERATION_VALIDATE,
        ).inc()

        print(
            f"Attempt: {attempts}"
        )

        start = time.monotonic()

        dependency_requests_total.labels(
            dependency=DEPENDENCY,
            operation=OPERATION_VALIDATE,
        ).inc()

        try:

            response = requests.post(
                f"{SAVER_URL}/validate",
                json=data,
                timeout=timeout,
            )

            duration = (
                time.monotonic() - start
            )

            dependency_request_duration_seconds.labels(
                dependency=DEPENDENCY,
                operation=OPERATION_VALIDATE,
            ).observe(duration)

            dependency_state.record_latency(
                duration
            )

            if response.status_code == 400:

                notes_invalid_total.inc()

            elif response.status_code == 200:

                notes_saved_total.inc()

            return response


        except requests.exceptions.Timeout:

            duration = (
                time.monotonic() - start
            )

            dependency_request_duration_seconds.labels(
                dependency=DEPENDENCY,
                operation=OPERATION_VALIDATE,
            ).observe(duration)

            dependency_timeouts_total.labels(
                dependency=DEPENDENCY,
                operation=OPERATION_VALIDATE,
            ).inc()

            dependency_errors_total.labels(
                dependency=DEPENDENCY,
                operation=OPERATION_VALIDATE,
            ).inc()

            if attempts > MAX_RETRIES:

                retry_exhausted_total.labels(
                    dependency=DEPENDENCY,
                    operation=OPERATION_VALIDATE,
                ).inc()

                raise

            retries_total.labels(
                dependency=DEPENDENCY,
                operation=OPERATION_VALIDATE,
            ).inc()

            delay = (
                0.5
                if attempts == 1
                else 1.0
            )

            retry_delay_seconds.labels(
                dependency=DEPENDENCY,
                operation=OPERATION_VALIDATE,
            ).observe(delay)

            print(
                f"Retrying after {delay}s"
            )

            time.sleep(delay)


        except requests.exceptions.ConnectionError:

            duration = (
                time.monotonic() - start
            )

            dependency_request_duration_seconds.labels(
                dependency=DEPENDENCY,
                operation=OPERATION_VALIDATE,
            ).observe(duration)

            dependency_connections_errors_total.labels(
                dependency=DEPENDENCY,
                operation=OPERATION_VALIDATE,
            ).inc()

            dependency_errors_total.labels(
                dependency=DEPENDENCY,
                operation=OPERATION_VALIDATE,
            ).inc()

            if attempts > MAX_RETRIES:

                retry_exhausted_total.labels(
                    dependency=DEPENDENCY,
                    operation=OPERATION_VALIDATE,
                ).inc()

                raise

            retries_total.labels(
                dependency=DEPENDENCY,
                operation=OPERATION_VALIDATE,
            ).inc()

            delay = (
                0.5
                if attempts == 1
                else 1.0
            )

            retry_delay_seconds.labels(
                dependency=DEPENDENCY,
                operation=OPERATION_VALIDATE,
            ).observe(delay)

            print(
                f"Retrying after {delay}s"
            )

            time.sleep(delay)


    raise RuntimeError(
        "Retry loop ended unexpectedly"
    )


# ============================================================
# GET ALL NOTES
# ============================================================

def get_all_notes():

    start = time.monotonic()

    dependency_requests_total.labels(
        dependency=DEPENDENCY,
        operation=OPERATION_GET_NOTES,
    ).inc()

    try:

        response = requests.get(
            f"{SAVER_URL}/get_notes",
            timeout=10,
        )

        duration = (
            time.monotonic() - start
        )

        dependency_request_duration_seconds.labels(
            dependency=DEPENDENCY,
            operation=OPERATION_GET_NOTES,
        ).observe(duration)

        return response


    except requests.exceptions.Timeout:

        duration = (
            time.monotonic() - start
        )

        dependency_request_duration_seconds.labels(
            dependency=DEPENDENCY,
            operation=OPERATION_GET_NOTES,
        ).observe(duration)

        dependency_timeouts_total.labels(
            dependency=DEPENDENCY,
            operation=OPERATION_GET_NOTES,
        ).inc()

        dependency_errors_total.labels(
            dependency=DEPENDENCY,
            operation=OPERATION_GET_NOTES,
        ).inc()

        raise


    except requests.exceptions.ConnectionError:

        duration = (
            time.monotonic() - start
        )

        dependency_request_duration_seconds.labels(
            dependency=DEPENDENCY,
            operation=OPERATION_GET_NOTES,
        ).observe(duration)

        dependency_connections_errors_total.labels(
            dependency=DEPENDENCY,
            operation=OPERATION_GET_NOTES,
        ).inc()

        dependency_errors_total.labels(
            dependency=DEPENDENCY,
            operation=OPERATION_GET_NOTES,
        ).inc()

        raise
