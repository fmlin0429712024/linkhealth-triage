# LinkHealth Intake Triage

An automated triage system for inbound business enquiries at a healthcare-sector AI
consultancy. Given a free-text enquiry plus industry, org size, and stated urgency, it
classifies the enquiry by service line, scores its complexity, flags PHI/compliance
exposure, and routes it to the right next step — with a hard stop for human review
whenever patient data is in play.

Built entirely from Claude Code primitives: a Skill, three Agents, and a hook. No
separate app or framework.

## What it does

```mermaid
flowchart TD
    A["Enquiry<br/>raw_text · industry · org_size · stated_urgency"] --> B

    subgraph MODEL["Model workflow — Skill + Agents, in-context"]
        B["intake-triage Skill (hub)"]
        B --> S1["1. Classify → one of 3 service lines"]
        S1 --> S2["2. Score complexity<br/>4 dimensions × 0–2 → simple / moderate / complex"]
        S2 --> S3["3. Flag PHI<br/>data_sensitivity ≥ 1 ⇒ phi_involved = true"]
        S3 --> S4["4. Ambiguity check<br/>weak fit → best-guess label, never a 4th category"]
        S4 --> W["Write decision to data/triage_log.jsonl"]
        D{requires_human_review?}
        D -->|true| STOP["Stop — queued for human sign-off"]
        D -->|false| SP["Dispatch to matching spoke agent<br/>(isolated context, Read/Write only)"]
        SP --> N["Scoping note + clarifying questions"]
    end

    subgraph HARNESS["Harness — PostToolUse hook, deterministic, outside the model"]
        H["validate_triage_log.py<br/>re-reads the file, enforces phi_involved ⇒ requires_human_review"]
        BLOCK["Exit 2 → write blocked, surfaced to operator"]
        H -->|violation| BLOCK
    end

    W --> H
    H -->|pass| D

    classDef modelNode fill:#e8edff,stroke:#3b5bdb,color:#1a1a2e
    classDef harnessNode fill:#ffe9d6,stroke:#c2650a,color:#1a1a2e
    class A,B,S1,S2,S3,S4,W,D,STOP,SP,N modelNode
    class H,BLOCK harnessNode
```

Two different planes, drawn deliberately: the blue nodes are the Skill/Agents reasoning
in-context — they can be wrong or forget an instruction. The orange node is a plain
Python script the Claude Code **harness** runs after every `Write`, entirely outside the
model's context — it doesn't trust the model, it re-reads the file and checks the rule
itself. See "The guardrail is enforced twice, on purpose" below.

**The one hard stop:** any enquiry touching clinical/patient-identifiable data
(`phi_involved: true`) always requires human review and is never auto-dispatched,
regardless of how "simple" it otherwise scores. Everything else can run end-to-end
without a human in the loop.

## Why hub-and-spoke, and why isolated spokes

- **Untrusted input** — `raw_text` comes from a public web form; it's a real
  prompt-injection surface. Tool-restricted (`Read`/`Write` only), isolated spoke
  agents bound the blast radius of anything embedded in an enquiry.
- **Batch processing, no cross-contamination** — enquiries get processed in batches. A
  shared-context design would accumulate every prior enquiry (including PHI) into one
  growing thread. Isolated spokes prevent that by construction.
- **Previews the production shape** — a webhook-triggered, per-submission job is a
  stateless hub (dispatcher) calling a stateless worker (spoke). Building it that way
  now avoids a rewrite later.

No message queue at current volume (~40–60/week, single operator) — the append-only log
already gives durability, since a decision is persisted before the spoke step runs. See
`docs/PRD.md` §7 for the specific triggers that would change this call.

## The guardrail is enforced twice, on purpose

The rule (`phi_involved: true` ⇒ `requires_human_review: true`, no auto-dispatch) is
stated once as a model instruction (`SKILL.md` Step 3) and enforced a second time in
code, independent of whether the model follows the instruction: a `PostToolUse` hook
fires on every write to the triage log, re-reads the file itself, and blocks (non-zero
exit, clear stderr) if a record violates the rule or is missing required fields. The
instruction can't be trusted alone; the hook doesn't depend on the model remembering
anything.

## Repository layout

```
.claude/
  skills/intake-triage/SKILL.md   the hub: classification + scoring rubric + routing rules
  agents/*.md                     the three spokes (automation-lead, data-lead, deployment-lead)
  hooks/validate_triage_log.py    deterministic guardrail backstop
  settings.json                   wires the hook to the Write tool
data/
  synthetic_enquiries.jsonl       12 hand-built test cases with expected_* labels
  triage_log.jsonl                append-only output of real triage runs
  eval_harness.py                 runs all 12 cases through the skill, grades the output
  test_guardrail_hook.py          isolated test suite for the hook (no model calls needed)
docs/
  PRD.md                          full spec: requirements, data flow, scope boundaries
  TASKS.md                        spec-driven task breakdown, done/open status
.claude-plugin/marketplace.json   repo-root marketplace listing (points at triage-claude-plugin/)
triage-claude-plugin/             self-contained plugin packaging of the same system
  (portable copy of the skill, agents, hook, and demo cases — see its own README)
```

## Installing the plugin

The repo root doubles as a plugin marketplace (`.claude-plugin/marketplace.json`), which
lists `triage-claude-plugin/` as a plugin by relative path — no separate repo needed.

**Claude Code (CLI):**

```
/plugin marketplace add fmlin0429712024/linkhealth-triage
/plugin install linkhealth-intake-triage
```

**Claude Cowork:** plugins install through the UI, not slash commands — open
**Customize → Plugins → Add marketplace**, paste
`https://github.com/fmlin0429712024/linkhealth-triage`, then install
`linkhealth-intake-triage` from the results.

Then try it on a bundled sample, e.g.: *"run intake-triage on case E005 in
triage-claude-plugin/examples/synthetic_enquiries.jsonl."*

## Validated in Claude Cowork

Beyond the synthetic eval harness, the packaged plugin was installed in Claude Cowork and
run live against two bundled cases:

- **E005** (AGV waste transport, hemodialysis center) — Onsite Automation & Robotics
  Deployment, moderate (total=4), `phi_involved: false`, auto-routed to `deployment-lead`,
  which drafted a scoping note and flagged an onsite walkthrough as a prerequisite.
- **E002** (prior-authorization automation, 450-bed hospital network) — Process &
  Workflow Automation, complex (total=6), `phi_involved: true` → `requires_human_review:
  true`, correctly stopped before any spoke dispatch.

Both matched their `expected_*` labels exactly. Two things this pass surfaced that a
synthetic eval alone wouldn't have caught:

- **A packaging bug**: `.claude-plugin/marketplace.json` initially listed only `plugins`,
  missing the required top-level `name` and `owner` fields — Cowork's "Add marketplace"
  rejected it until those were added. Worth checking if you fork this and rename things.
- **A design decision that paid off**: Cowork installs a plugin read-only and redirects
  `Write` calls to a per-task working folder outside the plugin directory. The guardrail
  hook (`scripts/validate_triage_log.py`) reads the actual written-to path from its own
  stdin payload rather than deriving it from its file location on disk — see "The
  guardrail is enforced twice, on purpose" above — which is exactly why it kept working
  once the log path moved somewhere the hook's source location never anticipated.

One operational implication for the guardrail-tripped case specifically: since sign-off
review should happen against the durable record, not a chat transcript, a reviewer should
open the actual `triage_log.jsonl` in Cowork's working folder for a queued case rather
than trusting the conversational summary — that's the whole point of logging it.

## Running the tests

```bash
# Hook logic, offline, no model calls
python3 data/test_guardrail_hook.py

# Full pipeline: feeds all 12 synthetic cases through headless Claude Code,
# grades classification/complexity/guardrail output against expected labels.
# Requires the `claude` CLI on PATH and network access.
python3 data/eval_harness.py
```

Both the hook's own test suite and a live run through the Skill (classify → log → hook
validate → dispatch to a spoke) have been exercised against real cases, including one
that trips the PHI guardrail and correctly halts before dispatch.

## Scope boundaries (deliberate, not gaps)

This system triages **business enquiries about services** — it does not triage
patients and is never repurposed for clinical decision support. Also deliberately not
built this round: a web front-end for the intake form (synthetic JSONL stands in for
submissions), an internal review dashboard (the log file is sufficient at this volume),
and a message queue (see the trigger table in `docs/PRD.md` §7 for when that changes).

## What I'd change with more scale or time

- Replace the synchronous Agent-tool dispatch with a real queue once volume or
  multi-lead claiming requires it (trigger table in `docs/PRD.md` §7).
- Add a lightweight review dashboard once the log file stops being a sufficient
  read surface for the operator.
- The PHI rubric intentionally treats plain scheduling metadata (a name + an
  appointment time) as not triggering the guardrail, reserving it for clinical
  content. That's a defensible but debatable line — worth revisiting against actual
  legal/compliance guidance rather than a judgment call made while building this.
