import os
import requests


SAVER_URL = os.getenv(
    "SAVER_URL",
    "http://localhost:5001"
)


def submit_note(data):
    timeout = data.get("timeout", 5)

    return requests.post(
        f"{SAVER_URL}/validate",
        json=data,
        timeout=timeout,
    )


def get_all_notes():
    return requests.get(
        f"{SAVER_URL}/get_notes"
    )
