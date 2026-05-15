# tests/test_mesh.py
"""
Test suite for the Astro.bot multi-agent mesh.
Covers: 4-layer isolation, A2A routing, persona authorisation,
        economist vertical filtering, scheduler job creation, PM isolation.
"""

import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio


# ── Helper ────────────────────────────────────────────────────────────────────

def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ════════════════════════════════════════════════════════════════════════════════
# Layer 1: Ingestion Gate
# ════════════════════════════════════════════════════════════════════════════════

class TestIngestionGate(unittest.TestCase):

    @patch("shared.security.isolation.firestore.Client")
    def test_known_space_resolves_to_client(self, mock_fs_cls):
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"client_id": "NPI", "active": True}
        mock_fs_cls.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

        from shared.security.isolation import IngestionGate
        gate      = IngestionGate()
        client_id = gate.resolve_client_id("spaces/npi_space")
        self.assertEqual(client_id, "NPI")

    @patch("shared.security.isolation.firestore.Client")
    def test_unknown_space_raises_permission_error(self, mock_fs_cls):
        mock_doc       = MagicMock()
        mock_doc.exists = False
        mock_fs_cls.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

        from shared.security.isolation import IngestionGate
        gate = IngestionGate()
        with self.assertRaises(PermissionError):
            gate.resolve_client_id("spaces/unknown_space")

    @patch("shared.security.isolation.firestore.Client")
    def test_inactive_space_raises_permission_error(self, mock_fs_cls):
        mock_doc       = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"client_id": "NPI", "active": False}
        mock_fs_cls.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

        from shared.security.isolation import IngestionGate
        gate = IngestionGate()
        with self.assertRaises(PermissionError):
            gate.resolve_client_id("spaces/inactive_space")

    @patch("shared.security.isolation.firestore.Client")
    def test_session_context_locks_client_id(self, mock_fs_cls):
        mock_doc       = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {"client_id": "Venetian", "active": True}
        mock_fs_cls.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

        from shared.security.isolation import IngestionGate
        gate = IngestionGate()
        ctx  = gate.build_session_context("spaces/venetian_space", "user1", "session1")

        self.assertEqual(ctx["client_id"],  "Venetian")
        self.assertEqual(ctx["space_id"],   "spaces/venetian_space")
        self.assertIn("hospitality",        ctx["vertical"])
        # BQ table must point to Venetian — not NPI or WinnDixie
        self.assertIn("Astrobot_Venetian",  ctx["bq_table"])
        self.assertNotIn("Astrobot_NPI",    ctx["bq_table"])
        self.assertNotIn("Astrobot_WinnDixie", ctx["bq_table"])


# ════════════════════════════════════════════════════════════════════════════════
# Layer 2: Schema Blindfold
# ════════════════════════════════════════════════════════════════════════════════

class TestSchemaBlindFold(unittest.TestCase):

    def setUp(self):
        from shared.security.isolation import SchemaBlindFold
        self.blindfold = SchemaBlindFold()

    def test_npi_schema_contains_only_npi(self):
        schema = self.blindfold.get_schema_context("NPI")
        self.assertIn("Astrobot_NPI",          schema)
        self.assertNotIn("Astrobot_Venetian",   schema)
        self.assertNotIn("Astrobot_WinnDixie",  schema)
        self.assertIn("Conversions",            schema)  # NPI has Conversions
        self.assertIn("AUTHORISED SCHEMA FOR CLIENT: NPI", schema)

    def test_venetian_schema_contains_only_venetian(self):
        schema = self.blindfold.get_schema_context("Venetian")
        self.assertIn("Astrobot_Venetian",  schema)
        self.assertNotIn("Astrobot_NPI",    schema)
        self.assertIn("KPI",                schema)  # Venetian uses KPI not Conversions

    def test_winndixie_schema_contains_only_winndixie(self):
        schema = self.blindfold.get_schema_context("WinnDixie")
        self.assertIn("Astrobot_WinnDixie", schema)
        self.assertNotIn("Astrobot_NPI",    schema)
        self.assertIn("ViVs",               schema)

    def test_unknown_client_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.blindfold.get_schema_context("UNKNOWN_CLIENT")

    def test_npi_schema_does_not_expose_other_schemas(self):
        """
        Critical: requesting NPI schema must NEVER reveal Venetian or WinnDixie.
        If this test fails, the Schema Blindfold Layer 2 is broken.
        """
        npi_schema       = self.blindfold.get_schema_context("NPI")
        venetian_schema  = self.blindfold.get_schema_context("Venetian")
        winndixie_schema = self.blindfold.get_schema_context("WinnDixie")

        # Each schema must be completely disjoint in table references
        self.assertNotIn("Astrobot_Venetian",  npi_schema)
        self.assertNotIn("Astrobot_WinnDixie", npi_schema)
        self.assertNotIn("Astrobot_NPI",       venetian_schema)
        self.assertNotIn("Astrobot_WinnDixie", venetian_schema)
        self.assertNotIn("Astrobot_NPI",       winndixie_schema)
        self.assertNotIn("Astrobot_Venetian",  winndixie_schema)


# ════════════════════════════════════════════════════════════════════════════════
# A2A Agent Card Protocol
# ════════════════════════════════════════════════════════════════════════════════

class TestAgentCard(unittest.TestCase):

    def test_all_cards_have_required_fields(self):
        from shared.a2a.agent_card import ALL_AGENT_CARDS
        required = ["agent_id", "display_name", "version", "capabilities",
                    "inputs", "output"]
        for agent_id, card in ALL_AGENT_CARDS.items():
            card_dict = card.to_dict()
            for field in required:
                self.assertIn(field, card_dict,
                    f"AgentCard for '{agent_id}' missing field '{field}'")

    def test_all_cards_require_client_id(self):
        from shared.a2a.agent_card import ALL_AGENT_CARDS
        for agent_id, card in ALL_AGENT_CARDS.items():
            self.assertTrue(
                card.requires_client_id,
                f"Agent '{agent_id}' must require client_id for isolation."
            )

    def test_card_serialisation_roundtrip(self):
        from shared.a2a.agent_card import DATA_SCIENTIST_CARD, AgentCard
        import json
        serialised   = DATA_SCIENTIST_CARD.to_json()
        deserialised = AgentCard.from_dict(json.loads(serialised))
        self.assertEqual(deserialised.agent_id,     DATA_SCIENTIST_CARD.agent_id)
        self.assertEqual(deserialised.capabilities, DATA_SCIENTIST_CARD.capabilities)

    def test_handshake_enforces_client_id_from_context(self):
        """
        The A2A handshake must always inject client_id from session_context,
        not from the payload. This prevents client_id spoofing via the payload.
        """
        from shared.a2a.handshake import A2AHandshakeClient
        client = A2AHandshakeClient()

        payload = {"query": "show me data", "client_id": "SPOOFED_CLIENT"}
        session = {"client_id": "NPI", "space_id": "spaces/npi"}

        # After _get_auth_token, payload client_id should be overwritten by session
        # We test the local fallback path which applies the same logic
        result = run(client._local_fallback("data_scientist", payload, session))
        self.assertIn("NPI", result)
        self.assertNotIn("SPOOFED_CLIENT", result)

    def test_unknown_agent_raises_value_error(self):
        from shared.a2a.handshake import A2AHandshakeClient
        client = A2AHandshakeClient()
        with self.assertRaises(ValueError):
            client.get_agent_card("nonexistent_agent")


# ════════════════════════════════════════════════════════════════════════════════
# Persona Authorisation — §3.2
# ════════════════════════════════════════════════════════════════════════════════

class TestPersonaAuthorisation(unittest.TestCase):

    @patch("shared.firestore.registry._get_fs")
    def test_authorised_persona_passes(self, mock_fs):
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "authorised_personas": ["budget_conscious_shopper", "streaming_viewer"]
        }
        mock_fs.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

        from shared.firestore.registry import is_persona_authorised
        self.assertTrue(is_persona_authorised("WinnDixie", "budget_conscious_shopper"))

    @patch("shared.firestore.registry._get_fs")
    def test_unauthorised_persona_blocked(self, mock_fs):
        mock_doc = MagicMock()
        mock_doc.exists = True
        mock_doc.to_dict.return_value = {
            "authorised_personas": ["high_intent_researcher"]
        }
        mock_fs.return_value.collection.return_value.document.return_value.get.return_value = mock_doc

        from shared.firestore.registry import is_persona_authorised
        # NPI is not authorised for streaming_viewer
        self.assertFalse(is_persona_authorised("NPI", "streaming_viewer"))

    def test_global_persona_definitions_have_no_client_data(self):
        """
        Global persona definitions must contain ZERO client-specific data.
        No client names, campaign references, or proprietary insights.
        """
        from persona_aggregator.agent import GLOBAL_PERSONA_DEFINITIONS
        forbidden_terms = ["NPI", "Venetian", "WinnDixie", "nc-ai-chatbot",
                           "Astrobot_NPI", "sample_astrobot"]
        for persona_id, pdef in GLOBAL_PERSONA_DEFINITIONS.items():
            definition_text = str(pdef)
            for term in forbidden_terms:
                self.assertNotIn(
                    term, definition_text,
                    f"Global persona '{persona_id}' contains client-specific "
                    f"term '{term}' — this violates §3 isolation."
                )


# ════════════════════════════════════════════════════════════════════════════════
# Economist Vertical Filtering — §4.1
# ════════════════════════════════════════════════════════════════════════════════

class TestEconomistAgent(unittest.TestCase):

    def _make_tool_context(self, client_id: str, vertical: list) -> MagicMock:
        ctx             = MagicMock()
        ctx.state       = {"session_context": {"client_id": client_id, "vertical": vertical}}
        return ctx

    def test_npi_gets_healthcare_indicators(self):
        from economist.agent import get_economic_indicators
        tc     = self._make_tool_context("NPI", ["healthcare", "medical"])
        result = get_economic_indicators("NPI", tc)
        self.assertIn("healthcare", result["indicators"])
        self.assertNotIn("grocery",     result["indicators"])
        self.assertNotIn("hospitality", result["indicators"])

    def test_venetian_gets_hospitality_indicators(self):
        from economist.agent import get_economic_indicators
        tc     = self._make_tool_context("Venetian", ["hospitality", "entertainment"])
        result = get_economic_indicators("Venetian", tc)
        self.assertIn("hospitality",   result["indicators"])
        self.assertNotIn("grocery",    result["indicators"])
        self.assertNotIn("healthcare", result["indicators"])

    def test_winndixie_gets_grocery_indicators(self):
        from economist.agent import get_economic_indicators
        tc     = self._make_tool_context("WinnDixie", ["grocery", "retail", "cpg"])
        result = get_economic_indicators("WinnDixie", tc)
        self.assertIn("grocery",         result["indicators"])
        self.assertNotIn("hospitality",  result["indicators"])
        self.assertNotIn("healthcare",   result["indicators"])

    def test_benchmark_comparison_above(self):
        from economist.agent import benchmark_performance
        tc     = self._make_tool_context("NPI", ["healthcare"])
        result = benchmark_performance(
            client_id="NPI",
            performance_data={"avg_cpc_search": 6.00},  # above $4.50 benchmark
            metric="avg_cpc_search",
            tool_context=tc,
        )
        self.assertIn("ABOVE", result["assessment"])
        self.assertGreater(result["pct_diff"], 0)

    def test_benchmark_comparison_below(self):
        from economist.agent import benchmark_performance
        tc     = self._make_tool_context("NPI", ["healthcare"])
        result = benchmark_performance(
            client_id="NPI",
            performance_data={"avg_cpc_search": 1.00},  # below $4.50 benchmark
            metric="avg_cpc_search",
            tool_context=tc,
        )
        self.assertIn("BELOW", result["assessment"])
        self.assertLess(result["pct_diff"], 0)


# ════════════════════════════════════════════════════════════════════════════════
# Project Manager Isolation — §4.2 (strictest)
# ════════════════════════════════════════════════════════════════════════════════

class TestProjectManagerIsolation(unittest.TestCase):

    def _make_tool_context(self, client_id: str) -> MagicMock:
        ctx       = MagicMock()
        ctx.state = {"session_context": {"client_id": client_id, "user_id": "test_user"}}
        return ctx

    @patch("project_manager.agent._get_fs")
    def test_task_created_with_client_partition_key(self, mock_fs):
        mock_ref  = MagicMock()
        mock_ref[1].id = "task_123"
        mock_fs.return_value.collection.return_value.add.return_value = mock_ref

        from project_manager.agent import create_task
        tc   = self._make_tool_context("NPI")
        task = create_task(
            title="Review Q2 spend",
            description="Review spend across all NPI channels",
            assignee="analyst@nc.com",
            due_date="2025-07-31",
            priority="high",
            tool_context=tc,
        )

        self.assertEqual(task["client_id"], "NPI")
        # Verify it wrote to NPI-scoped collection, not a shared collection
        mock_fs.return_value.collection.assert_called_with("tasks_NPI")

    @patch("project_manager.agent._get_fs")
    def test_list_tasks_scoped_to_active_client(self, mock_fs):
        mock_fs.return_value.collection.return_value \
               .where.return_value \
               .where.return_value \
               .order_by.return_value \
               .limit.return_value \
               .stream.return_value = iter([])

        from project_manager.agent import list_tasks
        tc = self._make_tool_context("WinnDixie")
        list_tasks(status="open", assignee="", tool_context=tc)

        # Must access WinnDixie-scoped collection only
        mock_fs.return_value.collection.assert_called_with("tasks_WinnDixie")
        # Must NOT have called tasks_NPI or tasks_Venetian
        calls = [str(c) for c in mock_fs.return_value.collection.call_args_list]
        for call in calls:
            self.assertNotIn("tasks_NPI",      call)
            self.assertNotIn("tasks_Venetian", call)


# ════════════════════════════════════════════════════════════════════════════════
# Scheduler Agent — §6
# ════════════════════════════════════════════════════════════════════════════════

class TestSchedulerAgent(unittest.TestCase):

    def _make_tool_context(self, client_id: str, space_id: str) -> MagicMock:
        ctx       = MagicMock()
        ctx.state = {"session_context": {
            "client_id":  client_id,
            "space_id":   space_id,
            "user_id":    "test_user",
            "session_id": "test_session",
        }}
        return ctx

    @patch("scheduler.agent.save_scheduled_job", return_value="job_abc123")
    def test_scheduled_job_inherits_client_and_space(self, mock_save):
        from scheduler.agent import create_scheduled_job
        tc     = self._make_tool_context("NPI", "spaces/npi_space")
        result = create_scheduled_job(
            job_name="Weekly NPI Spend Report",
            original_prompt="Show me total spend by channel for NPI",
            frequency="weekly",
            delivery_channel="email",
            delivery_config={"to": "analyst@nc.com"},
            condition="",
            tool_context=tc,
        )

        self.assertEqual(result["status"], "created")
        # Verify the saved job has client_id and space_id locked from context
        saved_job = mock_save.call_args[0][0]
        self.assertEqual(saved_job["client_id"], "NPI")
        self.assertEqual(saved_job["space_id"],  "spaces/npi_space")
        self.assertEqual(saved_job["execution_mode"], "AI_AGENT")

    def test_invalid_frequency_rejected(self):
        from scheduler.agent import create_scheduled_job
        tc     = self._make_tool_context("NPI", "spaces/npi_space")
        result = create_scheduled_job(
            job_name="Bad Job",
            original_prompt="some query",
            frequency="every_5_minutes",  # not a valid option
            delivery_channel="email",
            delivery_config={"to": "test@test.com"},
            condition="",
            tool_context=tc,
        )
        self.assertIn("error", result)
        self.assertIn("Invalid frequency", result["error"])

    def test_invalid_delivery_channel_rejected(self):
        from scheduler.agent import create_scheduled_job
        tc     = self._make_tool_context("NPI", "spaces/npi_space")
        result = create_scheduled_job(
            job_name="Bad Job",
            original_prompt="some query",
            frequency="weekly",
            delivery_channel="whatsapp",  # not a valid channel
            delivery_config={},
            condition="",
            tool_context=tc,
        )
        self.assertIn("error", result)
        self.assertIn("Invalid delivery channel", result["error"])

    def test_conditional_notification_stores_condition(self):
        from scheduler.agent import create_scheduled_job
        with patch("scheduler.agent.save_scheduled_job", return_value="job_cond"):
            tc     = self._make_tool_context("WinnDixie", "spaces/wd_space")
            result = create_scheduled_job(
                job_name="Anomaly Alert",
                original_prompt="Detect spend anomalies for WinnDixie",
                frequency="daily",
                delivery_channel="chat",
                delivery_config={"webhook_url": "https://chat.googleapis.com/xxx"},
                condition="only if spend anomaly detected",
                tool_context=tc,
            )
            self.assertEqual(result["status"], "created")
            self.assertIn("only if spend anomaly detected", result["summary"])

    def test_delivery_requirements_returns_correct_fields(self):
        from scheduler.agent import get_delivery_requirements
        tc   = self._make_tool_context("NPI", "spaces/npi")

        chat_req   = get_delivery_requirements("chat",   tc)
        email_req  = get_delivery_requirements("email",  tc)
        sheets_req = get_delivery_requirements("sheets", tc)

        self.assertIn("webhook_url",  chat_req["required_fields"])
        self.assertIn("to",           email_req["required_fields"])
        self.assertIn("folder_id",    sheets_req["required_fields"])
        self.assertIn("sheet_name",   sheets_req["required_fields"])


# ════════════════════════════════════════════════════════════════════════════════
# Orchestrator routing config
# ════════════════════════════════════════════════════════════════════════════════

class TestOrchestratorPrompt(unittest.TestCase):

    def test_prompt_contains_all_agent_routing(self):
        from orchestrator.prompts import return_instructions_orchestrator
        prompt = return_instructions_orchestrator()

        agents = [
            "call_data_scientist",
            "call_persona_aggregator",
            "call_economist",
            "call_project_manager",
            "call_scheduler",
            "submit_feedback",
        ]
        for agent in agents:
            self.assertIn(agent, prompt,
                f"Orchestrator prompt missing routing rule for '{agent}'")

    def test_prompt_enforces_client_isolation(self):
        from orchestrator.prompts import return_instructions_orchestrator
        prompt = return_instructions_orchestrator()
        self.assertIn("CLIENT ISOLATION",    prompt)
        self.assertIn("NEVER aggregate",     prompt)
        self.assertIn("locked",              prompt)

    def test_prompt_has_response_format(self):
        from orchestrator.prompts import return_instructions_orchestrator
        prompt = return_instructions_orchestrator()
        self.assertIn("**Result:**",         prompt)
        self.assertIn("**Explanation:**",    prompt)
        self.assertIn("**Recommendation:**", prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
