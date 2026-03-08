"""Tests for HAOS backup generation."""

import pytest
import tempfile
import tarfile
import json
from pathlib import Path
import yaml
from ha_fleet.backup.haos import HAOSBackupGenerator
from tests.fixtures import get_minimal_site_manifest, get_full_site_manifest


def test_backup_generator_initialization() -> None:
    """Test HAOSBackupGenerator initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        (site_dir / "bundles").mkdir()
        (site_dir / "overlays").mkdir()

        manifest = get_minimal_site_manifest()
        generator = HAOSBackupGenerator(manifest, site_dir)

        assert generator.manifest.site_id == "test_site"
        assert generator.site_path == site_dir


def test_create_backup_metadata() -> None:
    """Test backup.json metadata creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        (site_dir / "bundles").mkdir()
        (site_dir / "overlays").mkdir()

        manifest = get_minimal_site_manifest()
        generator = HAOSBackupGenerator(manifest, site_dir)

        metadata = generator._create_backup_metadata()
        assert metadata["version"] == 1
        assert metadata["name"] == "test_site_backup"
        assert metadata["type"] == "full"
        assert "key" in metadata


def test_create_ha_config_snapshot() -> None:
    """Test homeassistant.json config snapshot creation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        (site_dir / "bundles").mkdir()
        (site_dir / "overlays").mkdir()

        manifest = get_full_site_manifest()
        generator = HAOSBackupGenerator(manifest, site_dir)

        config = generator._create_ha_config_snapshot({})
        assert config["name"] == "Ottawa Pilot Home"
        assert config["version"]
        assert config["unit_system"] == "metric"


def test_calculate_sha256() -> None:
    """Test SHA256 calculation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        (site_dir / "bundles").mkdir()
        (site_dir / "overlays").mkdir()

        # Create a test file
        test_file = Path(tmpdir) / "test.txt"
        test_file.write_text("hello world")

        manifest = get_minimal_site_manifest()
        generator = HAOSBackupGenerator(manifest, site_dir)

        checksum = generator._calculate_sha256(test_file)
        assert len(checksum) == 64  # SHA256 hex is 64 chars
        assert checksum.isalnum()


def test_generate_backup_creates_tarball() -> None:
    """Test backup generation creates a valid tarball."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        bundles_dir = site_dir / "bundles"
        bundles_dir.mkdir()
        (site_dir / "overlays").mkdir()

        # Create a minimal bundle
        bundle_data = {"name": "routine"}
        with open(bundles_dir / "routine.yaml", "w") as f:
            yaml.dump(bundle_data, f)

        manifest = get_minimal_site_manifest()
        output_path = Path(tmpdir) / "backup.tar.gz"

        generator = HAOSBackupGenerator(manifest, site_dir)
        result = generator.generate(output_path)

        # Verify file exists
        assert output_path.exists()
        assert result["file_size"] > 0
        assert result["checksum"]
        assert result["site_id"] == "test_site"


def test_backup_contains_required_files() -> None:
    """Test backup tarball contains required files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        bundles_dir = site_dir / "bundles"
        bundles_dir.mkdir()
        (site_dir / "overlays").mkdir()

        # Create a minimal bundle
        bundle_data = {"name": "routine"}
        with open(bundles_dir / "routine.yaml", "w") as f:
            yaml.dump(bundle_data, f)

        manifest = get_minimal_site_manifest()
        output_path = Path(tmpdir) / "backup.tar.gz"

        generator = HAOSBackupGenerator(manifest, site_dir)
        result = generator.generate(output_path)

        # Verify tarball contents
        with tarfile.open(output_path, "r:gz") as tar:
            names = tar.getnames()
            assert "backup.json" in names
            assert "homeassistant.json" in names

            # Verify backup.json is valid JSON
            backup_member = tar.getmember("backup.json")
            f = tar.extractfile(backup_member)
            backup_data = json.load(f)
            assert "key" in backup_data
            assert "version" in backup_data
