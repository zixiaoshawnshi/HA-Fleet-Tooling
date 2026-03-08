"""Tests for HAOS backup generation."""

import json
import shutil
import tarfile
import uuid
from pathlib import Path

import yaml

from ha_fleet.backup.haos import HAOSBackupGenerator
from tests.fixtures import get_full_site_manifest, get_minimal_site_manifest


TEST_ROOT = Path("tests") / "_tmp"


def _new_case_dir() -> Path:
    case_dir = TEST_ROOT / f"case_{uuid.uuid4().hex}"
    case_dir.mkdir(parents=True, exist_ok=False)
    return case_dir


def _cleanup_case_dir(case_dir: Path) -> None:
    shutil.rmtree(case_dir, ignore_errors=True)


def _setup_site(case_dir: Path) -> Path:
    (case_dir / "bundles").mkdir()
    (case_dir / "overlays").mkdir()
    return case_dir


def test_backup_generator_initialization() -> None:
    """Test HAOSBackupGenerator initialization."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        manifest = get_minimal_site_manifest()
        generator = HAOSBackupGenerator(manifest, site_dir)

        assert generator.manifest.site_id == "test_site"
        assert generator.site_path == site_dir
    finally:
        _cleanup_case_dir(case_dir)


def test_create_backup_metadata() -> None:
    """Test backup.json metadata creation."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        manifest = get_minimal_site_manifest()
        generator = HAOSBackupGenerator(manifest, site_dir)

        metadata = generator._create_backup_metadata(
            exclude_media=True,
            exclude_history="7d",
        )
        assert metadata["version"] == 1
        assert metadata["name"] == "test_site_backup"
        assert metadata["type"] == "full"
        assert "key" in metadata
        assert metadata["ha_fleet_options"]["exclude_media"] is True
        assert metadata["ha_fleet_options"]["exclude_history"] == "7d"
    finally:
        _cleanup_case_dir(case_dir)


def test_create_ha_config_snapshot() -> None:
    """Test homeassistant.json config snapshot creation."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        manifest = get_full_site_manifest()
        generator = HAOSBackupGenerator(manifest, site_dir)

        config = generator._create_ha_config_snapshot({})
        assert config["name"] == "Ottawa Pilot Home"
        assert config["version"]
        assert config["unit_system"] == "metric"
    finally:
        _cleanup_case_dir(case_dir)


def test_calculate_sha256() -> None:
    """Test SHA256 calculation."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        test_file = case_dir / "test.txt"
        test_file.write_text("hello world", encoding="utf-8")

        manifest = get_minimal_site_manifest()
        generator = HAOSBackupGenerator(manifest, site_dir)

        checksum = generator._calculate_sha256(test_file)
        assert len(checksum) == 64
        assert checksum.isalnum()
    finally:
        _cleanup_case_dir(case_dir)


def test_generate_backup_creates_tarball() -> None:
    """Test backup generation creates a valid tarball."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        with open(site_dir / "bundles" / "routine.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump({"name": "routine"}, f)

        manifest = get_minimal_site_manifest()
        output_path = case_dir / "backup.tar.gz"

        generator = HAOSBackupGenerator(manifest, site_dir)
        result = generator.generate(output_path)

        assert output_path.exists()
        assert result["file_size"] > 0
        assert result["checksum"]
        assert result["site_id"] == "test_site"
    finally:
        _cleanup_case_dir(case_dir)


def test_backup_contains_required_files() -> None:
    """Test backup tarball contains required files."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        with open(site_dir / "bundles" / "routine.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump({"name": "routine"}, f)

        manifest = get_minimal_site_manifest()
        output_path = case_dir / "backup.tar.gz"

        generator = HAOSBackupGenerator(manifest, site_dir)
        generator.generate(output_path)

        with tarfile.open(output_path, "r:gz") as tar:
            names = tar.getnames()
            assert any(name.endswith("backup.json") for name in names)
            assert any(name.endswith("homeassistant.json") for name in names)

            backup_member = next(
                member for member in tar.getmembers() if member.name.endswith("backup.json")
            )
            extracted = tar.extractfile(backup_member)
            assert extracted is not None
            backup_data = json.load(extracted)
            assert "key" in backup_data
            assert "version" in backup_data
    finally:
        _cleanup_case_dir(case_dir)
