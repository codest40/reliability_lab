"""
    python chaos.py --rounds 3
    python chaos.py --workers 20
    python chaos.py --base-url http://localhost:5000
"""

import argparse
import concurrent.futures
import random
import sys
import time

import requests


DEFAULT_BASE_URL = "http://localhost:5000"


# ============================================================
# ARGUMENTS
# ============================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Run controlled SRE chaos experiments."
    )

    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Receiver service URL.",
    )

    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Number of times to run the full experiment.",
    )

    parser.add_argument(
        "--workers",
        type=int,
        default=20,
        help="Concurrent workers for saturation experiments.",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=30,
        help="HTTP client timeout in seconds.",
    )

    parser.add_argument(
        "--pause",
        type=float,
        default=2,
        help="Pause between experiment stages.",
    )

    return parser.parse_args()


# ============================================================
# OUTPUT
# ============================================================

def banner(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def result_line(name, result):
    print(
        f"{name:<32} "
        f"status={result['status']} "
        f"time={result['elapsed']:.2f}s"
    )


# ============================================================
# HTTP HELPERS
# ============================================================

def request(method, url, **kwargs):
    start = time.monotonic()

    try:
        response = requests.request(
            method,
            url,
            **kwargs,
        )

        elapsed = time.monotonic() - start

        return {
            "status": response.status_code,
            "elapsed": elapsed,
            "body": response.text[:200],
        }

    except requests.exceptions.Timeout as error:
        return {
            "status": "TIMEOUT",
            "elapsed": time.monotonic() - start,
            "body": str(error),
        }

    except requests.exceptions.ConnectionError as error:
        return {
            "status": "CONNECTION_ERROR",
            "elapsed": time.monotonic() - start,
            "body": str(error),
        }

    except requests.exceptions.RequestException as error:
        return {
            "status": "REQUEST_ERROR",
            "elapsed": time.monotonic() - start,
            "body": str(error),
        }


def post_notes(base_url, action="normal", timeout=30, word="chaos"):
    return request(
        "POST",
        f"{base_url}/notes",
        json={
            "word": word,
            "action": action,
        },
        timeout=timeout,
    )


def get_all_notes(base_url, timeout=30):
    return request(
        "GET",
        f"{base_url}/all_notes",
        timeout=timeout,
    )


# ============================================================
# BASIC TRAFFIC
# ============================================================

def normal_traffic(base_url, timeout):
    banner("1. NORMAL TRAFFIC")

    result = post_notes(
        base_url,
        action="normal",
        timeout=timeout,
        word="normal-traffic",
    )

    result_line("Normal POST /notes", result)


# ============================================================
# SLOW DEPENDENCY
# ============================================================

def slow_dependency(base_url, timeout, workers):
    banner("2. SLOW DEPENDENCY / LATENCY PRESSURE")

    def send(number):
        return post_notes(
            base_url,
            action="slow",
            timeout=timeout,
            word=f"slow-{number}",
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = [
            executor.submit(send, number)
            for number in range(workers)
        ]

        results = [
            future.result()
            for future in concurrent.futures.as_completed(futures)
        ]

    summarize_results(results)


# ============================================================
# DEPENDENCY ERROR
# ============================================================

def dependency_errors(base_url, timeout, workers):
    banner("3. DEPENDENCY / APPLICATION ERRORS")

    def send(number):
        return post_notes(
            base_url,
            action="error",
            timeout=timeout,
            word=f"error-{number}",
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = [
            executor.submit(send, number)
            for number in range(workers)
        ]

        results = [
            future.result()
            for future in concurrent.futures.as_completed(futures)
        ]

    summarize_results(results)


# ============================================================
# TIMEOUT PRESSURE
# ============================================================

def timeout_pressure(base_url, timeout, workers):
    banner("4. DEPENDENCY TIMEOUT PRESSURE")

    def send(number):
        return post_notes(
            base_url,
            action="timeout",
            timeout=timeout,
            word=f"timeout-{number}",
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = [
            executor.submit(send, number)
            for number in range(workers)
        ]

        results = [
            future.result()
            for future in concurrent.futures.as_completed(futures)
        ]

    summarize_results(results)


# ============================================================
# QUEUE / BULKHEAD SATURATION
# ============================================================

def queue_saturation(base_url, timeout, workers):
    banner("5. QUEUE + BULKHEAD SATURATION")

    print(
        f"Sending {workers} concurrent slow requests "
        "to a 4-worker / 10-slot queue..."
    )

    def send(number):
        return post_notes(
            base_url,
            action="slow",
            timeout=timeout,
            word=f"saturation-{number}",
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = [
            executor.submit(send, number)
            for number in range(1, workers + 1)
        ]

        results = [
            future.result()
            for future in concurrent.futures.as_completed(futures)
        ]

    summarize_results(results)


# ============================================================
# ALL NOTES CONTENTION
# ============================================================

def all_notes_contention(base_url, timeout, workers):
    banner("6. /all_notes QUEUE CONTENTION")

    def send(_):
        return get_all_notes(
            base_url,
            timeout=timeout,
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = [
            executor.submit(send, number)
            for number in range(workers)
        ]

        results = [
            future.result()
            for future in concurrent.futures.as_completed(futures)
        ]

    summarize_results(results)


# ============================================================
# CONNECTION ERROR
# ============================================================

def connection_error_route(base_url, timeout):
    banner("7. CONNECTION ERROR EXPERIMENT")

    result = request(
        "GET",
        f"{base_url}/conn_error",
        timeout=timeout,
    )

    result_line("/conn_error", result)


# ============================================================
# 404 / UNEXPECTED ROUTE
# ============================================================

def http_404(base_url, timeout):
    banner("8. 404 CLIENT ERROR")

    result = request(
        "GET",
        f"{base_url}/this-route-does-not-exist",
        timeout=timeout,
    )

    result_line("GET unknown route", result)


# ============================================================
# MIXED CHAOS
# ============================================================

def mixed_chaos(base_url, timeout, workers):
    banner("9. MIXED CONCURRENT CHAOS")

    actions = [
        "normal",
        "normal",
        "slow",
        "slow",
        "error",
        "timeout",
    ]

    def send(number):
        action = random.choice(actions)

        return post_notes(
            base_url,
            action=action,
            timeout=timeout,
            word=f"mixed-{number}-{action}",
        )

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers
    ) as executor:

        futures = [
            executor.submit(send, number)
            for number in range(1, workers + 1)
        ]

        results = [
            future.result()
            for future in concurrent.futures.as_completed(futures)
        ]

    summarize_results(results)


# ============================================================
# RESULTS
# ============================================================

def summarize_results(results):
    counts = {}

    for result in results:
        status = str(result["status"])
        counts[status] = counts.get(status, 0) + 1

    print("Results:")

    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")


# ============================================================
# HEALTH CHECK
# ============================================================

def check_service(base_url, timeout):
    banner("SERVICE CHECK")

    result = request(
        "GET",
        f"{base_url}/health",
        timeout=timeout,
    )

    result_line("GET /health", result)

    if result["status"] != 200:
        print()
        print("Receiver service is not healthy.")
        print("Start the lab before running chaos experiments.")
        sys.exit(1)


# ============================================================
# EXPERIMENT RUNNER
# ============================================================

def run_round(args, round_number):
    banner(f"CHAOS ROUND {round_number}/{args.rounds}")

    normal_traffic(
        args.base_url,
        args.timeout,
    )

    time.sleep(args.pause)

    slow_dependency(
        args.base_url,
        args.timeout,
        args.workers,
    )

    time.sleep(args.pause)

    dependency_errors(
        args.base_url,
        args.timeout,
        args.workers,
    )

    time.sleep(args.pause)

    timeout_pressure(
        args.base_url,
        args.timeout,
        args.workers,
    )

    time.sleep(args.pause)

    queue_saturation(
        args.base_url,
        args.timeout,
        args.workers,
    )

    time.sleep(args.pause)

    all_notes_contention(
        args.base_url,
        args.timeout,
        args.workers,
    )

    time.sleep(args.pause)

    connection_error_route(
        args.base_url,
        args.timeout,
    )

    time.sleep(args.pause)

    http_404(
        args.base_url,
        args.timeout,
    )

    time.sleep(args.pause)

    mixed_chaos(
        args.base_url,
        args.timeout,
        args.workers,
    )


# ============================================================
# MAIN
# ============================================================

def main():
    args = parse_args()

    if args.rounds < 1:
        raise SystemExit("--rounds must be >= 1")

    if args.workers < 1:
        raise SystemExit("--workers must be >= 1")

    print()
    print("SRE RELIABILITY LAB - CHAOS RUNNER")
    print(f"Target : {args.base_url}")
    print(f"Rounds : {args.rounds}")
    print(f"Workers: {args.workers}")

    check_service(
        args.base_url,
        args.timeout,
    )

    start = time.monotonic()

    for round_number in range(1, args.rounds + 1):
        run_round(
            args,
            round_number,
        )

    elapsed = time.monotonic() - start

    banner("CHAOS EXPERIMENT COMPLETE")

    print(
        f"Total experiment time: "
        f"{elapsed:.2f}s"
    )

if __name__ == "__main__":
    main()

