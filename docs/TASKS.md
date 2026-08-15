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
on first pass, 2/12 exposed a rubric ambiguity that was fixed (see 1.3). Live Skill-tool
smoke test: run via the `Skill` tool in-session on E001 (clean) and E002 (PHI trip),
and again through the packaged plugin in Claude Cowork on E005 (clean) and E002 (PHI
trip) — see 4.2. All four matched their `expected_*` labels.

### 2.2 Spoke agents (`automation-lead`, `data-lead`, `deployment-lead`) — DONE
**Spec:** each takes an already-classified enquiry (never re-classifies), produces a
scoping note + 2–3 clarifying questions, never quotes price/timeline, never runs if
`requires_human_review` is true, restricted to `Read`/`Write` tools only.
**Test:** frontmatter tool restriction inspected directly in each `.md` file. Behavioral
test covered by the same live runs as 2.1: `automation-lead` on E001 stayed within
its boundaries and additionally flagged a PHI-guardrail disagreement worth a human
look (see README "Why hub-and-spoke" discussion); `deployment-lead` on E005 recommended
an onsite walkthrough and flagged the biohazard/regulatory caveat exactly as specified
in its agent file, without quoting price or timeline.

### 2.3 PHI guardrail as a prompt instruction — DONE, superseded by §3.2
**Spec:** `SKILL.md` Step 3 states the hard rule (`phi_involved` true ⇒
`requires_human_review` true, no auto-dispatch). This is instruction-level enforcement
only — it depends on the model following it correctly every time. §3.2 adds a
deterministic backstop that doesn't depend on the model remembering.

## 3. Harness (observability + guardrail)

### 3.1 `eval_harness.py` — WRITTEN, NOT YET BATCH-RUN
**Spec:** for each synthetic case, invoke headless Claude Code with the intake-triage
skill, parse the JSON result, grade against `expected_*` fields, print pass/fail per
case and an aggregate score.
**Test:** requires the `claude` CLI on PATH and network access; not yet executed as a
full batch. Note this is distinct from the ad hoc live runs in 2.1/4.2, which used the
`Skill` tool and the Cowork plugin directly rather than this script's subprocess loop —
those exercised 4 of the 12 cases by hand, not all 12 automatically.

### 3.2 Guardrail hook (deterministic backstop) — DONE
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
**Result:** `test_guardrail_hook.py` runs all cases (A–F, F being 3.3's missing-field
check) against the real hook script via subprocess, asserting exit codes. 6/6 passed.
Also fired for real during the live runs in 2.1/4.2 — passed silently on all four (none
were guardrail violations by construction, so this confirms it activates on the right
writes without false-positiving on correct ones, not that it blocks — blocking is what
the isolated test suite specifically covers).

### 3.3 Observability completeness check — DONE
**Spec:** the same hook also confirms every written line has all 10 required output
fields (§1.2) before accepting it as a valid log entry — an incomplete record is as bad
as a missing one for anyone reading the log later.
**Test:** a record missing e.g. `rationale` or `routed_to` fails the same way Case E
above does.
**Result:** implemented alongside 3.2 (`REQUIRED_FIELDS` check in
`validate_triage_log.py`); covered by `test_guardrail_hook.py` case F (missing
`rationale` → exit 2). Full suite: 6/6 passed. ✅

## 4. Plugin packaging and live validation

### 4.1 Plugin packaging (`triage-claude-plugin/`) — DONE
**Spec:** self-contained plugin folder — `.claude-plugin/plugin.json` manifest, hard
copies (not symlinks) of the Skill, the three Agents, and the guardrail hook, plus
bundled demo cases so it's testable without the source repo alongside it.
**Result:** built per the current Claude Code plugin schema (`skills/`, `agents/`,
`hooks/hooks.json`, `scripts/`). The hook script was adapted, not copied verbatim — it
reads the target file path from the `PostToolUse` hook's stdin payload instead of
deriving it from its own file location, since the latter only resolves correctly inside
this specific repo. A repo-root `.claude-plugin/marketplace.json` lists the plugin by
relative path so it installs directly from this repo without a separate plugin-only
repository.

### 4.2 Live validation in Claude Cowork — DONE
**Spec:** confirm the packaged plugin (not just the source Skill/Agents) actually
installs and runs correctly end-to-end in a real product surface, not just headless.
**Test:** install via Cowork's Customize → Plugins → Add marketplace UI, run two
bundled cases, compare against `expected_*` labels.
**Result:** ran E005 (clean routing → `deployment-lead`) and E002 (PHI guardrail trip →
stopped before dispatch); both matched expected labels exactly. This surfaced one real
packaging bug (`marketplace.json` was missing the required top-level `name`/`owner`
fields — Cowork's "Add marketplace" rejected it until fixed) and validated one design
decision (the hook's stdin-based path resolution kept working even though Cowork
installs the plugin read-only and redirects `Write` calls to a per-task working folder
outside the plugin directory — a location the hook's own file path could never have
predicted). See root `README.md` → "Validated in Claude Cowork" for details. ✅

## Open items (not started, tracked so they don't get lost)

- Run `eval_harness.py` for real (batch, headless, all 12 cases) — the individual live
  Cowork runs in 4.2 substitute for a one-off smoke test, but not for the full
  automated grading pass across the whole synthetic set.
