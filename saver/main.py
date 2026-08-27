from flask import Flask, request, jsonify
import json
import os
import time


app = Flask(__name__)
DATA_FILE = os.getenv("DATA_FILE", "data.json")
READINESS_FILE = os.getenv("READINESS_FILE", "readiness.json")


def load_words():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r") as file:
        return json.load(file)


def save_words(words):
    with open(DATA_FILE, "w") as file:
        json.dump(words, file, indent=2)


def load_readiness_state():
    if not os.path.exists(READINESS_FILE):
        return {
            "action": "normal",
            "completed": True,
        }

    with open(READINESS_FILE, "r") as file:
        return json.load(file)


def save_readiness_state(action, completed):
    with open(READINESS_FILE, "w") as file:
        json.dump({
            "action": action,
            "completed": completed,
        }, file, indent=2)


def is_english_word(word):
    english_words = {
        "hello", "world", "reliability", "service",
        "system", "software", "python", "kubernetes",
        "docker", "database", "network", "server",
        "application", "engineering", "platform",
        "monitoring", "linux", "security", "infrastructure",
    }

    return word.lower() in english_words


@app.get("/")
def root():
    return "SAVER SERVICE ONLINE"


@app.get("/favicon.ico")
def favicon():
    return jsonify({"service": "saver"}), 200


@app.get("/health")
def health():
    return jsonify({
        "status": "healthy",
        "service": "saver",
    }), 200


def failure_control(action):
    if action == "slow":
        time.sleep(4)

    elif action == "error":
        return 500

    elif action == "timeout":
        time.sleep(15)


@app.get("/readiness")
def readiness():
    try:
        state = load_readiness_state()
        action = state.get("action", "normal")
        completed = state.get("completed", False)

        if not completed:
            return jsonify({
                "status": "not_ready",
                "service": "saver",
                "action": action,
                "completed": False,
                "summary": f"B is currently executing action: {action}",
            }), 503

        load_words()

        return jsonify({
            "status": "ready",
            "service": "saver",
            "action": action,
            "completed": True,
        }), 200

    except Exception as error:
        return jsonify({
            "status": "not_ready",
            "service": "saver",
            "error": str(error),
        }), 503


@app.post("/validate")
def validate_word():
    try:
        data = request.get_json()
    except Exception as error:
        return jsonify({"msg": str(error)}), 500

    if not data or "word" not in data:
        return jsonify({
            "error": "word is required",
            "saved": False,
            "source": "saver",
        }), 400

    action = data.get("action", "normal")

    save_readiness_state(action, False)

    if action != "normal":
        result = failure_control(action)

        if result:
            return jsonify({
                "error": "Backend Failure Control",
                "type": result,
                "saved": False,
                "source": "saver",
            }), 500

    word = data["word"]

    if not isinstance(word, str):
        save_readiness_state(action, True)

        return jsonify({
            "error": "word must be a string",
            "saved": False,
            "source": "saver",
        }), 400

    word = word.strip()

    if not word:
        save_readiness_state(action, True)

        return jsonify({
            "error": "word cannot be empty",
            "saved": False,
            "source": "saver",
        }), 400

    if not is_english_word(word):
        save_readiness_state(action, True)

        return jsonify({
            "word": word,
            "valid": False,
            "saved": False,
            "message": "Word is not recognized",
            "source": "saver",
        }), 400

    words = load_words()

    if word not in words:
        words.append(word)
        save_words(words)

    save_readiness_state(action, True)

    return jsonify({
        "word": word,
        "valid": True,
        "saved": True,
        "message": "Word saved successfully",
    }), 200


@app.get("/get_notes")
def get_words():
    words = load_words()

    return jsonify({
        "count": len(words),
        "words": words,
    })


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5001,
    )
