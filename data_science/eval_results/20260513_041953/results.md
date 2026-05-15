# Eval Run Report — 20260513_041953

Mode: `--full`
Run started: Wed May 13 04:19:53 AM UTC 2026


## [positive] pos_01_top_channels

**Prompt:** For NPI; show top 5 channels by spend last quarter as a bar chart 

**Duration:** 41s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.22448979591836737 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_02_volatility

**Prompt:** For NPI; which channels are most volatile in cost over last 12 months 

**Duration:** 27s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.17204301075268819 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_03_saturation

**Prompt:** For NPI; build a saturation model for next 100k investment 

**Duration:** 33s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (1):** `call_analytics_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.05106382978723405 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_04_peak_trough

**Prompt:** For NPI; channel mix shift peak months Nov Dec compared trough months 2 bar charts cost percent conversion attribution 

**Duration:** 56s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.10526315789473684 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_05_monthly_trend

**Prompt:** For NPI; show me total monthly spend trend over the last 6 months as a line chart 

**Duration:** 50s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.14953271028037382 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_06_blended_cpa

**Prompt:** For NPI; what is the blended CPA across all channels last 12 months 

**Duration:** 33s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.1724137931034483 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_07_pacing

**Prompt:** For NPI; are we on pace with budget this month 

**Duration:** 21s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (1):** `call_analytics_agent`
**Trajectory score:** 1.0 (threshold: 0.4)
**Response match:** 0.23529411764705882 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_08_pie_chart

**Prompt:** For NPI; show channel spend share as a pie chart for last quarter 

**Duration:** 44s
**Verdict:** PASS
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.15094339622641506 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_09_top_campaigns

**Prompt:** For NPI; list the top 10 campaigns by spend last 30 days 

**Duration:** 33s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.0546448087431694 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_10_volatility_summary

**Prompt:** For NPI; give me a channel volatility summary across cost conversions clicks and impressions 

**Duration:** 42s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.035623409669211195 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---
