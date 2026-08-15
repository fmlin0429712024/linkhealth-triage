# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

LinkHealth Intake Triage — a prototype that classifies, enriches, and routes inbound
business enquiries for a one-person AI-enablement consultancy serving the patient-care
domain. It is built entirely from Claude Code primitives (a Skill, three Agents, a
hook) rather than a standalone app. The original task brief is
`AIVC_Technical Challenge_Task 1.2.pdf`; the actual spec-as-built is `docs/PRD.md`, and
task-by-task status (including open items) is `docs/TASKS.md`. Read those two before
making non-trivial changes — this CLAUDE.md summarizes them but they are authoritative.

**Scope boundary (do not drift from this):** this system triages *business enquiries
about LinkHealth's services*. It never triages patients and must never be presented as,
or repurposed for, clinical decision support.

## Architecture: hub-and-spoke

```
enquiry (raw_text, industry, org_size, stated_urgency)
  → intake-triage Skill (hub, .claude/skills/intake-triage/SKILL.md)
      1. classify into exactly one of 3 service lines
      2. score complexity: 4 dimensions × 0-2, summed → simple/moderate/complex
      3. PHI guardrail: data_sensitivity ≥ 1 → phi_involved=true → requires_human_review=true, no auto-dispatch
      4. ambiguity check: weak fit → needs_manual_triage=true (never invent a 4th category)
      5. append decision to data/triage_log.jsonl (PostToolUse hook validates it, see below)
      6. if cleared, dispatch via Agent tool to the matching spoke
  → spoke agent (.claude/agents/{automation,data,deployment}-lead.md)
      Read/Write only, isolated context, never re-classifies, never quotes price/timeline,
      never runs if requires_human_review is true. Drafts a scoping note + 2-3 clarifying
      questions.
```

- **Hub** = the `intake-triage` Skill, runs in-context in the main session.
- **Spokes** = `automation-lead` / `data-lead` / `deployment-lead` Agents, each
  tool-restricted to `Read, Write` and dispatched only after the hub clears the
  enquiry. Routing: Process & Workflow Automation → `automation-lead`; Documentation &
  Data Analytics → `data-lead`; Onsite Automation & Robotics Deployment →
  `deployment-lead`.
- Isolation between hub and spokes is deliberate, not incidental — `raw_text` is
  untrusted public-form input (prompt-injection surface), and isolated spokes prevent
  cross-enquiry context bleed (including PHI) across a batch run. See PRD §7 for the
  full rationale and the trigger table for when a real queue would replace the current
  direct-dispatch design.
- **The PHI guardrail is the one hard stop.** `phi_involved: true` always forces
  `requires_human_review: true` and blocks auto-dispatch, regardless of complexity.
  Everything else can be automated end-to-end.

## Enforcement: prompt instruction + deterministic backstop

The guardrail is stated in `SKILL.md` Step 3, but that's instruction-level only — it
depends on the model remembering. `.claude/hooks/validate_triage_log.py` is a
`PostToolUse` hook (wired in `.claude/settings.json`, matcher `Write`) that fires
whenever `data/triage_log.jsonl` is written. It re-reads the file itself (does not
trust the hook payload), parses the last line, and enforces in code:
- all 10 required output fields are present (see schema below), and
- `phi_involved: true` ⇒ `requires_human_review: true`.

Exit 0 = silent pass. Exit 2 = blocked, reason printed to stderr. This means editing
the guardrail rule requires updating **both** `SKILL.md` Step 3 (the instruction) and
`validate_triage_log.py` (the enforcement) — they are intentionally redundant, not one
source of truth.

## Triage output schema

Every decision (including guardrail-tripped ones) is logged as one JSON line in
`data/triage_log.jsonl`:

```json
{
  "enquiry_id": "...",
  "service_line": "Process & Workflow Automation | Documentation & Data Analytics | Onsite Automation & Robotics Deployment",
  "complexity_score": {"integration_depth": 0, "data_sensitivity": 0, "physical_onsite": 0, "org_scale": 0, "total": 0},
  "complexity": "simple | moderate | complex",
  "urgency": "low | medium | high",
  "phi_involved": false,
  "requires_human_review": false,
  "needs_manual_triage": false,
  "routed_to": "automation-lead | data-lead | deployment-lead",
  "rationale": "one to three sentences citing the scoring dimensions that drove the result"
}
```

The full scoring rubric (including the "de-identification doesn't lower
`data_sensitivity`" rule, hand-corrected after catching two mislabeled synthetic cases)
lives only in `SKILL.md` — don't duplicate it elsewhere; change it there.

## Commands

```bash
# Run the guardrail hook's own test suite (no network, no claude CLI needed)
python3 data/test_guardrail_hook.py

# Run the hook directly against a specific log file
python3 .claude/hooks/validate_triage_log.py path/to/file.jsonl

# Run the full eval harness: feeds all 12 synthetic cases through headless Claude Code
# via the intake-triage skill and grades against expected_* fields.
# Requires the `claude` CLI on PATH and network access.
python3 data/eval_harness.py
```

There is no build step, package manifest, or app server in this repo — the "app" is
the Skill/Agent/hook configuration itself, invoked through Claude Code.

## Working in this repo

- `data/synthetic_enquiries.jsonl` (12 cases, `E001`–`E012`) is the only test fixture.
  It carries `expected_*` fields for grading and deliberately covers all 3 service
  lines, all 3 complexity buckets, PHI true/false, one ambiguous case, and one
  high-urgency case. If you add a case, add matching `expected_*` fields.
- `data/triage_log.jsonl` is append-only output, not a fixture — don't hand-edit it to
  "fix" a bad run; that defeats the point of the guardrail hook.
- Per PRD §11 (explicitly out of scope this round): no web front-end, no review
  dashboard, no message queue, no live conversational intake. Don't add these unless
  the user asks — they're deliberate scope cuts, not gaps.
- Open items tracked in `docs/TASKS.md` (not yet done as of last update): a live smoke
  test of the Skill via the `Skill` tool in a fresh session, and actually running
  `eval_harness.py` end-to-end.
