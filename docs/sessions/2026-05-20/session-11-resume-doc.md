# Session 11 Resume Doc — 2026-05-20

## Production state at session end
- **Cloud Run service:** `astrobot-ds-v4` in `nc-ai-chatbot` (`us-central1`)
- **Active revision:** `astrobot-ds-v4-00022-mey` (tag `item1d`) — 100% traffic
- **Image:** `gcr.io/nc-ai-chatbot/astrobot-ds-v4:item1d`
- **Production URL:** https://astrobot-ds-v4-2jfu4lrr2q-uc.a.run.app/dev-ui
- **Smoke suite:** 5/5 passing against production
- **Git HEAD:** branch `v3-dev`, ~17 commits ahead of `origin/v3-dev`. NOT YET PUSHED.

## Shipped this session
| # | Item | Commits | Notes |
|---|------|---------|-------|
| 6 | Phase G e2e tests | `d9230f9` | 5/5 green, ~80s runtime |
| 7a | Firestore SEG→TWDC drift fix | (Firestore-only write) | `ds_agent_datasets/WinnDixie.client_filter_value` now `'TWDC'` |
| 7b | NL2SQL client_filter injection | `3ec4ec9` + `e597d08` | MANDATORY clause in instruction string; SEG example stripped from prompt |
| 1 (partial) | Post-model interceptor as dormant infrastructure | `f528b20` + `e512b42` + `4246b9a` | Interceptor ships but is currently dormant — see "Item 1 status" below |

## Critical findings (this session's most important output)

### Finding 1: ADK `{state.X}` placeholders DON'T substitute
- ADK's `inject_session_state` uses `str.isidentifier()` on the var name
- Dots fail isidentifier(), so `{state.LOCKED_CLIENT}` returns False → passes through unchanged
- The correct format is `{LOCKED_CLIENT}` or `{LOCKED_CLIENT?}` (optional)
- **Entire codebase currently uses `{state.X}` form. These are passing through to the LLM as literal text**, treated as informational hints, never substituted.
- The agent works in spite of this, not because of it
- Source: `~/.local/lib/python3.12/site-packages/google/adk/utils/instructions_utils.py`
- Verification: `python3 -c "print('state.LOCKED_CLIENT'.isidentifier())"` → False
- Becomes **Item 10 — Audit all `{state.X}` placeholders, convert to `{X}` form** (~2-4h, codebase-wide)

### Finding 2: LlmResponse shape in ADK
- `LlmResponse` (the ADK wrapper) exposes `.content` directly (with `.parts` inside), NOT `.candidates`
- NOT `llm_response.candidates[0].content.parts` (that's the raw Vertex API shape)
- The existing dedup code in `after_model_callback` uses `.candidates` — fails silently in `except Exception`
- The dedup feature has been dead code since whenever it was written
- Flag for next session: fix dedup loop to use `.content.parts` (~10 min)

### Finding 3: Sub-agent state propagation works, but timing matters
- AgentTool DOES propagate sub-agent state to parent: `tool_context.state.update(event.actions.state_delta)`
- Source: `~/.local/lib/python3.12/site-packages/google/adk/tools/agent_tool.py:259-261`
- BUT: the propagation happens AFTER AgentTool returns. Parent prompt-render for the SAME turn that called the sub-agent has already happened.
- Implication: state captured by a sub-agent callback is visible to the parent on the NEXT turn, not the current one
- This is why state-based narration of the current-turn SQL is architecturally hard

### Finding 4: Item 9's prompt change caused WinnDixie regression
- Adding `{last_executed_sql?}` to the prompts.py Steps narration block caused WinnDixie data queries to return "no data for 2025" on item1b, item1c tag URLs
- NPI also intermittently failed (saturation timeout)
- Hypothesis: the LLM, seeing the placeholder rendered with stale or empty SQL, generated SQL that doesn't match the actual table
- Confirmed by reverting just the prompt: smoke 5/5 passed on item1d
- The callback writes (`tool_context.state["last_executed_sql"] = sql`) are themselves harmless — only the prompt referring to that field was problematic

## Item 1 status (in production but dormant)
What's deployed:
- `bigquery/agent.py` `store_results_in_context` captures `args.get("query")` from `execute_sql` calls into `state["last_executed_sql"]` (sub-agent-level write, propagates to root via state_delta after AgentTool returns)
- `data_science/agent.py` `after_tool_callback` mirrors the write at root layer when `execute_sql` is called directly (defense in depth)
- `data_science/agent.py` `after_model_callback` has `_STEPS_SQL_RE` regex and `_replace_fabricated_sql_in_text()` helper — scans for `**Steps:**`/`Generated SQL:` blocks and would swap fabricated SQL with `state["last_executed_sql"]` if found
- `data_science/prompts.py` Steps narration block reverted to pre-Item-9 state (no `{last_executed_sql?}` placeholder)

What's NOT deployed:
- The prompt directive telling the LLM to put a SQL block in Steps using the state value
- The broad SQL capture in `after_tool_callback` (caused regression, reverted in `4246b9a`)

Net behavior: identical to Item 7b's production. The interceptor is wired and ready but the prompt doesn't trigger Steps SQL blocks, so the interceptor never has a fabricated block to swap.

Next session: revisit narration with a different approach. Options to consider:
1. Move Steps narration into the BQ sub-agent's response (where `last_executed_sql` IS populated in time for the same-turn prompt)
2. Use a different mechanism — e.g., have execute_sql's response include a formatted "narration" field that gets injected by the interceptor
3. Accept that Steps narration with real SQL is architecturally incompatible with the current root-LLM flow

## Pending backlog
| # | Item | Est | Status |
|---|------|-----|--------|
| 1-tail / 9-tail | Steps narration architectural fix | ~2-4h | Approach 1 or 2 above |
| 2 | BQML model name hallucination | ~1-2h | Prompt fix in `data_science/sub_agents/bqml/prompts.py` |
| 3 | Chart viz intermittent failure | ~1-2h | Investigation-heavy |
| 4 | Saturation tool 1-row issue | ~1-2h | May be intentional — investigate first |
| 5 | Phase D train-from-scratch | ~2-3h | Was blocked by Item 1; can revisit |
| 8 | Auto drift detection | ~4-8h | NEW: periodic Firestore vs BQ Client column check |
| 10 | Audit `{state.X}` placeholders | ~2-4h | NEW: codebase-wide, requires testing |

## Cleanup needed next session
1. **7 idle tagged revisions at 0% traffic.** Cleanup with:
## Session meta-notes (what worked, what didn't)

What worked:
- Strict `--no-traffic --tag` deploy protocol caught the WinnDixie regression before users were affected
- Smoke suite from Item 6 was decisive — caught the regression that incognito browser testing missed
- Reverting in small pieces (Edit 1 first, then prompt) localized which change caused the regression

What didn't work / cost time today:
- Anti-pattern: assuming API shapes from memory (LlmResponse.candidates) — verify before write
- Anti-pattern: f-string brace handling for ADK prompts — same issue as Session 10 anti-pattern #5
- Anti-pattern: extending caps when fatigued — Item 1's regression debug happened 9+ hours in
- Bash heredoc with embedded backticks ate test fixtures multiple times
- Multiple directory confusion incidents (`~/astrobot_mesh` vs `~`)

For next session opener:
1. Read this resume doc first
2. Read the Session 10 resume doc's meta-notes — anti-patterns 1, 2, 5, 7 all hit again today
3. Start with cleanup (idle revisions, push commits) before any new feature work
4. Item 2 (model name hallucination) is the cleanest next pick — well-scoped, low architectural risk

## Tag/revision quick reference (for rollback or revisit)
- `00011-naf` / `item7b` — Item 7b state (last fully-clean pre-Item-9 deploy)
- `00015-ros` / (no tag) — Item 9 v1 (broken: `{state.X}` literals)
- `00017-los` / `item9b` — Item 9 v2 (broken: KeyError on first turn)
- `00018-bev` / `item9c` — Item 9 v3 (`{X?}` modifier; substitution worked but state empty on first turn)
- `00019-cer` / `item1` — Item 1 v1 (broken: LlmResponse.candidates AttributeError)
- `00020-col` / `item1b` — Item 1 v2 (LlmResponse fix; WinnDixie regression appeared)
- `00021-gab` / `item1c` — Item 1 v3 (broad capture reverted; regression persisted)
- `00022-mey` / `item1d` — **CURRENT PRODUCTION** (prompt reverted; smoke 5/5 green)

