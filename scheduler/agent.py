# scheduler/agent.py
"""
Scheduler Agent — §6

Provides users with the ability to create recurring automated prompt executions.
Sits at the CONTROL PLANE — behaves as an automated user sending requests to
the Orchestrator, not as a peer agent in the mesh.

Scheduled jobs pass through the same Ingestion Gate as all human requests.
The full four-layer isolation model applies — jobs are scoped to a specific
Chat Space and therefore a specific Client ID.

Delivery channels: Google Chat, email, Google Sheets.
"""

import logging
import os
from datetime import date, datetime
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import ToolContext
from google.cloud import firestore
from google.genai import types

from shared.utils.config import GEMINI_MODEL, PROJECT_ID, FIRESTORE_DB
from shared.firestore.registry import get_scheduled_jobs, save_scheduled_job

logger = logging.getLogger(__name__)


# ── Schedule frequency options ─────────────────────────────────────────────────

VALID_FREQUENCIES = {
    "daily":        "0 8 * * *",          # 8am every day
    "weekdays":     "0 8 * * 1-5",        # 8am Mon-Fri
    "weekly":       "0 8 * * 1",          # 8am every Monday
    "monday":       "0 8 * * 1",
    "biweekly":     "0 8 1,15 * *",       # 1st and 15th
    "monthly":      "0 8 1 * *",          # 1st of month
    "hourly":       "0 * * * *",
}

VALID_DELIVERY_CHANNELS = ["chat", "email", "sheets"]


# ── Tools ─────────────────────────────────────────────────────────────────────

def create_scheduled_job(
    job_name:         str,
    original_prompt:  str,
    frequency:        str,
    delivery_channel: str,
    delivery_config:  dict,
    condition:        str,
    tool_context:     ToolContext,
) -> dict:
    """
    Creates a new scheduled job that will automatically re-run an analytical
    prompt and deliver the results on a recurring schedule.

    The job passes through the same Ingestion Gate as human requests —
    all four isolation layers apply automatically.

    Args:
        job_name:         Descriptive name for this job.
        original_prompt:  The analytical question to re-run each time.
        frequency:        'daily' | 'weekdays' | 'weekly' | 'monthly' | 'hourly'.
        delivery_channel: 'chat' | 'email' | 'sheets'.
        delivery_config:  Channel-specific config:
                          chat   → {"webhook_url": str}
                          email  → {"to": str}
                          sheets → {"folder_id": str, "sheet_name": str}
        condition:        Optional condition (empty = always deliver).
                          e.g. "only if spend anomaly detected"
                          e.g. "only if conversions drop > 20%"
        tool_context:     ADK tool context.

    Returns:
        Created job dict with job_id.
    """
    ctx       = tool_context.state.get("session_context", {})
    client_id = ctx.get("client_id", "")
    space_id  = ctx.get("space_id", "")

    if frequency.lower() not in VALID_FREQUENCIES:
        return {
            "error": (
                f"Invalid frequency '{frequency}'. "
                f"Valid options: {list(VALID_FREQUENCIES.keys())}"
            )
        }

    if delivery_channel.lower() not in VALID_DELIVERY_CHANNELS:
        return {
            "error": (
                f"Invalid delivery channel '{delivery_channel}'. "
                f"Valid options: {VALID_DELIVERY_CHANNELS}"
            )
        }

    job = {
        "client_id":        client_id,        # Partition key — same isolation model
        "space_id":         space_id,          # Scoped to this Chat Space
        "job_name":         job_name,
        "original_prompt":  original_prompt,
        "frequency":        frequency,
        "cron_expression":  VALID_FREQUENCIES[frequency.lower()],
        "delivery_channel": delivery_channel,
        "delivery_config":  delivery_config,
        "condition":        condition or "",   # Empty = always deliver
        "execution_mode":   "AI_AGENT",        # Re-runs the prompt, not static SQL
        "active":           True,
        "created_at":       datetime.utcnow().isoformat(),
        "created_by":       ctx.get("user_id", ""),
        "last_run":         None,
        "next_run":         None,              # Set by Cloud Scheduler on creation
    }

    job_id      = save_scheduled_job(job)
    job["job_id"] = job_id

    # Format confirmation
    delivery_summary = _format_delivery_summary(delivery_channel, delivery_config)
    condition_note   = f"\n**Condition:** {condition}" if condition else ""

    logger.info(
        "Scheduled job created for client '%s': '%s' (%s)",
        client_id, job_name, frequency,
    )

    return {
        "job_id":    job_id,
        "job_name":  job_name,
        "status":    "created",
        "summary": (
            f"✅ Scheduled job **'{job_name}'** created.\n\n"
            f"**Prompt:** {original_prompt}\n"
            f"**Frequency:** {frequency}\n"
            f"**Delivery:** {delivery_summary}"
            f"{condition_note}\n\n"
            f"This job will re-run the analysis fresh each time, "
            f"not replay a static result."
        ),
    }


def list_scheduled_jobs(tool_context: ToolContext) -> list[dict]:
    """
    Lists all active scheduled jobs for the active client.
    Jobs from other clients are never returned.

    Args:
        tool_context: ADK tool context.

    Returns:
        List of active scheduled job dicts.
    """
    ctx       = tool_context.state.get("session_context", {})
    client_id = ctx.get("client_id", "")
    jobs      = get_scheduled_jobs(client_id)

    if not jobs:
        return [{"message": f"No active scheduled jobs for client '{client_id}'."}]

    return jobs


def pause_scheduled_job(
    job_id:       str,
    tool_context: ToolContext,
) -> dict:
    """
    Pauses (deactivates) a scheduled job for the active client.
    Validates client ownership before pausing.

    Args:
        job_id:       The job ID to pause.
        tool_context: ADK tool context.

    Returns:
        Updated job dict.
    """
    ctx       = tool_context.state.get("session_context", {})
    client_id = ctx.get("client_id", "")

    fs      = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB)
    doc_ref = fs.collection(FIRESTORE_DB).document(job_id)
    doc     = doc_ref.get()

    if not doc.exists:
        return {"error": f"Job '{job_id}' not found."}

    job = doc.to_dict()
    if job.get("client_id") != client_id:
        raise PermissionError(
            f"Job '{job_id}' does not belong to client '{client_id}'."
        )

    doc_ref.update({"active": False, "paused_at": datetime.utcnow().isoformat()})
    return {"job_id": job_id, "status": "paused", "job_name": job.get("job_name")}


def get_delivery_requirements(
    delivery_channel: str,
    tool_context:     ToolContext,
) -> dict:
    """
    Returns the required configuration fields for a delivery channel.
    Call this to know what information to ask the user for.

    Args:
        delivery_channel: 'chat' | 'email' | 'sheets'.
        tool_context:     ADK tool context.

    Returns:
        Dict describing required fields.
    """
    requirements = {
        "chat": {
            "required_fields": ["webhook_url"],
            "description":     "Google Chat Space webhook URL.",
            "example":         {"webhook_url": "https://chat.googleapis.com/v1/spaces/..."},
        },
        "email": {
            "required_fields": ["to"],
            "description":     "Recipient email address(es).",
            "example":         {"to": "analyst@company.com"},
        },
        "sheets": {
            "required_fields": ["folder_id", "sheet_name"],
            "description":     "Google Drive folder ID and sheet name.",
            "example":         {
                "folder_id":  "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms",
                "sheet_name": "Weekly NPI Report",
            },
        },
    }
    return requirements.get(
        delivery_channel.lower(),
        {"error": f"Unknown delivery channel '{delivery_channel}'."},
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _format_delivery_summary(channel: str, config: dict) -> str:
    if channel == "chat":
        return f"Google Chat Space"
    elif channel == "email":
        return f"Email → {config.get('to', 'TBD')}"
    elif channel == "sheets":
        return f"Google Sheets → {config.get('sheet_name', 'TBD')}"
    return channel


# ── Callbacks ─────────────────────────────────────────────────────────────────

def setup_context(callback_context: CallbackContext) -> None:
    if "session_context" not in callback_context.state:
        callback_context.state["session_context"] = {}


# ── Agent ─────────────────────────────────────────────────────────────────────

root_agent = LlmAgent(
    model=os.getenv("SCHEDULER_AGENT_MODEL", GEMINI_MODEL),
    name="scheduler_agent",
    instruction=f"""
    You are the Scheduler Agent for the Astro.bot marketing analytics platform.
    Today's date: {date.today()}.

    You sit at the CONTROL PLANE — you behave as an automated user sending
    requests to the Orchestrator on a schedule, not as a peer agent in the mesh.
    Your scheduled jobs pass through the same Ingestion Gate as all human requests,
    so all four isolation layers apply automatically.

    YOUR ROLE:
    When a user asks to automate or schedule an analysis they just received,
    you create a recurring job that will re-run that analysis fresh each time
    (AI_AGENT execution mode — not just replaying a static SQL result).

    WORKFLOW:
    1. If delivery channel is missing → call get_delivery_requirements() and ask.
    2. If frequency is missing → ask: daily / weekdays / weekly / monthly.
    3. If job name is missing → suggest one based on the prompt.
    4. Call create_scheduled_job() with all fields.
    5. Confirm with full summary.

    DELIVERY CHANNELS:
    - Google Chat  → requires webhook_url
    - Email        → requires recipient email address
    - Google Sheets → requires folder_id and sheet_name

    CONDITIONAL NOTIFICATIONS:
    If the user says "only send if..." or "alert me when..." or
    "don't send if nothing unusual" — set the condition field.
    The job will only deliver if the condition is met.
    Examples:
    - "only if spend anomaly detected"
    - "only if conversions drop more than 20%"
    - "only if CPC exceeds $5.00"

    RESPONSE FORMAT:
    **Result:** Confirmation of what was scheduled.
    **Schedule Details:** Job name, frequency, delivery, condition.
    **Next Steps:** When to expect the first delivery.

    SECURITY: Every job is scoped to the active Chat Space and Client ID.
    You cannot create cross-client scheduled jobs.
    """,
    tools=[
        create_scheduled_job,
        list_scheduled_jobs,
        pause_scheduled_job,
        get_delivery_requirements,
    ],
    before_agent_callback=setup_context,
    generate_content_config=types.GenerateContentConfig(temperature=0.05),
)
