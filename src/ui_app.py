"""Flask UI for Jeen Insights.

Acts as a thin pass-through to the FastAPI backend. The browser sends a
`connection` (source_key) along with every data-related request; this UI
forwards it on without inspecting it.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict

import requests
from flask import Flask, jsonify, render_template, request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates", static_folder="static")

API_BASE_URL = os.getenv("API_BASE_URL", "http://jeen-insights-api:8000")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _proxy_get(path: str, params: Dict[str, Any] | None = None, timeout: float = 30) -> Any:
    try:
        response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=timeout)
    except requests.exceptions.RequestException as e:
        logger.error("Backend GET %s failed: %s", path, e)
        return jsonify({"error": f"Backend unavailable: {e}"}), 503
    if response.status_code == 200:
        return jsonify(response.json())
    return jsonify({"error": response.text}), response.status_code


def _proxy_post(path: str, payload: Dict[str, Any], timeout: float = 60) -> Any:
    try:
        response = requests.post(f"{API_BASE_URL}{path}", json=payload, timeout=timeout)
    except requests.exceptions.RequestException as e:
        logger.error("Backend POST %s failed: %s", path, e)
        return jsonify({"error": f"Backend unavailable: {e}"}), 503
    if response.status_code == 200:
        return jsonify(response.json())
    return jsonify({"error": response.text}), response.status_code


# ----------------------------------------------------------------------
# Pages
# ----------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        backend_status = response.json() if response.status_code == 200 else {"status": "unhealthy"}
    except Exception as e:  # noqa: BLE001
        backend_status = {"status": "unhealthy", "error": str(e)}
    return jsonify({"ui_status": "healthy", "backend_status": backend_status})


# ----------------------------------------------------------------------
# Connections
# ----------------------------------------------------------------------
@app.route("/api/connections", methods=["GET"])
def list_connections():
    return _proxy_get("/api/connections", timeout=15)


@app.route("/api/connections/<source_key>", methods=["GET"])
def get_connection(source_key: str):
    return _proxy_get(f"/api/connections/{source_key}", timeout=15)


@app.route("/api/connections/<source_key>/refresh-metadata", methods=["POST"])
def refresh_metadata(source_key: str):
    return _proxy_post(f"/api/connections/{source_key}/refresh-metadata", payload={}, timeout=15)


# ----------------------------------------------------------------------
# Query / data exploration
# ----------------------------------------------------------------------
@app.route("/api/ask", methods=["POST"])
def ask_question():
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    connection = data.get("connection")
    session_id = data.get("session_id")

    if not question:
        return jsonify({"error": "Question cannot be empty"}), 400
    if not connection:
        return jsonify({"error": "No connection selected"}), 400

    payload: Dict[str, Any] = {"question": question, "connection": connection}
    if session_id:
        payload["session_id"] = session_id
    return _proxy_post("/api/query", payload, timeout=120)


@app.route("/api/tables", methods=["GET"])
def get_tables():
    connection = request.args.get("connection")
    if not connection:
        return jsonify({"error": "No connection selected"}), 400
    return _proxy_get("/api/tables", params={"connection": connection}, timeout=15)


@app.route("/api/schema/<table_name>", methods=["GET"])
def get_schema(table_name: str):
    connection = request.args.get("connection")
    if not connection:
        return jsonify({"error": "No connection selected"}), 400
    return _proxy_get(f"/api/schema/{table_name}", params={"connection": connection}, timeout=15)


# ----------------------------------------------------------------------
# Recent / pinned questions
# ----------------------------------------------------------------------
@app.route("/api/user/recent-questions", methods=["GET"])
def get_recent_questions():
    connection = request.args.get("connection")
    if not connection:
        return jsonify({"questions": []})
    return _proxy_get(
        "/api/user/recent-questions",
        params={
            "connection": connection,
            "user_id": request.args.get("user_id", "default"),
            "limit": request.args.get("limit", "15"),
        },
    )


@app.route("/api/user/pinned-questions", methods=["GET"])
def get_pinned_questions():
    connection = request.args.get("connection")
    if not connection:
        return jsonify({"questions": []})
    return _proxy_get(
        "/api/user/pinned-questions",
        params={
            "connection": connection,
            "user_id": request.args.get("user_id", "default"),
        },
    )


@app.route("/api/user/pin-question", methods=["POST"])
def pin_question():
    data = request.get_json() or {}
    if not data.get("connection"):
        return jsonify({"error": "No connection selected"}), 400
    return _proxy_post("/api/user/pin-question", data)


@app.route("/api/user/unpin-question", methods=["POST"])
def unpin_question():
    data = request.get_json() or {}
    if not data.get("connection"):
        return jsonify({"error": "No connection selected"}), 400
    return _proxy_post("/api/user/unpin-question", data)


# ----------------------------------------------------------------------
# Insights / charts / profile
# ----------------------------------------------------------------------
@app.route("/api/generate-chart", methods=["POST"])
def generate_chart():
    data = request.get_json() or {}
    if not data.get("connection"):
        return jsonify({"error": "No connection selected"}), 400
    return _proxy_post("/api/generate-chart", data)


@app.route("/api/generate-insights", methods=["POST"])
def generate_insights():
    data = request.get_json() or {}
    if not data.get("connection"):
        return jsonify({"error": "No connection selected"}), 400
    return _proxy_post("/api/generate-insights", data)


@app.route("/api/generate-profile", methods=["POST"])
def generate_profile():
    data = request.get_json() or {}
    return _proxy_post("/api/generate-profile", data, timeout=120)


@app.route("/api/enhance-chart", methods=["POST"])
def enhance_chart():
    data = request.get_json() or {}
    if not data.get("connection"):
        return jsonify({"error": "No connection selected"}), 400
    return _proxy_post("/api/enhance-chart", data)


# ----------------------------------------------------------------------
# Autocomplete (Tier 2 catalog + Tier 3 LLM)
# ----------------------------------------------------------------------
@app.route("/api/knowledge-questions", methods=["GET"])
def get_knowledge_questions():
    connection = request.args.get("connection")
    if not connection:
        return jsonify({"error": "No connection selected"}), 400
    return _proxy_get(
        "/api/knowledge-questions",
        params={"connection": connection},
        timeout=15,
    )


@app.route("/api/knowledge-columns", methods=["GET"])
def get_knowledge_columns():
    connection = request.args.get("connection")
    if not connection:
        return jsonify({"error": "No connection selected"}), 400
    params = {"connection": connection}
    table = request.args.get("table")
    if table:
        params["table"] = table
    return _proxy_get(
        "/api/knowledge-columns",
        params=params,
        timeout=15,
    )


@app.route("/api/suggest-questions", methods=["POST"])
def suggest_questions():
    data = request.get_json() or {}
    if not data.get("connection"):
        return jsonify({"error": "No connection selected"}), 400
    return _proxy_post("/api/suggest-questions", data, timeout=15)


# ----------------------------------------------------------------------
# Feedback / history
# ----------------------------------------------------------------------
@app.route("/api/feedback", methods=["POST"])
def submit_feedback():
    return _proxy_post("/api/feedback", request.get_json() or {})


@app.route("/api/conversation/<session_id>", methods=["GET"])
def get_conversation_history(session_id: str):
    return _proxy_get(f"/api/conversation/{session_id}", timeout=30)


if __name__ == "__main__":
    port = int(os.getenv("UI_PORT", "8501"))
    app.run(host="0.0.0.0", port=port, debug=True)
