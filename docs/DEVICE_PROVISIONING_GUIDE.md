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

From `ha-fleet-pilot-sites`:

```bash
# check that the manifest, bundles, and overlays are all valid
../ha-fleet-tooling/.venv/Scripts/ha-fleet validate \
    --site-path ./sites/site_001 --strict

# render the composed bundles/overlays into concrete YAML for inspection
../ha-fleet-tooling/.venv/Scripts/ha-fleet render \
    --site-path ./sites/site_001 --output ./build/site_001

# (optional) create the backup tarball for a dry‑run or to preview what will
# be applied on the device; not required for validation
../ha-fleet-tooling/.venv/Scripts/ha-fleet bundle-to-backup \
    --site-path ./sites/site_001 --output ./build/site_001_backup.tar.gz
```

Expected local results:
- `validate` exits 0 (or prints errors/warnings when things are wrong)
- `render` populates `./build/site_001` with all generated YAML files
- The backup command may be run if you want to inspect the archive, but you
  can skip it during early editing cycles

### Previewing the rendered configuration

If you want to **see what the configuration actually looks like in Home
Assistant (dashboards, entities, automations, etc.)** without touching an
edge device, run a local HA instance and point it at the build output.

A simple way to do this is with Docker:

```bash
# from inside ha-fleet-pilot-sites root
build_dir=./build/site_001
mkdir -p "$build_dir"
# (re-run render when you make changes)

# spin up a temporary HAOS container using the rendered config
docker run --rm -it \
    -v "$PWD/$build_dir:/config" \
    -p 8123:8123 \
    ghcr.io/home-assistant/operating-system-aarch64:latest
```

Once the container starts you can open `http://localhost:8123` in your browser
and the UI will reflect the rendered YAML. This is much faster than installing
a new device and creates an iterative feedback loop for dashboards or other
UI elements.

*You could also use a vanilla Home Assistant Core container* (not HAOS) by
testing only the relevant parts of the config (e.g. copying automations,
lovelace resources, etc.), but the OS-based image avoids compatibility issues.

#### Tips for dashboard iteration

1. Run `ha-fleet render` after each change, the contents of the container
   will update on next restart or when you manually reload config via the HA
   UI.
2. Use the **Lovelace raw config editor** (`Settings → Dashboards → Edit`) to
   preview modifications without re-deploying anything; the underlying YAML
   in `/config` reflects what the tooling generated.
3. You can mount only the packages subdirectory or individual files if you
   want to mix rendered and hand‑crafted config.

Tip: add a short `pytest` test in `ha-fleet-pilot-sites/tests/` that runs
`ha-fleet validate` against your site directory; this lets you catch
regressions before pushing changes.

The subsequent sections describe uploading the artifacts or running a restore
on an edge device once you’re satisfied with your configuration.

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
