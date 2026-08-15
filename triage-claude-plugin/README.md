# linkhealth-intake-triage (plugin)

Self-contained Claude Code plugin packaging of the LinkHealth intake-triage system: one
Skill (hub) that classifies/scores/routes an enquiry, three Agents (spokes) that draft
scoping notes, and a hook that deterministically enforces the PHI guardrail on every
write to a triage log — independent of the plugin's install location.

## Contents

```
.claude-plugin/plugin.json   plugin manifest
skills/intake-triage/        classification + complexity scoring + routing decision
agents/*.md                  automation-lead, data-lead, deployment-lead spokes
hooks/hooks.json             PostToolUse hook registration
scripts/validate_triage_log.py   guardrail enforcement (phi_involved ⇒ requires_human_review)
examples/synthetic_enquiries.jsonl   12 sample enquiries for a live demo — paste one at a
                              time (e.g. "run intake-triage on case E005 in
                              examples/synthetic_enquiries.jsonl") to show the classify →
                              log → guardrail → dispatch flow without touching real data
```

`examples/` is demo data only, not a test harness — for automated grading against
`expected_*` labels, use `data/eval_harness.py` in the source repo (root `README.md`),
which isn't bundled here since it depends on the `claude` CLI and repo-relative paths.

## Install

The repo this directory lives in doubles as a plugin marketplace
(`.claude-plugin/marketplace.json` at the repo root lists this folder by relative path)
— no separate plugin-only repo needed.

**Claude Code (CLI):**

```
/plugin marketplace add fmlin0429712024/linkhealth-triage
/plugin install linkhealth-intake-triage
```

**Claude Cowork:** Customize → Plugins → Add marketplace, paste
`https://github.com/fmlin0429712024/linkhealth-triage`, then install
`linkhealth-intake-triage`.

No build step either way — it's Skill + Agent markdown, plus one dependency-free Python
script. Live-validated in both: see root `README.md` §2 ("Validated in Claude Cowork").

## Source of truth

This is a packaged copy for portability/distribution. The source project (with the
architecture doc, synthetic eval set, and full test suite) lives at the repo root — see
the top-level `README.md`.
