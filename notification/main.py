from flask import Flask, request, jsonify
from datetime import datetime

app = Flask(__name__)

def get_time():
    return datetime.now().isoformat()

def line():
    return "=" * 70

def webhook_alert():
    try:
        data = request.get_json()
        alerts = data["alerts"]
        alert = alerts[0]
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alertname = labels.get("alertname", "unknown")
        category = labels.get("category", "unknown")
        severity = labels.get("severity", "unknown")
        description = annotations.get("description", "No description")
        summary = annotations.get("summary", "No summary")

    except Exception as e:
        print(f"{get_time()} | Webhook ERROR: {e}", flush=True)
        raise

    message = (
        f"Alertname: {alertname}\n"
        f"Category: {category}\n"
        f"Severity: {severity}\n"
        f"Description: {description}\n"
        f"Summary: {summary}"
    )

    print(f"{get_time()} | Webhook Received: ", flush=True)
    for each in message.splitlines():
      print("-----------------------")
      print(each)
    return {"status": "received"}, 200


@app.post("/webhook")
def get_notifications():
    print(line(), flush=True)
    print(f"{get_time()} | Webhook has been Received", flush=True)
    return webhook_alert()
    print(line(), flush=True)

@app.get("/health")
def health():
    return jsonify({"status": "ok", "source": "Notify"})


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5002
    )
