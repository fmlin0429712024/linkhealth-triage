# PRD — LinkHealth Agents GUI Plugin (linkhealth-gui-plugin)

Spec for the **front-door plugin**: brands the DeepSeek Harness (DSH) web surface as
the LinkHealth Agents workbench and exposes the product line's capability plugins
(Triage, CDI Audit) as first-class entries. Companion to `docs/PRD.md` (the triage
system itself) and to `dsh-cdi-plugin` (the audit system). This plugin is the
presentation shell only — it adds no business capability and touches no business
plugin.

## 1. Problem

DSH's web UI ships as a generic DeepSeek-branded agent workbench. LinkHealth is a
multi-plugin product line (Triage + CDI Audit, more later) running on one DSH
instance. Without a front door, the workbench looks generic, and a user has no
first-class way to see or launch the company's capabilities — they must know the
skills by name.

## 2. Goal

A standalone **client-side** DSH plugin (`linkhealth-gui-plugin/`) that turns the web
surface into the LinkHealth Agents front door:

- **Brand theme** — healthcare-professional color scheme applied globally.
- **Branded welcome** — the empty-session hero reads as LinkHealth, not DeepSeek.
- **Capability launcher** — first-class entries for **Triage** and **CDI Audit**
  (config-driven, so a third capability is a config change, not a code change).
- **Capability showcase** — a brand settings section presenting the product line.

All of it **additive** (no default component replaced), **hot-reloadable**, and
**fully reversible** (removing the patch rows restores the stock UI).

## 3. Explicit non-goals (scope boundary)

- **No graphical logo.** The owner deliberately provides none; the front door is
  color, copy, and capability cards — not an image mark. (DSH's built-in wordmark
  is component-hardcoded and not replaceable without risk.)
- **No replacement of default components.** `root`, `conversation`, `sidebar`,
  `details` and their primary occupants stay untouched; only additive injection
  points are used (`sidebar.footer.action`, `settings.section`, theme tokens,
  locale copy).
- **Not a client-facing product.** This is the internal workbench front door, not
  the customer portal (that belongs to the §5 VAS vision in the root README).
- **No authentication/authorization.** DSH does not own user identity; the plugin
  does not add any.
- **No changes to business plugins.** `triage-dsh-plugin` and `dsh-cdi-plugin`
  stay untouched; the GUI plugin only *perceives* their existence through its own
  config.
- **No persistent data.** Everything is configuration and presentation.

## 4. Users

- **LinkHealth team** — the operator(s) running triage and audit work in DSH every
  day. They need to recognize the workbench instantly as LinkHealth's, and to
  launch the right capability without hunting.

## 5. End-to-end flow

1. Operator opens the DSH web UI (local or GCP VM).
2. The surface renders in the LinkHealth brand theme; the empty-session welcome
   reads as LinkHealth Agents.
3. In the sidebar footer the operator sees the two capability entries:
   **Triage** and **CDI Audit**.
4. Clicking an entry starts a session for that capability (preset/composition
   configured per entry).
5. In Settings → the plugin's brand section, the operator sees the product line as
   two capability cards (name, one-line positioning, status).
6. Removing the plugin's patch rows restores the stock DSH UI exactly.

## 6. Functional requirements

### FR1 — Brand theme (client, `theme.overrideTokens`)
The plugin applies a brand palette — deep teal + deep blue base, distinct
light/dark token sets — over the active theme. All override layers are registered
through the theme service's override mechanism and torn down on unload.

**Acceptance:** the primary interactive/business accents change to the brand
palette in both color schemes; unload restores stock tokens.

### FR2 — Branded welcome (client, launcher/cards copy)
The branded welcome is carried by the plugin's own components — the launcher
entries and the capability showcase use LinkHealth copy (headline "LinkHealth
Agents"). The default hero copy is NOT overridden: DSH locale dictionaries
cannot be re-registered cross-package (same namespace + locale key throws), so
the stock hero stays untouched by design.

**Acceptance:** LinkHealth copy appears in the launcher and showcase; no other
UI copy is changed; no locale re-registration is attempted.

### FR3 — Capability launcher (client, `sidebar.footer.action`)
Two entries — **Triage** and **CDI Audit** — render in the sidebar footer. Each
entry is **config-driven**: the patch config declares the list
(`id`, `label`, `description`, `sessionStart`), so adding a third capability is a
config edit.

**Acceptance:** both entries render; clicking each starts a session targeting the
configured capability; entries disappear on unload.

### FR4 — Capability showcase (client, `settings.section`)
A "LinkHealth Capabilities" settings section renders one card per configured
capability (name, one-line positioning, status badge). It is additive beside the
existing settings sections.

**Acceptance:** the section and cards render in Settings; absent config renders no
section.

### FR5 — Configuration lives in the bundle, zero business coupling
The plugin's code contains **no reference** to triage/cdi internals — no imports
from `triage-dsh-plugin` or `dsh-cdi-plugin`, no knowledge of their skills/tools.
Capability entries come from `BUILTIN_CONFIG` in `lib/client.js` (one place to
edit): the client graph passes only `id`/`url`/`inject`, so a patch entry's
`config` never reaches the browser. If a config channel arrives later,
`resolveConfig` merges it over the built-ins.

**Acceptance:** code review shows zero imports of business plugins; editing the
capability list is a one-place change in the bundle.

### FR6 — Reversible and hot-reloadable
All registrations return disposers; the plugin is a pure client entry (no host
code), so it loads/unloads through the profile's hot-reloaded patch layer.

**Acceptance:** editing the patch rows updates the UI without a restart; removing
them restores stock UI without a restart.

## 7. Architecture

```
linkhealth-gui-plugin/
├── package.json          npm manifest: name, type: module, exports: { ".": host (noop), "./client": client entry }
├── cordis.patch.yml      adds ONE client entry row (id: linkhealth-gui, name: '<pkg>/client')
├── lib/
│   ├── launcher-config.js  pure logic: capability-list schema, defaults, session-start param building, brand tokens
│   └── client.js           window.__ModuleLoader__.load({ id, factory }) — theme override, locale, slots.inject for
│                           sidebar.footer.action + settings.section; imports launcher-config for data
└── test/
    └── launcher-config.test.mjs  node:test unit tests for the pure logic
```

- **Client only.** No host (`lib/index.js`) behavior beyond a no-op export so the
  module resolves on both planes; all effect lives in the browser half.
- **Dependencies:** peer/known packages only — `@deepseek-ai/dsh-client-runtime/client`,
  `@deepseek-ai/dsh-client-ui-primitives`, `react`. No business-plugin imports.
- **Config contract** (patch `config` of the client row):
  ```yaml
  config:
    headline: 'LinkHealth Agents'
    placeholder: 'Triage an enquiry, audit documentation — or describe what you need'
    capabilities:
      - id: triage
        label: Triage
        description: 'Classify, score, and route inbound business enquiries.'
        sessionStart: { workspace: null }
      - id: cdi
        label: CDI Audit
        description: 'Governed clinical-documentation audit against SOP rules.'
        sessionStart: { workspace: null }
  ```

## 8. Data

No persistent data. The only "data" is the declarative config above (owned by the
patch layer) and in-memory UI state.

## 9. Observability

- Client console diagnostics on apply/teardown and on launch actions.
- Launch failures surface in the session UI (existing DSH error path), not silently.
- No business data passes through this plugin — it is presentation only.

## 10. Testing strategy (TDD)

| Layer | What | How |
|---|---|---|
| Pure logic | `launcher-config.js`: schema validation, defaults merge, session-start param building, brand-token structure | **node:test** unit tests (zero deps, `node --test`) — written before the logic (red → green) |
| Registration | `client.js` structure: correct inject points, disposers returned, config threading | Static review + hot-reload smoke |
| UI | Theme, hero copy, launcher entries, settings cards render correctly | **Manual smoke checklist** against the live web profile (hot-reload) |
| Reversibility | Removing patch rows restores stock UI | Manual checklist |

**Honest boundary:** the plugin is mostly presentation; the *automatically tested*
part is the config/data logic. UI rendering is verified by the manual smoke
checklist below, because DSH client components render in the browser, not in a
node test runner.

## 11. Out of scope (this round)

Graphical logo; default-component replacement; customer portal; authentication;
multi-tenant; i18n beyond the shipped copy; mobile layout tuning; a third
capability (config-ready but not shipped).

## 12. Relationship to other docs

- `docs/PRD.md` — the triage business system (this plugin presents it).
- `dsh-cdi-plugin` — the audit capability (presented, not imported).
- Root `README.md` §4–5 — the deployment PoC and the VAS vision this front door
  serves.
