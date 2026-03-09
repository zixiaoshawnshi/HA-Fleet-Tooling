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

# same, but with an editable storage dashboard ("Fleet Draft") for quick UI edits
../ha-fleet-tooling/.venv/Scripts/ha-fleet dev-site \
    --site-path ./sites/site_001 \
    --action up \
    --port 8123 \
    --enable-draft-dashboard

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

When `--enable-draft-dashboard` is set, the generated `configuration.yaml`
includes a sidebar dashboard named **Fleet Draft** in storage mode. You can use
that dashboard in HA's graphical editor for cosmetic experimentation, then copy
the final YAML into `sites/<site_id>/dashboards/*.yaml`.

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

## 7. Canary Restore Test (Manual)

1. Upload backup artifact to the edge device (method of choice).
2. Restore in HA UI (Settings -> System -> Backups -> Restore) or API flow.
3. Wait for HA restart and stabilization.
4. Verify:
   - Required entities exist
   - Core automations loaded
   - Integrations healthy (Zigbee/MQTT/Calendar as applicable)

## 8. Rollback Drill

1. Confirm previous backup is retained.
2. Trigger restore to previous known-good backup.
3. Re-validate health checks post-rollback.

Pilot requirement:
- At least one successful rollback drill before scaling beyond canary.

## 9. Post-Provisioning Checklist

- [ ] Device reachable locally and over Tailscale
- [ ] Long-lived token created and stored securely
- [ ] Required secrets provisioned on edge
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



## 11. Next Step After Provisioning

Move from manual restore to scripted edge preflight/deploy (Phase 3):
- Edge preflight checks
- Artifact verification (SHA256)
- API-driven restore
- Health check + rollback automation
