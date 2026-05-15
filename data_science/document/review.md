# ADD_NEW_TABLE.md — How to extend Astrobot with new tables and clients

This document covers three scenarios:

1. **Add a new TABLE to an existing CLIENT** (e.g., `creative` table for NPI)
2. **Add a new CLIENT entirely** (e.g., Caesars, MGM)
3. **Add a new SQL VALIDATION RULE** (e.g., new anti-pattern to detect)

All changes are made in **two files**:
- `~/astrobot_mesh/ad_campaign_dataset_config_v3.json` (config — most changes)
- `~/astrobot_mesh/data_science/agent.py` (only if you want a hardcoded fallback)

No prompt edits, no agent code changes. Restart `adk web` and the new table/client/rule is live.

---

## 1. Add a new TABLE to an existing client

### Example: Add `creative` table for NPI

Open `ad_campaign_dataset_config_v3.json`. Find the NPI client block (`"client_id": "NPI"`). Inside its `"tables": [...]` array, append a new table entry:

```json
{
  "table_id": "creative",
  "_purpose": "Creative-level performance — ad-by-ad CTR, conversion rate, video completion",
  "enabled": true,
  "table_full_path": "nc-ai-chatbot.Astrobot_NPI.vw_astrobot_npi_creative_performance",
  "primary_metric": "Conversions",
  "kpi_column": "Conversions",
  "channel_column": "Channel",
  "client_column": "Client",
  "date_column": "Date",
  "spend_column": "Cost",

  "schema": {
    "_note": "Optional but recommended — documents columns for future devs",
    "dimensions": ["Date", "Client", "Channel", "Campaign", "Ad",
                   "Ad_Type", "Creative", "Ad_Group", "Targeting_Type"],
    "metrics": ["Cost", "Impressions", "Clicks", "Conversions",
                "Video_Views", "Video_Views_25Pct", "Video_Views_50Pct",
                "Video_Views_75Pct", "Video_Views_100Pct",
                "Engaged_Sessions"]
  },

  "channel_taxonomy": {
    "_inherit_from": "performance",
    "_note": "Same taxonomy as performance table"
  },

  "duality": {
    "has_duality": false,
    "_note": "Creative table has single-row metrics per ad-day. No spend/conv split."
  },

  "rules": [
    "video_completion_rate_pattern",
    "exclude_NA_creatives",
    "always_filter_by_client",
    "always_use_date_range_filter"
  ],

  "applicable_questions": [
    "creative",
    "ad type",
    "video completion",
    "creative performance",
    "which ad",
    "creative resonance",
    "video views",
    "ad-level",
    "best creative",
    "worst creative"
  ]
}
```

### Required fields explained

| Field | Required? | What it does |
|---|---|---|
| `table_id` | ✅ Yes | Used by the router. Must be unique per client. |
| `table_full_path` | ✅ Yes | Used in FROM clauses. Full BQ path. |
| `enabled` | Optional (default true) | Set to `false` to hide table while developing. Returns "not available yet" message. |
| `kpi_column` | ✅ Yes | Primary metric the LLM defaults to (Conversions / KPI / etc.) |
| `channel_column` | ✅ Yes | Column to GROUP BY for channel analysis (Channel / GVMM_Channel) |
| `client_column` | ✅ Yes | Column to filter on for client isolation |
| `date_column` | ✅ Yes | Column for date filters |
| `spend_column` | ✅ Yes | Cost / Spend column for budget analyses |
| `channel_taxonomy` | ✅ Yes | Dict of category → list of channel names |
| `duality` | ✅ Yes | `{has_duality: bool}` — true if spend and conversions are on separate rows |
| `rules` | ✅ Yes | List of rule_ids from `_global_rules.rule_definitions` |
| `applicable_questions` | ✅ Yes | Keywords that route a question to this table |

### Optional but recommended

| Field | What it does |
|---|---|
| `schema` | Documents column names for devs. Not used at runtime. |
| `_purpose` | Free-form description for humans. |
| `_note` / `_note_to_user` | Comments — fields starting with `_` are ignored by code. |

### Step 2: Add any new rules to `_global_rules.rule_definitions`

If your new table references rule IDs that don't exist yet, add them at the bottom of the config:

```json
"_global_rules": {
  "rule_definitions": {
    "// existing rules...": "",

    "video_completion_rate_pattern": {
      "description": "Use SAFE_DIVIDE(SUM(Video_Views_100Pct), NULLIF(SUM(Video_Views), 0)) for completion rate.",
      "applies_to_question_types": ["creative", "video_completion"],
      "anti_pattern_regex": "(?i)SUM\\(Video_Views_100Pct\\)\\s*/\\s*SUM\\(Video_Views\\)",
      "violation_msg": "Use SAFE_DIVIDE for completion rate to avoid divide-by-zero.",
      "severity": "warn"
    },

    "exclude_NA_creatives": {
      "description": "Filter Creative != 'NA' for creative-level analyses",
      "applies_to_question_types": ["creative"],
      "anti_pattern_regex": null,
      "violation_msg": "Add WHERE Creative != 'NA' to exclude placeholder creatives.",
      "severity": "info"
    }
  }
}
```

Rule fields:

| Field | What |
|---|---|
| `description` | What the rule means (shown to LLM in prompt context) |
| `applies_to_question_types` | List of question types this rule applies to. `"*"` = all. |
| `anti_pattern_regex` | Regex that, when matched, indicates a violation. `null` = info-only. |
| `violation_msg` | Message sent to LLM when violation detected |
| `severity` | `error` blocks SQL · `warn` retries once then allows · `info` logs only |

### Step 3: Restart adk

```bash
cd ~/astrobot_mesh
pkill -f "adk web" 2>/dev/null; sleep 2
adk web --allow_origins="*"
```

### Step 4: Test

Open a new session with NPI locked, ask:
```
For NPI, which creative has the highest video completion rate?
```

Expected logs:
```
📍 KM routed 'Which creative has...' → table=creative (confidence=medium)
```

If routing picks the wrong table, check that your keywords in `applicable_questions` don't overlap with another table's keywords.

---

## 2. Add a new CLIENT entirely

### Example: Add `Caesars` client

Open `ad_campaign_dataset_config_v3.json`. In the top-level `"datasets": [...]` array, append a new client:

```json
{
  "client_id": "Caesars",
  "name": "Astrobot_Caesars",
  "description": "Caesars Entertainment — hospitality and gaming client",
  "default_metric": "Conversions",
  "default_lookback_months": 12,
  "tables": [
    {
      "table_id": "performance",
      "enabled": true,
      "table_full_path": "nc-ai-chatbot.Astrobot_Caesars.vw_astrobot_caesars_nc360_dashboard",
      "kpi_column": "Conversions",
      "channel_column": "Channel",
      "client_column": "Client",
      "date_column": "Date",
      "spend_column": "Cost",

      "channel_taxonomy": {
        "organic": ["Organic Search", "Direct", "Email"],
        "paid": ["Paid Search", "Paid Social", "Display", "OTT", "Linear TV"],
        "awareness": ["OTT", "Linear TV", "OOH", "Online Video"],
        "direct_response": ["Paid Search"],
        "mid_funnel": ["Paid Social", "Display", "Demand Gen"],
        "tv": ["Linear TV", "OTT"]
      },

      "duality": {
        "has_duality": true,
        "spend_rows_filter": "Cost > 0",
        "conv_rows_filter": "Conversions > 0",
        "_note": "Caesars uses same nc360 dashboard structure as NPI"
      },

      "channel_unification": {
        "Paid Search": ["Search", "Paid Search"],
        "Demand Gen + P-Max": ["Cross-network", "Demand Gen", "Performance Max"],
        "Paid Social": ["Paid Social"],
        "Video/CTV/OTT/TV": ["Online Video", "Paid Video", "OTT", "CTV", "Linear TV", "Video"]
      },

      "rules": [
        "blended_cpa_use_unified_cte",
        "ranking_use_unified_cte",
        "always_resolve_channel_terms_via_taxonomy",
        "always_filter_by_client",
        "always_use_date_range_filter",
        "use_safe_divide_for_ratios"
      ],

      "applicable_questions": [
        "cpa", "channel", "performance", "conversions", "spend",
        "lift", "halo", "forecast", "volatility"
      ]
    }
  ]
}
```

### Step 2 (optional): Update hardcoded fallback in agent.py

If you want a hardcoded safety net in case KM fails, edit `~/astrobot_mesh/data_science/agent.py`:

```python
_CLIENT_TABLE_MAP = {
    "NPI":       f"{_PROJECT_ID}.Astrobot_NPI.vw_astrobot_npi_nc360_dashboard",
    "Venetian":  f"{_PROJECT_ID}.Astrobot_Venetian.sample_astrobot_venetian_nc360_dashboard",
    "WinnDixie": f"{_PROJECT_ID}.Astrobot_WinnDixie.sample_astrobot_wd_nc360_dashboard",
    "Caesars":   f"{_PROJECT_ID}.Astrobot_Caesars.vw_astrobot_caesars_nc360_dashboard",  # NEW
}
```

Skip this step if you trust KM to be available — the v3 config is the canonical source.

### Step 3: Client detection in agent.py (optional)

The default `_detect_client_from_text()` reads `km.list_clients()` and matches lowercase substrings. If Caesars users will write "Caesar" or "Caesars Palace" instead of "Caesars", add an alias:

```python
def _detect_client_from_text(text: str) -> Optional[str]:
    if not text:
        return None
    text_low = text.lower()

    # KM-discovered clients
    if _KM_AVAILABLE and km is not None:
        for client_id in km.list_clients():
            if client_id.lower() in text_low:
                return client_id

    # Aliases (add new client aliases here)
    if "npi" in text_low or "nassau" in text_low or "paradise island" in text_low:
        return "NPI"
    if "venetian" in text_low:
        return "Venetian"
    if "winndixie" in text_low or "winn dixie" in text_low or "seg" in text_low:
        return "WinnDixie"
    if "caesars" in text_low or "caesar" in text_low or "caesars palace" in text_low:  # NEW
        return "Caesars"
    return None
```

### Step 4: Restart and test

```bash
adk web --allow_origins="*"
```

In a new session, ask:
```
For Caesars, what's the best-performing channel last quarter?
```

Verify:
- Logs show `🔒 Session LOCKED to client: Caesars`
- Logs show `📍 KM routed ... → table=performance`
- SQL references `nc-ai-chatbot.Astrobot_Caesars.vw_astrobot_caesars_nc360_dashboard`

---

## 3. Add a new SQL VALIDATION RULE

### Example: Catch missing FULL OUTER JOIN in blended CPA queries

Open `ad_campaign_dataset_config_v3.json` and find `_global_rules.rule_definitions`. Add your new rule:

```json
"blended_cpa_must_use_full_outer_join": {
  "description": "Blended CPA with duality requires FULL OUTER JOIN to capture both spend and conversion rows",
  "applies_to_question_types": ["blended_cpa", "cpa"],
  "anti_pattern_regex": "(?i)WITH\\s+unified\\s+AS[\\s\\S]{0,500}FROM\\s+unified\\s+WHERE\\s+Cost\\s*>\\s*0",
  "violation_msg": "When duality.has_duality is true, use FULL OUTER JOIN between spend CTE and conv CTE. Don't filter Cost > 0 directly — it loses conversion rows.",
  "severity": "warn"
}
```

That's it. The validator auto-discovers it on next agent boot.

### Rule design principles

When writing a new rule:

1. **Pick severity carefully**:
   - `error`: Use for SECURITY or DATA CORRUPTION patterns (e.g., Channel='DEFAULT'). Blocks SQL completely.
   - `warn`: Use for BUSINESS LOGIC bugs (volatility without CV). Retries once, then allows.
   - `info`: Use for STYLE / HINT (date filter recommended). Logs only, never blocks.

2. **Make the regex specific**:
   - Bad: `STDDEV` — matches any STDDEV, even correctly-wrapped ones
   - Good: `(?<!SAFE_DIVIDE\()STDDEV\([^)]+\)(?!\s*/\s*(?:NULLIF\()?AVG)` — only matches raw STDDEV

3. **Test against false positives**:
   - Before adding a rule, run it against your existing test SQL queries
   - If it matches anything that's actually correct, refine the regex

4. **Use clear violation_msg**:
   - The LLM reads this message and rewrites the SQL
   - Be specific: tell it WHAT to do, not just what's wrong
   - Bad: "Use unified CTE"
   - Good: "Wrap with `WITH unified AS (SELECT CASE WHEN Channel IN ('Search','Paid Search') THEN 'Paid Search' ELSE Channel END AS uc, ...) ...`"

### Test your new rule

Add a unit test to `data_science/tests/test_sql_validator.py`:

```python
def test_blended_cpa_without_full_outer_join_triggers(self):
    sql = """
    WITH unified AS (SELECT ... FROM x)
    SELECT uc, SUM(Cost)/SUM(Conversions) FROM unified WHERE Cost > 0
    """
    result = validate_sql(sql, "Blended CPA?")
    rule_ids = [v["rule_id"] for v in result["violations"]]
    assert "blended_cpa_must_use_full_outer_join" in rule_ids
```

Run:
```bash
cd ~/astrobot_mesh
python3 -m pytest data_science/tests/test_sql_validator.py -v
```

If the test passes, your rule is working.

---

## Where things live

```
~/astrobot_mesh/
├── ad_campaign_dataset_config_v3.json    ← Single source of truth.
│                                           Edit here for new tables, clients, rules.
├── data_science/
│   ├── agent.py                          ← Edit ONLY for hardcoded fallbacks and aliases
│   ├── lib/
│   │   ├── channel_resolver.py           ← Don't edit — reads from config
│   │   ├── question_router.py            ← Don't edit — reads from config
│   │   └── sql_builder.py                ← Don't edit — uses config patterns
│   ├── utils/
│   │   ├── knowledge_manager.py          ← Don't edit — facade
│   │   └── sql_validator.py              ← Edit ONLY for new question_type keywords
│   └── tests/
│       ├── test_channel_resolver.py      ← Add test if new client
│       ├── test_question_router.py       ← Add test if new table
│       ├── test_sql_builder.py
│       ├── test_knowledge_manager.py
│       └── test_sql_validator.py         ← Add test if new rule
```

**Rule of thumb**: if your change is data (a table, a client, a rule), it goes in JSON. If it's a new question-type keyword (e.g., "lift" should also catch "halo"), it goes in `sql_validator.py`. Everything else stays untouched.

---

## Common mistakes

1. **Forgetting to add `enabled: true`** — Tables default to enabled, but if you copy from the pacing block (which has `enabled: false`), it'll stay disabled.

2. **Keyword overlap between tables** — If two tables in the same client list the same keyword, the router picks the one with MORE matches. If they tie, the first defined wins. Use unique keywords.

3. **Missing rules in `_global_rules.rule_definitions`** — If your table's `rules` list references a `rule_id` not defined globally, it's silently skipped. Check for typos.

4. **Regex without anchors** — `STDDEV(x)` matches inside `SAFE_DIVIDE(STDDEV(x), AVG(x))`. Use lookbehind/lookahead to be precise.

5. **Forgetting to restart `adk web`** — Config is loaded at boot. Editing JSON while adk is running has no effect until restart.

6. **JSON syntax errors** — A trailing comma will silently break agent boot. Always run `python3 -c "import json; json.load(open('ad_campaign_dataset_config_v3.json'))"` after editing.

---

## Adding a NEW table — full checklist

```
[ ] 1. Verify the BQ table actually exists and you can query it manually
[ ] 2. Get the column list (just like you did for the pacing table)
[ ] 3. Open ad_campaign_dataset_config_v3.json
[ ] 4. Find the client block, add new table to "tables": [...]
[ ] 5. Fill all required fields (table_id, table_full_path, kpi_column, etc.)
[ ] 6. Add any new rules to _global_rules.rule_definitions
[ ] 7. Validate JSON: python3 -c "import json; json.load(open('ad_campaign_dataset_config_v3.json'))"
[ ] 8. Add a test in data_science/tests/test_question_router.py:
       def test_new_table_routes_correctly():
           ctx = km.route_and_load_context("creative video completion?", "NPI")
           assert ctx["routed_table_id"] == "creative"
[ ] 9. Run pytest: python3 -m pytest data_science/tests/
[ ] 10. Restart adk web
[ ] 11. Test with a real question in the UI
[ ] 12. Check logs for: 📍 KM routed ... → table=<new_table_id>
[ ] 13. Verify SQL references the correct table path
```

---

## Adding a NEW client — full checklist

```
[ ] 1. Verify the BQ dataset Astrobot_<ClientName> exists
[ ] 2. Identify the primary dashboard table (vw_ or sample_)
[ ] 3. Open ad_campaign_dataset_config_v3.json
[ ] 4. Add new entry to top-level "datasets": [...]
[ ] 5. Fill client_id, name, description
[ ] 6. Add at least one table (usually "performance")
[ ] 7. Define channel_taxonomy for this client (clients differ in channels!)
[ ] 8. (Optional) Add fallback table_path to _CLIENT_TABLE_MAP in agent.py
[ ] 9. (Optional) Add client name aliases to _detect_client_from_text() in agent.py
[ ] 10. Validate JSON
[ ] 11. Add a test in data_science/tests/test_channel_resolver.py:
        def test_new_client_loads():
            assert "Caesars" in km.list_clients()
[ ] 12. Run pytest
[ ] 13. Restart adk web
[ ] 14. Test client locking: "For Caesars, ..." should set client_lock
[ ] 15. Test KM table lookup: state.routed_table_path is correct
[ ] 16. Run a real query and verify SQL hits the right table
```