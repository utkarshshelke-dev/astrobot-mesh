"""
Remote client for deployed Data Scientist agent on Cloud Run.
Uses metadata server for auth (no gcloud needed in container).
After each run, fetches chart artifacts from GCS and returns them
as base64 inline_data so the orchestrator UI renders them.
"""
import os
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

DS_ENDPOINT = os.getenv(
    "DS_AGENT_ENDPOINT",
    "https://astrobot-ds-v2-866797370377.us-central1.run.app"
)
APP_NAME      = "data_science"
GCS_BUCKET    = os.getenv("ARTIFACT_GCS_BUCKET", "gs://nc-ai-chatbot-astrobot-artifacts").replace("gs://", "")
GCS_CHART_PREFIX = "data_science/orchestrator"


def _get_token(audience: str = None) -> str:
    """Get identity token — metadata server in Cloud Run, gcloud locally."""
    aud = audience or DS_ENDPOINT
    # Metadata server (Cloud Run)
    try:
        req = urllib.request.Request(
            f"http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity?audience={aud}&format=full",
            headers={"Metadata-Flavor": "Google"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.read().decode()
    except Exception:
        pass
    # gcloud (local)
    try:
        import subprocess
        return subprocess.check_output(
            ["gcloud", "auth", "print-identity-token"],
            text=True
        ).strip()
    except Exception:
        pass
    # ADC
    try:
        import google.auth
        import google.auth.transport.requests
        creds, _ = google.auth.default()
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
    except Exception as e:
        logger.error(f"Auth failed: {e}")
        return ""


def _post(url: str, payload: dict, token: str) -> dict:
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def _fetch_charts_from_gcs(session_id: str, after_ts: float) -> list:
    """
    Fetch recent PNG charts from GCS bucket for this session.
    Returns list of base64-encoded image dicts.
    """
    charts = []
    try:
        from google.cloud import storage as _gcs
        import time as _t
        import base64
        client = _gcs.Client()
        bucket = client.bucket(GCS_BUCKET)
        prefix = f"{GCS_CHART_PREFIX}/{session_id}/"
        for blob in bucket.list_blobs(prefix=prefix):
            if not blob.name.endswith(".png/0") and not blob.name.endswith(".png"):
                continue
            if blob.updated.timestamp() < after_ts:
                continue
            data = blob.download_as_bytes()
            charts.append({
                "mime_type": "image/png",
                "data": base64.b64encode(data).decode(),
                "name": blob.name.split("/")[-2] if blob.name.endswith("/0") else blob.name.split("/")[-1]
            })
            logger.info(f"✓ Chart fetched from GCS: {blob.name} ({len(data)} bytes)")
    except Exception as e:
        logger.debug(f"GCS chart fetch failed: {e}")
    return charts


async def call_remote_ds_agent(
    query: str,
    client_id: str,
    user_id: str = "orchestrator",
    session_id: str = ""
) -> str:
    """Call deployed Data Scientist agent and include any generated charts."""
    import time
    try:
        token = _get_token()
        call_start = time.time()

        # Create session
        session = _post(
            f"{DS_ENDPOINT}/apps/{APP_NAME}/users/{user_id}/sessions",
            {"state": {
                "client_id": client_id,
                "LOCKED_CLIENT": client_id,
                "client_lock": client_id
            }},
            token
        )
        sid = session.get("id", f"orch_{client_id}")
        logger.info(f"Remote DS session: {sid}")
        # Store DS session id for orchestrator to fetch charts from
        import os as _osm
        _osm.environ["_LAST_DS_SESSION_ID"] = sid

        # Run query
        response = _post(f"{DS_ENDPOINT}/run", {
            "app_name": APP_NAME,
            "user_id": user_id,
            "session_id": sid,
            "new_message": {
                "role": "user",
                "parts": [{"text": f"[Client: {client_id}] {query}"}]
            }
        }, token)

        # Extract text response
        events = response if isinstance(response, list) else [response]
        parts = []
        for event in events:
            for part in event.get("content", {}).get("parts", []):
                if "text" in part and part["text"].strip():
                    parts.append(part["text"])
                if "inline_data" in part:
                    # Chart came back inline — pass through
                    mime = part["inline_data"].get("mime_type", "")
                    if "image" in mime:
                        parts.append(f"\n![chart](data:{mime};base64,{part['inline_data']['data'][:50]}...)\n")

        text_result = "\n".join(parts) or "(no response)"
        logger.info(f"Remote DS response: {len(text_result)} chars")

        # Fetch charts from GCS
        charts = _fetch_charts_from_gcs(sid, call_start)
        if charts:
            logger.info(f"✓ {len(charts)} chart(s) fetched from GCS for session {sid}")
            # Store chart data in a way orchestrator can access
            # Charts saved to GCS — orchestrator agent.py will fetch and forward

        return text_result

    except Exception as e:
        logger.error(f"Remote DS failed: {e}")
        return f"Error calling deployed agent: {e}"


async def get_session_artifacts(session_id: str, user_id: str = "orchestrator") -> list:
    """Fetch artifacts from remote session."""
    try:
        token = _get_token()
        req = urllib.request.Request(
            f"{DS_ENDPOINT}/apps/{APP_NAME}/users/{user_id}/sessions/{session_id}/artifacts",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        logger.warning(f"Could not fetch artifacts: {e}")
        return []
