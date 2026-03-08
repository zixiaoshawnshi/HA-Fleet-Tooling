"""Test fixtures and utilities."""

from ha_fleet.schemas.site import SiteManifest, Capability


def get_minimal_site_manifest() -> SiteManifest:
    """Return a minimal valid site manifest for tests."""
    return SiteManifest(
        site_id="test_site",
        display_name="Test Site",
        hardware_class="lenovo_tiny",
        runtime="haos_bare_metal",
        bundles=["routine"],
        capabilities=Capability(zigbee=True, mqtt=True),
        addons=["zigbee2mqtt", "mosquitto"],
        required_entities=["input_boolean.test"],
        required_secrets=["test_secret"],
    )


def get_full_site_manifest() -> SiteManifest:
    """Return a full site manifest with all fields."""
    return SiteManifest(
        site_id="site_001",
        display_name="Ottawa Pilot Home",
        hardware_class="lenovo_tiny",
        runtime="haos_bare_metal",
        bundles=["routine", "tasks", "transit"],
        capabilities=Capability(
            zigbee=True, mqtt=True, google_calendar=True
        ),
        addons=["zigbee2mqtt", "mosquitto", "google_calendar"],
        required_entities=[
            "input_boolean.morning_routine",
            "calendar.google_calendar",
        ],
        optional_entities=["sensor.bus_eta"],
        required_secrets=["notify_mobile_target", "google_calendar_api_key"],
        optional_secrets=["zigbee_backup_password"],
    )
