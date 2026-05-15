# Eval Run Report — 20260512_185723

Mode: `fast`
Run started: Tue May 12 06:57:23 PM UTC 2026


## [positive] pos_01_top_channels

**Prompt:** For NPI; show top 5 channels by spend last quarter as a bar chart 

**Duration:** 52s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (1):** `call_analytics_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.26506024096385544 (threshold: 0.15)

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
**Response match:** 0.25 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## Run Summary

| Category | Pass | Fail |
|----------|------|------|
| Positive | 1 | 0 |
| Negative | 0 | 1 |

**Total duration:** 142s
**Mode:** `fast`
**Total coverage:** 1.8%
**HTML report:** `htmlcov/index.html`

