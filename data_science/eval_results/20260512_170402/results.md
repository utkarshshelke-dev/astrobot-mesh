# Eval Run Report — 20260512_170402

Mode: `fast`
Run started: Tue May 12 05:04:02 PM UTC 2026


## [positive] pos_01_top_channels

**Prompt:** For NPI; show top 5 channels by spend last quarter as a bar chart 

**Duration:** 45s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.19130434782608693 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [negative] neg_01_out_of_scope

**Prompt:** What is the weather in Tokyo tomorrow 

**Duration:** 27s
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

**Total duration:** 124s
**Mode:** `fast`
**Total coverage:** 39.8%
**HTML report:** `htmlcov/index.html`

