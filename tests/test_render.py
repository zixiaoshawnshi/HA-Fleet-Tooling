"""Tests for render engine."""

import pytest
import tempfile
from pathlib import Path
import yaml
from ha_fleet.render.config import ConfigRenderer
from tests.fixtures import get_minimal_site_manifest


def test_config_renderer_initialization() -> None:
    """Test ConfigRenderer initialization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        (site_dir / "bundles").mkdir()
        (site_dir / "overlays").mkdir()

        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        assert renderer.manifest.site_id == "test_site"
        assert renderer.site_path == site_dir


def test_load_bundle() -> None:
    """Test loading a bundle."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        bundles_dir = site_dir / "bundles"
        bundles_dir.mkdir()

        # Create a test bundle
        bundle_data = {
            "name": "test_bundle",
            "version": "1.0.0",
            "requires_secrets": ["key1"],
        }
        with open(bundles_dir / "test_bundle.yaml", "w") as f:
            yaml.dump(bundle_data, f)

        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        bundle = renderer.load_bundle("test_bundle")
        assert bundle["name"] == "test_bundle"
        assert "key1" in bundle["requires_secrets"]


def test_load_nonexistent_bundle() -> None:
    """Test loading a nonexistent bundle raises error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        (site_dir / "bundles").mkdir()
        (site_dir / "overlays").mkdir()

        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        with pytest.raises(FileNotFoundError):
            renderer.load_bundle("nonexistent")


def test_render_automations_empty() -> None:
    """Test rendering automations with no bundles."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        (site_dir / "bundles").mkdir()
        (site_dir / "overlays").mkdir()

        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        automations = renderer.render_automations()
        assert automations == []


def test_merge_yaml_dicts() -> None:
    """Test YAML dict merging."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        (site_dir / "bundles").mkdir()
        (site_dir / "overlays").mkdir()

        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"d": 3}, "e": 4}

        result = renderer._merge_yaml_dicts(base, override)
        assert result["a"] == 1
        assert result["b"]["c"] == 2
        assert result["b"]["d"] == 3
        assert result["e"] == 4


def test_render_all_returns_dict() -> None:
    """Test render_all returns expected dict structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        site_dir = Path(tmpdir)
        (site_dir / "bundles").mkdir()
        (site_dir / "overlays").mkdir()

        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        config = renderer.render_all()
        assert "automations" in config
        assert "scripts" in config
        assert "input_booleans" in config
