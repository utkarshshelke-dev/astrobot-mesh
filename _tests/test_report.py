"""
test_report.py - Generate a human-readable Markdown report of every test case.

For each test, extracts:
- Test name
- Docstring (what it verifies)
- The actual assertions in the test body
- Pass/fail status from a pytest run
"""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path
from datetime import datetime


PROJECT_ROOT = Path(__file__).parent
TESTS_DIR = PROJECT_ROOT


def extract_tests_from_file(path: Path) -> list[dict]:
    """Parse a test file and extract every test method's metadata."""
    source = path.read_text()
    tree = ast.parse(source)
    tests = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not node.name.startswith("Test"):
            continue
        class_doc = ast.get_docstring(node) or ""

        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            if not item.name.startswith("test_"):
                continue

            # Extract docstring
            doc = ast.get_docstring(item) or ""

            # Extract assertions (the actual checks)
            assertions = []
            expected_answers = []
            for sub in ast.walk(item):
                if isinstance(sub, ast.Assert):
                    try:
                        assertions.append(ast.unparse(sub.test))
                        # Try to extract the RHS of an equality as 'Expected Answer'
                        if isinstance(sub.test, ast.Compare) and len(sub.test.ops) == 1 and isinstance(sub.test.ops[0], ast.Eq):
                            expected_answers.append(ast.unparse(sub.test.comparators[0]))
                    except Exception:
                        assertions.append("(complex assertion)")

            # Look for the call being tested and extract 'Questions' (string arguments)
            calls = []
            questions = []
            for sub in ast.walk(item):
                if isinstance(sub, ast.Call):
                    try:
                        call_str = ast.unparse(sub)
                        if any(name in call_str for name in [
                            "resolve_channel", "route_question", "build_",
                            "get_table", "get_client", "get_kpi", "get_channel_column",
                            "get_unification", "get_duality", "get_applicable_rules",
                            "load_config", "list_clients", "list_tables", "get_table_path",
                        ]):
                            calls.append(call_str.split("\n")[0][:120])
                            # Extract string literals as potential questions
                            for arg in sub.args:
                                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                                    if len(arg.value) > 5: # Likely a question or name, not just a short ID
                                        questions.append(arg.value)
                    except Exception:
                        pass

            tests.append({
                "file": path.name,
                "class": node.name,
                "class_doc": class_doc,
                "name": item.name,
                "doc": doc,
                "assertions": assertions,
                "expected_answers": expected_answers,
                "questions": questions,
                "calls": calls[:3],  # First 3 unique-ish calls
                "node_id": f"{path.name}::{node.name}::{item.name}",
            })

    return tests


def run_pytest_and_get_statuses() -> dict:
    """Run pytest and return {node_id: 'PASS' | 'FAIL'}."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", ".", "-v", "--tb=no",
         "--no-header", "-q", "--no-summary"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )

    statuses = {}
    # Strip ANSI codes that pytest emits with color
    output = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    for line in output.split("\n"):
        # Format: test_file.py::ClassName::test_method PASSED [  1%]
        m = re.match(r"^(\S+?)\s+(PASSED|FAILED|SKIPPED|ERROR)", line)
        if m:
            statuses[m.group(1)] = m.group(2)
    return statuses


def main():
    # Collect all tests
    all_tests = []
    for test_file in sorted(TESTS_DIR.glob("test_*.py")):
        all_tests.extend(extract_tests_from_file(test_file))

    # Run pytest to get pass/fail
    print(f"Running pytest to collect results...", file=sys.stderr)
    statuses = run_pytest_and_get_statuses()

    # Build markdown report
    lines = []
    lines.append("# Astrobot Deterministic Test Suite — Detailed Report")
    lines.append("")
    lines.append(f"**Generated**: {datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"**Total tests**: {len(all_tests)}")
    pass_count = sum(1 for t in all_tests if statuses.get(t["node_id"]) == "PASSED")
    fail_count = sum(1 for t in all_tests if statuses.get(t["node_id"]) == "FAILED")
    lines.append(f"**Passed**: {pass_count}")
    lines.append(f"**Failed**: {fail_count}")
    lines.append("")
    lines.append("Each test below shows:")
    lines.append("- **What it verifies** (docstring)")
    lines.append("- **What it calls** (the function under test)")
    lines.append("- **What it asserts** (the actual checks)")
    lines.append("- **Result** (PASS or FAIL)")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Group by file → class
    by_file = {}
    for t in all_tests:
        by_file.setdefault(t["file"], {}).setdefault(t["class"], []).append(t)

    test_counter = 0
    for fname in sorted(by_file.keys()):
        lines.append(f"## File: `{fname}`")
        lines.append("")

        for class_name in sorted(by_file[fname].keys()):
            tests = by_file[fname][class_name]
            class_doc = tests[0].get("class_doc", "")

            lines.append(f"### {class_name}")
            if class_doc:
                lines.append(f"_{class_doc.strip()}_")
            lines.append("")
            lines.append(f"({len(tests)} tests)")
            lines.append("")

            for t in tests:
                test_counter += 1
                status = statuses.get(t["node_id"], "UNKNOWN")
                badge = "✅ PASS" if status == "PASSED" else (
                    "❌ FAIL" if status == "FAILED" else f"⚠️ {status}"
                )

                lines.append(f"#### Test {test_counter}: `{t['name']}` — {badge}")
                lines.append("")

                if t["doc"]:
                    lines.append(f"**What it verifies**: {t['doc'].strip()}")
                else:
                    desc = t["name"].replace("test_", "").replace("_", " ")
                    lines.append(f"**What it verifies**: {desc}")
                lines.append("")

                if t["calls"]:
                    lines.append("**Function under test**:")
                    lines.append("```python")
                    for c in t["calls"][:3]: # Show up to 3 calls
                        lines.append(c)
                    lines.append("```")
                    lines.append("")

                if t["assertions"]:
                    lines.append("**Assertions**:")
                    lines.append("```python")
                    for a in t["assertions"][:10]: # Show up to 10 asserts
                        lines.append(f"assert {a}")
                    if len(t["assertions"]) > 10:
                        lines.append(f"# ... ({len(t['assertions']) - 10} more)")
                    lines.append("```")
                    lines.append("")

                lines.append("---")
                lines.append("")

    # Summary table at end
    lines.append("## Summary Table")
    lines.append("")
    lines.append("| # | File | Class | Test | Result |")
    lines.append("|---|------|-------|------|--------|")
    for i, t in enumerate(all_tests, 1):
        status = statuses.get(t["node_id"], "UNKNOWN")
        badge = "✅" if status == "PASSED" else ("❌" if status == "FAILED" else "⚠️")
        lines.append(f"| {i} | `{t['file']}` | {t['class']} | `{t['name']}` | {badge} {status} |")

    report = "\n".join(lines)

    out_path = PROJECT_ROOT / "TEST_REPORT.md"
    out_path.write_text(report)
    print(f"Report written to: {out_path}")
    print(f"Total: {len(all_tests)} tests | Passed: {pass_count} | Failed: {fail_count}")


if __name__ == "__main__":
    main()
