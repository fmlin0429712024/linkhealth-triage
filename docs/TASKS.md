# Tasks — SDD / TDD breakdown

Spec-driven: every task states its spec (what it must guarantee) and its test criteria
*before* implementation notes. "Done" tasks below are recorded retroactively in the same
shape so the spec/test trail is complete, not just the code.

## 1. Data

### 1.1 Enquiry input schema — DONE
**Spec:** every enquiry has exactly `raw_text`, `industry`, `org_size`, `stated_urgency`.
**Test:** all 12 rows in `synthetic_enquiries.jsonl` parse with these four fields
present and non-empty. ✅ verified by inspection.

### 1.2 Triage output schema — DONE
**Spec:** matches `SKILL.md` Step 5 exactly — `enquiry_id`, `service_line`,
`complexity_score` (4 sub-fields + `total`), `complexity`, `urgency`, `phi_involved`,
`requires_human_review`, `needs_manual_triage`, `routed_to`, `rationale`.
**Test:** `eval_harness.py`'s `grade()` fails loudly (`parse_error`) if the shape is
missing keys it checks against. ✅ implemented.

### 1.3 Synthetic dataset — DONE
**Spec:** ≥10 cases, all 3 service lines represented, all 3 complexity buckets
represented, at least one `phi_involved=true` and one `phi_involved=false` per line
where plausible, exactly one deliberately ambiguous case, at least one high-urgency
case.
**Test:** manual audit against `expected_*` fields.
**Result:** 12 cases (`E001`–`E012`). Manual rubric walkthrough caught 2 mislabeled
expectations (`E002`, `E008` — both under-scored `data_sensitivity` for research/
cross-site data); corrected in the data, and the rubric text in `SKILL.md` was
tightened with an explicit rule (de-identification doesn't lower the score for
research/cross-site cases) so the same mistake doesn't recur. ✅

## 2. Workflows (the MD-defined hub and spokes)

### 2.1 `intake-triage` Skill (hub) — DONE
**Spec:** given the 4 input fields, must (a) classify into exactly one of 3 lines, (b)
score complexity on the fixed 4-dimension rubric, (c) set `phi_involved` and enforce the
guardrail (§2.3 below), (d) set `needs_manual_triage` on weak fits instead of inventing
a 4th category, (e) log the decision, (f) dispatch to the correct spoke unless the
guardrail tripped.
**Test:** hand-simulated against all 12 synthetic cases; 10/12 matched expected labels
on first pass, 2/12 exposed a rubric ambiguity that was fixed (see 1.3). Live
Skill-tool smoke test is still pending — project-level skills are discovered at session
start, so this needs a fresh Claude Code session to invoke via the `Skill` tool
end-to-end (tracked as an open item, not yet run).

### 2.2 Spoke agents (`automation-lead`, `data-lead`, `deployment-lead`) — DONE
**Spec:** each takes an already-classified enquiry (never re-classifies), produces a
scoping note + 2–3 clarifying questions, never quotes price/timeline, never runs if
`requires_human_review` is true, restricted to `Read`/`Write` tools only.
**Test:** frontmatter tool restriction inspected directly in each `.md` file. Behavioral
test (does the drafted note stay within these boundaries) is covered by the same
pending live smoke test as 2.1.

### 2.3 PHI guardrail as a prompt instruction — DONE, superseded by §3.2
**Spec:** `SKILL.md` Step 3 states the hard rule (`phi_involved` true ⇒
`requires_human_review` true, no auto-dispatch). This is instruction-level enforcement
only — it depends on the model following it correctly every time. §3.2 adds a
deterministic backstop that doesn't depend on the model remembering.

## 3. Harness (observability + guardrail)

### 3.1 `eval_harness.py` — DONE
**Spec:** for each synthetic case, invoke headless Claude Code with the intake-triage
skill, parse the JSON result, grade against `expected_*` fields, print pass/fail per
case and an aggregate score.
**Test:** requires `claude` CLI + network; not yet executed end-to-end (same
dependency as 2.1's pending live smoke test).
**Status:** written, unexecuted.

### 3.2 Guardrail hook (deterministic backstop) — TO DO
**Spec:** a `PostToolUse` hook fires whenever the `Write` tool targets
`data/triage_log.jsonl`. It parses the just-written line and enforces, in code, not in
a prompt: **if `phi_involved` is `true`, `requires_human_review` must also be `true`.**
A violation is surfaced loudly (non-zero exit, clear stderr message) rather than
silently accepted. This exists specifically because §2.3 only works if the model
remembers to follow it — this hook doesn't depend on that.
**Test cases (write before implementing):**
| Case | Input record | Expected hook result |
|---|---|---|
| A | `phi_involved: true, requires_human_review: true` | pass silently |
| B | `phi_involved: true, requires_human_review: false` | **fail loudly** — this is the exact defect the hook exists to catch |
| C | `phi_involved: false, requires_human_review: false` | pass silently |
| D | `phi_involved: false, requires_human_review: true` | pass silently (over-caution isn't a violation) |
| E | malformed/non-JSON line written | fail loudly — a broken log entry is itself a defect worth surfacing |

### 3.3 Observability completeness check — TO DO
**Spec:** the same hook also confirms every written line has all 10 required output
fields (§1.2) before accepting it as a valid log entry — an incomplete record is as bad
as a missing one for anyone reading the log later.
**Test:** a record missing e.g. `rationale` or `routed_to` fails the same way Case E
above does.

## Open items (not started, tracked so they don't get lost)

- Live smoke test of the `intake-triage` Skill via the `Skill` tool in a fresh session
  (2.1, 3.1 depend on this).
- Run `eval_harness.py` for real once the above is possible.
- Plugin packaging (deliberately last, per earlier discussion).
