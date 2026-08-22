import concurrent.futures
import requests
import time


URL = "http://localhost:5000/notes"

TOTAL_REQUESTS = 20

def send_request(number):
    start = time.time()
    word = "platform"
    action = "slow"
    try:
        response = requests.post(
            URL,
            json={
                "word": word,
                "action": action
            },
            timeout=30
        )

        elapsed = time.time() - start
        print(f"Action Type: {action}")
        print(f"response: {response.json()}")
        return {
            "request": number,
            "status": response.status_code,
            "time": round(elapsed, 2),
            "response": response.json()
        }

    except Exception as error:
        elapsed = time.time() - start

        return {
            "request": number,
            "status": "ERROR",
            "time": round(elapsed, 2),
            "response": str(error)
        }


def main():

    print(
        f"Sending {TOTAL_REQUESTS} concurrent requests..."
    )

    start = time.time()

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=TOTAL_REQUESTS
    ) as executor:

        futures = [
            executor.submit(
                send_request,
                number
            )
            for number in range(1, TOTAL_REQUESTS + 1)
        ]

        for future in concurrent.futures.as_completed(futures):
            result = future.result()

            print(
                f"Request {result['request']:02d} | "
                f"Status: {result['status']} | "
                f"Time: {result['time']}s"
            )

    elapsed = time.time() - start

    print()
    print(
        f"Total experiment time: {round(elapsed, 2)}s"
    )


if __name__ == "__main__":
    main()
