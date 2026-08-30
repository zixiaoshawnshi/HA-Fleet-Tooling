"""SSH/SCP transport for pushing rendered config to a remote device.

Shells out to the `ssh`/`scp` binaries (present via Windows' or Git's bundled
OpenSSH on operator machines, and universal on Linux/Mac) rather than adding
a paramiko dependency, mirroring this codebase's existing pattern of shelling
out to real binaries (see _docker_capture/_docker_stream in cli/commands.py).

rsync is deliberately not used: it isn't on PATH on the Windows operator setup
this project targets, and the rendered build directory is small enough that
rsync's delta-transfer wouldn't be a meaningful win anyway.
"""

import shutil
import subprocess
from pathlib import Path

from ha_fleet.deploy.errors import DeployError
from ha_fleet.deploy.target import DeployTarget

SSH_OPTS = ["-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10"]


def _ensure_ssh_available() -> None:
    """Ensure ssh and scp exist on PATH."""
    missing = [tool for tool in ("ssh", "scp") if shutil.which(tool) is None]
    if missing:
        raise DeployError(f"{' and '.join(missing)} not found on PATH")


def ssh_run(target: DeployTarget, remote_cmd: str) -> str:
    """Run a command on the remote device over SSH and return stdout."""
    _ensure_ssh_available()
    args = [
        "ssh",
        *SSH_OPTS,
        "-i",
        str(target.resolved_ssh_key_path),
        f"{target.ssh_user}@{target.host}",
        remote_cmd,
    ]
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise DeployError((result.stderr or result.stdout).strip())
    return result.stdout


def scp_push(target: DeployTarget, local_dir: Path, remote_dir: str) -> None:
    """Copy the contents of local_dir into remote_dir on the device over SCP."""
    _ensure_ssh_available()
    ssh_run(target, f"mkdir -p '{remote_dir}'")
    args = [
        "scp",
        *SSH_OPTS,
        "-i",
        str(target.resolved_ssh_key_path),
        "-r",
        f"{local_dir}/.",
        f"{target.ssh_user}@{target.host}:{remote_dir}",
    ]
    result = subprocess.run(args, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise DeployError((result.stderr or result.stdout).strip())
