"""WebSocket client for Home Assistant's backup API (generate/restore/list).

Home Assistant only exposes backup generation and restore over the WebSocket
API, not REST (homeassistant/components/backup/websocket.py). This implements
the same auth_required/auth/auth_ok handshake already proven working in this
project's hub.html and calendar.html panels, but as a synchronous client
suitable for a click-based CLI (not asyncio) — hence websocket-client rather
than aiohttp or HA's own async client.
"""

import json
from typing import Any, Dict, List, Optional

import websocket

from ha_fleet.deploy.errors import DeployError
from ha_fleet.deploy.target import DeployTarget

# Default local backup agent ID differs by install type (verified from HA
# 2026.3.1 source): Core/Container installs register "backup.local"
# (homeassistant/components/backup/backup.py), but real HAOS/Supervisor
# installs -- the actual production target for this project -- register
# "hassio.local" instead (homeassistant/components/hassio/backup.py:80,
# domain "hassio" + unique_id "local"). Default to the HAOS value.
DEFAULT_AGENT_ID = "hassio.local"

# Fallback used only when testing against a bare Core/Container dev
# container (e.g. this project's local `ha-fleet dev-site` containers),
# which never has "hassio.local" registered.
CORE_LOCAL_AGENT_ID = "backup.local"


class HAWebSocketClient:
    """Synchronous client for Home Assistant's WebSocket API."""

    def __init__(self, target: DeployTarget, timeout: float = 30.0) -> None:
        self._target = target
        self._timeout = timeout
        self._ws: Optional[websocket.WebSocket] = None
        self._msg_id = 1

    def connect(self) -> None:
        """Open the WebSocket connection and complete authentication."""
        self._ws = websocket.create_connection(self._target.ws_url, timeout=self._timeout)

        auth_required = json.loads(self._ws.recv())
        if auth_required.get("type") != "auth_required":
            raise DeployError(f"Unexpected first frame from {self._target.ws_url}: {auth_required}")

        self._ws.send(json.dumps({"type": "auth", "access_token": self._target.token}))
        auth_result = json.loads(self._ws.recv())
        if auth_result.get("type") == "auth_invalid":
            raise DeployError("Home Assistant rejected the access token (auth_invalid)")
        if auth_result.get("type") != "auth_ok":
            raise DeployError(f"Unexpected auth response: {auth_result}")

    def close(self) -> None:
        """Close the WebSocket connection, if open."""
        if self._ws is not None:
            self._ws.close()
            self._ws = None

    def __enter__(self) -> "HAWebSocketClient":
        self.connect()
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def call(self, msg_type: str, **kwargs: Any) -> Dict[str, Any]:
        """Send a command and block for its matching result frame."""
        if self._ws is None:
            raise DeployError("call() invoked before connect()")

        msg_id = self._msg_id
        self._msg_id += 1
        self._ws.send(json.dumps({"id": msg_id, "type": msg_type, **kwargs}))

        while True:
            frame = json.loads(self._ws.recv())
            if frame.get("id") != msg_id:
                # Ignore unrelated event frames (e.g. from a prior subscription).
                continue
            if frame.get("type") != "result":
                raise DeployError(f"Unexpected frame for {msg_type}: {frame}")
            if not frame.get("success", False):
                raise DeployError(f"{msg_type} failed: {frame.get('error')}")
            return frame.get("result") or {}

    def generate_backup(self, name: str, agent_id: str = DEFAULT_AGENT_ID) -> str:
        """
        Ask the device to generate a real, natively-restorable backup of its
        current state. Returns the backup_id.

        Verified from source (backup/websocket.py handle_create): this awaits
        the full backup creation before responding, so a single blocking call
        is correct -- no poll-for-completion is needed.
        """
        result = self.call(
            "backup/generate",
            agent_ids=[agent_id],
            name=name,
            include_homeassistant=True,
            include_database=True,
        )
        backup_id = result.get("backup_id")
        if not backup_id:
            raise DeployError(f"backup/generate did not return a backup_id: {result}")
        return str(backup_id)

    def restore_backup(self, backup_id: str, agent_id: str = DEFAULT_AGENT_ID) -> None:
        """Restore the device to a previously generated backup."""
        self.call(
            "backup/restore",
            backup_id=backup_id,
            agent_id=agent_id,
            restore_homeassistant=True,
            restore_database=True,
        )

    def list_backups(self) -> List[Dict[str, Any]]:
        """List backups known to the device."""
        result = self.call("backup/info")
        return list(result.get("backups", []))

    def delete_backup(self, backup_id: str) -> None:
        """Delete a backup from the device (used for retention cleanup)."""
        self.call("backup/delete", backup_id=backup_id)
