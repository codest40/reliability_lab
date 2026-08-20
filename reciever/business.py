from flask import Flask, request, jsonify
import requests
import os

app = Flask(__name__)

SAVER_URL = os.getenv(
    "SAVER_URL",
    "http://localhost:5001"
)


@app.get("/")
def root():
    return "WELCOME TO RECIEVER APP"

@app.get("/favicon.ico")
def favicon():
    return jsonify({"f": "ok"})

@app.get("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "reciever"
    })


@app.post("/notes")
def submit_note():
    data = request.get_json()

    if not data:
        return jsonify({
            "error": "word is required",
            "source": "reciever"
        }), 400

    try:
        timeout = data.get("timeout", 5)
        response = requests.post(
          f"{SAVER_URL}/validate",
          json=data,
          timeout=timeout,
        )
    except requests.exceptions.Timeout:
      timeout="ERROR: Request timed out."
      return jsonify({"source": "reciver", "ERROR:": f"{timeout}"}), 504
    except requests.exceptions.ConnectionError:
      return jsonify({
       "source": "reciever",
       "ERROR:": "Dependency service Not availbale"
      }), 503
    except Exception as e:
      return jsonify({"source": "reciver", "ERROR:": f"{str(e)}"}), 404
    return jsonify(response.json()), response.status_code

@app.get("/all_notes")
def get_all_notes():
  try:
      response = requests.get(f"{SAVER_URL}/get_notes")
  except requests.exceptions.ConnectionError:
      return jsonify({
       "source": "reciever",
       "ERROR:": "Dependency service Not availbale"
      }), 503
  except requests.exceptions.Timeout:
      timeout="ERROR: Request timed out."
      return jsonify({"source": "reciver", "ERROR:": f"{timeout}"}), 504
  except Exception as e:
      return jsonify({"source": "reciever", "ERROR:": str(e)}),  404

  if not response:
    return jsonify({
      "msg": "No notes availbale yet",
      "source": "reciever"
    }), response.status_code
  return jsonify(response.json()), response.status_code

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000
    )
