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
```

## Install

Add this directory as a plugin source in Claude Code (local path or, once pushed, a Git
marketplace source), then enable `linkhealth-intake-triage`. No build step — it's Skill
+ Agent markdown, plus one dependency-free Python script.

## Source of truth

This is a packaged copy for portability/distribution. The source project (with the
architecture doc, synthetic eval set, and full test suite) lives at the repo root — see
the top-level `README.md`.
