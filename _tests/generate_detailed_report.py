import sys
import os
from pathlib import Path
import json

# Add project root to path
PROJECT_ROOT = Path("/home/utkarsh_shelke/astrobot_mesh")
sys.path.insert(0, str(PROJECT_ROOT))

# Imports from the deterministic library
from _tests.channel_resolver import resolve_channel_reference
from _tests.question_router import route_question_to_table

def run_detailed_report():
    report = []

    # 1. Routing Tests (The Questions)
    routing_questions = [
        ("Which channel has the lowest CPA?", "NPI", "performance"),
        ("Rank channels by efficiency", "NPI", "performance"),
        ("What's the organic efficiency for last 12 months?", "NPI", "performance"),
        ("Does TV halo lift Paid Search conversions?", "NPI", "performance"),
        ("Are we pacing well this month?", "NPI", "pacing"),
        ("How much budget is remaining?", "NPI", "pacing"),
        ("Will we hit budget for December?", "NPI", "pacing"),
        ("Show ViVs by month", "WinnDixie", "performance"),
    ]

    for q, client, expected_table in routing_questions:
        try:
            result = route_question_to_table(q, client)
            actual_table = result["table_id"]
            passed = actual_table == expected_table
            report.append({
                "Category": "Routing",
                "Input / Question": q,
                "Agent Response (Table)": actual_table,
                "Agent Response (Extra)": f"Confidence: {result.get('confidence')}, Matches: {result.get('matched_keywords')}",
                "Result": "PASS" if passed else "FAIL"
            })
        except Exception as e:
            report.append({
                "Category": "Routing",
                "Input / Question": q,
                "Agent Response (Table)": str(e),
                "Agent Response (Extra)": "N/A",
                "Result": "FAIL"
            })

    # 2. Channel Resolution Tests (Truth from ad_campaign_dataset_config.json)
    resolution_tests = [
        ("NPI", "Direct", ["Direct"]),
        ("NPI", "TV", ["Linear TV", "CTV", "OTT"]), # Updated to match config
        ("NPI", "Organic Search", ["Organic Search"]),
    ]

    for client, term, expected_list in resolution_tests:
        try:
            actual_list = resolve_channel_reference(client, term)
            passed = set(actual_list) == set(expected_list)
            report.append({
                "Category": "Resolution",
                "Input / Question": f"Resolve channel: {term} for {client}",
                "Agent Response (Table)": str(actual_list),
                "Agent Response (Extra)": "Deterministic",
                "Result": "PASS" if passed else "FAIL"
            })
        except Exception as e:
            report.append({
                "Category": "Resolution",
                "Input / Question": f"Resolve channel: {term} for {client}",
                "Agent Response (Table)": str(e),
                "Agent Response (Extra)": "N/A",
                "Result": "FAIL"
            })

    # Generate Markdown
    md = "# Detailed Test Execution Report\n\n"
    md += "This report summarizes the execution of key deterministic logic used by the Astrobot agent.\n\n"
    md += "| Category | Question / Input | Agent Response | Details | Result |\n"
    md += "| :--- | :--- | :--- | :--- | :--- |\n"
    
    for entry in report:
        resp = entry['Agent Response (Table)'].replace("|", "\\|")
        extra = entry['Agent Response (Extra)'].replace("|", "\\|")
        md += f"| {entry['Category']} | {entry['Input / Question']} | `{resp}` | {extra} | **{entry['Result']}** |\n"

    with open("/home/utkarsh_shelke/astrobot_mesh/_tests/detailed_test_results.md", "w") as f:
        f.write(md)
    
    print("Report saved to astrobot_mesh/_tests/detailed_test_results.md")

if __name__ == "__main__":
    os.environ["DATASET_CONFIG_FILE_V3"] = str(PROJECT_ROOT / "_tests/ad_campaign_dataset_config.json")
    run_detailed_report()
