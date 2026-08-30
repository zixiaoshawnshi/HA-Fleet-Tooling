"""Post-deploy health checks.

A single immediate check right after the API comes back isn't enough:
integrations with network dependencies (Zigbee coordinator re-init, MQTT
broker reconnect, Calendar OAuth refresh) finish reconnecting asynchronously
after Home Assistant itself reports "running". This polls with a settle
window instead of checking once.
"""

import time
from dataclasses import dataclass, field
from typing import List

from ha_fleet.deploy import rest_client
from ha_fleet.deploy.target import DeployTarget
from ha_fleet.schemas.site import SiteManifest

UNHEALTHY_STATES = {"unavailable", "unknown"}


@dataclass
class EntityHealth:
    """Health result for a single required entity."""

    entity_id: str
    ok: bool
    state: str | None = None


@dataclass
class HealthResult:
    """Overall health check result."""

    ok: bool
    entities: List[EntityHealth] = field(default_factory=list)

    @property
    def failures(self) -> List[EntityHealth]:
        return [e for e in self.entities if not e.ok]


def check_required_entities(
    target: DeployTarget,
    manifest: SiteManifest,
    timeout: float = 90.0,
    poll_interval: float = 5.0,
) -> HealthResult:
    """
    Poll each of the site's required_entities until they exist and are not
    unavailable/unknown, or until the timeout elapses.
    """
    required = manifest.required_entities
    if not required:
        return HealthResult(ok=True, entities=[])

    remaining = set(required)
    results: dict[str, EntityHealth] = {}
    deadline = time.monotonic() + timeout

    while remaining and time.monotonic() < deadline:
        for entity_id in list(remaining):
            state_obj = rest_client.get_state(target, entity_id)
            state = state_obj.get("state") if state_obj else None
            if state is not None and state not in UNHEALTHY_STATES:
                results[entity_id] = EntityHealth(entity_id=entity_id, ok=True, state=state)
                remaining.discard(entity_id)
        if remaining:
            time.sleep(poll_interval)

    for entity_id in remaining:
        state_obj = rest_client.get_state(target, entity_id)
        state = state_obj.get("state") if state_obj else None
        results[entity_id] = EntityHealth(entity_id=entity_id, ok=False, state=state)

    entities = [results[e] for e in required]
    return HealthResult(ok=all(e.ok for e in entities), entities=entities)
