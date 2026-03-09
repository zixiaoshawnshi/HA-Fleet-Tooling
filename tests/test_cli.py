"""Tests for CLI commands."""

import io
import json
import shutil
import tarfile
import uuid
from pathlib import Path

import yaml
from click.testing import CliRunner

from ha_fleet.cli.commands import (
    bundle_to_backup,
    dev_site,
    diff,
    ingest_backup,
    ingest_config_dir,
    new_site,
    validate,
)

TEST_ROOT = Path("tests") / "_tmp"


def _new_case_dir() -> Path:
    case_dir = TEST_ROOT / f"case_{uuid.uuid4().hex}"
    case_dir.mkdir(parents=True, exist_ok=False)
    return case_dir


def _cleanup_case_dir(case_dir: Path) -> None:
    shutil.rmtree(case_dir, ignore_errors=True)


def _write_manifest(site_dir: Path, bundles: list[str]) -> None:
    manifest = {
        "site_id": "site_001",
        "display_name": "Test Site",
        "runtime": "haos_bare_metal",
        "bundles": bundles,
        "capabilities": {"zigbee": True, "mqtt": True, "google_calendar": False},
    }
    with open(site_dir / "site_manifest.yaml", "w", encoding="utf-8") as f:
        yaml.safe_dump(manifest, f)


def _write_json_member(tar: tarfile.TarFile, name: str, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def _create_backup_with_registries(path: Path) -> None:
    with tarfile.open(path, "w:gz") as tar:
        _write_json_member(
            tar,
            ".storage/core.device_registry",
            {"data": {"devices": [{"id": "dev1", "name": "Sensor Device"}]}},
        )
        _write_json_member(
            tar,
            ".storage/core.entity_registry",
            {"data": {"entities": [{"entity_id": "sensor.temp", "platform": "mqtt"}]}},
        )
        _write_json_member(
            tar,
            ".storage/core.config_entries",
            {"data": {"entries": [{"entry_id": "cfg1", "domain": "mqtt", "title": "MQTT"}]}},
        )


def test_validate_strict_fails_missing_bundle_definition() -> None:
    """Strict validate should fail when bundle definition is missing."""
    case_dir = _new_case_dir()
    try:
        (case_dir / "bundles").mkdir()
        (case_dir / "overlays").mkdir()
        _write_manifest(case_dir, bundles=["routine"])

        runner = CliRunner()
        result = runner.invoke(validate, ["--site-path", str(case_dir), "--strict"])

        assert result.exit_code == 1
        assert "Bundle definition not found" in result.output
    finally:
        _cleanup_case_dir(case_dir)


def test_validate_non_strict_warns_but_passes() -> None:
    """Non-strict validate should surface warnings but return success."""
    case_dir = _new_case_dir()
    try:
        (case_dir / "bundles").mkdir()
        (case_dir / "overlays").mkdir()
        _write_manifest(case_dir, bundles=["routine"])

        runner = CliRunner()
        result = runner.invoke(validate, ["--site-path", str(case_dir)])

        assert result.exit_code == 0
        assert "Warnings:" in result.output
    finally:
        _cleanup_case_dir(case_dir)


def test_diff_returns_not_implemented() -> None:
    """Diff command should return explicit non-zero until implemented."""
    case_dir = _new_case_dir()
    try:
        (case_dir / "site_manifest.yaml").write_text("site_id: s\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(diff, ["--site-path", str(case_dir)])

        assert result.exit_code == 2
        assert "not implemented" in result.output.lower()
    finally:
        _cleanup_case_dir(case_dir)


def test_bundle_to_backup_accepts_exclude_flags() -> None:
    """Backup command should accept and apply exclusion options."""
    case_dir = _new_case_dir()
    try:
        bundles_dir = case_dir / "bundles" / "routine"
        bundles_dir.mkdir(parents=True)
        (case_dir / "overlays").mkdir()
        _write_manifest(case_dir, bundles=["routine"])
        with open(bundles_dir / "bundle.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump({"name": "routine", "version": "1.0.0"}, f)

        output = case_dir / "backup.tar.gz"
        runner = CliRunner()
        result = runner.invoke(
            bundle_to_backup,
            [
                "--site-path",
                str(case_dir),
                "--output",
                str(output),
                "--exclude-media",
                "--exclude-history",
                "14d",
            ],
        )

        assert result.exit_code == 0
        assert output.exists()
    finally:
        _cleanup_case_dir(case_dir)


def test_ingest_backup_writes_snapshot_file() -> None:
    """Ingest command should extract registries and write discovery snapshot."""
    case_dir = _new_case_dir()
    try:
        (case_dir / "bundles").mkdir()
        (case_dir / "overlays").mkdir()
        _write_manifest(case_dir, bundles=[])

        backup_path = case_dir / "ha_backup.tar.gz"
        _create_backup_with_registries(backup_path)

        output_path = case_dir / "discovery" / "latest.yaml"
        runner = CliRunner()
        result = runner.invoke(
            ingest_backup,
            [
                "--site-path",
                str(case_dir),
                "--backup",
                str(backup_path),
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code == 0
        assert output_path.exists()
        snapshot = yaml.safe_load(output_path.read_text(encoding="utf-8"))
        assert snapshot["counts"]["devices"] == 1
        assert snapshot["counts"]["entities"] == 1
        assert snapshot["counts"]["config_entries"] == 1
    finally:
        _cleanup_case_dir(case_dir)


def test_ingest_config_dir_writes_snapshot_file() -> None:
    """Config-dir ingest should read .storage and write discovery snapshot."""
    case_dir = _new_case_dir()
    try:
        (case_dir / "bundles").mkdir()
        (case_dir / "overlays").mkdir()
        _write_manifest(case_dir, bundles=[])

        storage_dir = case_dir / "ha_config" / ".storage"
        storage_dir.mkdir(parents=True)
        (storage_dir / "core.device_registry").write_text(
            json.dumps({"data": {"devices": [{"id": "dev1", "name": "Sensor Device"}]}}),
            encoding="utf-8",
        )
        (storage_dir / "core.entity_registry").write_text(
            json.dumps({"data": {"entities": [{"entity_id": "sensor.temp", "platform": "mqtt"}]}}),
            encoding="utf-8",
        )
        (storage_dir / "core.config_entries").write_text(
            json.dumps({"data": {"entries": [{"entry_id": "cfg1", "domain": "mqtt", "title": "MQTT"}]}}),
            encoding="utf-8",
        )

        output_path = case_dir / "discovery" / "latest.yaml"
        runner = CliRunner()
        result = runner.invoke(
            ingest_config_dir,
            [
                "--site-path",
                str(case_dir),
                "--config-dir",
                str(storage_dir.parent),
                "--output",
                str(output_path),
            ],
        )

        assert result.exit_code == 0
        assert output_path.exists()
        snapshot = yaml.safe_load(output_path.read_text(encoding="utf-8"))
        assert snapshot["counts"]["devices"] == 1
        assert snapshot["counts"]["entities"] == 1
        assert snapshot["counts"]["config_entries"] == 1
    finally:
        _cleanup_case_dir(case_dir)


def test_new_site_creates_scaffold() -> None:
    """new-site should scaffold expected site layout."""
    case_dir = _new_case_dir()
    try:
        sites_root = case_dir / "sites"
        sites_root.mkdir()

        runner = CliRunner()
        result = runner.invoke(
            new_site,
            [
                "--sites-root",
                str(sites_root),
                "--site-id",
                "site_050",
                "--display-name",
                "Pilot Site 050",
            ],
        )

        assert result.exit_code == 0
        site_path = sites_root / "site_050"
        assert (site_path / "site_manifest.yaml").exists()
        assert (site_path / "secrets_contract.yaml").exists()
        assert (site_path / "dashboards" / "ui-lovelace.yaml").exists()
        assert (site_path / "overlays" / "README.md").exists()
        assert (site_path / "operator" / "secrets.local.example.yaml").exists()
        assert (site_path / "discovery" / "README.md").exists()
    finally:
        _cleanup_case_dir(case_dir)


def test_dev_site_render_creates_build_and_secrets() -> None:
    """dev-site render should render config and copy operator mock secrets."""
    case_dir = _new_case_dir()
    try:
        site_dir = case_dir / "sites" / "site_070"
        (site_dir / "bundles").mkdir(parents=True)
        (site_dir / "overlays").mkdir()
        (site_dir / "operator").mkdir()
        _write_manifest(site_dir, bundles=[])
        (site_dir / "operator" / "secrets.local.example.yaml").write_text(
            'notify_mobile_target: "operator_phone"\n',
            encoding="utf-8",
        )

        build_dir = case_dir / "build" / "site_070"
        runner = CliRunner()
        result = runner.invoke(
            dev_site,
            [
                "--site-path",
                str(site_dir),
                "--action",
                "render",
                "--build-path",
                str(build_dir),
            ],
        )

        assert result.exit_code == 0
        assert (build_dir / "secrets.yaml").exists()
    finally:
        _cleanup_case_dir(case_dir)

