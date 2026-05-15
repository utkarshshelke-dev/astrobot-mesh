# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from google.cloud import bigquery
from vertexai import rag



def _clean_floats(obj):
    """Replace NaN/Infinity with None recursively."""
    import math
    if isinstance(obj, dict):
        return {k: _clean_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_floats(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj


def check_bq_models(dataset_id: str) -> str:
    """Lists models in a BigQuery dataset and returns them as a string.

    Args:
        dataset_id: The ID of the BigQuery dataset (e.g., "project.dataset").

    Returns:
        A string representation of a list of dictionaries, where each dictionary
        contains the 'name' and 'type' of a model in the specified dataset.
        Returns an empty string "[]" if no models are found.
    """

    try:
        client = bigquery.Client()

        models = client.list_models(dataset_id)
        model_list = []  # Initialize as a list

        print(f"Models contained in '{dataset_id}':")
        for model in models:
            model_id = model.model_id
            model_type = model.model_type
            model_list.append({"name": model_id, "type": model_type})

        return str(model_list)

    except Exception as e:
        return f"An error occurred: {e!s}"


def rag_response(query: str) -> str:
    """Retrieves contextually relevant information from a RAG corpus.

    Args:
        query (str): The query string to search within the corpus.

    Returns:
        vertexai.rag.RagRetrievalQueryResponse: The response containing retrieved
        information from the corpus.
    """
    corpus_name = os.getenv("BQML_RAG_CORPUS_NAME")

    rag_retrieval_config = rag.RagRetrievalConfig(
        top_k=3,  # Optional
        filter=rag.Filter(vector_distance_threshold=0.5),  # Optional
    )
    response = rag.retrieval_query(
        rag_resources=[
            rag.RagResource(
                rag_corpus=corpus_name,
            )
        ],
        text=query,
        rag_retrieval_config=rag_retrieval_config,
    )
    return str(response)


# ── Astrobot ad-campaign BQML tools appended below ───────────────────────────
# These SQL generators return BQML statements for user approval BEFORE
# the agent calls execute_sql — following the mandatory verification pattern.

import os
import re as _re

_data_project  = os.getenv("BQ_DATA_PROJECT_ID", "")
_bqml_dataset  = os.getenv("BQML_DATASET_ID", "astrobot_bqml_models")
_ARIMA_HORIZON = int(os.getenv("ARIMA_HORIZON_DAYS", "14"))
_ANOMALY_Z     = float(os.getenv("ANOMALY_Z_THRESHOLD", "2.5"))

# Real client → dataset + table mapping (mirrors bigquery/tools.py)
_CLIENT_TABLE_MAP = {
    "NPI":       {"dataset": "Astrobot_NPI",       "table": "vw_astrobot_npi_nc360_dashboard"},
    "Venetian":  {"dataset": "Astrobot_Venetian",   "table": "sample_astrobot_venetian_nc360_dashboard"},
    "WinnDixie": {"dataset": "Astrobot_WinnDixie",  "table": "sample_astrobot_wd_nc360_dashboard"},
}

def _perf_fqtn(client_id: str) -> str:
    cfg = _CLIENT_TABLE_MAP.get(client_id)
    if not cfg:
        raise ValueError(f"Unknown client_id '{client_id}'")
    return f"`{_data_project}.{cfg['dataset']}.{cfg['table']}`"


def get_arima_train_sql(
    client_id: str,
    channel: str = "ALL",
    metric: str = "Cost",
) -> str:
    """
    Generates ARIMA_PLUS CREATE MODEL SQL for the given client/channel/metric.
    Returns the SQL string for user approval — do NOT pass to execute_sql
    without presenting it to the user first.

    Args:
        client_id: One of 'NPI', 'Venetian', 'SEG'.
        channel:   Channel to train on (e.g. 'Search'). 'ALL' = no filter.
        metric:    Metric column to forecast (default: 'Cost').

    Returns:
        BQML CREATE MODEL SQL string.
    """
    slug       = _re.sub(r"[^a-z0-9]", "_", (channel or "all").lower())
    model_ref  = f"`{_data_project}.{_bqml_dataset}.arima_{client_id.lower()}_{slug}_{metric.lower()}`"
    perf_table = _perf_fqtn(client_id)
    ch_filter  = f"AND Channel = '{channel}'" if channel != "ALL" else ""

    return f"""
-- ARIMA_PLUS model: {client_id} | {channel} | {metric}
-- Present to user for approval before executing.
CREATE OR REPLACE MODEL {model_ref}
OPTIONS (
    model_type                = 'ARIMA_PLUS',
    time_series_timestamp_col = 'Date',
    time_series_data_col      = '{metric}',
    auto_arima                = TRUE,
    data_frequency            = 'AUTO_FREQUENCY',
    decompose_time_series     = TRUE,
    clean_spikes_and_dips     = TRUE
) AS
SELECT
    Date,
    SUM({metric}) AS {metric}
FROM {perf_table}
WHERE
    Client = '{client_id}'
    AND {metric} IS NOT NULL
    AND {metric} > 0
    {ch_filter}
GROUP BY Date
ORDER BY Date
""".strip()


def get_arima_forecast_sql(
    client_id: str,
    channel: str = "ALL",
    metric: str = "Cost",
    horizon_days: int = _ARIMA_HORIZON,
) -> str:
    """
    Generates ML.FORECAST SQL for the next horizon_days days.
    Requires a trained ARIMA_PLUS model (call get_arima_train_sql first).

    Args:
        client_id:    One of 'NPI', 'Venetian', 'SEG'.
        channel:      Channel filter used during training.
        metric:       Metric that was modelled.
        horizon_days: Number of days to forecast (default: 14).

    Returns:
        BQML ML.FORECAST SQL string.
    """
    slug      = _re.sub(r"[^a-z0-9]", "_", (channel or "all").lower())
    model_ref = f"`{_data_project}.{_bqml_dataset}.arima_{client_id.lower()}_{slug}_{metric.lower()}`"

    return f"""
SELECT
    forecast_timestamp              AS Forecast_Date,
    forecast_value                  AS Forecast_{metric},
    prediction_interval_lower_bound AS Lower_Bound,
    prediction_interval_upper_bound AS Upper_Bound,
    '{client_id}'                   AS Client,
    '{channel}'                     AS Channel
FROM ML.FORECAST(
    MODEL {model_ref},
    STRUCT({horizon_days} AS horizon, 0.9 AS confidence_level)
)
ORDER BY Forecast_Date
""".strip()


def get_anomaly_detect_sql(
    client_id: str,
    channel: str = "ALL",
    metric: str = "Cost",
    use_zscore_fallback: bool = False,
) -> str:
    """
    Generates anomaly detection SQL.
    Primary:  ML.DETECT_ANOMALIES on a trained ARIMA_PLUS model.
    Fallback: z-score SQL (pass use_zscore_fallback=True if no model trained yet).

    Args:
        client_id:           One of 'NPI', 'Venetian', 'SEG'.
        channel:             Channel filter ('ALL' = no filter).
        metric:              Metric to inspect (default: 'Cost').
        use_zscore_fallback: True to use z-score SQL instead of BQML.

    Returns:
        SQL string for anomaly detection.
    """
    perf_table = _perf_fqtn(client_id)
    ch_filter  = f"AND Channel = '{channel}'" if channel != "ALL" else ""

    if use_zscore_fallback:
        return f"""
WITH daily AS (
    SELECT Date, SUM({metric}) AS Daily_{metric}
    FROM {perf_table}
    WHERE Client = '{client_id}' {ch_filter}
    GROUP BY Date
),
stats AS (
    SELECT
        AVG(Daily_{metric}) AS mean_val,
        STDDEV(Daily_{metric}) AS std_val
    FROM daily
)
SELECT
    d.Date,
    d.Daily_{metric}                                                      AS Actual,
    s.mean_val                                                            AS Expected,
    SAFE_DIVIDE(ABS(d.Daily_{metric} - s.mean_val), NULLIF(s.std_val,0)) AS Z_Score,
    d.Daily_{metric} > (s.mean_val + {_ANOMALY_Z} * s.std_val)           AS Is_High_Anomaly,
    d.Daily_{metric} < (s.mean_val - {_ANOMALY_Z} * s.std_val)           AS Is_Low_Anomaly,
    '{client_id}'  AS Client,
    '{channel}'    AS Channel
FROM daily d CROSS JOIN stats s
WHERE ABS(SAFE_DIVIDE(d.Daily_{metric} - s.mean_val, NULLIF(s.std_val,0))) > {_ANOMALY_Z}
ORDER BY Z_Score DESC
LIMIT 50
""".strip()

    slug      = _re.sub(r"[^a-z0-9]", "_", (channel or "all").lower())
    model_ref = f"`{_data_project}.{_bqml_dataset}.arima_{client_id.lower()}_{slug}_{metric.lower()}`"

    return f"""
SELECT *
FROM ML.DETECT_ANOMALIES(
    MODEL {model_ref},
    STRUCT(0.9 AS anomaly_prob_threshold),
    (
        SELECT Date, SUM({metric}) AS {metric}
        FROM {perf_table}
        WHERE Client = '{client_id}' {ch_filter}
        GROUP BY Date
    )
)
WHERE is_anomaly = TRUE
ORDER BY anomaly_probability DESC
LIMIT 50
""".strip()


def get_eom_variance_sql(client_id: str) -> str:
    """
    Returns end-of-month budget variance SQL.
    Joins actuals to the budget table, projecting over/under-spend per channel
    for the current month. Useful as context for ARIMA forecasting.

    Args:
        client_id: One of 'NPI', 'Venetian', 'SEG'.

    Returns:
        BigQuery SQL string with Remaining_Budget and Pacing_Pct columns.
    """
    perf_table = _perf_fqtn(client_id)

    return f"""
-- End-of-month spend summary per channel (no separate budget table in BQ)
-- Compare Actual_Spend against your planned budget targets manually.
SELECT
    Channel,
    SUM(Cost)                                   AS Actual_Spend,
    COUNT(DISTINCT Date)                        AS Days_Active,
    SUM(Cost) / NULLIF(COUNT(DISTINCT Date), 0) AS Avg_Daily_Spend,
    SUM(Cost) * DATE_DIFF(
        LAST_DAY(CURRENT_DATE(), MONTH),
        DATE_TRUNC(CURRENT_DATE(), MONTH),
        DAY
    ) / NULLIF(COUNT(DISTINCT Date), 0)         AS Projected_EOM_Spend,
    CURRENT_DATE()                              AS As_Of_Date
FROM {perf_table}
WHERE
    Date >= DATE_TRUNC(CURRENT_DATE(), MONTH)
    AND Date < CURRENT_DATE()
GROUP BY Channel
ORDER BY Actual_Spend DESC
""".strip()
