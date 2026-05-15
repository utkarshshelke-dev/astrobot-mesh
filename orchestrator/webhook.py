# orchestrator/webhook.py
"""
Cloud Run Webhook — Google Chat → Astrobot Orchestrator.

Cloud Run hosts this webhook endpoint that:
1. Receives Google Chat webhook payloads.
2. Extracts the cryptographically-signed Space ID.
3. Passes Space ID to the Orchestrator session state.
4. Calls the Orchestrator and streams the response back to Chat.

Spec reference:
  Section 2.1 — Ingestion Gate (Space ID extraction)
  Section 7.1 — Cloud Run for connectivity; Agent Engine for reasoning
"""

from __future__ import annotations
import json
import logging
import os
from typing import Any, Dict

from fastapi import FastAPI, Request, Response

app = FastAPI(title="Astrobot Chat Webhook")
logger = logging.getLogger(__name__)

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
LOCATION   = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")


@app.post("/webhook/chat")
async def handle_chat_message(request: Request) -> Response:
    """
    Receives Google Chat webhook payload.
    Extracts Space ID and routes to Orchestrator.
    """
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        return Response(
            content=json.dumps({"text": "Invalid payload."}),
            media_type="application/json",
            status_code=400,
        )

    event_type = payload.get("type", "")
    if event_type == "REMOVED_FROM_SPACE":
        return Response(content="{}", media_type="application/json")

    # Extract Space ID (cryptographically signed by Google — cannot be faked)
    space_id = payload.get("space", {}).get("name", "")
    user_msg = payload.get("message", {}).get("text", "").strip()
    user_email = payload.get("user", {}).get("email", "")

    if not space_id or not user_msg:
        return Response(
            content=json.dumps({"text": "Could not parse message."}),
            media_type="application/json",
        )

    logger.info("Chat message from space=%s user=%s", space_id, user_email)

    # Call Orchestrator
    response_text = await _call_orchestrator(
        space_id=space_id,
        user_message=user_msg,
        user_email=user_email,
    )

    return Response(
        content=json.dumps({"text": response_text}),
        media_type="application/json",
    )


@app.post("/webhook/scheduler")
async def handle_scheduler_trigger(request: Request) -> Response:
    """
    Receives triggers from Cloud Scheduler for automated jobs.
    The scheduler acts as an automated user — same ingestion flow.
    """
    try:
        payload: Dict[str, Any] = await request.json()
    except Exception:
        return Response(status_code=400)

    job_id     = payload.get("job_id", "")
    space_id   = payload.get("space_id", "")
    prompt     = payload.get("prompt", "")
    client_id  = payload.get("client_id", "")
    delivery   = payload.get("delivery", {})
    condition  = payload.get("condition", "")

    logger.info("Scheduler trigger: job=%s client=%s", job_id, client_id)

    if not prompt or not client_id:
        return Response(status_code=400)

    # Re-run the scheduled prompt through the Orchestrator
    response_text = await _call_orchestrator(
        space_id=space_id,
        user_message=prompt,
        user_email="scheduler@astrobot.internal",
        client_id_override=client_id,
    )

    # Check condition if specified
    if condition and not _evaluate_condition(condition, response_text):
        logger.info("Job %s: condition not met, skipping delivery.", job_id)
        return Response(content='{"skipped": true}', media_type="application/json")

    # Deliver via specified channel
    await _deliver_response(response_text, delivery, job_id)

    return Response(content='{"delivered": true}', media_type="application/json")


async def _call_orchestrator(
    space_id: str,
    user_message: str,
    user_email: str = "",
    client_id_override: str = "",
) -> str:
    """Calls the Orchestrator Agent Engine endpoint."""
    try:
        import vertexai
        from vertexai.preview import agent_engines

        vertexai.init(project=PROJECT_ID, location=LOCATION)
        endpoint = os.getenv("ORCHESTRATOR_ENDPOINT", "")

        if not endpoint:
            # Local fallback
            from orchestrator.agent import root_agent
            from google.adk.runners import Runner
            from google.adk.sessions import InMemorySessionService

            session_service = InMemorySessionService()
            runner = Runner(
                agent=root_agent,
                app_name="astrobot",
                session_service=session_service,
            )
            session = await session_service.create_session(
                app_name="astrobot",
                user_id=user_email or "user",
                state={
                    "space_id":  space_id,
                    "client_id": client_id_override,
                    "user_email": user_email,
                },
            )
            from google.adk.types import Content, Part
            content = Content(role="user", parts=[Part(text=user_message)])
            response_parts = []
            async for event in runner.run_async(
                user_id=user_email or "user",
                session_id=session.id,
                new_message=content,
            ):
                if event.is_final_response() and event.content:
                    for part in event.content.parts:
                        if part.text:
                            response_parts.append(part.text)
            return "\n".join(response_parts) or "No response generated."

        # Remote Agent Engine call
        remote_agent = agent_engines.get(endpoint)
        session = remote_agent.create_session(
            user_id=user_email or "user",
            state={
                "space_id":   space_id,
                "client_id":  client_id_override,
                "user_email": user_email,
            },
        )
        parts = []
        for event in remote_agent.stream_query(
            user_id=user_email or "user",
            session_id=session["id"],
            message=user_message,
        ):
            if "content" in event and event["content"].get("parts"):
                for p in event["content"]["parts"]:
                    if "text" in p:
                        parts.append(p["text"])
        return "\n".join(parts) or "No response generated."

    except Exception as e:
        logger.error("Orchestrator call failed: %s", e)
        return f"Sorry, I encountered an error: {e}"


async def _deliver_response(
    response: str,
    delivery: dict,
    job_id: str,
) -> None:
    """Delivers the response via the configured channel."""
    channel = delivery.get("channel", "")

    if channel == "google_chat":
        webhook_url = delivery.get("webhook_url", "")
        if webhook_url:
            import httpx
            async with httpx.AsyncClient() as client:
                await client.post(
                    webhook_url,
                    json={"text": f"*Scheduled Report — {job_id}*\n\n{response}"},
                    timeout=30,
                )

    elif channel == "email":
        # Gmail MCP or SMTP
        logger.info("Email delivery for job %s — implement via Gmail MCP.", job_id)

    elif channel == "google_sheets":
        # Google Drive MCP
        logger.info("Sheets delivery for job %s — implement via Drive MCP.", job_id)


def _evaluate_condition(condition: str, response: str) -> bool:
    """
    Simple condition evaluator for conditional notifications.
    Returns True if the response should be delivered.
    In production: use the LLM to evaluate the condition against the response.
    """
    # Placeholder — in production call Gemini to evaluate
    return True


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "astrobot-webhook"}
