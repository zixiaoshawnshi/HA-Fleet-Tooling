"""Deploy module: push rendered site config to a remote HAOS device over SSH,
with a Home Assistant-native backup as a pre-deploy safety net.

See ha_fleet/deploy/orchestrator.py for the actual sequencing.
"""

from ha_fleet.deploy.errors import DeployError
from ha_fleet.deploy.orchestrator import DeployResult, run_push, run_rollback, run_verify
from ha_fleet.deploy.target import DeployTarget

__all__ = [
    "DeployError",
    "DeployTarget",
    "DeployResult",
    "run_push",
    "run_rollback",
    "run_verify",
]
