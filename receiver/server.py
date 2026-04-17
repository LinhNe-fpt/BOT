"""
Minimal multipart receiver for lab testing only.
Use only on machines you own or with explicit written authorization.
"""
import os
from datetime import datetime

from flask import Flask, request

app = Flask(__name__)
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "captured_data")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


@app.route("/upload", methods=["POST"])
def upload():
    if "image" not in request.files:
        return "missing image", 400
    file = request.files["image"]
    info = request.form.get("info", "")
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    print(f"[*] Saved {path} from: {info}")
    return "OK", 200


@app.route("/health", methods=["GET"])
def health():
    return {"status": "ok"}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
