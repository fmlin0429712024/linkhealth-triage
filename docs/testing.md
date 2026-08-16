# Testing — LinkHealth VAS

How the system is verified across three layers: **unit tests** (logic), **demo
prompts** (end-to-end behaviour), and **production verification** (live on the
GCP VM).

## 1. Unit tests (zero dependencies, `node:test`)

The pure logic is unit-tested with no external dependencies:

```sh
cd linkhealth-triage && node --test        # 22 cases
```

Coverage:

| Module | What is tested |
|---|---|
| `triage-dsh-plugin/lib/validate.js` | guardrail rule set: 10 required fields, `phi_involved ⇒ requires_human_review`, last-line validation, path detection |
| `linkhealth-gui-plugin/lib/launcher-config.js` | capability-list schema, defaults merge, launch-parameter building, brand-token structure (light/dark) |

Guardrail parity: the same rule set lives in three places, deliberately kept in
sync — SKILL.md Step 3 (instruction), `lib/validate.js` (JS), and
`scripts/validate_triage_log.py` (standalone):

```sh
python3 triage-dsh-plugin/scripts/validate_triage_log.py path/to/triage_log.jsonl
# exit 0 = pass · exit 2 = violation
```

## 2. Demo prompts (end-to-end behaviour)

Three ready-to-paste prompts in `examples/demo-prompts.md`, in order:

| Prompt | Demonstrates | Expected |
|---|---|---|
| 1 · Full flow | complete pipeline + spoke handoff | Process & Workflow Automation / simple / phi=false / routed automation-lead |
| 2 · Guardrail trip | PHI hard stop | complex(6) / phi=true → requires_human_review=true / **no dispatch** |
| 3 · Hard block | immediate backstop block | `[guardrail] BLOCKED` on a violating `write`/`edit` |

Run them in a LinkHealth session — local (`127.0.0.1:3081`) or the VM tunnel
(`127.0.0.1:3082`); same codebase.

## 3. Production verification (GCP VM)

Live checklist after each CI/CD deploy (`docs/deployment-gcp.md`):

- [ ] `systemctl is-active linkhealth` → active
- [ ] `curl localhost:3080` on the VM → LinkHealth UI responds (client graph
      contains `linkhealth-gui-plugin`)
- [ ] Demo prompt 1 → full flow + spoke deliverable
- [ ] Demo prompt 2 → PHI case queued for human review, no dispatch
- [ ] Demo prompt 3 (edit tool) → immediate `[guardrail] BLOCKED`
- [ ] `validate-triage-log` → PASS after each valid decision

## 4. Known boundaries (by design)

- The `tools/post-execute` backstop covers `write`/`edit` tool calls only —
  a **bash append bypasses it** (same design as the Claude Code hook). Shell
  appends are caught by model self-discipline (SKILL.md) and the
  `validate-triage-log` tool; SKILL.md instructs appending via write/edit.
- `validate-triage-log` and the backstop resolve the log path against the
  **session workspace** (`exec.agent.session.header.cwd`), not the process
  cwd — learned live on the VM where the service runs from the release
  directory while sessions work elsewhere.
- Data is **synthetic only**; before any real client/PHI data, see the
  compliance gate in README §5 and `docs/deployment-gcp.md` §Cost & hygiene.
