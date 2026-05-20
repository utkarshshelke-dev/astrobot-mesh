"""Cloud Run Service — Eventarc webhook for BQ table creation."""
import json
import logging
import os
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_event():
    try:
        envelope = request.get_json(silent=True) or {}
        proto_payload = envelope.get("protoPayload", {})
        resource_name = proto_payload.get("resourceName", "")
        method_name = proto_payload.get("methodName", "")
        logger.info(f"Event: method={method_name}, resource={resource_name}")

        if "Astrobot_" not in resource_name:
            return jsonify({"status": "ignored"}), 200

        os.environ["USE_FIRESTORE_CONFIG"] = "true"
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")

        from data_science.lib.client_sync import sync_all_clients
        result = sync_all_clients(dry_run=False)
        logger.info(f"Sync: new_clients={result['new_clients']}, new_tables={result['new_tables']}")
        return jsonify({"status": "ok", "result": result}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
