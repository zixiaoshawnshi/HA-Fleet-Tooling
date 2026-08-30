# HA Device Provisioning Guide (Pilot)

This guide covers initial provisioning of a new HAOS edge device for the HA Fleet pilot.

## Scope

- Hardware prep and HAOS install
- First-boot hardening
- Tailscale setup
- Site config and secrets provisioning
- First canary deployment test
- Rollback validation

## Prerequisites

- Mini PC with HAOS bootable USB ready
- Access to:
  - `ha-fleet-tooling` repo (public tooling)
  - `ha-fleet-pilot-sites` repo (private site config)
- Site assigned (for first rollout, use `site_001`)
- Stable local network with DHCP

## 1. Install HAOS On Device

1. Boot mini PC from HAOS USB installer.
2. Install HAOS to internal SSD.
3. Reboot and wait for initialization (can take several minutes).
4. Confirm HA is reachable:
   - `http://homeassistant.local:8123`, or
   - `http://<device-ip>:8123`

Expected result:
- Home Assistant onboarding page appears.

## 2. Complete First-Boot Setup

1. Create local admin account.
2. Set location, timezone, and units.
3. Apply pending HA updates before enabling fleet automation.

Recommended:
- Keep device on UPS power if available.
- Reserve a DHCP lease or static IP in router.

> **Weather integration:** Onboarding automatically starts a background setup
> for the Met.no weather integration (creating `weather.forecast_home`) right
> after the location step, using the location set in step 2. This call fails
> silently if the device has no outbound network access at that moment, so it
> is **not guaranteed** — confirm `weather.forecast_home` exists once
> onboarding completes (Developer Tools -> States, or check the weather card
> on the dashboard). If missing, add it manually: **Settings -> Devices &
> Services -> Add Integration -> Met.no -> Submit** (no configuration
> required, it uses the device's set location).

> **Calendar integration (site_002_Kevin only):** Kevin's dashboard shows a
> pictogram calendar backed by HA's built-in Local Calendar integration — one
> calendar per pictogram category, no Google account or API key needed. Add
> each of these via **Settings -> Devices & Services -> Add Integration ->
> Local Calendar -> Submit**, using these exact names so the generated
> entity_ids match what the dashboard expects:
>
> | Calendar Name (type exactly) | Resulting entity_id |
> |---|---|
> | Kevin Appointments | `calendar.kevin_appointments` |
> | Kevin School | `calendar.kevin_school` |
> | Kevin Family Fun | `calendar.kevin_family_fun` |
> | Kevin Home Reminders | `calendar.kevin_home_reminders` |
>
> Parents add events directly through HA's native **Calendar** sidebar view,
> picking whichever calendar matches the event's category — the pictogram is
> chosen automatically based on which calendar the event was added to.

## 3. Baseline Hardening

1. Enable backups in HA settings.
2. Create an initial manual backup in HA UI (pre-fleet baseline).
3. Create a long-lived access token:
   - Profile -> Security -> Long-Lived Access Tokens
4. Store token securely (password manager / secret store).

## 4. Install And Configure Tailscale Add-on

1. Install Tailscale add-on in HAOS.
2. Join tailnet with your operator account.
3. Confirm connectivity from operator machine:
   - `tailscale status`
   - `ping <tailscale-hostname>`

Expected result:
- Device is reachable over tailnet.

> **Note:** Tailscale caches the hostname at startup. If you change the system
> hostname (via SSH or the HA UI) the add-on will continue advertising the old
> name until the Tailscale daemon is restarted or the device is rejoined. See
> the troubleshooting section below for force‑refresh instructions.

## 5. Provision Site Secrets On Edge

Use the site contract as source of truth:
- `ha-fleet-pilot-sites/sites/site_001/secrets_contract.yaml`

Create/update `/config/secrets.yaml` on edge with required keys, for example:

```yaml
notify_mobile_target: "my_phone"
google_maps_api_key: "REDACTED"
zigbee_backup_password: "OPTIONAL_REDACTED"
```

Important:
- Do not commit live secrets to git.
- Keep only key contracts in repo, never values.

### Configure Terminal & SSH Add-on (for `ha-fleet deploy`)

`ha-fleet deploy` pushes rendered config to the device over SSH, then applies
it via Home Assistant's own API. This requires the official **Terminal & SSH**
add-on (`hassio-addons/app-ssh`), not Tailscale's own SSH feature —
**Tailscale's SSH-proxy feature (`tailscale up --ssh`) is server-side blocked
on Home Assistant OS.** Don't spend time trying to get `tailscale up --ssh`
working; it's a known Tailscale limitation on this platform, not a
misconfiguration. Plain SSH routed over the already-configured Tailscale
private network works fine — only Tailscale's own identity-proxied SSH
feature is blocked.

1. Install the **Terminal & SSH** add-on from the add-on store.
2. In its configuration, enable **SFTP** and set `username: root` (required
   by this add-on for SFTP/SCP access — it will not work as a different user).
3. Add the operator's SSH public key under `authorized_keys`. Generate a
   dedicated deploy key if you don't already have one:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/id_ha_fleet_deploy -C "ha-fleet-deploy"
   ```
4. Start the add-on, then verify manual SSH access over the tailnet works
   *before* ever running `ha-fleet deploy`:
   ```bash
   ssh -i ~/.ssh/id_ha_fleet_deploy root@<tailnet-host-or-ip>
   ```
5. Set up the deploy target config for this site (operator machine, in
   `ha-fleet-pilot-sites`):
   ```bash
   cp sites/site_001/operator/deploy_target.local.example.yaml \
      sites/site_001/operator/deploy_target.local.yaml
   # then edit host / ssh_key_path to match steps 3-4 above
   ```

## 6. Validate Site Config Locally (Operator Machine)

Before touching any edge device you can fully test your configuration on your
operator workstation. The CLI commands perform exactly the same schema
validation and rendering that will run on the device, so you do **not** need to
create a backup every time – that step is only required when you're ready to
upload an artifact to an edge.

### Python Environment (Operator)

Use Python `3.10+` for tooling. If Anaconda owns your default `python`, call an
explicit version via `py`:

```bash
# from ha-fleet-tooling
py -3.14 -m venv .venv
./.venv/Scripts/python -m pip install -e .
```

### Validate and Render

From `ha-fleet-pilot-sites`:

```bash
# check that the manifest, bundles, and overlays are all valid
../ha-fleet-tooling/.venv/Scripts/ha-fleet validate \
    --site-path ./sites/site_001 --strict

# render composed bundles, overlays, and dashboards into concrete YAML
../ha-fleet-tooling/.venv/Scripts/ha-fleet render \
    --site-path ./sites/site_001 --output ./build/site_001

# (optional) create the backup tarball for a dry‑run or to preview what will
# be applied on the device; not required for validation
../ha-fleet-tooling/.venv/Scripts/ha-fleet bundle-to-backup \
    --site-path ./sites/site_001 --output ./build/site_001_backup.tar.gz
```

Expected local results:
- `validate` exits 0 (or prints errors/warnings when things are wrong)
- `render` populates `./build/site_001` with generated YAML, including
  `./build/site_001/dashboards/*.yaml`
- The backup command may be run if you want to inspect the archive, but you
  can skip it during early editing cycles

### Create a New Site Scaffold

When onboarding a new home, scaffold a site folder first:

```bash
# PowerShell
../ha-fleet-tooling/.venv/Scripts/ha-fleet new-site \
    --sites-root ./sites \
    --site-id site_003 \
    --display-name "Pilot Site 003"

# bash
../ha-fleet-tooling/.venv/Scripts/ha-fleet new-site \
    --sites-root ./sites \
    --site-id site_003 \
    --display-name "Pilot Site 003"
```

This creates:
- `sites/<site_id>/site_manifest.yaml`
- `sites/<site_id>/secrets_contract.yaml`
- `sites/<site_id>/bundles/`
- `sites/<site_id>/dashboards/`
- `sites/<site_id>/overlays/`
- `sites/<site_id>/operator/`
- `sites/<site_id>/discovery/`

### Operator Mock Secrets (Local Only)

To imitate required keys locally, copy the operator example into the rendered
build directory:

```bash
cp ./sites/site_001/operator/secrets.local.example.yaml ./build/site_001/secrets.yaml
```

Notes:
- This file is for local operator testing only.
- Never copy production secrets into git.
- Keep edge `/config/secrets.yaml` managed separately on each device.

### Dashboard Source of Truth Layout

For fleet-managed YAML dashboards, use:

- `sites/site_001/dashboards/*.yaml` for base dashboard YAML
- `sites/site_001/overlays/dashboards/*.yaml` for site overlay overrides

Renderer behavior:
- Files are emitted to `build/site_001/dashboards/*.yaml`
- Overlay files override base dashboard files with the same relative path
- `build/site_001/configuration.yaml` is auto-generated with a
  `lovelace.dashboards` block, so dashboards appear in HA without
  manual config edits

### Previewing Rendered Config in Home Assistant

If you want to **see what the configuration actually looks like in Home
Assistant (dashboards, entities, automations, etc.)** without touching an
edge device, run a local HA instance and point it at the build output.

A simple way is the tooling CLI `dev-site` command:

```bash
# from inside ha-fleet-pilot-sites root
../ha-fleet-tooling/.venv/Scripts/ha-fleet dev-site \
    --site-path ./sites/site_001 \
    --action up \
    --port 8123

# re-render only (no container restart)
../ha-fleet-tooling/.venv/Scripts/ha-fleet dev-site \
    --site-path ./sites/site_001 \
    --action render

# restart container after changes
../ha-fleet-tooling/.venv/Scripts/ha-fleet dev-site \
    --site-path ./sites/site_001 \
    --action restart

# follow container logs
../ha-fleet-tooling/.venv/Scripts/ha-fleet dev-site \
    --site-path ./sites/site_001 \
    --action logs

# stop and remove the local dev container
../ha-fleet-tooling/.venv/Scripts/ha-fleet dev-site \
    --site-path ./sites/site_001 \
    --action down
```

Once the container starts you can open `http://localhost:8123` in your browser
and the UI will reflect the rendered YAML. This is much faster than installing
a new device and creates an iterative feedback loop for dashboards or other
UI elements.

This operator workflow is also useful for pre-deployment mockups: you can show
what dashboards and automations will look like on a laptop before arriving
onsite, then deploy the same site repo changes to edge once approved.

#### Tips for dashboard iteration

1. Run `ha-fleet render` after each change, the contents of the container
   will update on next restart or when you manually reload config via the HA
   UI.
2. Use the **Lovelace raw config editor** (`Settings → Dashboards → Edit`) to
   inspect and compare generated YAML with what is loaded in the UI.
3. You can mount only the packages subdirectory or individual files if you
   want to mix rendered and hand‑crafted config.

Tip: add a short `pytest` test in `ha-fleet-pilot-sites/tests/` that runs
`ha-fleet validate` against your site directory; this lets you catch
regressions before pushing changes.

The subsequent sections describe uploading the artifacts or running a restore
on an edge device once you’re satisfied with your configuration.

### Optional: Ingest Edge Discovery From Backup (Operator Stop-Gap)

If edge has newly onboarded hardware and you want operator-side visibility
without running scripts on the device, ingest a backup artifact:

```bash
# 1) produce or fetch a backup from the edge device into local filesystem
#    (example path shown below)

# 2) ingest discovery data from the backup
../ha-fleet-tooling/.venv/Scripts/ha-fleet ingest-backup \
    --site-path ./sites/site_001 \
    --backup ./build/site_001_backup_from_edge.tar.gz \
    --output ./sites/site_001/discovery/latest.yaml
```

What this does:
- Reads HA registry files from the backup archive:
  - `.storage/core.device_registry`
  - `.storage/core.entity_registry`
  - `.storage/core.config_entries`
- Writes a sanitized snapshot for review at:
  - `sites/site_001/discovery/latest.yaml`

Suggested workflow:
1. Edge operator onboards hardware in HA UI (edge is hardware source of truth).
2. Edge produces backup.
3. Operator ingests backup and reviews `discovery/latest.yaml`.
4. Operator updates fleet config (`site_manifest`, bundles, dashboards) via PR.
5. Deploy approved config back to edge.

### Optional: Ingest Discovery From Local Operator HA Config

If you are iterating in a local operator HA container and want to pull detected
devices/entities into the site repo without generating a backup, ingest directly
from the local config directory:

```bash
../ha-fleet-tooling/.venv/Scripts/ha-fleet ingest-config-dir \
    --site-path ./sites/site_001 \
    --config-dir ./build/site_001 \
    --output ./sites/site_001/discovery/latest.yaml
```

This reads:
- `.storage/core.device_registry`
- `.storage/core.entity_registry`
- `.storage/core.config_entries`

Use this as a rapid local loop. For production edge truth, continue ingesting
from edge-generated backups.

### Deploy To Edge

Once the Terminal & SSH add-on and `deploy_target.local.yaml` are set up
(§5), pushing a config update is one command from `ha-fleet-pilot-sites`:

```bash
export HA_FLEET_DEPLOY_TOKEN="<long-lived access token>"

../ha-fleet-tooling/.venv/Scripts/ha-fleet deploy push \
    --site-path ./sites/site_001
```

This renders the site, asks the device to generate a real Home Assistant
backup of its current state (a safety net — never a hand-built archive, see
§7), pushes the rendered config over SCP, verifies the files landed intact by
checksum, restarts Home Assistant, and polls the site's `required_entities`
for up to 90s before reporting success or failure. On failure, it does **not**
auto-rollback — it prints which entities are unhealthy and tells you to run
`deploy rollback`.

```bash
# Re-check health standalone (e.g. after a manual fix on the device)
ha-fleet deploy verify --site-path ./sites/site_001

# Fast rollback: re-push the previous successful build + restart (no state loss)
ha-fleet deploy rollback --site-path ./sites/site_001

# Slow rollback: restore the full pre-deploy backup (reverts ALL state changes
# since that snapshot, not just config — confirms before proceeding)
ha-fleet deploy rollback --site-path ./sites/site_001 --mode snapshot
```

Prefer the `HA_FLEET_DEPLOY_TOKEN` env var over `--token-file`, and never pass
a token as a bare CLI flag (it would land in shell history). A Home Assistant
long-lived access token has no scope or expiry — treat leakage as equivalent
to full admin compromise of that device.

## 7. Canary Restore Test

> **Important:** the archive produced by `ha-fleet bundle-to-backup` is **not**
> a real, restorable Home Assistant backup. It uses a flat tar.gz layout
> (`configuration.yaml`, `automations.yaml`, etc. at the root) intended only
> for local inspection and feeding `ingest-backup`/`ingest-config-dir`. Real HA
> backups are a different, specific format (an outer tar with `backup.json` +
> a nested, `securetar`-built `homeassistant.tar.gz`). **Never upload a
> `bundle-to-backup` artifact via the HA UI or `backup/restore` API and expect
> it to restore** — it won't. `bundle-to-backup`'s actual purpose (feeding
> discovery ingestion) is unaffected by this; just don't use it for restore.

The actual canary test is running a real deploy against the freshly
provisioned device:

1. Complete §5's Terminal & SSH setup and `deploy_target.local.yaml` first.
2. From the operator machine, run `ha-fleet deploy push --site-path
   ./sites/site_001` (see §6 "Deploy To Edge") against the canary device.
3. Confirm the command's own automated health check passes (it polls
   `required_entities` for up to 90s and reports failures explicitly if any
   don't come back healthy).
4. Additionally spot-check in the HA UI:
   - Required entities exist and have sensible states
   - Core automations loaded
   - Integrations healthy (Zigbee/MQTT/Calendar as applicable)

## 8. Rollback Drill

Using the canary deploy from §7:

1. Run `ha-fleet deploy rollback --site-path ./sites/site_001` (default
   `--mode config`: re-pushes the previous build and restarts — fast, no
   state loss). Confirm health checks pass post-rollback.
2. Also run the heavier path once: `ha-fleet deploy rollback --site-path
   ./sites/site_001 --mode snapshot`. This restores the full pre-deploy
   backup captured by `deploy push`'s safety-snapshot step, reverting **all**
   state changes since that snapshot (not just config files) — confirm you
   understand this tradeoff before relying on it during a real incident.

Pilot requirement:
- At least one successful rollback drill of **each** mode before scaling
  beyond canary.

## 9. Post-Provisioning Checklist

- [ ] Device reachable locally and over Tailscale
- [ ] Long-lived token created and stored securely
- [ ] Required secrets provisioned on edge
- [ ] `weather.forecast_home` entity exists (Met.no onboarding setup can fail silently)
- [ ] (site_002_Kevin only) All 4 `calendar.kevin_*` Local Calendar entities exist
- [ ] `site_001` validate/render/backup completed
- [ ] Canary restore succeeded
- [ ] Rollback drill succeeded
- [ ] Ops notes captured in runbook

## 10. Common Failure Modes

- Missing secrets:
  - Symptom: automations fail or integration setup errors
  - Fix: align `/config/secrets.yaml` with site contract
- Network-only dependency failures:
  - Symptom: APIs/integrations unavailable
  - Fix: verify outbound DNS/network and API credentials
- Add-on not running:
  - Symptom: entity load failures
  - Fix: check add-on logs and restart add-on
- Tailscale still showing old hostname after renaming:
  - Symptom: `tailscale status` continues to list the previous name even
    after system hostname change and reboot.
  - Fix: restart or reconfigure the Tailscale daemon. E.g.:  
    ```bash
    # via SSH on HAOS
    tailscale down
    tailscale up --hostname "new-name" --force-reauth
    # or simply restart the add-on from the Supervisor UI
    ```
    A full reboot also re-joins with the updated hostname.



## 11. Remaining Future Work

The scripted edge preflight/deploy flow described in §6-8 (`ha-fleet deploy
push/verify/rollback`) covers preflight render, checksum verification,
API-driven restart, and health-check + rollback automation. Remaining
follow-ups, not yet built:
- A faster `--reload-only` apply path for automation/script/helper-only
  changes that don't need a full restart (today `deploy push` always does a
  full restart, which is simple and safe but slower than necessary for small
  changes).
- Fleet-wide orchestration (deploying to N devices at once, staged rollout)
  — today's tooling deploys to one device per invocation.
- A secrets-manager-backed alternative to `HA_FLEET_DEPLOY_TOKEN`/
  `--token-file` if the number of operators/devices grows past what
  per-operator local config comfortably covers.
