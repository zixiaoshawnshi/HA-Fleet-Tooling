"""Ingest discovery data from HA backups."""

from __future__ import annotations

from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tarfile
from typing import Any, Dict


class BackupDiscoveryIngestor:
    """Extract and sanitize discovery data from Home Assistant backups."""

    REGISTRY_SUFFIXES = {
        "device_registry": "storage/core.device_registry",
        "entity_registry": "storage/core.entity_registry",
        "config_entries": "storage/core.config_entries",
    }

    def ingest(
        self,
        backup_path: Path,
        site_id: str,
        backup_filename: str | None = None,
    ) -> Dict[str, Any]:
        """Read a backup tarball and return a sanitized discovery snapshot."""
        registries: Dict[str, Dict[str, Any]] = {}
        with tarfile.open(backup_path, "r:*") as tar:
            self._collect_registries_from_tar(tar, registries, depth=0)

        if not registries:
            raise FileNotFoundError(
                "No supported HA registry files found in backup "
                "(expected .storage/core.device_registry, "
                ".storage/core.entity_registry, .storage/core.config_entries)"
            )

        devices = self._sanitize_devices(registries.get("device_registry"))
        entities = self._sanitize_entities(registries.get("entity_registry"))
        config_entries = self._sanitize_config_entries(registries.get("config_entries"))

        snapshot = {
            "snapshot_version": 1,
            "captured_at_utc": datetime.now(timezone.utc).isoformat(),
            "site_id": site_id,
            "source_backup": backup_filename or backup_path.name,
            "counts": {
                "devices": len(devices),
                "entities": len(entities),
                "config_entries": len(config_entries),
            },
            "devices": devices,
            "entities": entities,
            "config_entries": config_entries,
        }
        return snapshot

    def _collect_registries_from_tar(
        self,
        tar: tarfile.TarFile,
        registries: Dict[str, Dict[str, Any]],
        depth: int,
    ) -> None:
        """Collect known registry files from tar, traversing nested tar archives."""
        if depth > 2:
            return

        for member in tar.getmembers():
            if not member.isfile():
                continue

            member_name = member.name.lstrip("./")
            for registry_key, suffix in self.REGISTRY_SUFFIXES.items():
                if registry_key in registries:
                    continue
                if member_name.endswith(suffix):
                    payload = self._read_member_json(tar, member)
                    if payload is not None:
                        registries[registry_key] = payload

            if member_name.endswith((".tar.gz", ".tgz", ".tar")):
                nested_tar = self._open_nested_tar(tar, member)
                if nested_tar is None:
                    continue
                with nested_tar as nested:
                    self._collect_registries_from_tar(nested, registries, depth=depth + 1)

    def _open_nested_tar(self, tar: tarfile.TarFile, member: tarfile.TarInfo) -> tarfile.TarFile | None:
        """Open a nested tar member into a TarFile object."""
        extracted = tar.extractfile(member)
        if extracted is None:
            return None
        data = extracted.read()
        try:
            return tarfile.open(fileobj=io.BytesIO(data), mode="r:*")
        except tarfile.TarError:
            return None

    def _read_member_json(self, tar: tarfile.TarFile, member: tarfile.TarInfo) -> Dict[str, Any] | None:
        """Read and parse JSON content for a tar member."""
        extracted = tar.extractfile(member)
        if extracted is None:
            return None
        try:
            return json.load(extracted)
        except json.JSONDecodeError:
            return None

    def _extract_registry_items(self, registry_payload: Dict[str, Any] | None, item_key: str) -> list[Dict[str, Any]]:
        """Extract data list from Home Assistant registry JSON payload."""
        if not registry_payload:
            return []

        data = registry_payload.get("data")
        if not isinstance(data, dict):
            return []

        items = data.get(item_key)
        if not isinstance(items, list):
            return []

        return [item for item in items if isinstance(item, dict)]

    def _sanitize_devices(self, payload: Dict[str, Any] | None) -> list[Dict[str, Any]]:
        """Sanitize device registry entries."""
        devices = self._extract_registry_items(payload, "devices")
        sanitized = []
        for device in devices:
            sanitized.append(
                {
                    "id": device.get("id"),
                    "name": device.get("name_by_user") or device.get("name"),
                    "manufacturer": device.get("manufacturer"),
                    "model": device.get("model"),
                    "area_id": device.get("area_id"),
                    "config_entries": sorted(device.get("config_entries") or []),
                    "disabled_by": device.get("disabled_by"),
                }
            )
        return sorted(sanitized, key=lambda item: str(item.get("id") or ""))

    def _sanitize_entities(self, payload: Dict[str, Any] | None) -> list[Dict[str, Any]]:
        """Sanitize entity registry entries."""
        entities = self._extract_registry_items(payload, "entities")
        sanitized = []
        for entity in entities:
            sanitized.append(
                {
                    "entity_id": entity.get("entity_id"),
                    "platform": entity.get("platform"),
                    "device_id": entity.get("device_id"),
                    "original_name": entity.get("original_name"),
                    "area_id": entity.get("area_id"),
                    "disabled_by": entity.get("disabled_by"),
                    "hidden_by": entity.get("hidden_by"),
                }
            )
        return sorted(sanitized, key=lambda item: str(item.get("entity_id") or ""))

    def _sanitize_config_entries(self, payload: Dict[str, Any] | None) -> list[Dict[str, Any]]:
        """Sanitize config entry registry entries."""
        entries = self._extract_registry_items(payload, "entries")
        sanitized = []
        for entry in entries:
            sanitized.append(
                {
                    "entry_id": entry.get("entry_id"),
                    "domain": entry.get("domain"),
                    "title": entry.get("title"),
                    "source": entry.get("source"),
                    "state": entry.get("state"),
                }
            )
        return sorted(sanitized, key=lambda item: str(item.get("entry_id") or ""))
