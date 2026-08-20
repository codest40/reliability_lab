import argparse
import sys

import requests


def parse_args():
    parser = argparse.ArgumentParser(
        description="Send a word to the SRE Lab receiver service."
    )

    parser.add_argument(
        "message",
        help="Word or message to send"
    )

    parser.add_argument(
        "--action",
        type=str,
        default="normal",
        help="Behavior Controller Action (default: normal)"
    )

    parser.add_argument(
        "--host",
        default="localhost",
        help="Receiver host (default: localhost)"
    )

    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Receiver port (default: 5000)"
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=5,
        help="Request timeout in seconds (default: 5)"
    )

    return parser.parse_args()


def main():
    args = parse_args()
    url_post = f"http://{args.host}:{args.port}/notes"
    url_get = f"http://{args.host}:{args.port}/all_notes"

    payload = {
        "word": args.message,
        "action": args.action,
    }

    try:
        if args.message == "all":
          url = url_get
          response = requests.get(
              url_get,
              json=payload,
              timeout=args.timeout
          )
        else:
          url = url_post
          response = requests.post(
              url_post,
              json=payload,
              timeout=args.timeout
          )

    except requests.exceptions.Timeout:
        print("ERROR: Request timed out.")
        sys.exit(1)

    except requests.exceptions.ConnectionError:
        print(
            f"ERROR: Could not connect to receiver at {url}"
        )
        sys.exit(1)

    except requests.exceptions.RequestException as error:
        print(f"ERROR: Request failed: {error}")
        sys.exit(1)

    try:
        result = response.json()
    except ValueError as e:
        print("ERROR: Receiver returned invalid JSON.", e)
        print(f"HTTP status: {response.status_code}")
        sys.exit(1)

    if response.ok:
        print("SUCCESS")
        print(f"Message: {args.message}")
        print(f"Response: {result}")
        return

    print("FAILED")
    print(f"HTTP status: {response.status_code}")
    print(f"Response: {result}")

    sys.exit(1)

if __name__ == "__main__":
    main()

