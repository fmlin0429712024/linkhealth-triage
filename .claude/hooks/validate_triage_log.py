#!/usr/bin/env python3
"""Deterministic backstop for the intake-triage guardrail (docs/TASKS.md 3.2, 3.3).

Runs as a PostToolUse hook after any Write to data/triage_log.jsonl. Re-reads the file
itself (rather than trusting the hook payload's content field) and validates the last
line written. This does not depend on the model remembering the guardrail rule in
SKILL.md Step 3 — it enforces it in code.

Exit 0 = pass (silent). Exit 2 = violation found, printed to stderr, tool call blocked.
"""
import json
import sys
from pathlib import Path

DEFAULT_LOG_PATH = Path(__file__).resolve().parents[2] / "data" / "triage_log.jsonl"

REQUIRED_FIELDS = [
    "enquiry_id",
    "service_line",
    "complexity_score",
    "complexity",
    "urgency",
    "phi_involved",
    "requires_human_review",
    "needs_manual_triage",
    "routed_to",
    "rationale",
]


def fail(message: str) -> None:
    print(f"[guardrail-hook] BLOCKED: {message}", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOG_PATH
    if not log_path.exists():
        return

    lines = [line for line in log_path.read_text().splitlines() if line.strip()]
    if not lines:
        return

    last_line = lines[-1]
    try:
        record = json.loads(last_line)
    except json.JSONDecodeError as e:
        fail(f"last line of {log_path.name} is not valid JSON ({e})")
        return

    missing = [f for f in REQUIRED_FIELDS if f not in record]
    if missing:
        fail(f"triage record {record.get('enquiry_id', '?')} is missing required field(s): {missing}")
        return

    if record["phi_involved"] is True and record["requires_human_review"] is not True:
        fail(
            f"triage record {record['enquiry_id']} has phi_involved=true but "
            f"requires_human_review={record['requires_human_review']!r} — "
            "PHI-flagged enquiries must always require human review."
        )
        return


if __name__ == "__main__":
    main()
