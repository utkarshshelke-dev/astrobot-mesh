"""A2A Handshake Client — calls agents via ADK api_server --a2a protocol."""
from __future__ import annotations
import json, logging, uuid
from typing import Any
import httpx
from google.auth import default as google_auth_default
from google.auth.transport.requests import Request
from shared.a2a.agent_card import AgentCard, ALL_AGENT_CARDS
from shared.utils.config import PROJECT_ID, LOCATION

logger = logging.getLogger(__name__)

class A2AHandshakeClient:
    def __init__(self):
        self._credentials, _ = google_auth_default()
        self._http = httpx.AsyncClient(timeout=180.0)

    async def _get_auth_token(self):
        if not self._credentials.valid:
            self._credentials.refresh(Request())
        return self._credentials.token

    def get_agent_card(self, agent_id):
        card = ALL_AGENT_CARDS.get(agent_id)
        if not card:
            raise ValueError(f"No Agent Card for '{agent_id}'. Valid: {list(ALL_AGENT_CARDS)}")
        return card

    async def call_agent(self, agent_id, payload, session_context):
        card = self.get_agent_card(agent_id)
        payload["client_id"] = session_context.get("client_id", "NPI")
        client_id = payload["client_id"]

        query = payload.get("query",
                payload.get("analysis_request",
                payload.get("persona_request",
                payload.get("pm_request",
                payload.get("schedule_request", json.dumps(payload))))))
        full_message = f"[Client: {client_id}] {query}"

        a2a_body = {
            "jsonrpc": "2.0",
            "id": str(uuid.uuid4()),
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"type": "text", "text": full_message}],
                    "messageId": str(uuid.uuid4()),
                },
                "metadata": {
                    "client_id":  client_id,
                    "space_id":   session_context.get("space_id", ""),
                    "session_id": session_context.get("session_id", ""),
                },
            },
        }

        endpoint = card.endpoint
        is_local  = endpoint.startswith("http://localhost")
        headers   = {"Content-Type": "application/json"}
        if not is_local:
            token = await self._get_auth_token()
            headers["Authorization"] = f"Bearer {token}"
            headers["X-Client-ID"]   = client_id

        logger.info("[A2A] → %s  client=%s  url=%s", agent_id, client_id, endpoint)
        try:
            resp = await self._http.post(endpoint, headers=headers, json=a2a_body)
            resp.raise_for_status()
            return self._extract_text(resp.json(), agent_id)
        except Exception as e:
            logger.error("[A2A] '%s' failed: %s", agent_id, e)
            raise

    def _extract_text(self, data, agent_id):
        try:
            result = data.get("result", {})
            parts  = result.get("status", {}).get("message", {}).get("parts", [])
            if parts:
                return "\n".join(p.get("text","") for p in parts if p.get("type")=="text")
            for art in result.get("artifacts", []):
                for p in art.get("parts", []):
                    if p.get("type") == "text": return p["text"]
            if isinstance(result, str): return result
            return str(data)
        except Exception as e:
            logger.error("[A2A] parse error from %s: %s", agent_id, e)
            return str(data)

    async def close(self):
        await self._http.aclose()
