#!/usr/bin/env python3
"""Deterministic backstop for the intake-triage guardrail.

Runs as a PostToolUse hook after any Write tool call. Reads the hook's JSON
payload from stdin to find which file was written, only acts if that file is
a `data/triage_log.jsonl`, then re-reads the file itself (not the payload's
content field) and validates the last line written. This does not depend on
the model remembering the guardrail rule in SKILL.md Step 3 — it enforces it
in code.

Portable by design: unlike a path derived from this script's own location,
this reads the target path from the hook payload, so it works regardless of
where the plugin is installed relative to the project it's validating.

Exit 0 = pass (silent, or not applicable). Exit 2 = violation, printed to
stderr, tool call blocked.
"""
import json
import sys
from pathlib import Path

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


def resolve_log_path() -> Path | None:
    if len(sys.argv) > 1:
        return Path(sys.argv[1])
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return None
    file_path = payload.get("tool_input", {}).get("file_path")
    if not file_path or not file_path.replace("\\", "/").endswith("data/triage_log.jsonl"):
        return None
    return Path(file_path)


def main() -> None:
    log_path = resolve_log_path()
    if log_path is None or not log_path.exists():
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
