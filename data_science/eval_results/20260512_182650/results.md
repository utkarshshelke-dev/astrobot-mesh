# Eval Run Report — 20260512_182650

Mode: `--full`
Run started: Tue May 12 06:26:50 PM UTC 2026


## [positive] pos_01_top_channels

**Prompt:** For NPI; show top 5 channels by spend last quarter as a bar chart 

**Duration:** 58s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (1):** `call_analytics_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.26506024096385544 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_02_volatility

**Prompt:** For NPI; which channels are most volatile in cost over last 12 months 

**Duration:** 49s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.14634146341463414 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_03_saturation

**Prompt:** For NPI; build a saturation model for next 100k investment 

**Duration:** 253s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.06422018348623854 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---
