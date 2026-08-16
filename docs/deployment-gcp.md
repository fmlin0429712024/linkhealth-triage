# Deployment — LinkHealth VAS on GCP (CI/CD)

Goal: run the `linkhealth` profile (DSH + triage + GUI plugins) on a GCP VM via
**CI/CD** — push to `main` deploys. The release directory (profile + plugins) is
a **self-contained deploy unit**: the same files that run locally run on the VM,
and rollback is a symlink switch.

This is **stage 0 of the §5 roadmap**: internal engine, private access,
synthetic data only.

## How it works

```
GitHub push main
  → .github/workflows/deploy.yml (GitHub Actions)
      → build dist/profile/  (deploy template + triage + gui plugins + relative symlink)
      → tar → scp → VM:/opt/linkhealth/incoming/
      → ssh → deploy.sh: unpack to releases/<sha> → switch `current` → restart → health check
```

- **Immutable releases**: `/opt/linkhealth/releases/<sha>/` per deploy; `current`
  is a symlink. Rollback = point `current` at a previous release + restart.
- **Self-contained**: `cordis.patch.yml` uses **relative** paths
  (`./plugins/triage-dsh-plugin/lib/index.js`) and a relative node_modules
  symlink — the release folder is portable and identical everywhere.
- **Trigger**: push to `main` touching plugins/deploy/workflow, or manual
  `workflow_dispatch` from the Actions tab.

## Topology

```
GitHub Actions ──scp/ssh──► GCP VM (linkhealth-vm, us-central1-a)
                              systemd: linkhealth.service
                              /opt/linkhealth/
                                releases/<sha>/    immutable deploy units
                                current → releases/<sha>
                                dsh-home/profiles/linkhealth → current
                                scripts/{bootstrap,deploy}.sh
```

Access for humans: `gcloud compute ssh linkhealth-vm -- -L 3080:localhost:3080`
(SSH tunnel; no public port for the app).

## One-time setup (done)

- [x] Billing linked (`linkhealth-care-2024` → LHS account)
- [x] VM `linkhealth-vm` (e2-standard-2, 20GB, Debian 12), static IP `35.188.149.18`
- [x] Firewall `allow-ssh-linkhealth` (tcp:22, tag `linkhealth-vm`)
- [x] OS Login disabled so `authorized_keys` works; deploy key pair generated
- [x] Bootstrap: Node 22 + dsh + release layout + systemd unit
  (`deploy/scripts/bootstrap-vm.sh`, idempotent)

## Required GitHub repository secrets

| Secret | Value |
|---|---|
| `DEPLOY_HOST` | `35.188.149.18` |
| `DEPLOY_USER` | `fmlin` |
| `DEPLOY_SSH_KEY` | private half of the deploy keypair (ed25519) |
| `DEEPSEEK_API_KEY` | the DeepSeek key used by DSH on the VM |

## Deploying

```sh
git push origin main                    # auto-deploys when relevant files change
# or manual:
# GitHub → Actions → Deploy LinkHealth VAS → Run workflow
```

Verify: `ssh …/systemctl status linkhealth` → active; `curl localhost:3080` on
the VM → the LinkHealth branded UI; run one triage case — the guardrail backstop
runs on the VM too.

Rollback:

```sh
ssh fmlin@35.188.149.18
sudo ln -sfn /opt/linkhealth/releases/<previous-sha> /opt/linkhealth/current
sudo systemctl restart linkhealth
```

## Cost & hygiene

- e2-standard-2 in us-central1 ≈ $49/mo + static IP ≈ $3/mo. Stop the VM when
  unused: `gcloud compute instances stop linkhealth-vm`.
- DeepSeek API: set a monthly budget + alert in the DeepSeek console — the
  deployment never controls spend, the account does.
- Synthetic data only. Before ANY real client/PHI data: region choice,
  encryption, audit logging, customer data-processing agreement (README §5).

## Future (community asset)

The deploy unit + workflow are intentionally repo-relative and secret-driven —
anyone can fork and point the secrets at their own VM. That is the "open-source
asset for community dev" shape: clone → configure 4 secrets → deploy.
