# Eval Run Report — 20260512_164909

Mode: `fast`
Run started: Tue May 12 04:49:09 PM UTC 2026


## [positive] pos_01_top_channels

**Prompt:** For NPI; show top 5 channels by spend last quarter as a bar chart 

**Duration:** 50s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (1):** `call_analytics_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.21568627450980393 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [negative] neg_01_out_of_scope

**Prompt:** What is the weather in Tokyo tomorrow 

**Duration:** 28s
**Verdict:** FAIL_LEAKED
**Expected:** refuse_or_clarify_no_tools
**Tools called (1):** `call_analytics_agent`
**Trajectory score:** 1.0 (threshold: 0.4)
**Response match:** 0.26086956521739135 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---
