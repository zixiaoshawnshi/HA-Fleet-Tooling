"""Tests for bundle engine."""

import pytest
from ha_fleet.bundles.engine import BundleEngine
from ha_fleet.schemas.bundle import BundleDefinition


def test_bundle_engine_load() -> None:
    """Test loading bundles."""
    engine = BundleEngine()
    bundle = BundleDefinition(name="test_bundle")
    engine.load_bundle(bundle)
    assert "test_bundle" in engine.bundles


def test_bundle_composition_valid() -> None:
    """Test valid bundle composition."""
    engine = BundleEngine()
    routine = BundleDefinition(name="routine")
    tasks = BundleDefinition(name="tasks")
    engine.load_bundle(routine)
    engine.load_bundle(tasks)

    is_valid, warnings = engine.validate_composition(["routine", "tasks"])
    assert is_valid is True
    assert len(warnings) == 0


def test_bundle_missing_requirement() -> None:
    """Test bundle with missing requirement."""
    engine = BundleEngine()
    routine = BundleDefinition(name="routine", requires=["tasks"])
    engine.load_bundle(routine)

    is_valid, warnings = engine.validate_composition(["routine"])
    assert is_valid is False
    assert any("requires" in w for w in warnings)


def test_bundle_conflict() -> None:
    """Test conflicting bundles."""
    engine = BundleEngine()
    bundle1 = BundleDefinition(name="bundle1", conflicts=["bundle2"])
    bundle2 = BundleDefinition(name="bundle2")
    engine.load_bundle(bundle1)
    engine.load_bundle(bundle2)

    is_valid, warnings = engine.validate_composition(["bundle1", "bundle2"])
    assert is_valid is False
    assert any("conflicts" in w for w in warnings)
