#!/usr/bin/env python3
"""Eval harness for the intake-triage skill.

Feeds each synthetic enquiry in synthetic_enquiries.jsonl to headless Claude Code
with an instruction to run the intake-triage skill, parses the resulting JSON, and
grades it against the expected labels. Requires the `claude` CLI on PATH and network
access (each case is one API round trip).

Usage: python3 eval_harness.py
"""
import json
import subprocess
from pathlib import Path

DATA = Path(__file__).parent / "synthetic_enquiries.jsonl"


def run_case(case: dict) -> str:
    prompt = (
        "Use the intake-triage skill to classify this enquiry. "
        "Output ONLY the JSON object described in the skill's Step 5 output shape "
        "— no prose before or after it.\n\n"
        f"enquiry_id: {case['enquiry_id']}\n"
        f"raw_text: {case['raw_text']}\n"
        f"industry: {case['industry']}\n"
        f"org_size: {case['org_size']}\n"
        f"stated_urgency: {case['stated_urgency']}"
    )
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    return result.stdout


def grade(case: dict, output_text: str) -> dict:
    try:
        start = output_text.index("{")
        end = output_text.rindex("}") + 1
        actual = json.loads(output_text[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"enquiry_id": case["enquiry_id"], "pass": False, "parse_error": True, "raw_output": output_text}

    checks = {
        "service_line": actual.get("service_line") == case["expected_service_line"],
        "complexity": actual.get("complexity") == case["expected_complexity_bucket"],
        "phi_involved": actual.get("phi_involved") == case["expected_phi_involved"],
        "requires_human_review": actual.get("requires_human_review") == case["expected_requires_human_review"],
        "needs_manual_triage": actual.get("needs_manual_triage") == case["expected_needs_manual_triage"],
    }
    return {
        "enquiry_id": case["enquiry_id"],
        "pass": all(checks.values()),
        "checks": checks,
        "actual": actual,
    }


def main() -> None:
    cases = [json.loads(line) for line in DATA.read_text().splitlines() if line.strip()]
    results = []
    for case in cases:
        output = run_case(case)
        graded = grade(case, output)
        results.append(graded)
        status = "PASS" if graded.get("pass") else "FAIL"
        detail = graded.get("checks", {"parse_error": graded.get("parse_error")})
        print(f"[{status}] {case['enquiry_id']}: {detail}")

    n_pass = sum(1 for r in results if r.get("pass"))
    print(f"\n{n_pass}/{len(results)} passed")


if __name__ == "__main__":
    main()
