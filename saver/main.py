from flask import Flask, request, jsonify
import json
import os
import time

app = Flask(__name__)

DATA_FILE = os.getenv(
    "DATA_FILE",
    "data.json"
)

def load_words():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r") as file:
        return json.load(file)


def save_words(words):
    with open(DATA_FILE, "w") as file:
        json.dump(words, file, indent=2)


def is_english_word(word):

    english_words = {
        "hello",
        "world",
        "reliability",
        "service",
        "system",
        "software",
        "python",
        "kubernetes",
        "docker",
        "database",
        "network",
        "server",
        "application",
        "engineering",
        "platform",
        "monitoring",
        "observability",
        "security",
        "infrastructure",
    }

    return word.lower() in english_words


@app.get("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "saver"
    })

def failure_control(action):

    if action == "slow":
      time.sleep(4)
    elif action == "error":
      return 500
    elif action == "timeout":
      time.sleep(15)


@app.post("/validate")
def validate_word():
    try:
      data = request.get_json()
    except Exception as e:
      return ({"msg": f"{e}"}), 500

    if not data or not data["word"]:
        return jsonify({
            "error": "word is required",
            "saved": False,
            "source": "saver"
        }), 400

    if data["action"] != "normal":
      result = failure_control(data["action"])
      if result:
        return jsonify({
            "error": "Backend Failure Control",
            "type": result,
            "saved": False,
            "source": "saver"
        }), 400


    word = data["word"]

    if not isinstance(word, str):
        return jsonify({
            "error": "word must be a string",
            "saved": False,
            "source": "saver"
        }), 400

    word = word.strip()

    if not word:
        return jsonify({
            "error": "word cannot be empty",
            "saved": False,
            "source": "saver"
        }), 400

    if not is_english_word(word):
        return jsonify({
            "word": word,
            "valid": False,
            "saved": False,
            "message": "Word is not recognized",
            "source": "saver"
        }), 400

    words = load_words()

    if word not in words:
        words.append(word)
        save_words(words)

    return jsonify({
        "word": word,
        "valid": True,
        "saved": True,
        "message": "Word saved successfully"
    }), 200


@app.get("/get_notes")
def get_words():
    words = load_words()

    return jsonify({
        "count": len(words),
        "words": words
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001
    )

