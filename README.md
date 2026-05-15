# Astro.bot Multi-Agent Mesh

NetConversion marketing analytics multi-agent system built on Google ADK and Vertex AI Agent Engine.

## Architecture

```
Google Chat
    │  (cryptographically signed Space ID)
    ▼
Cloud Run Webhook  ──── Layer 1: Ingestion Gate (Space ID → Client ID)
    │
    ▼
Astro.bot Orchestrator  (Vertex AI Agent Engine)
    │   A2A Agent Card Protocol
    ├──▶ Data Scientist Agent    — SQL, charts, BQML forecasting/clustering
    ├──▶ Persona Aggregator      — audience personas (Global Def / Local Exec)
    ├──▶ Economist Agent         — macroeconomic context + benchmarks
    ├──▶ Project Manager Agent   — tasks, emails, timelines
    └──▶ Scheduler Agent         — recurring automated reports
              │
              └──▶ Orchestrator (as automated user — not peer-to-peer)
```

## Four-Layer Isolation (§2)

| Layer | Mechanism | What it prevents |
|---|---|---|
| 1. Ingestion Gate | Space ID → Client ID via Firestore | User cannot redirect to another client's data |
| 2. Schema Blindfold | Only active client's DDL in context | LLM cannot generate SQL against unauthorised tables |
| 3. IAM Enforcement | Short-lived scoped BQ tokens | GCP rejects unauthorised queries at infrastructure level |
| 4. Memory Partition | All state filtered by Client ID | Cross-client learning contamination |

## Clients

| Client | Dataset | Channel type | Primary metric |
|---|---|---|---|
| NPI | `Astrobot_NPI` | Search / PMax / Social | Conversions |
| Venetian | `Astrobot_Venetian` | OOH (Strata) | KPI |
| WinnDixie | `Astrobot_WinnDixie` | OTT (Viant) | ViVs |

## Quick Start

### 1. Prerequisites
```bash
gcloud auth application-default login
gcloud config set project nc-ai-chatbot
```

### 2. Install
```bash
cd astrobot_mesh
cp .env.example .env
# Fill in .env with your values
uv sync
```

### 3. Setup infrastructure (run once)
```bash
uv run python deployment/setup_firestore.py
```
This creates:
- Firestore collections: `space_client_registry`, `persona_authorizations`, `agent_registry`, `scheduled_jobs`
- BigQuery datasets: `astrobot_rlhf`, `astrobot_memory`
- BQML dataset: `astrobot_bqml_models`

### 4. Register Chat Spaces
After setup, add real Google Chat Space IDs to Firestore:
```python
# Get Space ID from Google Chat API or from webhook payload
# Format: spaces/XXXXXXXXX
fs.collection("space_client_registry").document("spaces/YOUR_SPACE_ID").set({
    "client_id": "NPI",  # or "Venetian" or "WinnDixie"
    "active": True,
})
```

### 5. Run tests
```bash
uv run pytest tests/test_mesh.py -v
```

### 6. Test locally (Orchestrator only)
```bash
adk web --allow_origins="*" .
# Select "orchestrator" from dropdown
```

### 7. Deploy to Agent Engine
```bash
# Deploy all agents (specialist agents first, orchestrator last)
uv run python deployment/deploy_mesh.py --action deploy --agent all

# Or deploy one at a time
uv run python deployment/deploy_mesh.py --action deploy --agent persona_aggregator
uv run python deployment/deploy_mesh.py --action deploy --agent economist
uv run python deployment/deploy_mesh.py --action deploy --agent project_manager
uv run python deployment/deploy_mesh.py --action deploy --agent scheduler
uv run python deployment/deploy_mesh.py --action deploy --agent orchestrator

# Deploy Cloud Run webhook
uv run python deployment/deploy_mesh.py --action deploy-webhook
```

### 8. Connect Data Scientist Agent
The Data Scientist Agent is already deployed at `~/astrobot_data_science`.
Get its endpoint and set it in `.env`:
```bash
# Get endpoint from Agent Engine console or from deploy output
DATA_SCIENTIST_ENDPOINT=projects/nc-ai-chatbot/locations/us-central1/reasoningEngines/XXXXXXXXX
```

Then update the Firestore registry:
```python
from shared.firestore.registry import update_agent_endpoint
update_agent_endpoint("data_scientist", "projects/.../reasoningEngines/XXX")
```

## Example NLP queries

### Via Google Chat
```
@Astro.bot Show me total spend by channel for NPI
@Astro.bot Forecast NPI spend for next 14 days
@Astro.bot Who is our audience for WinnDixie?
@Astro.bot How does our NPI performance compare to healthcare benchmarks?
@Astro.bot Schedule this report every Monday and send to our Google Space
@Astro.bot Create a task for reviewing Q3 campaign performance
```

### Via ADK web UI (local dev)
```
Show me total spend by channel for NPI
Cluster NPI campaigns by performance and visualize
Train an ARIMA model to forecast WinnDixie ViVs for next 14 days
What economic conditions affect our Venetian campaigns?
Set up a weekly spend report delivered via email
```

## Scheduler delivery examples

```
Schedule the daily spend report to be sent to our Google Chat every morning
Send me an alert via email if NPI spend anomalies are detected
Save the weekly performance report to Google Sheets every Friday
Only notify me via Chat if CPC exceeds $5.00 this week
```

## File structure

```
astrobot_mesh/
├── orchestrator/           Astro.bot Orchestrator — central routing
│   ├── agent.py            LlmAgent with A2A tools
│   └── prompts.py          Routing rules + response format
├── persona_aggregator/     Persona Aggregator — §3
│   └── agent.py            Global Definition / Local Execution
├── economist/              Economist Agent — §4.1
│   └── agent.py            Vertical-filtered economic indicators
├── project_manager/        Project Manager Agent — §4.2
│   └── agent.py            Tasks, emails, timelines (strictest isolation)
├── scheduler/              Scheduler Agent — §6
│   └── agent.py            Recurring jobs, conditional notifications
├── shared/
│   ├── a2a/
│   │   ├── agent_card.py   AgentCard dataclass + all canonical cards
│   │   └── handshake.py    A2AHandshakeClient
│   ├── security/
│   │   └── isolation.py    4-layer isolation model
│   ├── firestore/
│   │   └── registry.py     Persona auth, agent endpoints, scheduled jobs
│   └── utils/
│       └── config.py       GCP config, client table map
├── deployment/
│   ├── setup_firestore.py  One-time infrastructure setup
│   ├── deploy_mesh.py      Agent Engine + Cloud Run deployment
│   └── webhook.py          Cloud Run Flask webhook handler
├── tests/
│   └── test_mesh.py        Full test suite (isolation, A2A, routing)
├── cloudbuild.yaml         CI/CD pipeline
├── pyproject.toml
└── .env.example
```

## Agent Card Protocol (§7.2)

Each agent publishes an `AgentCard` describing its capabilities, inputs, and
output format. The Orchestrator uses the card to communicate with agents via
the `A2AHandshakeClient` rather than hard-coded API calls.

This means agent implementations can change — tools can be added, behaviour
can be modified — without breaking the Orchestrator, as long as the AgentCard
contract is honoured.

```python
from shared.a2a.agent_card import ALL_AGENT_CARDS
print(ALL_AGENT_CARDS["data_scientist"].to_json())
```
