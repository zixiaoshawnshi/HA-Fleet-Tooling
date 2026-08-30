"""REST client for Home Assistant's HTTP API (restart, health polling)."""

import time
from typing import Any, Dict, Optional

import requests

from ha_fleet.deploy.errors import DeployError
from ha_fleet.deploy.target import DeployTarget

DEFAULT_TIMEOUT = 10.0


def _headers(target: DeployTarget) -> Dict[str, str]:
    return {"Authorization": f"Bearer {target.token}", "Content-Type": "application/json"}


def restart(target: DeployTarget) -> None:
    """Trigger a full Home Assistant restart via the homeassistant.restart service."""
    url = f"{target.base_url}/api/services/homeassistant/restart"
    try:
        resp = requests.post(url, headers=_headers(target), json={}, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as err:
        raise DeployError(f"Failed to call restart service: {err}") from err
    if resp.status_code >= 400:
        raise DeployError(f"Restart service call failed: HTTP {resp.status_code} {resp.text}")


def wait_for_api(target: DeployTarget, timeout: float = 120.0, poll_interval: float = 3.0) -> None:
    """Poll GET /api/ until it responds, or raise DeployError on timeout."""
    url = f"{target.base_url}/api/"
    deadline = time.monotonic() + timeout
    last_error: Optional[str] = None

    while time.monotonic() < deadline:
        try:
            resp = requests.get(url, headers=_headers(target), timeout=DEFAULT_TIMEOUT)
            if resp.status_code == 200:
                return
            last_error = f"HTTP {resp.status_code}"
        except requests.RequestException as err:
            last_error = str(err)
        time.sleep(poll_interval)

    raise DeployError(f"Device did not come back online within {timeout}s (last error: {last_error})")


def get_state(target: DeployTarget, entity_id: str) -> Optional[Dict[str, Any]]:
    """Fetch an entity's current state, or None if it doesn't exist / errors out."""
    url = f"{target.base_url}/api/states/{entity_id}"
    try:
        resp = requests.get(url, headers=_headers(target), timeout=DEFAULT_TIMEOUT)
    except requests.RequestException:
        return None
    if resp.status_code != 200:
        return None
    return resp.json()
