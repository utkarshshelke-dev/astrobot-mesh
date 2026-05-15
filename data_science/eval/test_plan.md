# Astrobot Test Plan — Validation Procedure for Updated Files

This document covers every test you should run against the updated files. Three layers:

| Layer | Where it runs | Tests | Time |
|---|---|---|---|
| **Layer 1: Automated unit tests** | `pytest` on your machine | 166 tests | < 5 sec |
| **Layer 2: Smoke tests** | `python3 -c` snippets | 8 quick checks | < 30 sec |
| **Layer 3: Integration / end-to-end** | `adk web` in browser | 12 scenarios | ~15 min |

Run them in order. If Layer 1 fails, don't bother with Layer 2.

---

## Pre-flight: Make sure files are in place

```bash
cd ~/astrobot_mesh

# Verify these exist
ls -la ad_campaign_dataset_config_v3.json
ls -la data_science/agent.py
ls -la data_science/prompts.py
ls -la data_science/tools.py
ls -la data_science/lib/{channel_resolver,question_router,sql_builder}.py
ls -la data_science/utils/{knowledge_manager,sql_validator}.py
ls -la data_science/tests/test_{channel_resolver,question_router,sql_builder,knowledge_manager,sql_validator}.py
ls -la data_science/tests/conftest.py
ls -la pytest.ini

# If any of those are missing, copy them from the astrobot_integration/ download.
```

---

## Layer 1: Automated unit tests (166 tests)

### Setup

```bash
cd ~/astrobot_mesh
pip install pytest --break-system-packages  # or just `pip install pytest`
```

### Run all 166 tests

```bash
python3 -m pytest data_science/tests/ -v
```

**Expected output (last line):**
```
============================= 166 passed in 0.32s ==============================
```

If you see fewer tests or any failures, see "Troubleshooting" at the end.

### Run by module

If something fails, narrow down by module:

```bash
# Channel resolver (40 tests) — terminology → exact channel list
python3 -m pytest data_science/tests/test_channel_resolver.py -v

# Question router (24 tests) — question → which table
python3 -m pytest data_science/tests/test_question_router.py -v

# SQL builder (30 tests) — deterministic SQL templates
python3 -m pytest data_science/tests/test_sql_builder.py -v

# Knowledge Manager facade (37 tests) — agent integration surface
python3 -m pytest data_science/tests/test_knowledge_manager.py -v

# SQL validator (35 tests) — anti-pattern detection
python3 -m pytest data_science/tests/test_sql_validator.py -v
```

### Run a single test (debugging)

```bash
python3 -m pytest data_science/tests/test_sql_validator.py::TestVolatilityViolation::test_raw_stddev_triggers_violation -v
```

### Generate test report

```bash
python3 generate_test_report.py
# Creates TEST_REPORT.md with every test name + assertions + pass/fail
```

### What each module verifies

| Module | What it prevents |
|---|---|
| `test_channel_resolver.py` | "Direct" mistakenly → "DEFAULT", "awareness" missing channels, organic with paid |
| `test_question_router.py` | Pacing questions routed to performance table |
| `test_sql_builder.py` | Missing FULL OUTER JOIN, raw STDDEV instead of CV, etc. |
| `test_knowledge_manager.py` | Context injection broken, prompt snippet bloat, wrong KPI column |
| `test_sql_validator.py` | Anti-pattern regex false positives/negatives, severity logic |

---

## Layer 2: Smoke tests (8 manual checks)

These verify modules import correctly and basic flows work BEFORE you boot adk.

### Smoke 1: KnowledgeManager imports and loads config

```bash
cd ~/astrobot_mesh
python3 -c "
from data_science.utils.knowledge_manager import manager as km
print('Clients:', km.list_clients())
print('NPI tables:', km.list_tables('NPI'))
"
```

**Expected:**
```
Clients: ['NPI', 'Venetian', 'WinnDixie']
NPI tables: ['performance', 'pacing']
```

❌ If you see "MODULE NOT FOUND" → `utils/__init__.py` missing or wrong path.

### Smoke 2: SQL validator imports

```bash
cd ~/astrobot_mesh
python3 -c "
from data_science.utils.sql_validator import validate_sql, get_decision
r = validate_sql('SELECT STDDEV(Conversions) FROM x', 'most volatile?')
print('Question type detected:', r['question_type'])
print('Violations:', [v['rule_id'] for v in r['violations']])
print('Decision:', get_decision(r))
"
```

**Expected:**
```
Question type detected: ['volatility']
Violations: ['volatility_use_cv_not_stddev']
Decision: retry
```

### Smoke 3: Channel resolver returns correct lists

```bash
cd ~/astrobot_mesh
python3 -c "
from data_science.utils.knowledge_manager import manager as km
print('Direct →', km.resolve_term_safe('NPI', 'direct')['channels'])
print('Awareness →', km.resolve_term_safe('NPI', 'awareness')['channels'])
print('Organic →', km.resolve_term_safe('NPI', 'organic')['channels'])
"
```

**Expected:**
```
Direct → ['Direct']
Awareness → ['Linear TV', 'CTV', 'OTT', 'Online Audio', 'Online Video', 'Paid Video', 'Video', 'OOH', 'Print']
Organic → ['Organic Search', 'Organic Social', 'Organic Video', 'Direct', 'Referral', 'Email']
```

❌ If "Direct" returns "DEFAULT" → config v3 not loaded; check `DATASET_CONFIG_FILE_V3` env var.

### Smoke 4: Question router picks correct tables

```bash
cd ~/astrobot_mesh
python3 -c "
from data_science.utils.knowledge_manager import manager as km

scenarios = [
    ('Which channel has lowest CPA?', 'performance'),
    ('Are we pacing well in December?', 'pacing'),
    ('Show me organic efficiency', 'performance'),
    ('Budget remaining for NPI?', 'pacing'),
    ('Forecast next quarter conversions', 'performance'),
]
for question, expected in scenarios:
    ctx = km.route_and_load_context(question, 'NPI')
    status = '✓' if ctx['routed_table_id'] == expected else '✗'
    print(f\"{status} '{question[:40]}' → {ctx['routed_table_id']} (expected {expected})\")
"
```

**Expected:** All 5 lines show ✓.

### Smoke 5: SQL validator catches the documented bugs

```bash
cd ~/astrobot_mesh
python3 -c "
from data_science.utils.sql_validator import validate_sql

# Bug 1: Channel='DEFAULT' for direct conversions (was a real bug)
r1 = validate_sql(\"SELECT * FROM x WHERE Channel = 'DEFAULT'\", 'Show direct conversions')
print(f'Bug1 (Channel=DEFAULT): caught={len(r1[\"errors\"])>0}, severity={[e[\"severity\"] for e in r1[\"errors\"]]}')

# Bug 2: Raw STDDEV for volatility (was a real bug)
r2 = validate_sql('SELECT Channel, STDDEV(Conversions) FROM x GROUP BY Channel', 'most volatile?')
print(f'Bug2 (raw STDDEV): caught={len(r2[\"warnings\"])>0}')

# Bug 3: total_conv/total_spend as organic efficiency (was a real bug)
r3 = validate_sql('SELECT SAFE_DIVIDE(SUM(Conversions), NULLIF(SUM(Cost), 0)) FROM x', 'organic efficiency?')
print(f'Bug3 (wrong org-eff formula): caught={len(r3[\"warnings\"])>0}')

# Bug 4: SELECT * without LIMIT
r4 = validate_sql('SELECT * FROM x WHERE Client = \"NPI\"', 'show data')
print(f'Bug4 (SELECT * no LIMIT): caught={len(r4[\"errors\"])>0}')

# Negative: correct CV pattern should NOT trigger
r5 = validate_sql(
    'SELECT Channel, SAFE_DIVIDE(STDDEV(Conversions), NULLIF(AVG(Conversions), 0)) AS cv FROM x GROUP BY Channel',
    'most volatile?'
)
vol_violations = [v for v in r5['violations'] if v['rule_id'] == 'volatility_use_cv_not_stddev']
print(f'Negative test (proper CV): false_positive={len(vol_violations)>0}')
"
```

**Expected:**
```
Bug1 (Channel=DEFAULT): caught=True, severity=['error']
Bug2 (raw STDDEV): caught=True
Bug3 (wrong org-eff formula): caught=True
Bug4 (SELECT * no LIMIT): caught=True
Negative test (proper CV): false_positive=False
```

### Smoke 6: Walled garden blocks cross-client

```bash
cd ~/astrobot_mesh
python3 << 'EOF'
import sys
sys.path.insert(0, '.')
from data_science.agent import _ac5_walled_garden_check

tests = [
    # (sql, locked_client, expected_pass)
    ("SELECT Channel FROM `nc-ai-chatbot.Astrobot_NPI.vw_astrobot_npi_nc360_dashboard` LIMIT 10", "NPI", True),
    ("SELECT * FROM `nc-ai-chatbot.Astrobot_Venetian.sample_astrobot_venetian_nc360_dashboard`", "NPI", False),  # cross-client
    ("SELECT * FROM ML.PREDICT(MODEL `nc-ai-chatbot.astrobot_bqml_models.npi_arima_spend`, ...)", "NPI", True),  # BQML OK
]
for sql, cid, expected in tests:
    ok, msg = _ac5_walled_garden_check(sql, cid)
    status = '✓' if ok == expected else '✗'
    print(f"{status} [{cid}] {sql[:60]}... → {'PASS' if ok else 'BLOCK'}")
EOF
```

**Expected:** All 3 lines show ✓.

### Smoke 7: Agent module boots without errors

```bash
cd ~/astrobot_mesh
python3 -c "
from data_science.agent import root_agent
print('Agent name:', root_agent.name)
print('Model:', root_agent.model)
print('Tools:', [t.__name__ for t in root_agent.tools])
print('Sub-agents:', [a.name for a in root_agent.sub_agents])
"
```

**Expected:**
```
Agent name: data_science_root_agent
Model: gemini-2.5-flash
Tools: ['call_analytics_agent', 'call_bigquery_agent']
Sub-agents: ['bqml_agent']
```

❌ If "MISSING REQUIRED ARGUMENT" / "AttributeError" → there's a Python error in `agent.py`. Check the stack trace.

### Smoke 8: Config v3 JSON is valid

```bash
cd ~/astrobot_mesh
python3 -c "
import json
d = json.load(open('ad_campaign_dataset_config_v3.json'))
print('Clients:', [x['client_id'] for x in d['datasets']])
print('Rule count:', len(d['_global_rules']['rule_definitions']))
print('Structured rules:', sum(1 for r in d['_global_rules']['rule_definitions'].values() if isinstance(r, dict)))
"
```

**Expected:**
```
Clients: ['NPI', 'Venetian', 'WinnDixie']
Rule count: 18
Structured rules: 18
```

❌ If "JSONDecodeError" → unbalanced bracket / trailing comma in config v3. Open in editor and check.

---

## Layer 3: Integration tests via adk web (12 scenarios)

Start adk web first:

```bash
cd ~/astrobot_mesh
pkill -f "adk web" 2>/dev/null; sleep 2
rm -f data_science/.adk/session.db 2>/dev/null
export DATASET_CONFIG_FILE=$(pwd)/ad_campaign_dataset_config.json
export DATASET_CONFIG_FILE_V3=$(pwd)/ad_campaign_dataset_config_v3.json
adk web --allow_origins="*"
```

Open the browser at the URL adk prints. Open **a new session** for each scenario unless stated otherwise.

### Test status tracking

Use this checklist as you go:

```
[ ] T1: Client lock works for NPI
[ ] T2: Cross-client blocked
[ ] T3: KM routes to performance table
[ ] T4: KM routes to pacing table
[ ] T5: Channel taxonomy: "Direct" → 'Direct' not 'DEFAULT'
[ ] T6: Channel taxonomy: "awareness" includes all 9 channels
[ ] T7: SQL validator catches raw STDDEV (volatility)
[ ] T8: SQL validator catches Channel='DEFAULT' as error
[ ] T9: Walled garden blocks Venetian table in NPI session
[ ] T10: AC-3 dry-run catches bad SQL syntax
[ ] T11: ML.FORECAST works (BQML exception)
[ ] T12: Pacing question hits real budget table
```

### T1: Client lock works for NPI

**New session. Type:**
```
For NPI, show me the lowest CPA channel last 12 months
```

**Expected in adk web logs:**
```
🔒 Session LOCKED to client: NPI
📍 KM routed 'For NPI, show me the...' → table=performance (confidence=low)
```

**Expected in UI:** Table with channels and CPA, lowest first.

### T2: Cross-client blocked mid-session

**Same session as T1. Type:**
```
Now show me Venetian's data
```

**Expected:** Agent refuses, says something like "This session is locked to NPI. Click + New Session to analyze Venetian."

**Expected in logs:**
```
🚫 Cross-client attempt: Venetian while locked to NPI
```

### T3: KM routes performance question to performance table

**New session. Type:**
```
For NPI, what's the channel mix in November vs December?
```

**Expected in logs:**
```
📍 KM routed 'For NPI, what's the channel mix...' → table=performance
```

**Expected in UI:** Channel × month comparison.

### T4: KM routes pacing question to pacing table

**New session. Type:**
```
For NPI, are we pacing well in December?
```

**Expected in logs:**
```
📍 KM routed 'For NPI, are we pacing well...' → table=pacing (confidence=low)
```

Since pacing has `enabled: true` and you have the real DDL now, it should generate SQL against `vw_astrobot_npi_nc360_budget`. If you set `enabled: false`, it returns the "not available yet" message instead.

### T5: Channel taxonomy — "Direct" is correct

**New session. Type:**
```
For NPI, show me Direct conversions over the last 12 months
```

**Expected:** SQL should use `Channel = 'Direct'` (not `Channel = 'DEFAULT'`).

**Expected in logs:** If the LLM tries `Channel = 'DEFAULT'`, the SQL validator should catch it:
```
SQL VALIDATOR BLOCKED: 1 error(s) for question type [...] —
errors: ['always_resolve_channel_terms_via_taxonomy']
```

Then a retry should produce the correct SQL.

### T6: Channel taxonomy — "awareness" includes all channels

**New session. Type:**
```
For NPI, what's our total awareness spend last 12 months?
```

**Expected:** SQL filter contains all 9 awareness channels:
```sql
WHERE Channel IN ('Linear TV', 'CTV', 'OTT', 'Online Audio',
                  'Online Video', 'Paid Video', 'Video', 'OOH', 'Print')
```

**If you see only 2-3 channels** (e.g., just `Linear TV, CTV`), the LLM is guessing instead of calling `resolve_channel_reference_tool`. Check that the tool is registered (see SUB_AGENT_BQ_PATCH.py).

### T7: SQL validator catches raw STDDEV for volatility

**New session. Type:**
```
For NPI, which channel is most volatile?
```

**Expected:**
1. LLM first attempt may use raw `STDDEV(Conversions)`
2. Validator catches it (`volatility_use_cv_not_stddev`, severity=warn)
3. LLM retries with `SAFE_DIVIDE(STDDEV(...), NULLIF(AVG(...), 0))`
4. Final result shows CV-based ranking

**Expected in logs:**
```
SQL VALIDATOR warns: 1 warning(s) — requesting retry (attempt 1)
```

### T8: SQL validator catches Channel='DEFAULT' as error

**New session.** This one is tricky to test directly because the LLM rarely uses 'DEFAULT' anymore. But you can force it:

```
For NPI, what are the conversions where Channel = 'DEFAULT'?
```

**Expected:** Even though the user explicitly typed `DEFAULT`, the validator should catch it on execution. The agent should explain that 'DEFAULT' is unmapped data and ask if they meant 'Direct'.

### T9: Walled garden blocks Venetian table in NPI session

**Same session as T1 or new NPI session. Try:**
```
For NPI, compare with Venetian's spend last quarter
```

**Expected:** Either:
- Agent refuses the cross-client comparison (preferred), OR
- If LLM tries to write a query referencing Venetian's table, walled garden blocks it:
```
AC-5 BLOCKED: Cross-client violation: SQL references Venetian's dataset (astrobot_venetian)
while session is locked to NPI.
```

### T10: AC-3 dry-run catches bad SQL

**This is hard to trigger intentionally** because CHASE-SQL produces syntactically valid SQL. But you can force it by asking for a non-existent column:

```
For NPI, what's the average Foo_Bar_Baz by channel?
```

**Expected:** Dry-run catches the unknown column, sends back to LLM, LLM corrects to a real column.

### T11: ML.FORECAST works (BQML exception)

**New session. Type:**
```
Forecast NPI conversions for the next quarter
```

**Expected:**
- LLM uses `arima_npi_all_conversions` model
- ML.FORECAST query passes walled-garden (BQML exception)
- Returns forecast values with confidence intervals

### T12: Pacing question hits real budget table

**New session. Type:**
```
For NPI, what's the budget remaining by channel?
```

**Expected:**
- Routes to pacing table
- SQL uses `nc-ai-chatbot.Astrobot_NPI.vw_astrobot_npi_nc360_budget`
- GROUP BY uses `GVMM_Channel` (not `Channel`)
- Excludes `GVMM_Channel = 'DEFAULT'`
- Result table shows budget by channel

If pacing is `enabled: false`, you get the friendly "not available yet" message instead.

---

## Troubleshooting

### Layer 1 fails

**Symptom:** `pytest` reports collection errors or failures.

| Error | Likely cause | Fix |
|---|---|---|
| `ModuleNotFoundError: No module named 'lib'` | `data_science/lib/__init__.py` missing | Copy from astrobot_integration/ |
| `ModuleNotFoundError: No module named 'utils'` | `data_science/utils/__init__.py` missing | Copy from astrobot_integration/ |
| `FileNotFoundError: ad_campaign_dataset_config_v3.json` | Config not at project root | Move it to `~/astrobot_mesh/` |
| `KeyError: 'datasets'` | Wrong config file loaded | Set `DATASET_CONFIG_FILE_V3` env var |
| Specific test failures with red X | Real test regression | Read the assertion message — code was edited |

**Run failing test alone:**
```bash
python3 -m pytest data_science/tests/test_X.py::TestY::test_specific -v --tb=long
```

### Layer 2 fails

**Symptom:** Python `-c` snippets throw errors.

| Error | Likely cause | Fix |
|---|---|---|
| `AttributeError: 'KnowledgeManager' object has no attribute 'X'` | Old KM file still on disk | Re-copy `data_science/utils/knowledge_manager.py` |
| `ImportError: cannot import name 'validate_sql'` | sql_validator.py missing | Copy it |
| `ValueError: Unknown client 'NPI'` | Config v3 not loaded | Check env var; check file exists |
| Channels show as `[]` empty list | Config v3 path placeholder not replaced | Verify `table_full_path` not `<...>` |

### Layer 3 fails

**Symptom:** adk web behaves wrong.

| Symptom | Likely cause | Fix |
|---|---|---|
| Agent asks "which client" after you said NPI | `_detect_client_from_text()` not matching | Check the function in agent.py |
| Wrong table queried | KM routing returns wrong table_id | Smoke test 4 should have caught this |
| SQL still uses `Channel='DEFAULT'` | Validator not wired in OR not running | Check before_tool_callback in agent.py |
| Awareness only has 2 channels | LLM not calling resolve_channel_reference_tool | Check SUB_AGENT_BQ_PATCH applied to bigquery sub-agent |
| 504 timeout on first message | Vertex AI quota / cold start | Wait 30s, retry |
| `MALFORMED_FUNCTION_CALL` error | Argument too large | Should be caught by `_enforce_arg_size` guard |

---

## Test counts after each module

When all tests pass, you should see:

```
data_science/tests/test_channel_resolver.py    →  40 tests
data_science/tests/test_question_router.py     →  24 tests
data_science/tests/test_sql_builder.py         →  30 tests
data_science/tests/test_knowledge_manager.py   →  37 tests
data_science/tests/test_sql_validator.py       →  35 tests
                                          TOTAL: 166 tests passing in <1 second
```

---

## Quick reference: run order

```bash
# 1. Pre-flight: verify files exist
ls -la ~/astrobot_mesh/data_science/utils/sql_validator.py  # should exist

# 2. Layer 1: unit tests (should be 166 passed)
cd ~/astrobot_mesh
python3 -m pytest data_science/tests/ -v

# 3. Layer 2: smoke tests (paste the 8 snippets, all should print expected output)

# 4. Layer 3: adk web with the 12 scenarios in your browser

# 5. If all pass: deploy to Cloud Run as astrobot-ds-v2
```

---

## After deploying

Once all 3 layers pass and you've deployed to Cloud Run:

1. **Smoke test the deployed service:**
   ```bash
   curl https://astrobot-ds-v2-XXXXX-uc.a.run.app/health
   ```

2. **Run the 12 integration scenarios against the deployed URL** (not localhost).

3. **Check Cloud Run logs** for any errors:
   ```bash
   gcloud run services logs read astrobot-ds-v2 --region us-central1 --limit 50
   ```

4. **Monitor for the first hour** — quota, latency, error rate.

5. **If stable: announce to pilot users.** Direct them to the new URL.

---

## Adding more tests

When you add new tables/clients/rules (see ADD_NEW_TABLE.md), add corresponding tests:

| You added | Test file | Pattern |
|---|---|---|
| New client | `test_channel_resolver.py` | `def test_new_client_loads()` |
| New table | `test_question_router.py` | `def test_new_table_routes_correctly()` |
| New rule | `test_sql_validator.py` | `def test_new_rule_catches_pattern()` |

Keep tests fast (<1 ms each). They run in <1 second total — keep it that way.

Always update `TEST_REPORT.md` after adding tests:
```bash
python3 generate_test_report.py
```