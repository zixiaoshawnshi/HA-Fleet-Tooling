"""Tests for schemas."""

import pytest
from ha_fleet.schemas.site import SiteManifest, Capability, BackupConfig
from ha_fleet.schemas.bundle import BundleDefinition
from ha_fleet.schemas.secrets import SecretsContract
from tests.fixtures import get_minimal_site_manifest, get_full_site_manifest


def test_site_manifest_minimal() -> None:
    """Test minimal site manifest validation."""
    manifest = get_minimal_site_manifest()
    assert manifest.site_id == "test_site"
    assert manifest.runtime == "haos_bare_metal"
    assert "routine" in manifest.bundles


def test_site_manifest_full() -> None:
    """Test full site manifest with all fields."""
    manifest = get_full_site_manifest()
    assert manifest.site_id == "site_001"
    assert manifest.display_name == "Ottawa Pilot Home"
    assert len(manifest.bundles) == 3
    assert manifest.capabilities.google_calendar is True


def test_capability_defaults() -> None:
    """Test capability defaults."""
    cap = Capability()
    assert cap.zigbee is False
    assert cap.mqtt is False
    assert cap.google_calendar is False


def test_backup_config_defaults() -> None:
    """Test backup config defaults."""
    backup = BackupConfig()
    assert backup.exclude_media is True
    assert backup.exclude_history == "7d"


def test_bundle_definition() -> None:
    """Test bundle definition schema."""
    bundle = BundleDefinition(
        name="test_bundle",
        version="1.0.0",
        requires_secrets=["secret1"],
        requires_capabilities={"zigbee": True},
    )
    assert bundle.name == "test_bundle"
    assert "secret1" in bundle.requires_secrets


def test_secrets_contract() -> None:
    """Test secrets contract schema."""
    contract = SecretsContract(
        required=["required_secret"],
        optional=["optional_secret"],
    )
    assert "required_secret" in contract.required
    assert "optional_secret" in contract.optional


def test_site_manifest_json_schema() -> None:
    """Test that site manifest can be exported to JSON schema."""
    schema = SiteManifest.model_json_schema()
    assert "properties" in schema
    assert "site_id" in schema["properties"]
    assert "bundles" in schema["properties"]
