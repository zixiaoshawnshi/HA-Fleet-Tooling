"""Tests for CLI commands."""

import shutil
import uuid
from pathlib import Path

import yaml
from click.testing import CliRunner

from ha_fleet.cli.commands import bundle_to_backup, diff, validate

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
