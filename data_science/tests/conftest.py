"""Write test results to JSON for the HTML test log tracker."""
import json, os, time
from pathlib import Path

RESULTS_FILE = Path(__file__).parent / "test_results.json"

def pytest_runtest_logreport(report):
    if report.when != "call":
        return
    results = {}
    if RESULTS_FILE.exists():
        try:
            results = json.loads(RESULTS_FILE.read_text())
        except Exception:
            pass
    results[report.nodeid.split("::")[-1]] = {
        "status": "pass" if report.passed else "fail" if report.failed else "skip",
        "duration": round(report.duration, 1),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "notes": str(report.longreprtext)[:200] if report.failed else "",
    }
    RESULTS_FILE.write_text(json.dumps(results, indent=2))
