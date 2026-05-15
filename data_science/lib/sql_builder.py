"""
Deterministic SQL builders.

Generates correct SQL for common patterns (blended CPA, channel ranking,
organic share, volatility). The LLM only needs to choose WHICH builder
to call — the SQL itself is deterministic and tested.
"""

from typing import Optional
from .channel_resolver import (
    get_table,
    get_unification_map,
    get_duality_info,
    resolve_channel_reference,
    get_channel_column,
)


def build_unified_cte(
    client_id: str,
    table_id: str = "performance",
    config: Optional[dict] = None,
) -> str:
    """
    Build the CASE WHEN unification clause for unifying channel variants.
    Returns just the CASE expression, suitable for use in a SELECT.
    """
    unification = get_unification_map(client_id, table_id, config)
    channel_col = get_channel_column(client_id, table_id, config)

    if not unification:
        return channel_col

    case_lines = []
    for unified, variants in unification.items():
        quoted = ", ".join(f"'{v}'" for v in variants)
        case_lines.append(f"      WHEN {channel_col} IN ({quoted}) THEN '{unified}'")

    return (
        "CASE\n"
        + "\n".join(case_lines)
        + f"\n      ELSE {channel_col}\n    END"
    )


def build_blended_cpa_sql(
    client_id: str,
    lookback_months: int = 12,
    table_id: str = "performance",
    config: Optional[dict] = None,
) -> str:
    """
    Build unified-CTE blended CPA SQL handling Cost/Conversion duality.
    """
    table = get_table(client_id, table_id, config)
    table_path = table["table_full_path"]
    client_col = table.get("client_column", "Client")
    date_col = table.get("date_column", "Date")
    duality = get_duality_info(client_id, table_id, config)
    unify_case = build_unified_cte(client_id, table_id, config)

    if duality.get("has_duality"):
        spend_filter = duality.get("spend_rows_filter", "Cost > 0")
        conv_filter = duality.get("conv_rows_filter", "Conversions > 0")

        return f"""WITH unified AS (
  SELECT
    {date_col},
    {unify_case} AS unified_channel,
    Cost,
    Conversions
  FROM `{table_path}`
  WHERE {date_col} >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_months} MONTH)
    AND {client_col} = '{client_id}'
),
spend AS (
  SELECT {date_col}, unified_channel, SUM(Cost) AS s
  FROM unified WHERE {spend_filter}
  GROUP BY {date_col}, unified_channel
),
conv AS (
  SELECT {date_col}, unified_channel, SUM(Conversions) AS c
  FROM unified WHERE {conv_filter}
  GROUP BY {date_col}, unified_channel
)
SELECT
  COALESCE(s.unified_channel, c.unified_channel) AS Channel,
  ROUND(SUM(s.s), 2) AS spend,
  SUM(c.c) AS conversions,
  ROUND(SAFE_DIVIDE(SUM(s.s), SUM(c.c)), 2) AS cpa
FROM spend s
FULL OUTER JOIN conv c USING ({date_col}, unified_channel)
GROUP BY Channel
HAVING spend > 0 AND conversions > 0
ORDER BY cpa ASC"""

    # No duality - simple aggregation
    return f"""SELECT
  {unify_case} AS Channel,
  ROUND(SUM(Cost), 2) AS spend,
  SUM(Conversions) AS conversions,
  ROUND(SAFE_DIVIDE(SUM(Cost), SUM(Conversions)), 2) AS cpa
FROM `{table_path}`
WHERE {date_col} >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_months} MONTH)
  AND {client_col} = '{client_id}'
GROUP BY Channel
HAVING spend > 0 AND conversions > 0
ORDER BY cpa ASC"""


def build_organic_share_sql(
    client_id: str,
    lookback_months: int = 12,
    table_id: str = "performance",
    config: Optional[dict] = None,
) -> str:
    """
    Build SQL for monthly organic conversion share %.
    Uses taxonomy to determine which channels count as organic.
    """
    table = get_table(client_id, table_id, config)
    table_path = table["table_full_path"]
    client_col = table.get("client_column", "Client")
    date_col = table.get("date_column", "Date")
    channel_col = get_channel_column(client_id, table_id, config)

    organic_channels = resolve_channel_reference(client_id, "organic", table_id, config)
    organic_list = ", ".join(f"'{c}'" for c in organic_channels)

    return f"""SELECT
  FORMAT_DATE('%Y-%m', {date_col}) AS month,
  SUM(CASE WHEN {channel_col} IN ({organic_list}) THEN Conversions ELSE 0 END) AS organic_conv,
  SUM(Conversions) AS total_conv,
  ROUND(100.0 * SAFE_DIVIDE(
    SUM(CASE WHEN {channel_col} IN ({organic_list}) THEN Conversions ELSE 0 END),
    SUM(Conversions)
  ), 1) AS pct_organic
FROM `{table_path}`
WHERE {date_col} >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_months} MONTH)
  AND {client_col} = '{client_id}'
GROUP BY month
ORDER BY pct_organic DESC"""


def build_funnel_spend_sql(
    client_id: str,
    lookback_months: int = 12,
    table_id: str = "performance",
    config: Optional[dict] = None,
) -> str:
    """
    Build SQL that returns spend by funnel category (awareness/DR/mid-funnel).
    Uses taxonomy - no LLM cherry-picking possible.
    """
    table = get_table(client_id, table_id, config)
    table_path = table["table_full_path"]
    client_col = table.get("client_column", "Client")
    date_col = table.get("date_column", "Date")
    channel_col = get_channel_column(client_id, table_id, config)

    awareness = resolve_channel_reference(client_id, "awareness", table_id, config)
    dr = resolve_channel_reference(client_id, "direct response", table_id, config)
    mid = resolve_channel_reference(client_id, "mid funnel", table_id, config)

    def quote_list(channels):
        return ", ".join(f"'{c}'" for c in channels) if channels else "''"

    return f"""SELECT
  ROUND(SUM(CASE WHEN {channel_col} IN ({quote_list(awareness)}) THEN Cost ELSE 0 END), 2) AS awareness_spend,
  ROUND(SUM(CASE WHEN {channel_col} IN ({quote_list(dr)}) THEN Cost ELSE 0 END), 2) AS dr_spend,
  ROUND(SUM(CASE WHEN {channel_col} IN ({quote_list(mid)}) THEN Cost ELSE 0 END), 2) AS midfunnel_spend,
  ROUND(SUM(Cost), 2) AS total_spend,
  ROUND(SAFE_DIVIDE(
    SUM(CASE WHEN {channel_col} IN ({quote_list(awareness)}) THEN Cost ELSE 0 END),
    SUM(CASE WHEN {channel_col} IN ({quote_list(dr)}) THEN Cost ELSE 0 END)
  ), 3) AS awareness_dr_ratio
FROM `{table_path}`
WHERE {date_col} >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_months} MONTH)
  AND {client_col} = '{client_id}'
  AND Cost > 0"""


def build_volatility_sql(
    client_id: str,
    metric: str = "Conversions",
    lookback_months: int = 12,
    min_months: int = 8,
    table_id: str = "performance",
    config: Optional[dict] = None,
) -> str:
    """
    Build SQL for Coefficient of Variation (CV) of monthly metric by channel.
    """
    table = get_table(client_id, table_id, config)
    table_path = table["table_full_path"]
    client_col = table.get("client_column", "Client")
    date_col = table.get("date_column", "Date")
    channel_col = get_channel_column(client_id, table_id, config)
    unify_case = build_unified_cte(client_id, table_id, config)

    return f"""WITH monthly AS (
  SELECT
    FORMAT_DATE('%Y-%m', {date_col}) AS month,
    {unify_case} AS channel,
    SUM({metric}) AS value
  FROM `{table_path}`
  WHERE {date_col} >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_months} MONTH)
    AND {client_col} = '{client_id}'
    AND {metric} > 0
  GROUP BY month, channel
)
SELECT
  channel,
  COUNT(*) AS months,
  ROUND(AVG(value), 0) AS avg_value,
  ROUND(STDDEV(value), 0) AS stddev_value,
  ROUND(SAFE_DIVIDE(STDDEV(value), AVG(value)), 3) AS cv
FROM monthly
GROUP BY channel
HAVING months >= {min_months} AND avg_value > 100
ORDER BY cv DESC"""