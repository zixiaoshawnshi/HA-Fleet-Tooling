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

From `ha-fleet-pilot-sites`:

```bash
../ha-fleet-tooling/.venv/Scripts/ha-fleet validate --site-path ./sites/site_001 --strict
../ha-fleet-tooling/.venv/Scripts/ha-fleet render --site-path ./sites/site_001 --output ./build/site_001
../ha-fleet-tooling/.venv/Scripts/ha-fleet bundle-to-backup --site-path ./sites/site_001 --output ./build/site_001_backup.tar.gz
```

Expected result:
- Validate exits 0
- Render outputs YAML files
- Backup artifact generated successfully

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

## 11. Next Step After Provisioning

Move from manual restore to scripted edge preflight/deploy (Phase 3):
- Edge preflight checks
- Artifact verification (SHA256)
- API-driven restore
- Health check + rollback automation
