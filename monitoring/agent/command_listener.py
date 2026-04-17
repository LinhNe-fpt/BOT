"""
HTTP nhẹ trên localhost để nhận lệnh (kill process). Bật qua COMMAND_LISTENER=1.
Chỉ lắng nghe 127.0.0.1; mọi request cần header X-Agent-Secret khớp COMMAND_SECRET.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

import psutil


def _status_phrase(code: int) -> str:
    return {
        200: "OK",
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
    }.get(code, "Error")


def _json_response(start_response: Any, status: int, body: dict) -> list[bytes]:
    data = json.dumps(body).encode("utf-8")
    headers = [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(data))),
    ]
    start_response(f"{status} {_status_phrase(status)}", headers)
    return [data]


def app(environ: Any, start_response: Any) -> list[bytes]:
    if environ.get("REQUEST_METHOD") != "POST":
        return _json_response(start_response, 405, {"error": "method_not_allowed"})
    secret = os.environ.get("COMMAND_SECRET", "")
    if environ.get("HTTP_X_AGENT_SECRET") != secret or not secret:
        return _json_response(start_response, 401, {"error": "unauthorized"})
    try:
        size = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        size = 0
    raw = environ["wsgi.input"].read(size) if size else b"{}"
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        return _json_response(start_response, 400, {"error": "invalid_json"})
    cmd = data.get("cmd")
    if cmd == "kill_process":
        pid = data.get("pid")
        try:
            pid = int(pid)
        except (TypeError, ValueError):
            return _json_response(start_response, 400, {"error": "bad_pid"})
        try:
            p = psutil.Process(pid)
            p.kill()
            return _json_response(start_response, 200, {"status": "killed", "pid": pid})
        except psutil.NoSuchProcess:
            return _json_response(start_response, 404, {"error": "no_such_process"})
        except psutil.AccessDenied:
            return _json_response(start_response, 403, {"error": "access_denied"})
    if cmd == "ping":
        return _json_response(start_response, 200, {"status": "pong"})
    return _json_response(start_response, 400, {"error": "unknown_cmd"})


def main(host: str = "127.0.0.1", port: int = 18765, secret: str | None = None) -> None:
    if secret:
        os.environ["COMMAND_SECRET"] = secret
    from wsgiref.simple_server import make_server

    print(f"Command listener http://{host}:{port}/ (POST only)", file=sys.stderr)
    srv = make_server(host, port, app)
    srv.serve_forever()
