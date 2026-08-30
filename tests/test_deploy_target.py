"""Tests for DeployTarget config loading and token precedence."""

import os
import shutil
import uuid
from pathlib import Path

import pytest

from ha_fleet.deploy.errors import DeployError
from ha_fleet.deploy.target import TOKEN_ENV_VAR, DeployTarget

TEST_ROOT = Path("tests") / "_tmp"


def _new_case_dir() -> Path:
    case_dir = TEST_ROOT / f"case_{uuid.uuid4().hex}"
    case_dir.mkdir(parents=True, exist_ok=False)
    return case_dir


def _cleanup_case_dir(case_dir: Path) -> None:
    shutil.rmtree(case_dir, ignore_errors=True)


def _write_target_config(site_dir: Path, extra: str = "") -> None:
    (site_dir / "operator").mkdir(parents=True, exist_ok=True)
    (site_dir / "operator" / "deploy_target.local.yaml").write_text(
        f"""host: "100.1.2.3"
ssh_key_path: "~/.ssh/id_test"
{extra}
""",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _clear_token_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(TOKEN_ENV_VAR, raising=False)


def test_load_raises_when_config_missing() -> None:
    case_dir = _new_case_dir()
    try:
        with pytest.raises(DeployError, match="No deploy target config"):
            DeployTarget.load(case_dir)
    finally:
        _cleanup_case_dir(case_dir)


def test_load_raises_when_no_token_available() -> None:
    case_dir = _new_case_dir()
    try:
        _write_target_config(case_dir)
        with pytest.raises(DeployError, match="No access token"):
            DeployTarget.load(case_dir)
    finally:
        _cleanup_case_dir(case_dir)


def test_token_precedence_env_var_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    case_dir = _new_case_dir()
    try:
        _write_target_config(case_dir, extra="token: file-token")
        monkeypatch.setenv(TOKEN_ENV_VAR, "env-token")

        target = DeployTarget.load(case_dir)

        assert target.token == "env-token"
    finally:
        _cleanup_case_dir(case_dir)


def test_token_precedence_token_file_over_embedded() -> None:
    case_dir = _new_case_dir()
    try:
        _write_target_config(case_dir, extra="token: file-token")
        token_file = case_dir / "token.txt"
        token_file.write_text("token-file-value\n", encoding="utf-8")

        target = DeployTarget.load(case_dir, token_file=token_file)

        assert target.token == "token-file-value"
    finally:
        _cleanup_case_dir(case_dir)


def test_token_precedence_embedded_last_resort() -> None:
    case_dir = _new_case_dir()
    try:
        _write_target_config(case_dir, extra="token: embedded-token")

        target = DeployTarget.load(case_dir)

        assert target.token == "embedded-token"
    finally:
        _cleanup_case_dir(case_dir)


def test_load_defaults_ssh_user_and_port() -> None:
    case_dir = _new_case_dir()
    try:
        _write_target_config(case_dir, extra="token: t")

        target = DeployTarget.load(case_dir)

        assert target.ssh_user == "root"
        assert target.ha_port == 8123
        assert target.base_url == "http://100.1.2.3:8123"
        assert target.ws_url == "ws://100.1.2.3:8123/api/websocket"
    finally:
        _cleanup_case_dir(case_dir)
