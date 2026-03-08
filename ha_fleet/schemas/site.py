"""Site manifest schema."""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class Capability(BaseModel):
    """Hardware/integration capability."""

    zigbee: bool = False
    mqtt: bool = False
    google_calendar: bool = False
    bt_proxy: bool = False


class BackupConfig(BaseModel):
    """Backup configuration for site."""

    estimated_size: str = "300-500MB"
    exclude_media: bool = True
    exclude_history: str = "7d"


class SiteManifest(BaseModel):
    """Site manifest schema for deployment."""

    site_id: str = Field(..., description="Unique site identifier")
    display_name: str = Field(..., description="Human-readable site name")
    hardware_class: str = Field("lenovo_tiny", description="Hardware class")
    runtime: str = Field("haos_bare_metal", description="Runtime (haos_bare_metal)")
    bundles: List[str] = Field(default_factory=list, description="Bundle names")
    capabilities: Capability = Field(default_factory=Capability)
    addons: List[str] = Field(default_factory=list, description="HAOS addons")
    required_entities: List[str] = Field(default_factory=list)
    optional_entities: List[str] = Field(default_factory=list)
    required_secrets: List[str] = Field(default_factory=list)
    optional_secrets: List[str] = Field(default_factory=list)
    backup: BackupConfig = Field(default_factory=BackupConfig)

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "site_id": "site_001",
                "display_name": "Ottawa Pilot Home",
                "hardware_class": "lenovo_tiny",
                "runtime": "haos_bare_metal",
                "bundles": ["routine", "tasks", "transit"],
                "capabilities": {
                    "zigbee": True,
                    "mqtt": True,
                    "google_calendar": True,
                },
                "addons": ["zigbee2mqtt", "mosquitto", "google_calendar"],
                "required_entities": [
                    "input_boolean.morning_routine",
                    "calendar.google_calendar",
                ],
                "optional_entities": ["sensor.bus_eta"],
                "required_secrets": ["notify_mobile_target", "google_calendar_api_key"],
                "optional_secrets": ["zigbee_backup_password"],
            }
        }
