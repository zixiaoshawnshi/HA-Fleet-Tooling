"""Deploy target configuration: how to reach a remote edge device."""

import os
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field

from ha_fleet.deploy.errors import DeployError

TOKEN_ENV_VAR = "HA_FLEET_DEPLOY_TOKEN"


class DeployTarget(BaseModel):
    """Connection details for a remote HAOS device."""

    host: str = Field(..., description="Tailscale IP or MagicDNS hostname")
    ssh_user: str = Field("root", description="SSH user (must be root for SFTP on Terminal & SSH add-on)")
    ssh_key_path: str = Field(..., description="Path to the SSH private key")
    ha_port: int = Field(8123, description="Home Assistant HTTP port")
    token: str = Field(..., description="Long-lived access token")

    @property
    def base_url(self) -> str:
        """Base HTTP URL for the device's Home Assistant API."""
        return f"http://{self.host}:{self.ha_port}"

    @property
    def ws_url(self) -> str:
        """WebSocket URL for the device's Home Assistant API."""
        return f"ws://{self.host}:{self.ha_port}/api/websocket"

    @property
    def resolved_ssh_key_path(self) -> Path:
        """SSH key path with ~ expanded."""
        return Path(self.ssh_key_path).expanduser()

    @classmethod
    def load(
        cls,
        site_dir: Path,
        token_override: Optional[str] = None,
        token_file: Optional[Path] = None,
    ) -> "DeployTarget":
        """
        Load deploy target config for a site.

        Token resolution precedence:
          1. `token_override` (e.g. from HA_FLEET_DEPLOY_TOKEN env var)
          2. `token_file` (e.g. from --token-file)
          3. `token:` embedded in deploy_target.local.yaml (last resort)

        A bare CLI --token value is deliberately not a supported path here
        (shell history exposure) — callers should read HA_FLEET_DEPLOY_TOKEN
        or pass --token-file instead.
        """
        config_path = site_dir / "operator" / "deploy_target.local.yaml"
        if not config_path.exists():
            raise DeployError(
                f"No deploy target config found at {config_path}. "
                f"Copy operator/deploy_target.local.example.yaml to deploy_target.local.yaml "
                f"and fill in your device's connection details."
            )

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        token = token_override or os.environ.get(TOKEN_ENV_VAR)
        if not token and token_file is not None:
            token = Path(token_file).read_text(encoding="utf-8").strip()
        if not token:
            token = data.get("token")
        if not token:
            raise DeployError(
                f"No access token found. Set {TOKEN_ENV_VAR}, pass --token-file, "
                f"or (last resort) add 'token:' to {config_path}."
            )

        return cls(
            host=data["host"],
            ssh_user=data.get("ssh_user", "root"),
            ssh_key_path=data["ssh_key_path"],
            ha_port=data.get("ha_port", 8123),
            token=token,
        )
