"""HAOS backup generation."""

import json
import tarfile
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional
import uuid
import yaml
from ha_fleet.schemas.site import SiteManifest
from ha_fleet.render.config import ConfigRenderer


class HAOSBackupGenerator:
    """Generate HAOS-compatible backup artifacts."""

    def __init__(self, site_manifest: SiteManifest, site_path: Path) -> None:
        """
        Initialize backup generator.

        Args:
            site_manifest: Loaded site manifest
            site_path: Root path to site directory
        """
        self.manifest = site_manifest
        self.site_path = site_path
        self.renderer = ConfigRenderer(site_manifest, site_path)

    def _create_backup_metadata(
        self, exclude_media: bool, exclude_history: Optional[str]
    ) -> Dict[str, Any]:
        """Create backup.json metadata."""
        backup_id = str(uuid.uuid4())
        return {
            "version": 1,
            "key": backup_id,
            "name": f"{self.manifest.site_id}_backup",
            "date": datetime.utcnow().isoformat(),
            "type": "full",
            "protected": False,
            "compressed": True,
            "includes": {
                "homeassistant": True,
                "database": False,
                "addons": [],
                "folders": ["config"],
            },
            "ha_fleet_options": {
                "exclude_media": exclude_media,
                "exclude_history": exclude_history,
            },
        }

    def _create_ha_config_snapshot(self, rendered_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create homeassistant.json config snapshot."""
        return {
            "version": "2024.1.0",  # HAOS version
            "name": self.manifest.display_name,
            "latitude": 0.0,
            "longitude": 0.0,
            "elevation": 0,
            "unit_system": "metric",
            "time_zone": "UTC",
            "external_url": None,
            "internal_url": None,
            "currency": "USD",
            "customize": {},
            "default_config": True,
        }

    def generate(
        self,
        output_path: Path,
        exclude_media: bool = False,
        exclude_history: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate HAOS backup artifact.

        Creates a .tar.gz file with HAOS backup structure:
        - backup.json (metadata)
        - homeassistant.json (config snapshot)
        - automations.yaml (rendered automations)
        - scripts.yaml (rendered scripts)
        - input_booleans.yaml (rendered input helpers)
        - config/ (subdirectory for additional configs)

        Args:
            output_path: Path where backup .tar.gz will be created

        Returns:
            Dict with backup metadata (size, checksum, etc.)
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Render all config
        rendered_config = self.renderer.render_all()

        # Create temporary directory for backup contents
        backup_temp_dir = output_path.parent / f".backup_temp_{uuid.uuid4()}"
        backup_temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Write backup.json
            backup_meta = self._create_backup_metadata(
                exclude_media=exclude_media,
                exclude_history=exclude_history,
            )
            with open(backup_temp_dir / "backup.json", "w") as f:
                json.dump(backup_meta, f, indent=2)

            # Write homeassistant.json
            ha_config = self._create_ha_config_snapshot(rendered_config)
            with open(backup_temp_dir / "homeassistant.json", "w") as f:
                json.dump(ha_config, f, indent=2)

            # Write config files
            for section_name, config_data in rendered_config.items():
                if not config_data:
                    continue

                config_file = backup_temp_dir / f"{section_name}.yaml"
                with open(config_file, "w") as f:
                    yaml.dump(config_data, f, default_flow_style=False)

            # Create tar.gz archive
            with tarfile.open(output_path, "w:gz") as tar:
                tar.add(backup_temp_dir, arcname=".")

            # Calculate checksum
            sha256_sum = self._calculate_sha256(output_path)

            # Get file size
            file_size = output_path.stat().st_size

            result = {
                "backup_file": str(output_path),
                "file_size": file_size,
                "file_size_mb": round(file_size / (1024 * 1024), 2),
                "checksum": sha256_sum,
                "backup_id": backup_meta["key"],
                "timestamp": backup_meta["date"],
                "site_id": self.manifest.site_id,
            }

            return result

        finally:
            # Cleanup temp directory
            import shutil

            if backup_temp_dir.exists():
                shutil.rmtree(backup_temp_dir)

    def _calculate_sha256(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
