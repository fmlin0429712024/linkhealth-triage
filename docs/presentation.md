---
marp: true
theme: default
paginate: true
title: LinkHealth Intake Triage
---

<!-- 1 · Use Case -->

# LinkHealth Intake Triage

**An AI triage system for inbound business enquiries**

*"LinkHealth" is a fictional company name used for this case study.*

Forest Lin · 08/16/2026

- A professional-services firm receives **40–60 enquiries/week** via a web form
- Today: a junior analyst reads each submission, tags service line, estimates
  complexity, routes to the right lead — **~8 hours/week, error-prone**
- This system automates: **classify → score → guardrail → route**

---

<!-- 2 · App Architecture -->

# Architecture — hub & spoke, with a hard guardrail

```
enquiry (raw_text · industry · org_size · urgency)
  → intake-triage hub
      1. classify → one of 3 service lines
      2. score complexity (4 dimensions × 0-2 → simple/moderate/complex)
      3. PHI guardrail: data_sensitivity ≥ 1 → phi_involved → requires_human_review
      4. ambiguity → needs_manual_triage (never invent a 4th category)
      5. log decision to data/triage_log.jsonl
      6. dispatch to the matching spoke
  → spoke (automation / data / deployment lead) → scoping note + questions
```

- **Two enforcement layers**: prompt instruction (SKILL.md) **+** deterministic
  backstop in code (post-write validator — the model cannot skip it)
- **The one hard stop**: any PHI-involved enquiry is queued for human review,
  never auto-dispatched
- **Model/API**: LLM classification via API — the same prompt assets run on
  Claude Code and DeepSeek Harness, so the model choice is swappable, not baked in
- **Enrichment**: each enquiry is enriched into a structured decision — service
  line + a 4-dimension score with a rationale — not just a label
- **Integration points**: web-form input → hub → spoke deliverable; the spokes
  adapt to the client's existing systems (scheduling app, EHR, insurance portals)

---

<!-- 3 · Test 1 — Full Flow -->

# Test 1 · Full flow (automatic, no guardrail)

**Enquiry**: small dental practice, no-show revenue loss, wants reminders + prediction

| Step | Result |
|---|---|
| Classification | Process & Workflow Automation |
| Complexity | simple (1/8 — single scheduling-app integration, admin-only data) |
| Guardrail | phi=false → auto-handoff permitted |
| Logged | data/triage_log.jsonl, validator PASS |
| Handoff | automation-lead produced scoping note + 3 clarifying questions |

**Demonstrates**: the fully automatic loop, end to end.

---

<!-- 4 · Test 2 — Guardrail trip -->

# Test 2 · Guardrail trip (PHI → human review)

**Enquiry**: regional hospital network, prior-authorization re-keying from EHR

| Step | Result |
|---|---|
| Classification | Process & Workflow Automation |
| Complexity | complex (6/8 — multi-system integration, 450-bed org scale) |
| Guardrail | data_sensitivity=2 → **phi=true → requires_human_review=true** |
| Dispatch | **BLOCKED — no spoke, queued for human compliance sign-off** |
| Logged | validator PASS (guardrail constraint satisfied) |

**Demonstrates**: the system's only hard stop — PHI never auto-dispatches.

---

<!-- 5 · Test 3 — Hard block -->

# Test 3 · Hard block (backstop rejects a violating write)

**Attempt**: append a record with `phi_involved: true` but `requires_human_review: false`

- The `tools/post-execute` backstop re-reads the file and **blocks the write**:
  `[guardrail] BLOCKED: triage record … PHI-flagged enquiries must always require
  human review`
- Model cannot proceed until the record is corrected; validator then returns PASS

**Demonstrates**: enforcement in code, not just instruction — the model cannot
silently skip the guardrail.

---

<!-- 6 · Production Thinking -->

# Production thinking — what breaks first, what to monitor

| Question | Answer |
|---|---|
| **What breaks first?** | model scoring drift on edge cases (ambiguous enquiries); log write contention at batch volume |
| **What to monitor?** | triage_log.jsonl (append-only audit trail), guardrail block rate, per-class accuracy vs `expected_*` labels |
| **Fallback when the model is wrong?** | the deterministic backstop rejects violations; `needs_manual_triage` routes weak fits to a human; every decision is logged and replayable |
| **Scale trigger** | a real queue replaces direct dispatch once volume/multi-lead claiming demands it (PRD §7) |

---

<!-- 7 · Extension — Deploy to VM (beyond the core brief) -->

# Extension · Deployed to a cloud VM via CI/CD

*Beyond the core brief — an optional stretch showing the same capability
running in production; the assignment itself is fully covered by slides 1–6.*

```
git push main → GitHub Actions → build self-contained release → GCP VM
               → releases/<sha> → current → systemd → health check
               (rollback = symlink switch)
```

- **One DSH install, two profiles**: `web` (clean dev) vs `linkhealth` (the product)
- **The profile is the deployment unit**: same files run locally and on the VM
- Private access via SSH tunnel (no public app port); synthetic data only
- Front door: brand theme + capability launcher (Triage enabled; CDI Audit ready)

---

<!-- 8 · Summary -->

# Summary

- **Judgement, not boilerplate**: a deliberately small scope done deeply —
  classification + scoring + routing, with a guardrail designed as the core asset
- **The guardrail is the differentiator**: instruction *and* code enforcement,
  PHI as a hard stop, audit trail on every decision
- **Production-minded**: what breaks, what to monitor, fallback when the model errs
- **Beyond the brief**: the same capability runs as plugins on Claude Code and
  DeepSeek Harness, and deploys to a cloud VM through CI/CD

> AI assists · a human decides · everything is auditable.
