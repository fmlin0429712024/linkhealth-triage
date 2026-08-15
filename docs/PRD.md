# PRD — Intake Triage Agent (LinkHealth)

## 1. Problem

LinkHealth is a one-person AI-enablement consultancy serving the patient-care domain.
Inbound business enquiries arrive via a public web form: a short free-text description of
what the prospective client needs, their industry, org size, and stated urgency. Today
every enquiry would need to be manually read, tagged by service line, scored for
complexity, and routed to the right next step — the exact bottleneck described in the
source brief (~8 hrs/week, error-prone, doesn't scale past one person).

## 2. Goal

Replace the manual triage step with an automated system that classifies, enriches, and
routes each enquiry, so the operator only sees enquiries that are already scoped and
prioritized.

## 3. Explicit non-goal (scope boundary)

This system triages **business enquiries about LinkHealth's services**. It does **not**
triage patients and must never be presented as, or repurposed for, clinical decision
support. Every component (Skill, agents, docs) states this boundary explicitly to
prevent scope drift.

## 4. Users

| User | Interaction |
|---|---|
| **Enquirer** (prospective client — a clinic, hospital, dialysis center, etc.) | Fills a public, no-login web form. Never sees or interacts with any agent. Experience ends at a submission confirmation. |
| **Operator** (LinkHealth — currently one person) | Reads triaged output (classification, complexity, routing, draft scoping note) from a durable log and decides how to follow up. Never described as "the AI decided" — the system prepares, the operator decides. |

## 5. End-to-end flow

```
Enquirer → web form (name, org, industry, org_size, stated_urgency, raw_text)
         → submission confirmation (end of enquirer-facing experience)
         ────────────────────────────────────────────────────────────
                          (everything below is backend, invisible to enquirer)
         → intake-triage Skill (hub): classify service line, score complexity,
           evaluate PHI/compliance guardrail, decide routing
         → append decision to data/triage_log.jsonl (durable, append-only)
         → IF requires_human_review: stop here, queued for operator sign-off
         → ELSE: dispatch to the matching spoke agent (isolated context,
           tool-restricted) to draft a scoping note + clarifying questions
         → Operator reads the log + draft and follows up with the client directly
```

No agent ever talks to the enquirer. The system's output is decision support for the
operator, not an autonomous client-facing action.

## 6. Functional requirements

### 6.1 Service line classification

Exactly one of three lines per enquiry — no catch-all category. A weak fit still gets a
best-guess classification plus a `needs_manual_triage` flag (see 6.4), rather than
inventing a fourth bucket.

| Service line | Covers |
|---|---|
| Process & Workflow Automation | Automating an existing business/admin process (scheduling, reminders, prior auth, claims routing, intake routing, RPA, admin/billing chatbots) |
| Documentation & Data Analytics | Turning documents/data into structured output or insight (chart summarization, coding automation, dashboards, trend analysis, research pipelines) |
| Onsite Automation & Robotics Deployment | Physical/hardware automation inside a facility (AGVs, robotic transport, autonomous disinfection, anything requiring a site visit or hardware install) |

### 6.2 Complexity scoring

Four dimensions, scored 0–2 each, summed to 0–8:

| Dimension | 0 | 1 | 2 |
|---|---|---|---|
| `integration_depth` | Standalone | One existing system | Multiple/legacy systems |
| `data_sensitivity` | No patient-identifiable clinical data | Patient-identifiable data, standard handling | Clinical/health record content, or heightened scope (research, cross-site, cross-border — de-identification does not lower this) |
| `physical_onsite` | Fully remote/software | Some onsite configuration | Onsite hardware deployment |
| `org_scale` | Single small practice | Mid-size, multi-location | Large health system / hospital network |

Total 0–2 = **simple**, 3–5 = **moderate**, 6–8 = **complex**. Fixed rubric, not a
model "vibe check" — every score must cite which dimensions drove it.

### 6.3 PHI / compliance guardrail

`data_sensitivity ≥ 1` → `phi_involved: true`. This is a cross-cutting attribute, not a
service line — it can trigger on any of the three lines. Whenever `phi_involved` is
true, `requires_human_review` MUST be true regardless of complexity bucket, and the
system MUST NOT auto-dispatch to a spoke agent. This is the system's one hard stop;
everything else can be automated end-to-end.

### 6.4 Ambiguity handling

If an enquiry doesn't clearly fit one line (vague, multi-line, or under-specified),
still produce a best-guess classification and set `needs_manual_triage: true` with a
one-line reason. Never leave a field empty and never fabricate details not present in
the enquiry.

### 6.5 Routing

| Service line | Routed to |
|---|---|
| Process & Workflow Automation | `automation-lead` |
| Documentation & Data Analytics | `data-lead` |
| Onsite Automation & Robotics Deployment | `deployment-lead` |

Each is a separate, tool-restricted (`Read`, `Write` only) agent that drafts a scoping
note and 2–3 clarifying questions from the already-classified enquiry — never re-runs
classification, never quotes price/timeline, never proceeds if the guardrail tripped.

## 7. Architecture

**Hub-and-spoke.** Hub = `intake-triage` (Claude Code Skill, runs in-context). Spokes =
`automation-lead` / `data-lead` / `deployment-lead` (Claude Code Agents, isolated
context, dispatched via the Agent tool only when the guardrail clears).

Isolation for the spokes is a deliberate choice, not decoration:

- **Untrusted input surface** — `raw_text` is public-form input, a real prompt-injection
  vector. Tool-restricted, isolated spokes bound the blast radius of anything embedded
  in an enquiry.
- **Batch operation, cross-client contamination** — the operator processes a backlog in
  one sitting; a shared-context design would accumulate every prior enquiry's details
  (including PHI) in one growing thread. Isolated spokes prevent that.
- **Production shape** — the eventual production version is a webhook-triggered,
  per-submission job. Hub (stateless dispatcher) + spoke (stateless worker) previews
  that shape now instead of requiring a rewrite later.

**No message queue between hub and spokes at current volume** (~40–60/week, single
operator). `data/triage_log.jsonl` already provides the durability a queue would give —
a decision is persisted before the spoke step runs, so a spoke failure doesn't lose the
classification. A real queue gets added when any of these trip:

| Trigger | What gets added |
|---|---|
| Volume reaches ~50–100+/day | Real queue (e.g. SQS); hub writes to it instead of calling the Agent tool synchronously |
| Multiple human leads need to claim from a shared backlog | Queue + claim/status field |
| Spoke failures happen often enough to need retries | Retry + backoff + dead-letter handling |
| SLA moves from "weekly batch" to "respond within minutes" | Real-time event-driven processing |

## 8. Data

Enquiry input schema: `raw_text`, `industry`, `org_size`, `stated_urgency`.

Triage output schema (see `SKILL.md` Step 5 for the authoritative shape):
`enquiry_id`, `service_line`, `complexity_score` (per-dimension + total), `complexity`,
`urgency`, `phi_involved`, `requires_human_review`, `needs_manual_triage`, `routed_to`,
`rationale`.

Synthetic dataset: `data/synthetic_enquiries.jsonl` — 12 cases spanning all three
service lines, all three complexity buckets, PHI true/false, one deliberately ambiguous
case, and one high-urgency case. Each case carries `expected_*` fields for grading.

## 9. Observability

Every triage decision — including guardrail-tripped ones — is appended to
`data/triage_log.jsonl`. This is the system's day-one instrumentation: nothing is
silently decided without a durable record.

## 10. Testing strategy

- `data/eval_harness.py` runs each synthetic case through the skill (headless) and
  grades the output against `expected_*` fields.
- Rubric was hand-validated against all 12 synthetic cases before trusting the harness;
  this caught two mislabeled expectations (E002, E008 — both under-scored
  `data_sensitivity` for cross-site/research data), which were corrected in the data and
  clarified in the rubric text rather than left as silent inconsistencies.

## 11. Out of scope (this round)

- Plugin packaging for external distribution — deliberately last, not started.
- A real web front-end for the intake form — the form is treated as the input contract;
  synthetic JSONL stands in for actual submissions.
- An internal review dashboard — the log file is sufficient at current volume.
- A message queue — see trigger table in §7.
- Live conversational intake (chat-based form-filling) — the brief's literal scenario is
  a static form; a conversational front-end is a larger, separate product decision.
