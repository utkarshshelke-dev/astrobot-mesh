# Session 10 Resume Doc — for Session 11 (post-break, fresh context)

**Created:** Wed May 20, 2026 ~hour 9.7 of Session 10
**Deployed:** astrobot-ds-v4-00008-vjh at https://astrobot-ds-v4-2jfu4lrr2q-uc.a.run.app
**Branch:** v3-dev (5 commits today; last commit b43e136)

═══════════════════════════════════════════════════════════════
## PASTE INTO NEW CONVERSATION (short version)
═══════════════════════════════════════════════════════════════

Resuming Astrobot Mesh work from Session 10. The full session 10 transcript
is at /mnt/transcripts/2026-05-20-{timestamp}.txt. Today shipped 5 verified
wins in production (WinnDixie filter, BEF dynamic discovery, 4 tool regression
fixes, Phase H anti-hallucination, Fix-T state substitution). Verified working
in fresh sessions; long sessions may drift due to LLM reusing prior turn
output. Six remaining items: long-session drift (~2-3h), model-name
hallucination (~1-2h), chart viz intermittent failure (~1-2h), saturation
tool 1-row issue (~1-2h), Phase D train-from-scratch (~2-3h), Phase G e2e
tests (~1h). Total remaining: 8-13 hours of work, spread across 1-2 sessions.

Start by reading docs/sessions/2026-05-20/session-10-resume-doc.md (this file)
for full context. Then verify deployed revision is still astrobot-ds-v4-00008-vjh
and run smoke tests 4-8 from this doc to confirm current state.

═══════════════════════════════════════════════════════════════
## VERIFIED WORKING — DO NOT REWORK
═══════════════════════════════════════════════════════════════

1. **WinnDixie filter routing** (commits 011c3ba + b43e136)
   - client_filter_value="SEG" in Firestore for WinnDixie
   - get_client_filter_value() helper in channel_resolver.py
   - 3 state-population sites in agent.py
   - 14 changes in bigquery/tools.py for SQL filter routing
   - Verified: "Show total spend by channel for last quarter" returns 10 rows
     for WinnDixie (Paid Social $650K, Search $456K, PMax $417K, CTV $327K, etc.)
   - To re-verify: lock WinnDixie in dev-ui, ask "spend by channel last quarter"

2. **BEF dynamic BQML discovery + state injection** (commit 2320df2)
   - data_science/lib/bqml_registry.py (NEW, 8 functions)
   - bqml_before_agent_callback in sub_agents/bqml/agent.py
   - {client_models_inventory} placeholder in bqml/prompts.py
   - Verified: NPI shows 37-40 models with health flags; degenerate models
     (npi_conversions_saturation r²=NaN MAE=0) marked correctly
   - To re-verify: "what BQML models do you have for NPI?"

3. **4 BQML/analysis tool regression fixes** (commit 011c3ba)
   - compute_channel_volatility, compute_saturation_curve,
     train_arima_model_bqml, train_saturation_model_bqml in bigquery/tools.py
   - Added `client_filter = get_client_filter_value(client_id)` lookup
   - Verified: "next $100K allocation" prompt no longer errors with
     "name 'client_filter' is not defined"

4. **Phase H anti-hallucination** (commit c8fe4e6)
   - Removed worked-example numbers ($85.50 Social, $44.94 Search, etc.)
   - Replaced with <placeholder> syntax in 2 separate worked-example blocks
   - Stripped literal numbers from MANDATORY_TOOL_CALL rule
   - Moved MANDATORY rule to top of prompt (before FORECAST_HANDLING)
   - Verified: FRESH session test (incognito browser) — saturation analysis
     returns REAL BQ data (Paid Search R²=0.867, etc.) not fabricated numbers
   - **IMPORTANT:** Only verified in fresh sessions. Long sessions may drift.

5. **Fix-T state substitution for SQL templates** (commit 7becfea)
   - bqml callback now populates state[client_lower] + state[LOCKED_CLIENT_LOWER]
   - 18 placeholder swaps: <client_lower>_X → {state.client_lower}_X
   - Astrobot_<client>.vw_astrobot_<client_lower>_X →
     Astrobot_{state.LOCKED_CLIENT}.vw_astrobot_{state.client_lower}_X
   - Removed duplicate PLACEHOLDER NOTATION header (had both old + new versions)
   - Verified: no "Unknown client: 'LOCKED_CLIENT'" errors in latest test logs

═══════════════════════════════════════════════════════════════
## SIX REMAINING ITEMS
═══════════════════════════════════════════════════════════════

### Item 1 — Long-session drift (~2-3 hours, architectural)
**Problem:** In long conversations, LLM reuses prior turn output as "established
fact" instead of running fresh queries, despite the MANDATORY rule (lines 19-37
of bqml/prompts.py) explicitly forbidding this.

**Why prompt edits won't fix:** The rule ALREADY says everything I'd want to
add. Today's Phase H edits attempted this 3 times and the LLM still ignored
the rule in contaminated sessions. **Diagnosed via H1 test:** fresh incognito
session works correctly. Same prompt in a session with prior fabricated content
reproduces the same hallucinated numbers.

**Real fix options (pick one):**
- (a) **Conversation history truncation** (~2-3h): Modify ADK callback to scrub
  prior turn content from what the LLM sees. Smallest scope.
- (b) **Tool-call enforcement at framework level** (~4-5h): Intercept LLM
  responses; if specific numbers present and no tool called this turn, reject
  and force re-prompt. Most robust but biggest.
- (c) **Session state validation** (~3-4h): Post-process responses to verify
  numbers came from tool calls. Belt-and-suspenders alongside (b).

**Pre-flight:** Read ADK's after_model_callback / before_tool_callback docs.
Check what callback hooks are available for response interception.

**Anti-pattern to avoid:** Adding more MANDATORY-style rules to the prompt.
Today proved this doesn't work.

### Item 2 — Model name hallucination (~1-2 hours)
**Problem:** Agent invents non-existent model names like `arima_npi_all_spend`
by combining patterns (real names are `arima_npi_all_conversions` AND
`npi_arima_spend` — agent merges them). Self-corrects via list_available_models
after first failure.

**Real fix:** Add explicit rule near top of bqml/prompts.py:
"Only use model names present in {client_models_inventory}. If you're about
to write a model name, verify it's in the inventory first. Never invent
model names by combining patterns from existing ones."

**Pre-flight:** Re-read bqml/prompts.py lines 1-50 to find good insertion
point near the MANDATORY rule.

**Anti-pattern:** Don't write this as a worked example — that's what triggered
the numbers hallucination in the first place.

### Item 3 — Chart visualization intermittent failure (~1-2 hours investigation)
**Problem:** `call_analytics_for_visualization` sometimes fails with
"x and y must have same first dimension, but have shapes (14,) and (0,)".
Worked for conversions forecast (21:23) + clusters (22:40) earlier today.
Failed for spend forecast (22:39) post-deploy. Same agent, same tool.

**Hypothesis:** Data shape varies between models. Conversions returns ints,
spend returns floats — possibly different JSON serialization path.

**Pre-flight diagnostic:**
```bash
"
Read each function — determine if "1 row" is the intentional return format
(summary row) or a bug.

**Anti-pattern:** Don't modify training tools without understanding the
existing return contract. They feed agent's response formatting.

### Item 5 — Phase D: train-from-scratch for new clients (~2-3 hours)
**Problem:** Currently only NPI has the 37+ models. Venetian and WinnDixie
have 0 BQML models. Onboarding a new client should auto-train baseline ARIMA
+ saturation + clustering models on their data.

**Blocked by:** Item 1 (long-session drift) — auto-training based on agent's
data interpretation is dangerous if the agent's interpretation can be wrong.

**Real fix design (when Item 1 is done):**
- New Firestore field per client: `bqml_training_templates`
- Tool: `auto_train_baseline_models(client_id)` that creates 3-5 standard
  models with parameterized SQL
- Wired into onboarding flow

**Anti-pattern:** Don't hardcode NPI's training SQL into the function. Use
the {state.client_lower} pattern from Fix-T.

### Item 6 — Phase G: e2e test suite (~1 hour)
**Problem:** No formalized smoke tests. Today's verification was manual
incognito sessions.

**Real fix design:**
- File: `data_science/tests/test_e2e_smoke.py`
- Test cases:
  - Verify dev-ui endpoint responds
  - For each client (NPI, Venetian, WinnDixie):
    - "What models do you have?" returns >0 models for NPI, expected zero/few
      for others
    - "Forecast spend next 14 days" returns numbers in reasonable range
    - "Saturation analysis" calls tools (not hallucinates)
  - Verify SQL contains real client name, never literal "LOCKED_CLIENT"

**Pre-flight:** Check if pytest is set up in the repo:
```bash
**Anti-pattern:** Don't test against the LLM's natural-language response.
Test against the structured tool calls + final state. Natural language varies.

═══════════════════════════════════════════════════════════════
## SUGGESTED ORDER FOR SESSION 11
═══════════════════════════════════════════════════════════════

Reasoning: dependencies + risk + remaining cap.

1. **Item 6 (Phase G tests)** first, ~1 hour
   - Why: Pure additive, no risk of breaking existing wins
   - Bonus: tests will catch any regression in Items 2-4 work
   - Use those tests to gate Items 2-4 changes

2. **Item 2 (model name hallucination)** ~1-2 hours
   - Why: Smallest of the prompt-edit items, well-scoped
   - Tests from Item 6 confirm it works

3. **Item 4 (saturation tool 1-row)** ~1-2 hours
   - Why: Self-contained, doesn't affect other items
   - May reveal it's intentional behavior (then no fix needed)

4. **Item 3 (chart viz)** ~1-2 hours
   - Why: Most investigation-heavy. Logs comparison may reveal quick fix.

5. **Item 1 (long-session drift)** ~2-3 hours
   - Why: Hardest, most architectural. Tackle when other items are done.
   - Provides confidence to start Item 5 after.

6. **Item 5 (Phase D train-from-scratch)** ~2-3 hours
   - Why: New feature, blocked by Item 1, biggest scope.

**Realistic split:**
- Session 11 (~5-6 hours): Items 6 + 2 + 4 = ~3-5 hours, with buffer
- Session 12 (~5-6 hours): Items 3 + 1 = ~3-5 hours
- Session 13 (~3-4 hours): Item 5 + cleanup

═══════════════════════════════════════════════════════════════
## CRITICAL ANTI-PATTERNS FROM SESSION 10
═══════════════════════════════════════════════════════════════

These are mistakes I made today that I want Session 11 me to NOT repeat:

1. **Grep-and-edit without reading whole files.** Today I had 4 scope surprises
   on Chunk 3 work because I kept grepping for specific patterns and missing
   structurally similar blocks. Read whole files first when in doubt.

2. **Verifying in contaminated sessions.** I declared "Phase H worked"
   based on a test in the same session that had previously contained the
   hallucinated content. Fresh incognito session is REQUIRED for verification.

3. **Adding more MANDATORY rules.** The MANDATORY_TOOL_CALL rule already
   covers everything. Adding more rules doesn't help when the LLM ignores
   the rule. Architectural fix needed instead.

4. **Self-trapping verification.** Putting literal "$85.50, 0.65" in the
   anti-hallucination rule itself, then grepping for those numbers as
   evidence of hallucination. The grep can't distinguish negative-example
   text from real hallucination triggers.

5. **f-string vs plain-string for ADK prompts.** bigquery/prompts.py uses
   plain `return """..."""` + ADK substitutes {state.X} at runtime. bqml/
   prompts.py was f-string `return f"""..."""` which breaks on bare ADK
   placeholders (Python evaluates them first). FIXED but watch for the
   pattern.

6. **Saying "this is bounded ~X min" then surprising.** Today: 5+ scope
   surprises. Don't make sharp estimates on prompt-editing work — read the
   whole file first, then estimate.

7. **Continuing decisions past hour 8.** Multiple "fix-it-now" overrides at
   hour 8+ led to bigger problems (Phase T broke production, Fix-T was
   recovery). If a decision is needed at hour 8+, document and defer.

8. **Misreading my own track record.** I told the user "I cannot fix this
   today" then 30 min later "actually it IS fixed (in fresh session)". Two
   wrong diagnostic calls in a row. Trust the data (BQ verification, logs),
   not recent memory.

═══════════════════════════════════════════════════════════════
## STATE AT SESSION END
═══════════════════════════════════════════════════════════════

### Git
- Branch: v3-dev
- Last 5 commits (Session 10):
I (Session 10 Claude) had no context on these orchestrator changes —
they're from a different work track. Operator should review and commit
or revert as appropriate.

### Backup files preserved
- ~24 .before_* files in data_science/* (today's safety nets)
- All preserved for reference if any commit needs to be reverted

═══════════════════════════════════════════════════════════════
## SMOKE TESTS TO RE-RUN IN SESSION 11 START
═══════════════════════════════════════════════════════════════

Open https://astrobot-ds-v4-2jfu4lrr2q-uc.a.run.app/dev-ui in incognito.
Lock NPI. Run these in order, paste responses back:

**Smoke 1:** "what BQML models do you have for NPI?"
- Expected: 37-40 models listed, grouped by type
- Confirms: BEF dynamic discovery

**Smoke 2:** "Forecast spend for next 14 days"
- Expected: arima model name, real numbers ~$14K-$30K range, chart renders
- Confirms: Forecast path + Fix-T (no LOCKED_CLIENT errors)
- Watch for: Item 3 (chart viz failure)

**Smoke 3:** "Show me saturation analysis by channel"
- Expected: Paid Search R²=0.867, Demand Gen + P-Max R²=0.442, real channels
- Confirms: Phase H anti-hallucination + tool calls actually happening
- Watch for: Item 4 (saturation 1-row issue)

**Smoke 4:** "Build saturation model for NPI"  
- Expected: SQL uses Client = 'NPI' (not LOCKED_CLIENT)
- Confirms: Fix-T state substitution
- Watch for: Item 2 (might invent model names)

**Smoke 5:** Lock WinnDixie. "spend by channel last quarter"
- Expected: 10 rows, $650K Paid Social, $456K Search, etc.
- Confirms: WinnDixie filter still working

If all 5 pass: Session 10 wins held. Proceed to Item 6 (Phase G tests).
If any fail: stop, diagnose, document, then decide.
