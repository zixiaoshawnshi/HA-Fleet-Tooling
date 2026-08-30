"""Tests for deploy checksum manifest helpers."""

import shutil
import uuid
from pathlib import Path
from unittest.mock import patch

from ha_fleet.deploy.checksum import build_manifest, diff_manifests, remote_manifest, verify_push
from ha_fleet.deploy.errors import DeployError
from ha_fleet.deploy.target import DeployTarget

TEST_ROOT = Path("tests") / "_tmp"


def _new_case_dir() -> Path:
    case_dir = TEST_ROOT / f"case_{uuid.uuid4().hex}"
    case_dir.mkdir(parents=True, exist_ok=False)
    return case_dir


def _cleanup_case_dir(case_dir: Path) -> None:
    shutil.rmtree(case_dir, ignore_errors=True)


def _target() -> DeployTarget:
    return DeployTarget(host="100.0.0.1", ssh_key_path="~/.ssh/id_test", token="tok")


def test_build_manifest_hashes_all_files() -> None:
    case_dir = _new_case_dir()
    try:
        (case_dir / "configuration.yaml").write_text("default_config:\n", encoding="utf-8")
        (case_dir / "sub").mkdir()
        (case_dir / "sub" / "automations.yaml").write_text("[]\n", encoding="utf-8")

        manifest = build_manifest(case_dir)

        assert set(manifest.keys()) == {"configuration.yaml", "sub/automations.yaml"}
        assert len(manifest["configuration.yaml"]) == 64
    finally:
        _cleanup_case_dir(case_dir)


def test_diff_manifests_flags_mismatches_and_missing() -> None:
    local = {"a.yaml": "hash_a", "b.yaml": "hash_b"}
    remote = {"a.yaml": "hash_a", "b.yaml": "different"}

    mismatches = diff_manifests(local, remote)

    assert mismatches == ["b.yaml"]


def test_diff_manifests_flags_missing_remote_file() -> None:
    local = {"a.yaml": "hash_a"}
    remote: dict = {}

    mismatches = diff_manifests(local, remote)

    assert mismatches == ["a.yaml"]


def test_remote_manifest_parses_ssh_output() -> None:
    target = _target()
    fake_output = "/config/configuration.yaml abc123\n/config/automations.yaml def456\n"

    with patch("ha_fleet.deploy.checksum.ssh_run", return_value=fake_output) as mock_ssh:
        result = remote_manifest(target, "/config", ["configuration.yaml", "automations.yaml"])

    mock_ssh.assert_called_once()
    assert result == {"configuration.yaml": "abc123", "automations.yaml": "def456"}


def test_remote_manifest_skips_error_lines() -> None:
    target = _target()
    fake_output = "/config/configuration.yaml abc123\n/config/missing.yaml ERROR\n"

    with patch("ha_fleet.deploy.checksum.ssh_run", return_value=fake_output):
        result = remote_manifest(target, "/config", ["configuration.yaml", "missing.yaml"])

    assert result == {"configuration.yaml": "abc123"}


def test_remote_manifest_empty_paths_skips_ssh_call() -> None:
    target = _target()

    with patch("ha_fleet.deploy.checksum.ssh_run") as mock_ssh:
        result = remote_manifest(target, "/config", [])

    mock_ssh.assert_not_called()
    assert result == {}


def test_verify_push_raises_on_mismatch() -> None:
    case_dir = _new_case_dir()
    try:
        (case_dir / "configuration.yaml").write_text("default_config:\n", encoding="utf-8")
        target = _target()

        with patch("ha_fleet.deploy.checksum.ssh_run", return_value="/config/configuration.yaml WRONGHASH\n"):
            try:
                verify_push(target, case_dir, "/config")
                assert False, "expected DeployError"
            except DeployError as e:
                assert "configuration.yaml" in str(e)
    finally:
        _cleanup_case_dir(case_dir)


def test_verify_push_passes_on_match() -> None:
    case_dir = _new_case_dir()
    try:
        (case_dir / "configuration.yaml").write_text("default_config:\n", encoding="utf-8")
        target = _target()
        local = build_manifest(case_dir)
        matching_hash = local["configuration.yaml"]

        with patch(
            "ha_fleet.deploy.checksum.ssh_run",
            return_value=f"/config/configuration.yaml {matching_hash}\n",
        ):
            verify_push(target, case_dir, "/config")  # should not raise
    finally:
        _cleanup_case_dir(case_dir)
