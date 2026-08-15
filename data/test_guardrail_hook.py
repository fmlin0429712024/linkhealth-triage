#!/usr/bin/env python3
"""TDD test cases for the guardrail hook (docs/TASKS.md 3.2, 3.3).

Written before trusting the hook: each case is a one-line JSONL fixture fed to
validate_triage_log.py via a temp file, checking the exit code matches what the spec
in TASKS.md 3.2 table says it should.

Usage: python3 test_guardrail_hook.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "validate_triage_log.py"

BASE_RECORD = {
    "enquiry_id": "TEST",
    "service_line": "Process & Workflow Automation",
    "complexity_score": {"integration_depth": 1, "data_sensitivity": 0, "physical_onsite": 0, "org_scale": 0, "total": 1},
    "complexity": "simple",
    "urgency": "medium",
    "phi_involved": False,
    "requires_human_review": False,
    "needs_manual_triage": False,
    "routed_to": "automation-lead",
    "rationale": "test fixture",
}

CASES = [
    ("A: phi=true, review=true -> pass", {**BASE_RECORD, "phi_involved": True, "requires_human_review": True}, 0),
    ("B: phi=true, review=false -> BLOCK", {**BASE_RECORD, "phi_involved": True, "requires_human_review": False}, 2),
    ("C: phi=false, review=false -> pass", {**BASE_RECORD, "phi_involved": False, "requires_human_review": False}, 0),
    ("D: phi=false, review=true -> pass", {**BASE_RECORD, "phi_involved": False, "requires_human_review": True}, 0),
]


def run_case(label: str, record: dict, expected_code: int) -> bool:
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps(record) + "\n")
        path = f.name

    result = subprocess.run([sys.executable, str(HOOK), path], capture_output=True, text=True)
    ok = result.returncode == expected_code
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {label} (exit={result.returncode}, expected={expected_code})")
    if not ok and result.stderr:
        print(f"    stderr: {result.stderr.strip()}")
    return ok


def run_malformed_case() -> bool:
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write("{not valid json\n")
        path = f.name
    result = subprocess.run([sys.executable, str(HOOK), path], capture_output=True, text=True)
    ok = result.returncode == 2
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] E: malformed JSON -> BLOCK (exit={result.returncode}, expected=2)")
    return ok


def run_missing_field_case() -> bool:
    record = dict(BASE_RECORD)
    del record["rationale"]
    with tempfile.NamedTemporaryFile("w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps(record) + "\n")
        path = f.name
    result = subprocess.run([sys.executable, str(HOOK), path], capture_output=True, text=True)
    ok = result.returncode == 2
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] F: missing required field -> BLOCK (exit={result.returncode}, expected=2)")
    return ok


def main() -> None:
    results = [run_case(label, record, code) for label, record, code in CASES]
    results.append(run_malformed_case())
    results.append(run_missing_field_case())
    n_pass = sum(results)
    print(f"\n{n_pass}/{len(results)} passed")
    sys.exit(0 if n_pass == len(results) else 1)


if __name__ == "__main__":
    main()
