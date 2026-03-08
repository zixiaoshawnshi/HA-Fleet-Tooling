"""Tests for backup discovery ingestion."""

import io
import json
import shutil
import tarfile
import uuid
from pathlib import Path

import pytest

from ha_fleet.discovery.ingest import BackupDiscoveryIngestor

TEST_ROOT = Path("tests") / "_tmp"


def _new_case_dir() -> Path:
    case_dir = TEST_ROOT / f"case_{uuid.uuid4().hex}"
    case_dir.mkdir(parents=True, exist_ok=False)
    return case_dir


def _cleanup_case_dir(case_dir: Path) -> None:
    shutil.rmtree(case_dir, ignore_errors=True)


def _write_json_member(tar: tarfile.TarFile, name: str, payload: dict) -> None:
    data = json.dumps(payload).encode("utf-8")
    info = tarfile.TarInfo(name=name)
    info.size = len(data)
    tar.addfile(info, io.BytesIO(data))


def _build_registry_payloads() -> tuple[dict, dict, dict]:
    device_registry = {
        "data": {
            "devices": [
                {
                    "id": "dev1",
                    "name": "Thermostat",
                    "name_by_user": "Hallway Thermostat",
                    "manufacturer": "Nest",
                    "model": "T-2000",
                    "config_entries": ["cfg1"],
                    "connections": [["mac", "AA:BB:CC:DD:EE:FF"]],
                }
            ]
        }
    }
    entity_registry = {
        "data": {
            "entities": [
                {
                    "entity_id": "climate.hallway",
                    "platform": "nest",
                    "device_id": "dev1",
                    "unique_id": "private-uid",
                }
            ]
        }
    }
    config_entries = {
        "data": {
            "entries": [
                {
                    "entry_id": "cfg1",
                    "domain": "nest",
                    "title": "Nest Account",
                    "source": "user",
                    "data": {"access_token": "secret"},
                }
            ]
        }
    }
    return device_registry, entity_registry, config_entries


def test_ingest_reads_nested_tar_and_sanitizes() -> None:
    """Ingestor should read nested homeassistant tar and strip sensitive fields."""
    case_dir = _new_case_dir()
    try:
        backup_path = case_dir / "backup.tar.gz"
        device_registry, entity_registry, config_entries = _build_registry_payloads()

        nested_buffer = io.BytesIO()
        with tarfile.open(fileobj=nested_buffer, mode="w:gz") as nested:
            _write_json_member(nested, ".storage/core.device_registry", device_registry)
            _write_json_member(nested, ".storage/core.entity_registry", entity_registry)
            _write_json_member(nested, ".storage/core.config_entries", config_entries)
        nested_bytes = nested_buffer.getvalue()

        with tarfile.open(backup_path, "w:gz") as outer:
            info = tarfile.TarInfo(name="homeassistant.tar.gz")
            info.size = len(nested_bytes)
            outer.addfile(info, io.BytesIO(nested_bytes))

        snapshot = BackupDiscoveryIngestor().ingest(backup_path, site_id="site_001")

        assert snapshot["counts"]["devices"] == 1
        assert snapshot["counts"]["entities"] == 1
        assert snapshot["counts"]["config_entries"] == 1
        assert snapshot["devices"][0]["name"] == "Hallway Thermostat"
        assert "connections" not in snapshot["devices"][0]
        assert "unique_id" not in snapshot["entities"][0]
    finally:
        _cleanup_case_dir(case_dir)


def test_ingest_fails_if_no_registry_files() -> None:
    """Ingestor should fail fast when backup does not include registry files."""
    case_dir = _new_case_dir()
    try:
        backup_path = case_dir / "empty_backup.tar.gz"
        with tarfile.open(backup_path, "w:gz"):
            pass

        with pytest.raises(FileNotFoundError):
            BackupDiscoveryIngestor().ingest(backup_path, site_id="site_001")
    finally:
        _cleanup_case_dir(case_dir)
