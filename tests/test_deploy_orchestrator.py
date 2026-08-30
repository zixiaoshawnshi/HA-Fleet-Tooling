"""Tests for deploy orchestration sequencing.

Mocks all network/subprocess I/O (SSH, WebSocket, REST) to exercise the
actual new sequencing logic -- state persistence, retention, rollback modes,
no-auto-rollback-on-failure -- without any real device.
"""

import json
import shutil
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ha_fleet.deploy.errors import DeployError
from ha_fleet.deploy.health import EntityHealth, HealthResult
from ha_fleet.deploy.orchestrator import run_push, run_rollback, run_verify
from ha_fleet.deploy.target import DeployTarget

TEST_ROOT = Path("tests") / "_tmp"


def _new_case_dir() -> Path:
    case_dir = TEST_ROOT / f"case_{uuid.uuid4().hex}"
    case_dir.mkdir(parents=True, exist_ok=False)
    return case_dir


def _cleanup_case_dir(case_dir: Path) -> None:
    shutil.rmtree(case_dir, ignore_errors=True)


def _setup_site(site_dir: Path, required_entities: list | None = None) -> None:
    (site_dir / "bundles").mkdir(parents=True, exist_ok=True)
    (site_dir / "overlays").mkdir(parents=True, exist_ok=True)
    required = required_entities or []
    (site_dir / "site_manifest.yaml").write_text(
        "site_id: test_site\n"
        "display_name: Test Site\n"
        "bundles: []\n"
        f"required_entities: {required!r}\n",
        encoding="utf-8",
    )


def _target() -> DeployTarget:
    return DeployTarget(host="100.0.0.1", ssh_key_path="~/.ssh/id_test", token="tok")


def _mock_ws_client(mock_cls: MagicMock, generate_backup_id: str = "backup-123") -> MagicMock:
    instance = MagicMock()
    instance.generate_backup.return_value = generate_backup_id
    mock_cls.return_value.__enter__.return_value = instance
    return instance


@patch("ha_fleet.deploy.orchestrator.check_required_entities")
@patch("ha_fleet.deploy.orchestrator.rest_client")
@patch("ha_fleet.deploy.orchestrator.checksum")
@patch("ha_fleet.deploy.orchestrator.scp_push")
@patch("ha_fleet.deploy.orchestrator.HAWebSocketClient")
def test_run_push_happy_path(mock_ws_cls, mock_scp, mock_checksum, mock_rest, mock_health) -> None:
    case_dir = _new_case_dir()
    try:
        site_dir = case_dir / "site"
        _setup_site(site_dir)
        build_dir = case_dir / "build"
        ws_instance = _mock_ws_client(mock_ws_cls)
        mock_health.return_value = HealthResult(ok=True, entities=[])

        result = run_push(site_dir, _target(), build_dir=build_dir)

        assert result.ok
        ws_instance.generate_backup.assert_called_once()
        mock_scp.assert_called_once_with(_target(), build_dir, "/config")
        mock_checksum.verify_push.assert_called_once()
        mock_rest.restart.assert_called_once()
        mock_rest.wait_for_api.assert_called_once()

        assert (build_dir / "configuration.yaml").exists()
        assert (site_dir / "operator" / ".deploy_last_good" / "configuration.yaml").exists()

        state = json.loads((site_dir / "operator" / ".deploy_state.local.json").read_text(encoding="utf-8"))
        assert state["backup_id"] == "backup-123"
    finally:
        _cleanup_case_dir(case_dir)


@patch("ha_fleet.deploy.orchestrator.check_required_entities")
@patch("ha_fleet.deploy.orchestrator.rest_client")
@patch("ha_fleet.deploy.orchestrator.checksum")
@patch("ha_fleet.deploy.orchestrator.scp_push")
@patch("ha_fleet.deploy.orchestrator.HAWebSocketClient")
def test_run_push_skip_snapshot_does_not_generate_backup(
    mock_ws_cls, mock_scp, mock_checksum, mock_rest, mock_health
) -> None:
    case_dir = _new_case_dir()
    try:
        site_dir = case_dir / "site"
        _setup_site(site_dir)
        ws_instance = _mock_ws_client(mock_ws_cls)
        mock_health.return_value = HealthResult(ok=True, entities=[])

        result = run_push(site_dir, _target(), build_dir=case_dir / "build", skip_snapshot=True)

        assert result.ok
        ws_instance.generate_backup.assert_not_called()
        # No backup_id, so no state file should be written.
        assert not (site_dir / "operator" / ".deploy_state.local.json").exists()
    finally:
        _cleanup_case_dir(case_dir)


@patch("ha_fleet.deploy.orchestrator.check_required_entities")
@patch("ha_fleet.deploy.orchestrator.rest_client")
@patch("ha_fleet.deploy.orchestrator.checksum")
@patch("ha_fleet.deploy.orchestrator.scp_push")
@patch("ha_fleet.deploy.orchestrator.HAWebSocketClient")
def test_run_push_health_failure_does_not_auto_rollback(
    mock_ws_cls, mock_scp, mock_checksum, mock_rest, mock_health
) -> None:
    case_dir = _new_case_dir()
    try:
        site_dir = case_dir / "site"
        _setup_site(site_dir, required_entities=["input_boolean.test"])
        _mock_ws_client(mock_ws_cls)
        mock_health.return_value = HealthResult(
            ok=False,
            entities=[EntityHealth(entity_id="input_boolean.test", ok=False, state="unavailable")],
        )

        result = run_push(site_dir, _target(), build_dir=case_dir / "build")

        assert not result.ok
        assert "input_boolean.test" in result.message
        assert "rollback" in result.message.lower()
        # No .deploy_last_good should have been created on failure.
        assert not (site_dir / "operator" / ".deploy_last_good").exists()
        # But the new backup_id should still be persisted as the rollback point.
        state = json.loads((site_dir / "operator" / ".deploy_state.local.json").read_text(encoding="utf-8"))
        assert state["backup_id"] == "backup-123"
    finally:
        _cleanup_case_dir(case_dir)


@patch("ha_fleet.deploy.orchestrator.check_required_entities")
@patch("ha_fleet.deploy.orchestrator.rest_client")
@patch("ha_fleet.deploy.orchestrator.checksum")
@patch("ha_fleet.deploy.orchestrator.scp_push")
@patch("ha_fleet.deploy.orchestrator.HAWebSocketClient")
def test_run_push_retires_previous_snapshot_on_success(
    mock_ws_cls, mock_scp, mock_checksum, mock_rest, mock_health
) -> None:
    case_dir = _new_case_dir()
    try:
        site_dir = case_dir / "site"
        _setup_site(site_dir)
        (site_dir / "operator").mkdir(parents=True, exist_ok=True)
        (site_dir / "operator" / ".deploy_state.local.json").write_text(
            json.dumps({"backup_id": "old-backup-id"}), encoding="utf-8"
        )
        ws_instance = _mock_ws_client(mock_ws_cls, generate_backup_id="new-backup-id")
        mock_health.return_value = HealthResult(ok=True, entities=[])

        result = run_push(site_dir, _target(), build_dir=case_dir / "build")

        assert result.ok
        ws_instance.delete_backup.assert_called_once_with("old-backup-id")
        state = json.loads((site_dir / "operator" / ".deploy_state.local.json").read_text(encoding="utf-8"))
        assert state["backup_id"] == "new-backup-id"
    finally:
        _cleanup_case_dir(case_dir)


def test_run_rollback_config_mode_without_last_good_raises() -> None:
    case_dir = _new_case_dir()
    try:
        site_dir = case_dir / "site"
        _setup_site(site_dir)

        with pytest.raises(DeployError, match="No previous build available"):
            run_rollback(site_dir, _target(), mode="config")
    finally:
        _cleanup_case_dir(case_dir)


@patch("ha_fleet.deploy.orchestrator.check_required_entities")
@patch("ha_fleet.deploy.orchestrator.rest_client")
@patch("ha_fleet.deploy.orchestrator.checksum")
@patch("ha_fleet.deploy.orchestrator.scp_push")
def test_run_rollback_config_mode_pushes_last_good(mock_scp, mock_checksum, mock_rest, mock_health) -> None:
    case_dir = _new_case_dir()
    try:
        site_dir = case_dir / "site"
        _setup_site(site_dir)
        last_good = site_dir / "operator" / ".deploy_last_good"
        last_good.mkdir(parents=True)
        (last_good / "configuration.yaml").write_text("default_config:\n", encoding="utf-8")
        mock_health.return_value = HealthResult(ok=True, entities=[])

        result = run_rollback(site_dir, _target(), mode="config")

        assert result.ok
        mock_scp.assert_called_once_with(_target(), last_good, "/config")
        mock_rest.restart.assert_called_once()
    finally:
        _cleanup_case_dir(case_dir)


def test_run_rollback_snapshot_mode_without_backup_id_raises() -> None:
    case_dir = _new_case_dir()
    try:
        site_dir = case_dir / "site"
        _setup_site(site_dir)

        with pytest.raises(DeployError, match="No backup_id recorded"):
            run_rollback(site_dir, _target(), mode="snapshot")
    finally:
        _cleanup_case_dir(case_dir)


@patch("ha_fleet.deploy.orchestrator.check_required_entities")
@patch("ha_fleet.deploy.orchestrator.rest_client")
@patch("ha_fleet.deploy.orchestrator.HAWebSocketClient")
def test_run_rollback_snapshot_mode_restores_backup(mock_ws_cls, mock_rest, mock_health) -> None:
    case_dir = _new_case_dir()
    try:
        site_dir = case_dir / "site"
        _setup_site(site_dir)
        (site_dir / "operator").mkdir(parents=True, exist_ok=True)
        (site_dir / "operator" / ".deploy_state.local.json").write_text(
            json.dumps({"backup_id": "backup-to-restore"}), encoding="utf-8"
        )
        ws_instance = _mock_ws_client(mock_ws_cls)
        mock_health.return_value = HealthResult(ok=True, entities=[])

        result = run_rollback(site_dir, _target(), mode="snapshot")

        assert result.ok
        ws_instance.restore_backup.assert_called_once_with("backup-to-restore")
    finally:
        _cleanup_case_dir(case_dir)


def test_run_rollback_unknown_mode_raises() -> None:
    case_dir = _new_case_dir()
    try:
        site_dir = case_dir / "site"
        _setup_site(site_dir)

        with pytest.raises(DeployError, match="Unknown rollback mode"):
            run_rollback(site_dir, _target(), mode="bogus")
    finally:
        _cleanup_case_dir(case_dir)


@patch("ha_fleet.deploy.orchestrator.check_required_entities")
def test_run_verify_reports_health(mock_health) -> None:
    case_dir = _new_case_dir()
    try:
        site_dir = case_dir / "site"
        _setup_site(site_dir)
        mock_health.return_value = HealthResult(ok=True, entities=[])

        result = run_verify(site_dir, _target())

        assert result.ok
        assert "healthy" in result.message.lower()
    finally:
        _cleanup_case_dir(case_dir)
