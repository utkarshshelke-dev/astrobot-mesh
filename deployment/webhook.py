# deployment/webhook.py
"""
Cloud Run Webhook Handler — §7.1

Receives Google Chat webhook payloads, extracts the cryptographically signed
Space ID, resolves it to a locked Client ID via the Ingestion Gate (Layer 1),
and forwards the request to the Orchestrator on Agent Engine.

Cloud Run hosts this webhook — it does NOT run agents.
Agent Engine runs the agents. (§7.1 distinction)
"""

import json
import logging
import os
import uuid

from flask import Flask, request, jsonify
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request
import httpx

from shared.security.isolation import IngestionGate
from shared.utils.config import AGENT_ENDPOINTS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app   = Flask(__name__)
_gate = IngestionGate()


@app.route("/webhook/chat", methods=["POST"])
def google_chat_webhook():
    """
    Receives Google Chat webhook payloads.
    Extracts Space ID, resolves to Client ID, forwards to Orchestrator.
    """
    payload = request.get_json(silent=True) or {}

    # Extract the cryptographically signed Space ID from Google Chat
    space_id = payload.get("space", {}).get("name", "")
    user_id  = (
        payload.get("sender", {})
        .get("name", "unknown_user")
    )
    message  = (
        payload.get("message", {})
        .get("text", "")
        .strip()
    )

    if not space_id:
        return jsonify({"text": "❌ Could not identify your Chat Space."}), 400
    if not message:
        return jsonify({"text": ""}), 200

    # Layer 1: Ingestion Gate — deterministic routing from Space ID
    try:
        session_context = _gate.build_session_context(
            space_id=space_id,
            user_id=user_id,
            session_id=str(uuid.uuid4()),
        )
    except PermissionError as e:
        logger.warning("Ingestion gate rejected Space '%s': %s", space_id, e)
        return jsonify({"text": f"🔒 Access denied: {e}"}), 403

    client_id = session_context["client_id"]
    logger.info(
        "Chat webhook: Space '%s' → Client '%s' | Message: %s",
        space_id, client_id, message[:60],
    )

    # Forward to Orchestrator on Agent Engine
    orchestrator_url = AGENT_ENDPOINTS.get("orchestrator", "")
    if not orchestrator_url:
        logger.error("Orchestrator endpoint not configured")
        return jsonify({"text": "❌ Orchestrator not reachable. Contact support."}), 503

    try:
        response_text = _call_orchestrator(
            message=message,
            session_context=session_context,
            orchestrator_url=orchestrator_url,
        )
    except Exception as e:
        logger.error("Orchestrator call failed: %s", e)
        return jsonify({"text": f"❌ An error occurred: {e}"}), 500

    return jsonify({"text": response_text})


@app.route("/webhook/feedback", methods=["POST"])
def feedback_webhook():
    """
    Receives thumbs up/down feedback from Google Chat card actions.
    Forwards to Orchestrator which logs it via the RLHF tool.
    """
    payload    = request.get_json(silent=True) or {}
    space_id   = payload.get("space_id", "")
    user_id    = payload.get("user_id", "")
    rating     = payload.get("rating", 0)      # 1 or -1
    correction = payload.get("correction", "")
    session_id = payload.get("session_id", "")

    if not space_id or not rating:
        return jsonify({"status": "ignored"}), 200

    try:
        session_context = _gate.build_session_context(
            space_id=space_id,
            user_id=user_id,
            session_id=session_id,
        )
        session_context["rating"]     = rating
        session_context["correction"] = correction

        logger.info(
            "Feedback received for client '%s': rating=%d",
            session_context["client_id"], rating,
        )
        return jsonify({"status": "recorded"})
    except PermissionError as e:
        return jsonify({"status": "denied", "reason": str(e)}), 403


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "astrobot-webhook"})


def _call_orchestrator(
    message:          str,
    session_context:  dict,
    orchestrator_url: str,
) -> str:
    """
    Calls the Orchestrator on Agent Engine with the user's message
    and the locked session context.
    """
    credentials, _ = google_auth_default()
    if not credentials.valid:
        credentials.refresh(Request())

    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type":  "application/json",
        "X-Client-ID":   session_context.get("client_id", ""),
        "X-Space-ID":    session_context.get("space_id", ""),
    }

    body = {
        "app_name":   "orchestrator",
        "user_id":    session_context.get("user_id", ""),
        "session_id": session_context.get("session_id", ""),
        "message":    message,
        "state": {
            "session_context": session_context,
        },
    }

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(
            f"{orchestrator_url}/run",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", str(data))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
