from __future__ import annotations

import json
import os
import threading
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


WORKFLOW_ID = "EQvN9tFGuFCotDS1"
N8N_WEBHOOK = os.environ.get("N8N_WEBHOOK", "http://127.0.0.1:5678/webhook/composer-v2-" + WORKFLOW_ID)


def validate_result(result, run_id):
    from autowfbench.core.contracts import validate
    validate("submission", result)
    if result["run_id"] != run_id:
        raise ValueError("n8n returned a different run_id")
    provenance = [e["data"] for e in result["trace"] if e["kind"] == "n8n_execution"]
    if not any(e.get("workflow_id") == WORKFLOW_ID and e.get("execution_id")
               and e.get("run_id") == run_id for e in provenance):
        raise ValueError("Missing Composer workflow execution provenance")
    if result["status"] == "completed" and not any(
        a["name"] == "incident-summary.md" and a["content"].strip() for a in result["artifacts"]
    ):
        raise ValueError("Missing incident summary")
    return result

jobs = {}
lock = threading.RLock()


def trigger_n8n(request):
    env = request["environment"]

    payload = {
        "environment_url": env["base_url"],
        "run_token": env["access_token"],
        "run_id": request["run_id"],
        "challenge": request["challenge"],
    }

    req = urllib.request.Request(
        N8N_WEBHOOK,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as response:
        body = response.read().decode("utf-8")

    try:
        result = json.loads(body) if body else {}
    except json.JSONDecodeError:
        result = {"raw": body}

    return validate_result(result, request["run_id"])


class Handler(BaseHTTPRequestHandler):

    def send_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        self.wfile.write(body)

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length)

        return json.loads(body.decode("utf-8"))

    def do_POST(self):
        if self.path == "/runs":
            request = self.read_json()

            execution_id = uuid.uuid4().hex

            with lock:
                jobs[execution_id] = {
                    "status": "running"
                }

            def work():
                try:
                    result = trigger_n8n(request)
                except Exception as exc:
                    result = {
                        "protocol_version": "1.0",
                        "run_id": request["run_id"],
                        "status": "failed",
                        "final_answer": str(exc),
                        "artifacts": [],
                        "trace": [],
                    }

                with lock:
                    jobs[execution_id] = {
                        "status": result["status"],
                        "submission": result,
                    }

            threading.Thread(
                target=work,
                daemon=True
            ).start()

            return self.send_json(
                202,
                {
                    "execution_id": execution_id,
                    "status": "running",
                },
            )

        self.send_json(404, {"error": "Not found"})

    def do_GET(self):
        parts = self.path.strip("/").split("/")

        if len(parts) == 2 and parts[0] == "runs":
            execution_id = parts[1]

            with lock:
                job = jobs.get(execution_id)

            if job is None:
                return self.send_json(
                    404,
                    {"error": "Unknown execution"}
                )

            return self.send_json(200, job)

        self.send_json(404, {"error": "Not found"})


if __name__ == "__main__":
    port = int(os.environ.get("N8N_SOLUTION_PORT", "9401"))
    print(
        "Generated n8n workflow solution: "
        f"http://127.0.0.1:{port}",
        flush=True,
    )

    ThreadingHTTPServer(
        ("127.0.0.1", port),
        Handler
    ).serve_forever()
