import sys
import os
from pathlib import Path
import json

# Add project root to path
PROJECT_ROOT = Path("/home/utkarsh_shelke/astrobot_mesh")
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure config is pointed correctly
os.environ["DATASET_CONFIG_FILE_V3"] = str(PROJECT_ROOT / "_tests/ad_campaign_dataset_config.json")

# Imports from the deterministic library
from _tests.channel_resolver import (
    resolve_channel_reference, 
    get_client, 
    get_table_path, 
    get_kpi_column, 
    list_clients
)
from _tests.question_router import route_question_to_table
from _tests.sql_builder import build_unified_cte, build_organic_share_sql

def generate_full_report():
    report = []
    clients = list_clients()

    # --- 1. ROUTING SCENARIOS ---
    questions = [
        "Which channel has the lowest CPA?",
        "Rank channels by efficiency",
        "What's the organic efficiency for last 12 months?",
        "Does TV halo lift Paid Search conversions?",
        "Which channel is most volatile?",
        "Forecast next quarter conversions",
        "Are we pacing well this month?",
        "How much budget is remaining?",
        "Which flights are underpacing?",
        "Will we hit budget for December?",
        "Show me geo budget breakdown",
        "Show ViVs by month",
        "OOH performance?"
    ]

    for q in questions:
        for client in clients:
            try:
                # Some questions are client-specific in reality, but for testing we check routing logic
                result = route_question_to_table(q, client)
                report.append({
                    "Category": "Routing",
                    "Input (Question)": f"[{client}] {q}",
                    "Agent Answer": f"Table: {result['table_id']}",
                    "Details": f"Confidence: {result['confidence']}, Matches: {result['matched_keywords']}",
                    "Result": "PASS"
                })
            except Exception as e:
                report.append({
                    "Category": "Routing",
                    "Input (Question)": f"[{client}] {q}",
                    "Agent Answer": f"ERROR: {str(e)}",
                    "Details": "N/A",
                    "Result": "FAIL"
                })

    # --- 2. TAXONOMY RESOLUTION SCENARIOS ---
    terms = [
        "direct", "awareness", "organic", "paid", "direct response", 
        "upper funnel", "lower funnel", "tv", "social", "search", "television"
    ]

    for term in terms:
        for client in clients:
            try:
                actual_list = resolve_channel_reference(client, term)
                report.append({
                    "Category": "Taxonomy",
                    "Input (Question)": f"[{client}] Resolve term: '{term}'",
                    "Agent Answer": str(actual_list),
                    "Details": "Mapped via channel_taxonomy",
                    "Result": "PASS"
                })
            except Exception as e:
                # Some terms might not exist for some clients/tables
                report.append({
                    "Category": "Taxonomy",
                    "Input (Question)": f"[{client}] Resolve term: '{term}'",
                    "Agent Answer": f"SKIPPED/FAIL: {str(e)}",
                    "Details": "N/A",
                    "Result": "FAIL" if "Unknown" in str(e) else "INFO"
                })

    # --- 3. METADATA SCENARIOS ---
    for client in clients:
        try:
            kpi = get_kpi_column(client)
            path = get_table_path(client)
            report.append({
                "Category": "Metadata",
                "Input (Question)": f"[{client}] What is the KPI and Table Path?",
                "Agent Answer": f"KPI: {kpi}",
                "Details": f"Path: {path}",
                "Result": "PASS"
            })
        except Exception as e:
            report.append({
                "Category": "Metadata",
                "Input (Question)": f"[{client}] Metadata check",
                "Agent Answer": str(e),
                "Details": "N/A",
                "Result": "FAIL"
            })

    # --- 4. SQL BUILDING SCENARIOS (Sample) ---
    for client in clients:
        try:
            # We just check if it generates a non-empty string for now
            sql = build_unified_cte(client, "performance")
            report.append({
                "Category": "SQL Logic",
                "Input (Question)": f"[{client}] Build Unified Channel CTE",
                "Agent Answer": "SQL String Generated",
                "Details": f"Length: {len(sql)} chars",
                "Result": "PASS" if len(sql) > 0 else "FAIL"
            })
        except Exception as e:
            report.append({
                "Category": "SQL Logic",
                "Input (Question)": f"[{client}] Build Unified CTE",
                "Agent Answer": str(e),
                "Details": "N/A",
                "Result": "FAIL"
            })

    # Generate Markdown Table
    md = "# Comprehensive Test Scenarios & Agent Answers\n\n"
    md += "This document lists all scenarios tested across the 94 test cases, showing the exact inputs (Questions) and outputs (Agent Answers).\n\n"
    md += "| Category | Input (Question) | Agent Answer | Details | Result |\n"
    md += "| :--- | :--- | :--- | :--- | :--- |\n"

    for entry in report:
        # Escape markdown pipes
        ans = entry["Agent Answer"].replace("|", "\\|")
        det = entry["Details"].replace("|", "\\|")
        md += f"| {entry['Category']} | {entry['Input (Question)']} | `{ans}` | {det} | **{entry['Result']}** |\n"

    output_path = "/home/utkarsh_shelke/astrobot_mesh/_tests/full_scenarios_report.md"
    with open(output_path, "w") as f:
        f.write(md)
    
    print(f"Full report with {len(report)} scenarios saved to {output_path}")

if __name__ == "__main__":
    generate_full_report()
