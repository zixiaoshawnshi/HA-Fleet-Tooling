"""Deploy sequencing: push, rollback, and verify.

`run_push`'s happy path: preflight render -> safety snapshot (backup/generate,
never backup/restore for the routine case) -> push files over SCP -> checksum
verify -> restart -> health check. On health-check failure, this does NOT
auto-rollback -- it reports failure and leaves the operator to run
`deploy rollback` explicitly, since auto-reverting on a possibly-transient
health-check flake is worse than a clear manual step.

State (the current rollback backup_id and a copy of the last successfully
deployed build) persists across CLI invocations in a gitignored
sites/<site>/operator/.deploy_state.local.json + .deploy_last_good/ pair, so
`deploy rollback` works even from a fresh terminal session.
"""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

from ha_fleet.deploy import checksum, rest_client
from ha_fleet.deploy.errors import DeployError
from ha_fleet.deploy.health import HealthResult, check_required_entities
from ha_fleet.deploy.target import DeployTarget
from ha_fleet.deploy.transport import scp_push
from ha_fleet.deploy.ws_client import HAWebSocketClient
from ha_fleet.render.config import ConfigRenderer
from ha_fleet.schemas.site import SiteManifest

REMOTE_CONFIG_DIR = "/config"

# Full restart is the safe default: new configuration.yaml includes and
# lovelace.dashboards registrations need it, and only automation/script/
# helper-only edits could use a targeted <domain>.reload. Named here so a
# faster path isn't a rewrite later.
APPLY_METHOD = "restart"


@dataclass
class DeployResult:
    """Outcome of a push/rollback operation."""

    ok: bool
    message: str
    health: Optional[HealthResult] = None


def _state_path(site_dir: Path) -> Path:
    return site_dir / "operator" / ".deploy_state.local.json"


def _last_good_dir(site_dir: Path) -> Path:
    return site_dir / "operator" / ".deploy_last_good"


def _load_state(site_dir: Path) -> dict:
    path = _state_path(site_dir)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_state(site_dir: Path, state: dict) -> None:
    path = _state_path(site_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def _load_manifest(site_dir: Path) -> SiteManifest:
    manifest_path = site_dir / "site_manifest.yaml"
    if not manifest_path.exists():
        raise DeployError(f"site_manifest.yaml not found in {site_dir}")
    with open(manifest_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return SiteManifest(**data)


def _default_build_dir(site_dir: Path) -> Path:
    if site_dir.parent.name == "sites":
        return site_dir.parent.parent / "build" / site_dir.name
    return site_dir / "build"


def run_push(
    site_dir: Path,
    target: DeployTarget,
    build_dir: Optional[Path] = None,
    skip_snapshot: bool = False,
    restart_timeout: float = 120.0,
    health_timeout: float = 90.0,
) -> DeployResult:
    """Render, snapshot, push, restart, and health-check a site deploy."""
    manifest = _load_manifest(site_dir)
    resolved_build_dir = build_dir or _default_build_dir(site_dir)

    # Preflight: render raises on missing bundle files / bad composition,
    # and SiteManifest(**data) already gave us schema validation. This is
    # not a substitute for `ha-fleet validate --strict`'s fuller
    # capability-mismatch warnings -- operators should still run that
    # themselves before deploying.
    renderer = ConfigRenderer(manifest, site_dir)
    renderer.write_to_dir(resolved_build_dir, format="yaml")

    state = _load_state(site_dir)
    previous_backup_id = state.get("backup_id")

    backup_id: Optional[str] = None
    if not skip_snapshot:
        with HAWebSocketClient(target) as ws:
            backup_id = ws.generate_backup(name=f"ha-fleet-deploy-pre-{manifest.site_id}")

    scp_push(target, resolved_build_dir, REMOTE_CONFIG_DIR)
    checksum.verify_push(target, resolved_build_dir, REMOTE_CONFIG_DIR)

    rest_client.restart(target)
    rest_client.wait_for_api(target, timeout=restart_timeout)
    health = check_required_entities(target, manifest, timeout=health_timeout)

    if not health.ok:
        # No auto-rollback. Persist the new backup_id (it's the correct
        # rollback point for this failed attempt) but leave .deploy_last_good
        # and the previous backup_id untouched -- run `deploy rollback`.
        if backup_id:
            _save_state(site_dir, {"backup_id": backup_id, "updated_at": _now()})
        failed = ", ".join(f"{e.entity_id} ({e.state})" for e in health.failures)
        return DeployResult(
            ok=False,
            message=f"Health check failed for: {failed}. Run 'ha-fleet deploy rollback' to revert.",
            health=health,
        )

    # Success: promote this build to .deploy_last_good, retire the previous
    # snapshot (keep only the most recent pre-deploy backup), and record state.
    last_good_dir = _last_good_dir(site_dir)
    if last_good_dir.exists():
        shutil.rmtree(last_good_dir)
    shutil.copytree(resolved_build_dir, last_good_dir)

    if previous_backup_id and previous_backup_id != backup_id:
        with HAWebSocketClient(target) as ws:
            try:
                ws.delete_backup(previous_backup_id)
            except DeployError:
                pass  # Retention cleanup is best-effort; don't fail the deploy over it.

    if backup_id:
        _save_state(site_dir, {"backup_id": backup_id, "updated_at": _now()})

    return DeployResult(ok=True, message="Deploy succeeded and health check passed.", health=health)


def run_rollback(
    site_dir: Path,
    target: DeployTarget,
    mode: str = "config",
    restart_timeout: float = 120.0,
    health_timeout: float = 90.0,
) -> DeployResult:
    """Roll back a deploy. mode='config' re-pushes the previous build (fast,
    no state loss). mode='snapshot' restores the pre-deploy backup (slow,
    reverts all state changes since that snapshot -- callers must confirm
    with the operator before calling this)."""
    if mode == "config":
        last_good_dir = _last_good_dir(site_dir)
        if not last_good_dir.exists():
            raise DeployError(
                "No previous build available for --mode config rollback "
                "(no successful deploy has completed from this operator machine yet). "
                "Use --mode snapshot instead."
            )
        scp_push(target, last_good_dir, REMOTE_CONFIG_DIR)
        checksum.verify_push(target, last_good_dir, REMOTE_CONFIG_DIR)
        rest_client.restart(target)
        rest_client.wait_for_api(target, timeout=restart_timeout)
        manifest = _load_manifest(site_dir)
        health = check_required_entities(target, manifest, timeout=health_timeout)
        return DeployResult(
            ok=health.ok,
            message="Config rollback complete." if health.ok else "Config rollback pushed, but health check failed.",
            health=health,
        )

    if mode == "snapshot":
        state = _load_state(site_dir)
        backup_id = state.get("backup_id")
        if not backup_id:
            raise DeployError("No backup_id recorded for --mode snapshot rollback.")
        with HAWebSocketClient(target) as ws:
            ws.restore_backup(backup_id)
        rest_client.wait_for_api(target, timeout=restart_timeout)
        manifest = _load_manifest(site_dir)
        health = check_required_entities(target, manifest, timeout=health_timeout)
        return DeployResult(
            ok=health.ok,
            message="Snapshot restore complete." if health.ok else "Snapshot restored, but health check failed.",
            health=health,
        )

    raise DeployError(f"Unknown rollback mode: {mode!r} (expected 'config' or 'snapshot')")


def run_verify(site_dir: Path, target: DeployTarget, health_timeout: float = 90.0) -> DeployResult:
    """Re-run the health check standalone, e.g. after a manual fix."""
    manifest = _load_manifest(site_dir)
    health = check_required_entities(target, manifest, timeout=health_timeout)
    return DeployResult(
        ok=health.ok,
        message="All required entities healthy." if health.ok else "Some required entities are unhealthy.",
        health=health,
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
