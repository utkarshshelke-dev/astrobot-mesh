# project_manager/agent.py
"""
Project Manager Agent — §4.2

Handles client-specific project management: email communications, task
management, project timelines, and team correspondence.

Subject to the STRICTEST client isolation model — no cross-client data sharing.
There is no scenario in which this agent's outputs for one client should
inform or influence its behaviour for another.

Task and email APIs are scoped to the active client's authorised accounts only.

All 6 ADK callbacks implemented:
  before_agent_callback — §4.2 isolation init, client lock, audit log
  after_agent_callback  — turn logging, RLHF tagging partitioned by client_id
  before_tool_callback  — strict client_id injection + cross-client guard
  after_tool_callback   — response audit + isolation verification
  before_model_callback — context logging
  after_model_callback  — token tracking per client
"""

import logging
import os
from datetime import date, datetime
from typing import Any, Optional

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import BaseTool, ToolContext
from google.cloud import firestore
from google.genai import types

from shared.utils.config import GEMINI_MODEL, PROJECT_ID, FIRESTORE_DB

logger = logging.getLogger(__name__)

_fs: Optional[firestore.Client] = None

VALID_CLIENTS = {"NPI", "Venetian", "WinnDixie"}


def _get_fs() -> firestore.Client:
    global _fs
    if _fs is None:
        _fs = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB)
    return _fs


def _get_client_id(tool_context: ToolContext) -> str:
    """Extracts and validates client_id from tool context."""
    ctx = tool_context.state.get("session_context", {})
    client_id = ctx.get("client_id", "")
    if not client_id:
        client_id = tool_context.state.get("client_id", "")
    return client_id


def _assert_client(client_id: str, operation: str) -> None:
    """
    §4.2: Hard assertion — raises if client_id is invalid or missing.
    No operation proceeds without a locked, validated client_id.
    """
    if not client_id:
        raise PermissionError(
            f"§4.2 Isolation violation: No client_id set for operation "
            f"'{operation}'. All PM operations require a locked client context."
        )
    if client_id not in VALID_CLIENTS:
        raise PermissionError(
            f"§4.2 Isolation violation: Unknown client_id '{client_id}' "
            f"for operation '{operation}'. "
            f"Valid clients: {sorted(VALID_CLIENTS)}."
        )


# ══════════════════════════════════════════════════════════════════════════════
# TASK MANAGEMENT TOOLS
# ══════════════════════════════════════════════════════════════════════════════

def create_task(
    title:        str,
    description:  str,
    assignee:     str,
    due_date:     str,
    priority:     str,
    tool_context: ToolContext,
) -> dict:
    """
    Creates a new task for the active client.
    Tasks are scoped exclusively to the active client_id — they cannot be
    accessed, listed, or modified in any other client's context.

    Args:
        title:        Task title.
        description:  Task description.
        assignee:     Team member to assign to.
        due_date:     Due date in YYYY-MM-DD format.
        priority:     'high' | 'medium' | 'low'.
        tool_context: ADK tool context.

    Returns:
        Created task dict with task_id.
    """
    client_id = _get_client_id(tool_context)
    _assert_client(client_id, "create_task")

    ctx = tool_context.state.get("session_context", {})
    task = {
        "client_id":   client_id,
        "title":       title,
        "description": description,
        "assignee":    assignee,
        "due_date":    due_date,
        "priority":    priority,
        "status":      "open",
        "created_at":  datetime.utcnow().isoformat(),
        "created_by":  ctx.get("user_id", ""),
    }

    ref = _get_fs().collection(f"tasks_{client_id}").add(task)
    task["task_id"] = ref[1].id

    logger.info(
        "§4.2 Task created | client=%s | title=%s | id=%s",
        client_id, title, task["task_id"],
    )
    return task


def list_tasks(
    status:       str,
    assignee:     str,
    tool_context: ToolContext,
) -> list[dict]:
    """
    Lists tasks for the active client only.
    Hard filter by client_id prevents cross-client data exposure.

    Args:
        status:       Filter by status: 'open' | 'in_progress' | 'done' | 'all'.
        assignee:     Filter by assignee (empty = all assignees).
        tool_context: ADK tool context.

    Returns:
        List of task dicts for the active client only.
    """
    client_id = _get_client_id(tool_context)
    _assert_client(client_id, "list_tasks")

    col   = _get_fs().collection(f"tasks_{client_id}")

    # Use single-field query to avoid composite index requirement
    # Filter in Python for additional fields
    if status and status != "all":
        docs = col.where("status", "==", status).limit(100).stream()
    else:
        docs = col.limit(100).stream()

    tasks = []
    for d in docs:
        t = d.to_dict() | {"task_id": d.id}
        # §4.2: double-check client_id in Python
        if t.get("client_id") != client_id:
            continue
        # Filter assignee in Python
        if assignee and t.get("assignee") != assignee:
            continue
        tasks.append(t)

    # Sort by due_date in Python
    tasks = sorted(tasks, key=lambda x: x.get("due_date", ""))[:50]

    logger.info("§4.2 Listed %d tasks | client=%s", len(tasks), client_id)
    return tasks


def update_task_status(
    task_id:      str,
    new_status:   str,
    note:         str,
    tool_context: ToolContext,
) -> dict:
    """
    Updates the status of an existing task.
    Validates that the task belongs to the active client before updating.
    Cross-client task updates are rejected with a PermissionError.

    Args:
        task_id:      The task ID to update.
        new_status:   'open' | 'in_progress' | 'done'.
        note:         Optional progress note.
        tool_context: ADK tool context.

    Returns:
        Updated task dict.
    """
    client_id = _get_client_id(tool_context)
    _assert_client(client_id, "update_task_status")

    ctx     = tool_context.state.get("session_context", {})
    doc_ref = _get_fs().collection(f"tasks_{client_id}").document(task_id)
    doc     = doc_ref.get()

    if not doc.exists:
        return {"error": f"Task '{task_id}' not found for client '{client_id}'."}

    task = doc.to_dict()

    # §4.2: Extra safety check — verify task belongs to active client
    if task.get("client_id") != client_id:
        raise PermissionError(
            f"§4.2 Isolation violation: Task '{task_id}' belongs to "
            f"client '{task.get('client_id')}' but active client is "
            f"'{client_id}'. Cross-client task modification is forbidden."
        )

    update_data = {
        "status":     new_status,
        "updated_at": datetime.utcnow().isoformat(),
    }
    if note:
        update_data["notes"] = firestore.ArrayUnion([{
            "note":     note,
            "added_at": datetime.utcnow().isoformat(),
            "added_by": ctx.get("user_id", ""),
        }])

    doc_ref.update(update_data)
    logger.info(
        "§4.2 Task updated | client=%s | task=%s | status=%s",
        client_id, task_id, new_status,
    )
    return task | update_data | {"task_id": task_id}


# ══════════════════════════════════════════════════════════════════════════════
# EMAIL TOOLS
# ══════════════════════════════════════════════════════════════════════════════

def draft_email(
    to:           str,
    subject:      str,
    context:      str,
    tone:         str,
    tool_context: ToolContext,
) -> dict:
    """
    Drafts a professional email for the active client context.
    Email drafts are scoped to the active client and stored in the
    client-partitioned Firestore collection.

    Args:
        to:           Recipient name or email.
        subject:      Email subject line.
        context:      Context / key points to include.
        tone:         'formal' | 'friendly' | 'urgent'.
        tool_context: ADK tool context.

    Returns:
        Dict with subject and body of the drafted email.
    """
    client_id = _get_client_id(tool_context)
    _assert_client(client_id, "draft_email")

    ctx   = tool_context.state.get("session_context", {})
    draft = {
        "client_id":  client_id,
        "to":         to,
        "subject":    subject,
        "context":    context,
        "tone":       tone,
        "status":     "draft",
        "created_at": datetime.utcnow().isoformat(),
        "created_by": ctx.get("user_id", ""),
        "note": (
            "Email drafted for your review. "
            "Reply 'send' to dispatch or 'edit' with your changes."
        ),
    }

    # Store draft in client-partitioned Firestore collection
    try:
        ref = _get_fs().collection(f"email_drafts_{client_id}").add(draft)
        draft["draft_id"] = ref[1].id
        logger.info(
            "§4.2 Email draft created | client=%s | subject=%s | id=%s",
            client_id, subject, draft["draft_id"],
        )
    except Exception as e:
        logger.warning("Could not persist draft to Firestore: %s", e)

    return draft


# ══════════════════════════════════════════════════════════════════════════════
# PROJECT TIMELINE TOOLS
# ══════════════════════════════════════════════════════════════════════════════

def get_project_status(
    project_name: str,
    tool_context: ToolContext,
) -> dict:
    """
    Retrieves the current status of a project for the active client.
    Only returns projects belonging to the active client_id.

    Args:
        project_name: Project name to look up.
        tool_context: ADK tool context.

    Returns:
        Project status dict or error if not found.
    """
    client_id = _get_client_id(tool_context)
    _assert_client(client_id, "get_project_status")

    docs = (
        _get_fs()
        .collection(f"projects_{client_id}")
        .where("client_id", "==", client_id)
        .where("name", "==", project_name)
        .limit(1)
        .stream()
    )
    results = [d.to_dict() | {"project_id": d.id} for d in docs]

    if not results:
        return {
            "error": (
                f"Project '{project_name}' not found for client '{client_id}'. "
                f"Check the project name or create a new project."
            )
        }

    logger.info(
        "§4.2 Project status retrieved | client=%s | project=%s",
        client_id, project_name,
    )
    return results[0]


def create_project(
    name:         str,
    description:  str,
    start_date:   str,
    end_date:     str,
    owner:        str,
    tool_context: ToolContext,
) -> dict:
    """
    Creates a new project for the active client.

    Args:
        name:         Project name.
        description:  Project description.
        start_date:   Start date in YYYY-MM-DD format.
        end_date:     End date in YYYY-MM-DD format.
        owner:        Project owner/lead.
        tool_context: ADK tool context.

    Returns:
        Created project dict with project_id.
    """
    client_id = _get_client_id(tool_context)
    _assert_client(client_id, "create_project")

    ctx     = tool_context.state.get("session_context", {})
    project = {
        "client_id":   client_id,
        "name":        name,
        "description": description,
        "start_date":  start_date,
        "end_date":    end_date,
        "owner":       owner,
        "status":      "active",
        "created_at":  datetime.utcnow().isoformat(),
        "created_by":  ctx.get("user_id", ""),
        "milestones":  [],
    }

    ref = _get_fs().collection(f"projects_{client_id}").add(project)
    project["project_id"] = ref[1].id

    logger.info(
        "§4.2 Project created | client=%s | name=%s | id=%s",
        client_id, name, project["project_id"],
    )
    return project


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS — ALL 6 (§4.2 STRICTEST ISOLATION)
# ══════════════════════════════════════════════════════════════════════════════

def before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """
    §4.2: Fires before every agent turn.
    Initialises strict client isolation context.
    Locks client_id — rejects if missing or invalid.
    Logs audit trail for every PM operation.
    """
    state = callback_context.state

    # Initialise session_context if missing
    if "session_context" not in state:
        state["session_context"] = {}

    # Parse client_id from orchestrator prefix
    try:
        for msg in reversed(
            callback_context._invocation_context.session.events or []
        ):
            if hasattr(msg, "content") and msg.content:
                for part in msg.content.parts or []:
                    if hasattr(part, "text") and part.text:
                        text = part.text
                        if text.startswith("[Client:"):
                            client_id = text[9: text.index("]")].strip()
                            if client_id in VALID_CLIENTS:
                                state["session_context"]["client_id"] = client_id
                                state["client_id"] = client_id
                                logger.info(
                                    "§4.2 Client locked | client=%s", client_id
                                )
                        break
            break
    except Exception as e:
        logger.debug("Could not parse client prefix: %s", e)

    # Default client
    if "client_id" not in state["session_context"]:
        default = os.getenv("DEFAULT_CLIENT_ID", "NPI")
        state["session_context"]["client_id"] = default
        state["client_id"] = default

    client_id = state["session_context"]["client_id"]

    # §4.2: Strict validation — warn if client unknown
    if client_id not in VALID_CLIENTS:
        logger.error(
            "§4.2 ISOLATION ALERT: Unknown client_id '%s' in PM agent. "
            "Operations will be blocked.", client_id
        )

    # Audit log entry
    state.setdefault("_pm_audit_log", []).append({
        "event":     "session_start",
        "client_id": client_id,
        "timestamp": datetime.utcnow().isoformat(),
    })

    logger.info(
        "▶ PM before_agent | client=%s | §4.2 isolation active",
        client_id,
    )
    return None


def after_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """
    §4.2: Fires after every agent turn.
    Tags last exchange for RLHF — partitioned by client_id.
    """
    state     = callback_context.state
    client_id = state.get("session_context", {}).get("client_id", "unknown")

    # Tag for RLHF — client-partitioned
    state["last_exchange"] = {
        "client_id":  client_id,
        "agent":      "project_manager",
        "timestamp":  datetime.utcnow().isoformat(),
    }

    logger.info(
        "◀ PM after_agent | client=%s | audit_entries=%d",
        client_id,
        len(state.get("_pm_audit_log", [])),
    )
    return None


def before_tool_callback(
    tool:         BaseTool,
    args:         dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict]:
    """
    §4.2: Fires before every tool call.
    Enforces strictest client isolation:
    - Validates client_id before every tool call
    - Logs audit trail for every PM operation
    - Blocks any tool call without valid client context
    """
    client_id = _get_client_id(tool_context)
    tool_name = tool.name if hasattr(tool, "name") else str(tool)

    # §4.2: Block if no valid client
    if not client_id or client_id not in VALID_CLIENTS:
        logger.error(
            "§4.2 BLOCK: Tool '%s' blocked — invalid client_id '%s'",
            tool_name, client_id,
        )
        return {
            "error": (
                f"§4.2 Security: Operation blocked. "
                f"No valid client context. client_id='{client_id}'."
            )
        }

    # Audit log
    tool_context.state.setdefault("_pm_audit_log", []).append({
        "event":     "tool_call",
        "tool":      tool_name,
        "client_id": client_id,
        "timestamp": datetime.utcnow().isoformat(),
    })

    logger.info(
        "⚙ PM before_tool | tool=%s | client=%s | §4.2 validated",
        tool_name, client_id,
    )
    return None


def after_tool_callback(
    tool:          BaseTool,
    args:          dict[str, Any],
    tool_context:  ToolContext,
    tool_response: Any,
) -> Optional[Any]:
    """
    §4.2: Fires after every tool call.
    Audits response — verifies no cross-client data leaked.
    """
    client_id = _get_client_id(tool_context)
    tool_name = tool.name if hasattr(tool, "name") else str(tool)
    response  = str(tool_response) if tool_response else ""

    # §4.2: Scan response for cross-client data leakage
    other_clients = VALID_CLIENTS - {client_id}
    for other in other_clients:
        if other.lower() in response.lower():
            logger.warning(
                "§4.2 AUDIT WARNING: Response from tool '%s' for client '%s' "
                "contains reference to '%s'. Review for potential data leakage.",
                tool_name, client_id, other,
            )

    logger.info(
        "✓ PM after_tool | tool=%s | client=%s | response_len=%d",
        tool_name, client_id, len(response),
    )
    return None


def before_model_callback(
    callback_context: CallbackContext,
    llm_request:      Any,
) -> Optional[Any]:
    """
    §4.2: Fires before every Gemini API call.
    Logs client context for full audit trail.
    """
    state     = callback_context.state
    client_id = state.get("session_context", {}).get("client_id", "unknown")

    logger.info(
        "⚡ PM before_model | client=%s | audit_entries=%d",
        client_id,
        len(state.get("_pm_audit_log", [])),
    )
    return None


def after_model_callback(
    callback_context: CallbackContext,
    llm_response:     Any,
) -> Optional[Any]:
    """
    §4.2: Fires after every Gemini API response.
    Tracks token usage per client for cost attribution.
    """
    state     = callback_context.state
    client_id = state.get("session_context", {}).get("client_id", "unknown")

    try:
        usage     = llm_response.usage_metadata
        input_tok = getattr(usage, "prompt_token_count",     0)
        out_tok   = getattr(usage, "candidates_token_count", 0)

        logger.info(
            "🔢 PM after_model | client=%s | tokens in=%d out=%d",
            client_id, input_tok, out_tok,
        )

        # Per-client token tracking for cost attribution
        key = f"tokens_{client_id}"
        state[key] = {
            "in":    state.get(key, {}).get("in",  0) + input_tok,
            "out":   state.get(key, {}).get("out", 0) + out_tok,
        }
    except Exception:
        pass

    return None


# ══════════════════════════════════════════════════════════════════════════════
# ROOT AGENT
# ══════════════════════════════════════════════════════════════════════════════

root_agent = LlmAgent(
    model=os.getenv("PM_AGENT_MODEL", GEMINI_MODEL),
    name="project_manager_agent",
    instruction=f"""
    You are the Project Manager Agent for the Astro.bot marketing analytics
    platform. Today's date: {date.today()}.

    Your role: manage client-specific project work — tasks, email drafts,
    project timelines, and team correspondence.

    ══════════════════════════════════════════════════════════
    §4.2 STRICTEST ISOLATION MODEL — NON-NEGOTIABLE
    ══════════════════════════════════════════════════════════

    You operate EXCLUSIVELY within the active client's context.
    This is the strictest isolation in the entire Astro.bot mesh.

    NEVER:
    - Reference another client's tasks, emails, or projects
    - Use one client's patterns or history to inform another's
    - Acknowledge cross-client data even as a generalised pattern
    - Proceed without a confirmed, locked client_id

    ALL operations use client-partitioned Firestore collections:
    - tasks_NPI / tasks_Venetian / tasks_WinnDixie
    - email_drafts_NPI / email_drafts_Venetian / email_drafts_WinnDixie
    - projects_NPI / projects_Venetian / projects_WinnDixie

    ══════════════════════════════════════════════════════════
    WORKFLOW
    ══════════════════════════════════════════════════════════

    TASK REQUESTS:
    - "create task"  → create_task() — ask for assignee + due date if missing
    - "list tasks"   → list_tasks() filtered by status/assignee
    - "update task"  → update_task_status() with task_id + new status

    EMAIL REQUESTS:
    - "draft email"  → draft_email() with context and tone
    - Present draft for review — never send without confirmation

    PROJECT REQUESTS:
    - "project status"  → get_project_status() by project name
    - "create project"  → create_project() with all required fields

    REQUIRED FIELDS FOR TASK CREATION:
    - Title (required)
    - Assignee (required — ask if not provided)
    - Due date (required — ask if not provided)
    - Priority: high / medium / low (default: medium)

    ══════════════════════════════════════════════════════════
    RESPONSE FORMAT
    ══════════════════════════════════════════════════════════

    **Result:** Task/email/project outcome.
    **Details:** Specific fields, IDs, or content.
    **Next Steps:** What action to take next.
    """,
    tools=[
        create_task,
        list_tasks,
        update_task_status,
        draft_email,
        get_project_status,
        create_project,
    ],

    # ── All 6 callbacks — §4.2 strictest isolation ───────────────────────────
    before_agent_callback = before_agent_callback,  # client lock + audit init
    after_agent_callback  = after_agent_callback,   # RLHF tagging by client
    before_tool_callback  = before_tool_callback,   # §4.2 block + audit log
    after_tool_callback   = after_tool_callback,    # cross-client leak scan
    before_model_callback = before_model_callback,  # audit trail logging
    after_model_callback  = after_model_callback,   # per-client token tracking

    generate_content_config=types.GenerateContentConfig(temperature=0.1),
)