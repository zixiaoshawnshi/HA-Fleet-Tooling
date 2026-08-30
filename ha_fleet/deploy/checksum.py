"""File manifest hashing for verifying a config push landed intact.

Only the pushed subtree is manifested — never all of /config, which also
holds HA's own runtime state (.storage/, home-assistant_v2.db, deps/) that
would show up as false "drift" on every single run.
"""

import hashlib
from pathlib import Path
from typing import Dict, List

from ha_fleet.deploy.errors import DeployError
from ha_fleet.deploy.target import DeployTarget
from ha_fleet.deploy.transport import ssh_run


def _sha256_file(path: Path) -> str:
    """Calculate SHA256 checksum of a single file."""
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def build_manifest(build_dir: Path) -> Dict[str, str]:
    """Build a relative-path -> sha256 manifest for every file under build_dir."""
    manifest: Dict[str, str] = {}
    for file_path in sorted(build_dir.rglob("*")):
        if file_path.is_file():
            rel_path = file_path.relative_to(build_dir).as_posix()
            manifest[rel_path] = _sha256_file(file_path)
    return manifest


def remote_manifest(target: DeployTarget, remote_dir: str, rel_paths: List[str]) -> Dict[str, str]:
    """
    Hash the given relative paths under remote_dir on the device over SSH.

    Uses python3 (guaranteed present, since HA itself runs on it) rather than
    sha256sum, since coreutils availability on the Terminal & SSH add-on's
    base image isn't guaranteed.
    """
    if not rel_paths:
        return {}

    script = (
        "import hashlib,sys\n"
        "for p in sys.argv[1:]:\n"
        "    h = hashlib.sha256()\n"
        "    try:\n"
        "        with open(p, 'rb') as f:\n"
        "            for chunk in iter(lambda: f.read(4096), b''):\n"
        "                h.update(chunk)\n"
        "        print(p, h.hexdigest())\n"
        "    except OSError as e:\n"
        "        print(p, 'ERROR', e, file=sys.stderr)\n"
    )
    remote_paths = " ".join(f"'{remote_dir.rstrip('/')}/{p}'" for p in rel_paths)
    remote_cmd = f"python3 -c \"{script}\" {remote_paths}"
    output = ssh_run(target, remote_cmd)

    manifest: Dict[str, str] = {}
    prefix = remote_dir.rstrip("/") + "/"
    for line in output.splitlines():
        parts = line.rsplit(" ", 1)
        if len(parts) != 2:
            continue
        remote_path, digest = parts
        if digest == "ERROR":
            continue
        rel_path = remote_path[len(prefix):] if remote_path.startswith(prefix) else remote_path
        manifest[rel_path] = digest
    return manifest


def diff_manifests(local: Dict[str, str], remote: Dict[str, str]) -> List[str]:
    """Return relative paths whose checksums don't match (or are missing remotely)."""
    mismatches = []
    for rel_path, local_hash in local.items():
        remote_hash = remote.get(rel_path)
        if remote_hash != local_hash:
            mismatches.append(rel_path)
    return mismatches


def verify_push(target: DeployTarget, build_dir: Path, remote_dir: str) -> None:
    """Raise DeployError if the pushed files don't match the local build."""
    local = build_manifest(build_dir)
    remote = remote_manifest(target, remote_dir, list(local.keys()))
    mismatches = diff_manifests(local, remote)
    if mismatches:
        raise DeployError(
            f"Checksum verification failed for {len(mismatches)} file(s) after push: "
            f"{', '.join(mismatches[:10])}" + (" ..." if len(mismatches) > 10 else "")
        )
