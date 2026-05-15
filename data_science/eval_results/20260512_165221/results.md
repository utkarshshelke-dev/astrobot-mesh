# Eval Run Report — 20260512_165221

Mode: `--full`
Run started: Tue May 12 04:52:21 PM UTC 2026


## [positive] pos_01_top_channels

**Prompt:** For NPI; show top 5 channels by spend last quarter as a bar chart 

**Duration:** 50s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (1):** `call_analytics_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.23404255319148937 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_02_volatility

**Prompt:** For NPI; which channels are most volatile in cost over last 12 months 

**Duration:** 35s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.15384615384615385 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_03_saturation

**Prompt:** For NPI; build a saturation model for next 100k investment 

**Duration:** 126s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.043613707165109025 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_04_peak_trough

**Prompt:** For NPI; channel mix shift peak months Nov Dec compared trough months 2 bar charts cost percent conversion attribution 

**Duration:** 120s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (1):** `call_analytics_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.08372093023255814 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 

**Error:** `CHART_RENDER_ERROR`

---

## [positive] pos_05_monthly_trend

**Prompt:** For NPI; show me total monthly spend trend over the last 6 months as a line chart 

**Duration:** 49s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.18390804597701146 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_06_blended_cpa

**Prompt:** For NPI; what is the blended CPA across all channels last 12 months 

**Duration:** 40s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.12987012987012989 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_07_pacing

**Prompt:** For NPI; are we on pace with budget this month 

**Duration:** 28s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (1):** `call_analytics_agent`
**Trajectory score:** 1.0 (threshold: 0.4)
**Response match:** 0.0 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_08_pie_chart

**Prompt:** For NPI; show channel spend share as a pie chart for last quarter 

**Duration:** 52s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.09638554216867469 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_09_top_campaigns

**Prompt:** For NPI; list the top 10 campaigns by spend last 30 days 

**Duration:** 41s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.07766990291262137 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_10_volatility_summary

**Prompt:** For NPI; give me a channel volatility summary across cost conversions clicks and impressions 

**Duration:** 48s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (2):** `call_analytics_agent|call_bigquery_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.08139534883720931 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---

## [positive] pos_11_bqml_train

**Prompt:** For NPI; train a saturation model using BQML 

**Duration:** 76s
**Verdict:** FAIL
**Expected:** answer_with_tools_and_data
**Tools called (1):** `call_analytics_agent`
**Trajectory score:** 0.0 (threshold: 0.4)
**Response match:** 0.163265306122449 (threshold: 0.15)

**Agent response:**
> expected_tool_calls 



---
