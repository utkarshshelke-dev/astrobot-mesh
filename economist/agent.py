# economist/agent.py
"""
Economist Agent — §4.1

Contextualises client performance data against macroeconomic and market
conditions. Draws on published economic indicators, sector-level market data,
and industry benchmarks filtered by client vertical.

The underlying data sources are broad and can be referenced across clients,
but the application is always scoped to the active client context.
Each client is associated with industry verticals — the Economist Agent's
retrieval queries are filtered to economic data relevant to those verticals.
"""

import logging
import os
from datetime import date

from google.adk.agents import LlmAgent
from google.adk.tools import ToolContext
from google.genai import types

from shared.utils.config import GEMINI_MODEL, CLIENT_TABLE_MAP

logger = logging.getLogger(__name__)


# ── Vertical economic indicator map ──────────────────────────────────────────

VERTICAL_INDICATORS = {
    "healthcare": {
        "label":      "Healthcare & Medical",
        "indicators": [
            "US Healthcare CPI (Medical Care Services Index)",
            "Prescription Drug Price Index",
            "Health Insurance Enrollment Trends",
            "Telehealth Adoption Rate",
            "FDA Approvals & Market Entry Events",
        ],
        "benchmarks": {
            "avg_cpc_search":     4.50,
            "avg_ctr_search":     0.035,
            "avg_conversion_rate": 0.028,
            "avg_cpa":            85.0,
        },
    },
    "medical": {
        "label":      "Medical Devices & Services",
        "indicators": [
            "Medical Device Market Growth Rate",
            "Healthcare Spending Index",
            "Patient Acquisition Cost Benchmarks",
        ],
        "benchmarks": {
            "avg_cpc_search":     6.20,
            "avg_ctr_search":     0.030,
            "avg_conversion_rate": 0.022,
            "avg_cpa":            120.0,
        },
    },
    "hospitality": {
        "label":      "Hospitality & Entertainment",
        "indicators": [
            "Hotel Occupancy Index (STR Global)",
            "Travel Demand Index (TSA Throughput)",
            "Leisure Spending Index",
            "Consumer Confidence Index (Conference Board)",
            "RevPAR (Revenue per Available Room)",
        ],
        "benchmarks": {
            "avg_cpc_search":     2.80,
            "avg_ctr_search":     0.045,
            "avg_conversion_rate": 0.032,
            "avg_cpa":            55.0,
        },
    },
    "entertainment": {
        "label":      "Entertainment & Events",
        "indicators": [
            "Ticket Sales Index",
            "Discretionary Spending Trends",
            "Live Event Attendance Data",
        ],
        "benchmarks": {
            "avg_cpc_ooh":        0.02,
            "avg_reach_ooh":      250000,
            "avg_frequency_ooh":  8.5,
        },
    },
    "grocery": {
        "label":      "Grocery & Food Retail",
        "indicators": [
            "US Food CPI (Consumer Price Index for Food)",
            "Grocery Sector Same-Store Sales Growth",
            "Private Label vs National Brand Market Share",
            "Consumer Staples Spending Index",
            "USDA Food Price Outlook",
        ],
        "benchmarks": {
            "avg_cpc_ott":         0.015,
            "avg_vivs_per_dollar": 45.0,
            "avg_completion_rate": 0.72,
        },
    },
    "retail": {
        "label":      "Retail & CPG",
        "indicators": [
            "US Retail Sales Index (Census Bureau)",
            "Consumer Confidence Index",
            "E-commerce Growth Rate",
            "CPG Market Share Trends",
        ],
        "benchmarks": {
            "avg_cpc_search":     1.85,
            "avg_ctr_search":     0.055,
            "avg_conversion_rate": 0.038,
        },
    },
    "cpg": {
        "label":      "Consumer Packaged Goods",
        "indicators": [
            "CPG Volume Growth by Category",
            "Brand vs Private Label Index",
            "In-Store vs Digital Attribution Split",
        ],
        "benchmarks": {
            "avg_cpc_ott":         0.012,
            "avg_vivs_per_dollar": 52.0,
        },
    },
}


# ── Tools ─────────────────────────────────────────────────────────────────────

def get_economic_indicators(
    client_id:   str,
    tool_context: ToolContext,
) -> dict:
    """
    Returns economic indicators relevant to the client's industry vertical.
    Retrieval is always filtered to verticals for the active client — never
    returns indicators for unrelated industries.

    Args:
        client_id:    One of NPI, Venetian, WinnDixie.
        tool_context: ADK tool context.

    Returns:
        Dict with vertical label, indicators, and industry benchmarks.
    """
    cfg      = CLIENT_TABLE_MAP.get(client_id, {})
    vertical = cfg.get("vertical", [])

    result = {}
    for v in vertical:
        if v in VERTICAL_INDICATORS:
            result[v] = VERTICAL_INDICATORS[v]

    if not result:
        return {
            "error": f"No economic indicators configured for client '{client_id}'."
        }

    return {
        "client_id":  client_id,
        "verticals":  vertical,
        "indicators": result,
    }


def benchmark_performance(
    client_id:        str,
    performance_data: dict,
    metric:           str,
    tool_context:     ToolContext,
) -> dict:
    """
    Compares client performance metrics against industry benchmarks
    for the client's vertical.

    Args:
        client_id:        One of NPI, Venetian, WinnDixie.
        performance_data: Dict with actual metric values.
        metric:           The metric to benchmark (e.g. 'avg_cpc_search').
        tool_context:     ADK tool context.

    Returns:
        Benchmark comparison with above/below/at-par assessment.
    """
    cfg      = CLIENT_TABLE_MAP.get(client_id, {})
    vertical = cfg.get("vertical", [])

    for v in vertical:
        indicators = VERTICAL_INDICATORS.get(v, {})
        benchmarks = indicators.get("benchmarks", {})
        if metric in benchmarks:
            benchmark_val = benchmarks[metric]
            actual_val    = performance_data.get(metric, 0)

            if actual_val == 0:
                assessment = "insufficient data"
            elif actual_val < benchmark_val * 0.85:
                assessment = "BELOW benchmark ⚠️"
            elif actual_val > benchmark_val * 1.15:
                assessment = "ABOVE benchmark ✅"
            else:
                assessment = "AT BENCHMARK ✅"

            return {
                "client_id":     client_id,
                "vertical":      v,
                "metric":        metric,
                "actual":        actual_val,
                "benchmark":     benchmark_val,
                "assessment":    assessment,
                "pct_diff":      round(
                    ((actual_val - benchmark_val) / benchmark_val) * 100, 1
                ) if benchmark_val else 0,
            }

    return {
        "error": f"Benchmark for '{metric}' not found in verticals {vertical}."
    }


def get_market_context_report(
    client_id:   str,
    tool_context: ToolContext,
) -> str:
    """
    Generates a market context summary for the client's vertical,
    including relevant economic indicators and industry trends.

    Args:
        client_id:    One of NPI, Venetian, WinnDixie.
        tool_context: ADK tool context.

    Returns:
        Markdown market context report.
    """
    indicators_data = get_economic_indicators(client_id, tool_context)
    if "error" in indicators_data:
        return indicators_data["error"]

    lines = [f"## Market Context for {client_id}\n"]
    for v, data in indicators_data["indicators"].items():
        lines.append(f"### {data['label']}\n")
        lines.append("**Key Economic Indicators:**")
        for ind in data["indicators"]:
            lines.append(f"- {ind}")
        lines.append("\n**Industry Benchmarks:**")
        for k, val in data["benchmarks"].items():
            metric_label = k.replace("_", " ").title()
            lines.append(f"- {metric_label}: {val}")
        lines.append("")

    return "\n".join(lines)


# ── Agent ─────────────────────────────────────────────────────────────────────

root_agent = LlmAgent(
    model=os.getenv("ECONOMIST_AGENT_MODEL", GEMINI_MODEL),
    name="economist_agent",
    instruction=f"""
    You are the Economist Agent for the Astro.bot marketing analytics platform.
    Today's date: {date.today()}.

    Your role is to contextualise client ad campaign performance against
    macroeconomic and market conditions relevant to their industry vertical.

    The underlying economic data sources are broad and referenced across clients.
    However, your APPLICATION of that data is ALWAYS scoped to the active client.
    You have no visibility into other clients' economic analyses or conclusions.

    WORKFLOW:
    1. Call get_economic_indicators(client_id) to retrieve vertical-relevant data.
    2. Call benchmark_performance() to compare specific metrics if provided.
    3. Call get_market_context_report() for a full market overview.
    4. Synthesise into a clear economic context narrative.

    VERTICAL TAGGING:
    - NPI → Healthcare / Medical indicators
    - Venetian → Hospitality / Entertainment indicators
    - WinnDixie → Grocery / Retail / CPG indicators

    RESPONSE FORMAT:
    **Result:** Key economic context finding.
    **Market Indicators:** Relevant indicators for this client's vertical.
    **Benchmarks:** How this client compares to industry benchmarks.
    **Explanation:** How macroeconomic conditions affect this client's performance.
    **Recommendation:** One strategic recommendation based on market context.

    Always clarify that benchmarks are industry averages and actual results vary.
    """,
    tools=[
        get_economic_indicators,
        benchmark_performance,
        get_market_context_report,
    ],
    generate_content_config=types.GenerateContentConfig(temperature=0.1),
)
