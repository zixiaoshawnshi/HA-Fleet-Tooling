"""Tests for render engine."""

import shutil
import uuid
from pathlib import Path

import pytest
import yaml

from ha_fleet.render.config import ConfigRenderer
from tests.fixtures import get_minimal_site_manifest

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


def test_config_renderer_initialization() -> None:
    """Test ConfigRenderer initialization."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        assert renderer.manifest.site_id == "test_site"
        assert renderer.site_path == site_dir
    finally:
        _cleanup_case_dir(case_dir)


def test_load_bundle() -> None:
    """Test loading a bundle."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)

        bundle_data = {
            "name": "test_bundle",
            "version": "1.0.0",
            "requires_secrets": ["key1"],
        }
        with open(site_dir / "bundles" / "test_bundle.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump(bundle_data, f)

        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        bundle = renderer.load_bundle("test_bundle")
        assert bundle["name"] == "test_bundle"
        assert "key1" in bundle["requires_secrets"]
    finally:
        _cleanup_case_dir(case_dir)


def test_load_nonexistent_bundle() -> None:
    """Test loading a nonexistent bundle raises error."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        with pytest.raises(FileNotFoundError):
            renderer.load_bundle("nonexistent")
    finally:
        _cleanup_case_dir(case_dir)


def test_render_automations_empty() -> None:
    """Test rendering automations with no bundles."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        automations = renderer.render_automations()
        assert automations == []
    finally:
        _cleanup_case_dir(case_dir)


def test_merge_yaml_dicts() -> None:
    """Test YAML dict merging."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"d": 3}, "e": 4}

        result = renderer._merge_yaml_dicts(base, override)
        assert result["a"] == 1
        assert result["b"]["c"] == 2
        assert result["b"]["d"] == 3
        assert result["e"] == 4
    finally:
        _cleanup_case_dir(case_dir)


def test_render_all_returns_dict() -> None:
    """Test render_all returns expected dict structure."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)

        config = renderer.render_all()
        assert "automations" in config
        assert "scripts" in config
        assert "input_booleans" in config
        assert "dashboards" in config
        assert "configuration" in config
        assert "configuration_overrides" in config
    finally:
        _cleanup_case_dir(case_dir)


def test_render_automations_supports_bundle_directory_layout() -> None:
    """Renderer should not require flat bundles/<name>.yaml when bundle dir exists."""
    case_dir = _new_case_dir()
    try:
        (case_dir / "bundles" / "routine").mkdir(parents=True)
        (case_dir / "overlays").mkdir()

        with open(
            case_dir / "bundles" / "routine" / "automations.yaml",
            "w",
            encoding="utf-8",
        ) as f:
            yaml.safe_dump([{"id": "test_auto", "alias": "Test"}], f)

        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, case_dir)
        automations = renderer.render_automations()

        assert len(automations) == 1
        assert automations[0]["id"] == "test_auto"
    finally:
        _cleanup_case_dir(case_dir)


def test_render_dashboards_supports_site_and_overlay_files() -> None:
    """Dashboards should be loaded from site and overridden by overlay files."""
    case_dir = _new_case_dir()
    try:
        (case_dir / "bundles").mkdir()
        (case_dir / "overlays" / "dashboards").mkdir(parents=True)
        (case_dir / "dashboards").mkdir()

        with open(case_dir / "dashboards" / "ui-lovelace.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump({"title": "Base Dashboard"}, f)
        with open(case_dir / "dashboards" / "transit.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump({"title": "Transit Dashboard"}, f)
        with open(
            case_dir / "overlays" / "dashboards" / "ui-lovelace.yaml",
            "w",
            encoding="utf-8",
        ) as f:
            yaml.safe_dump({"title": "Overlay Dashboard"}, f)

        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, case_dir)
        dashboards = renderer.render_dashboards()

        assert dashboards["ui-lovelace.yaml"]["title"] == "Overlay Dashboard"
        assert dashboards["transit.yaml"]["title"] == "Transit Dashboard"
    finally:
        _cleanup_case_dir(case_dir)


def test_write_to_dir_outputs_dashboards_directory() -> None:
    """Renderer should write dashboard files under output/dashboards."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        (site_dir / "dashboards").mkdir()
        with open(site_dir / "dashboards" / "ui-lovelace.yaml", "w", encoding="utf-8") as f:
            yaml.safe_dump({"title": "Ops Dashboard"}, f)

        output_dir = case_dir / "build"
        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)
        renderer.write_to_dir(output_dir)

        output_file = output_dir / "dashboards" / "ui-lovelace.yaml"
        assert output_file.exists()
        with open(output_file, "r", encoding="utf-8") as f:
            rendered_data = yaml.safe_load(f)
        assert rendered_data["title"] == "Ops Dashboard"

        configuration_file = output_dir / "configuration.yaml"
        assert configuration_file.exists()
        configuration_text = configuration_file.read_text(encoding="utf-8")
        assert "lovelace:" in configuration_text
        assert "dashboards:" in configuration_text
        assert "fleet-test-site-ui-lovelace-yaml:" in configuration_text
        assert "filename: dashboards/ui-lovelace.yaml" in configuration_text
    finally:
        _cleanup_case_dir(case_dir)


def test_configuration_overrides_are_appended() -> None:
    """Site-level configuration overrides should be appended to configuration.yaml."""
    case_dir = _new_case_dir()
    try:
        site_dir = _setup_site(case_dir)
        override_file = site_dir / "configuration_overrides.yaml"
        override_file.write_text(
            "sensor:\n  - platform: alpha_vantage\n    api_key: !secret alpha_vantage_api_key\n",
            encoding="utf-8",
        )

        output_dir = case_dir / "build"
        manifest = get_minimal_site_manifest()
        renderer = ConfigRenderer(manifest, site_dir)
        renderer.write_to_dir(output_dir)

        configuration_text = (output_dir / "configuration.yaml").read_text(encoding="utf-8")
        assert "platform: alpha_vantage" in configuration_text
        assert "!secret alpha_vantage_api_key" in configuration_text
    finally:
        _cleanup_case_dir(case_dir)
