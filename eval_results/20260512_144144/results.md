# Eval Run Report — 20260512_144144

Mode: `fast`
Run started: Tue May 12 02:41:44 PM UTC 2026


## [positive] pos_smoke

**Prompt:** For NPI; show top 5 channels by spend last quarter as a bar chart 

**Duration:** 63s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (0):** `none`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.2268041237113402 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [negative] neg_out_of_scope

**Prompt:** What is the weather in Tokyo tomorrow? 

**Duration:** 31s
**Verdict:** PASS_REFUSED
**Expected:** refuse_or_clarify_no_tools
**Tools called (0):** `none`
**Trajectory score:** 1.0 (threshold: 0.4)
**Response match:** 0.34782608695652173 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---
