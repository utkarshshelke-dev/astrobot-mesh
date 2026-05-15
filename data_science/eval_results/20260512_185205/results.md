# Eval Run Report — 20260512_185205

Mode: `--full`
Run started: Tue May 12 06:52:05 PM UTC 2026


## [positive] pos_01_top_channels

**Prompt:** For NPI; show top 5 channels by spend last quarter as a bar chart 

**Duration:** 51s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (1):** `call_analytics_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.23655913978494622 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_02_volatility

**Prompt:** For NPI; which channels are most volatile in cost over last 12 months 

**Duration:** 46s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.15126050420168066 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_03_saturation

**Prompt:** For NPI; build a saturation model for next 100k investment 

**Duration:** 39s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.06829268292682927 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---
