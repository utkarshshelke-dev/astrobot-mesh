"""
data_science/utils/load_ad_campaign_data.py

Loads the three ad-campaign client CSVs (NPI, Venetian, Winn-Dixie) into
BigQuery and creates the budget table schema.

Usage:
    python data_science/utils/load_ad_campaign_data.py

Requires env vars:
    BQ_DATA_PROJECT_ID, BQ_DATASET_ID, GOOGLE_CLOUD_LOCATION

Place the three source CSV files (tab-delimited) next to this script or
update DATA_DIR below before running.
"""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google.cloud import bigquery

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT  = os.environ["BQ_DATA_PROJECT_ID"]
DATASET  = os.environ["BQ_DATASET_ID"]
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "US")
DATA_DIR = Path(__file__).parent / "data"

# ── Performance table schema (52-column flat fact table) ──────────────────────
# Columns 1-28: dimensions  |  Columns 29-52: metrics
# Conversions/KPI and Partner_Linkouts handled via separate client views below.

PERFORMANCE_SCHEMA = [
    bigquery.SchemaField("Row",                 "INTEGER"),
    bigquery.SchemaField("Date",                "DATE"),
    bigquery.SchemaField("Platform",            "STRING"),
    bigquery.SchemaField("Client",              "STRING"),
    bigquery.SchemaField("Account",             "STRING"),
    bigquery.SchemaField("Business_Unit",       "STRING"),
    bigquery.SchemaField("Sub_Business_Unit",   "STRING"),
    bigquery.SchemaField("Campaign",            "STRING"),
    bigquery.SchemaField("Channel",             "STRING"),
    bigquery.SchemaField("Status",              "STRING"),
    bigquery.SchemaField("Tactic",              "STRING"),
    bigquery.SchemaField("Geo",                 "STRING"),
    bigquery.SchemaField("Sub_Geo",             "STRING"),
    bigquery.SchemaField("NC_Paid",             "STRING"),
    bigquery.SchemaField("Partner",             "STRING"),
    bigquery.SchemaField("Targeting_Type",      "STRING"),
    bigquery.SchemaField("Audience_Modifier",   "STRING"),
    bigquery.SchemaField("Active",              "STRING"),
    bigquery.SchemaField("Campaign_Objective",  "STRING"),
    bigquery.SchemaField("Ad_Group",            "STRING"),
    bigquery.SchemaField("Ad_Group_Status",     "STRING"),
    bigquery.SchemaField("Ad",                  "STRING"),
    bigquery.SchemaField("Ad_Status",           "STRING"),
    bigquery.SchemaField("Ad_Type",             "STRING"),
    bigquery.SchemaField("Creative",            "STRING"),
    bigquery.SchemaField("Device",              "STRING"),
    bigquery.SchemaField("Source_Medium",       "STRING"),
    bigquery.SchemaField("Network",             "STRING"),
    # Metrics — col 29 is Conversions for NPI, KPI for others
    bigquery.SchemaField("Conversions",         "FLOAT64"),   # NPI only; NULL for others
    bigquery.SchemaField("KPI",                 "FLOAT64"),   # Venetian/SEG; NULL for NPI
    bigquery.SchemaField("Cost",                "FLOAT64"),
    bigquery.SchemaField("Clicks",              "INTEGER"),
    bigquery.SchemaField("Impressions",         "STRING"),    # STRING: OOH rows are null string
    bigquery.SchemaField("Video_Views",         "INTEGER"),
    bigquery.SchemaField("Video_Views_25Pct",   "INTEGER"),
    bigquery.SchemaField("Video_Views_50Pct",   "INTEGER"),
    bigquery.SchemaField("Video_Views_75Pct",   "INTEGER"),
    bigquery.SchemaField("Video_Views_100Pct",  "INTEGER"),
    bigquery.SchemaField("ViVs",                "INTEGER"),
    bigquery.SchemaField("eViVs",               "INTEGER"),
    bigquery.SchemaField("Sessions",            "INTEGER"),
    bigquery.SchemaField("Engaged_Sessions",    "INTEGER"),
    bigquery.SchemaField("Users",               "INTEGER"),
    bigquery.SchemaField("New_Users",           "INTEGER"),
    bigquery.SchemaField("Pageviews",           "INTEGER"),
    bigquery.SchemaField("Session_Duration",    "FLOAT64"),
    bigquery.SchemaField("Bounces",             "INTEGER"),
    bigquery.SchemaField("Revenue",             "FLOAT64"),
    bigquery.SchemaField("Transactions",        "INTEGER"),
    bigquery.SchemaField("Item_Quantity",       "INTEGER"),
    bigquery.SchemaField("Platform_Revenue",    "FLOAT64"),
    bigquery.SchemaField("Platform_Transactions","INTEGER"),
    bigquery.SchemaField("Partner_Linkouts",    "INTEGER"),   # NPI only; NULL for others
]

BUDGET_SCHEMA = [
    bigquery.SchemaField("Client",         "STRING",  mode="REQUIRED"),
    bigquery.SchemaField("Channel",        "STRING"),
    bigquery.SchemaField("Campaign",       "STRING"),
    bigquery.SchemaField("Period_Start",   "DATE"),
    bigquery.SchemaField("Period_End",     "DATE"),
    bigquery.SchemaField("Planned_Spend",  "FLOAT64"),
    bigquery.SchemaField("Currency",       "STRING"),
    bigquery.SchemaField("Updated_At",     "TIMESTAMP"),
]

# Map: (client display name, CSV filename)
CLIENT_FILES = {
    "NPI":      "npi_performance.csv",
    "Venetian": "venetian_performance.csv",
    "SEG":      "seg_performance.csv",
}


def ensure_dataset(client: bigquery.Client) -> None:
    dataset_ref = bigquery.DatasetReference(PROJECT, DATASET)
    try:
        client.get_dataset(dataset_ref)
        logger.info("Dataset %s.%s already exists.", PROJECT, DATASET)
    except Exception:
        ds = bigquery.Dataset(dataset_ref)
        ds.location = LOCATION
        client.create_dataset(ds)
        logger.info("Created dataset %s.%s", PROJECT, DATASET)


def load_performance_csv(bq: bigquery.Client, csv_path: Path) -> None:
    table_ref = f"{PROJECT}.{DATASET}.performance"
    job_config = bigquery.LoadJobConfig(
        schema=PERFORMANCE_SCHEMA,
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        field_delimiter="\t",
        null_marker="",
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
        create_disposition=bigquery.CreateDisposition.CREATE_IF_NEEDED,
        time_partitioning=bigquery.TimePartitioning(field="Date"),
        clustering_fields=["Client", "Campaign", "Channel", "Device"],
    )
    with open(csv_path, "rb") as f:
        job = bq.load_table_from_file(f, table_ref, job_config=job_config)
    job.result()
    logger.info("Loaded %s → %s (%d rows)", csv_path.name, table_ref, job.output_rows)


def create_budget_table(bq: bigquery.Client) -> None:
    table_ref = f"{PROJECT}.{DATASET}.budget"
    table = bigquery.Table(table_ref, schema=BUDGET_SCHEMA)
    table.time_partitioning = bigquery.TimePartitioning(field="Period_Start")
    table.clustering_fields = ["Client", "Channel"]
    try:
        bq.create_table(table)
        logger.info("Created budget table %s", table_ref)
    except Exception:
        logger.info("Budget table already exists: %s", table_ref)


def create_client_views(bq: bigquery.Client) -> None:
    """
    Creates per-client views that expose the correct KPI column name,
    making ad-hoc queries simpler for the bigquery_agent.
    """
    views = {
        "v_npi": f"""
            SELECT * EXCEPT(KPI)
            FROM `{PROJECT}.{DATASET}.performance`
            WHERE Client = 'NPI'
        """,
        "v_venetian": f"""
            SELECT * EXCEPT(Conversions, Partner_Linkouts)
            FROM `{PROJECT}.{DATASET}.performance`
            WHERE Client = 'Venetian'
        """,
        "v_seg": f"""
            SELECT * EXCEPT(Conversions, Partner_Linkouts)
            FROM `{PROJECT}.{DATASET}.performance`
            WHERE Client = 'SEG'
        """,
    }
    for view_name, view_sql in views.items():
        full_ref = f"{PROJECT}.{DATASET}.{view_name}"
        table = bigquery.Table(full_ref)
        table.view_query = view_sql.strip()
        try:
            bq.create_table(table)
            logger.info("Created view %s", full_ref)
        except Exception:
            bq.update_table(table, ["view_query"])
            logger.info("Updated view %s", full_ref)


def main() -> None:
    bq = bigquery.Client(project=PROJECT)
    ensure_dataset(bq)
    create_budget_table(bq)

    for client_id, filename in CLIENT_FILES.items():
        csv_path = DATA_DIR / filename
        if not csv_path.exists():
            logger.warning(
                "CSV not found for %s: %s — skipping. "
                "Place the tab-delimited file at that path.",
                client_id, csv_path,
            )
            continue
        load_performance_csv(bq, csv_path)

    create_client_views(bq)
    logger.info("✅ All ad-campaign data loaded into %s.%s", PROJECT, DATASET)


if __name__ == "__main__":
    main()
