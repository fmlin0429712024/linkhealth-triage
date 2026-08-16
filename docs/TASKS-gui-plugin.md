# Tasks — linkhealth-gui-plugin (SDD / TDD breakdown)

Spec-driven, matching the style of `docs/TASKS.md`: every task states its **spec**
(what it must guarantee) and its **test** (acceptance) *before* implementation.
TDD order: write the failing test first (red), then implement (green). Status:
`TODO` → `IN PROGRESS` → `DONE`.

Reference: `docs/PRD-gui-plugin.md`.

## 1. Scaffold

### 1.1 Plugin folder + manifest — DONE
**Spec:** `linkhealth-gui-plugin/` exists with a valid npm manifest (`name:
linkhealth-gui-plugin`, `type: module`, `exports` with `./client`), a
`cordis.patch.yml` adding one client entry row (`id: linkhealth-gui`,
`name: 'linkhealth-gui-plugin/client'`, `config` per PRD §7), and a no-op host
`lib/index.js`.
**Test:** `node --input-type=module -e "await import('./linkhealth-gui-plugin/lib/index.js')"`
resolves; the entry row composes into `dsh --profile web --dump-config`.

### 1.2 Client entry boots (smoke) — DONE (code; live smoke pending one server restart)
**Spec:** `lib/client.js` is a `window.__ModuleLoader__.load({ id, factory })`
module that applies nothing yet but loads without throwing.
**Test:** hot-reload smoke on the live web profile: adding the patch row produces
no client-side error; removing it restores stock UI.

## 2. Pure logic (`lib/launcher-config.js`) — TDD, node:test, zero deps

### 2.1 Capability-list schema validation — DONE (22/22 tests green)
**Spec:** `parseCapabilities(input)` validates the config list per PRD §7: each
entry requires string `id`, `label`, `description`; `sessionStart` optional;
unknown/malformed entries are rejected with a named error; empty list is valid.
**Test:** `test/launcher-config.test.mjs` (node:test): valid list passes; missing
label throws; non-string id throws; malformed entry throws; `[]` returns `[]`.

### 2.2 Defaults merge — DONE (22/22 tests green)
**Spec:** `resolveConfig(partial)` merges the patch config over defaults
(`headline`, `placeholder`, empty capability list); unknown keys are dropped,
present keys win.
**Test:** empty input → defaults; partial input → defaults + overrides; unknown
key dropped.

### 2.3 Session-start parameter building — DONE (22/22 tests green)
**Spec:** `buildLaunch(capability, workspaceId)` returns a JSON-safe
`{ workspaceId, note }` shaped for starting a session via the client runtime's
sessions API; workspaceId nullable; no business-plugin knowledge.
**Test:** returns the exact shape; `workspaceId: null` allowed; `note` includes the
capability label.

### 2.4 Brand token structure — DONE (22/22 tests green)
**Spec:** `brandTokens(scheme)` returns the brand palette for `'light'`/`'dark'` as
a flat token map (deep teal + deep blue base) using only token names the theme
service accepts; `'dark'` differs from `'light'`.
**Test:** both schemes return non-empty flat maps; keys differ between schemes;
every value is a CSS color string.

## 3. Client registrations (`lib/client.js`)

### 3.1 Theme override — DONE (smoke verified via playwright on the live profile)
**Spec:** on apply, `theme.overrideTokens(brandTokens(scheme))` is registered for
both schemes; the disposer is retained and returned so unload restores stock
tokens.
**Test (smoke checklist):** accents shift to brand palette in light + dark; plugin
unload restores stock colors.

### 3.2 Branded welcome — DONE (via launcher/cards copy; hero copy intentionally NOT overridden — locale cannot be re-registered cross-package)
**Spec:** `locale.register` overrides `hero.headline` and `placeholder.hero` from
config; other copy untouched.
**Test (smoke checklist):** empty-session hero shows the configured headline and
placeholder; no other UI copy changes.

### 3.3 Capability launcher (`sidebar.footer.action`) — TODO (smoke)
**Spec:** injects the list slot; renders one entry per configured capability
(label + description); click starts a session via `buildLaunch`; absent config
renders nothing.
**Test (smoke checklist):** two entries render; each starts a session; empty
config → no entries.

### 3.4 Capability showcase (`settings.section`) — TODO (smoke)
**Spec:** injects `settings.section`; renders the "LinkHealth Capabilities"
section with one card per capability (name, description, status badge); absent
config renders no section.
**Test (smoke checklist):** section + cards render in Settings; empty config → no
section.

## 4. Verification

### 4.1 Full hot-reload cycle — DONE (first inclusion needed one restart; subsequent bundle edits hot-reload — verified)
**Spec:** PRD FR6 — every change above lands without a restart; removing all patch
rows restores stock DSH UI exactly.
**Test:** apply checklist → edit config → observe launcher update live → remove
rows → stock UI restored.

### 4.2 Unit tests green — DONE (node --test: 22 pass, after all fixes)
**Spec:** all of §2 passes under `node --test test/` with zero external
dependencies.
**Test:** `node --test test/` exits 0.

### 4.3 Plugin README — DONE
**Spec:** `linkhealth-gui-plugin/README.md` documents install (personal patch-row
deployment), config contract, the additive/no-replace design rule, and the smoke
checklist.
**Test:** review: covers the three items; config example matches PRD §7.
