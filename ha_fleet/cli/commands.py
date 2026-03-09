"""CLI commands for ha-fleet."""

import shutil
import subprocess
from pathlib import Path
from typing import Optional

import click
import yaml

from ha_fleet.backup.haos import HAOSBackupGenerator
from ha_fleet.bundles.engine import BundleEngine
from ha_fleet.discovery.ingest import BackupDiscoveryIngestor
from ha_fleet.render.config import ConfigRenderer
from ha_fleet.schemas.bundle import BundleDefinition
from ha_fleet.schemas.site import SiteManifest


def _load_manifest(site_dir: Path) -> SiteManifest:
    """Load and validate site manifest."""
    manifest_path = site_dir / "site_manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"site_manifest.yaml not found in {site_dir}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = yaml.safe_load(f)
    return SiteManifest(**manifest_data)


def _load_bundle_definition(site_dir: Path, bundle_name: str) -> BundleDefinition:
    """Load bundle definition from supported paths."""
    bundle_file = site_dir / "bundles" / bundle_name / "bundle.yaml"
    if not bundle_file.exists():
        bundle_file = site_dir / "bundles" / f"{bundle_name}.yaml"
    if not bundle_file.exists():
        raise FileNotFoundError(
            f"Bundle definition not found for '{bundle_name}' "
            f"(expected bundles/{bundle_name}/bundle.yaml or bundles/{bundle_name}.yaml)"
        )

    with open(bundle_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    data.setdefault("name", bundle_name)
    return BundleDefinition(**data)


def _default_build_path(site_dir: Path) -> Path:
    """Infer a build output directory from a site path."""
    if site_dir.parent.name == "sites":
        return site_dir.parent.parent / "build" / site_dir.name
    return site_dir / "build"


def _render_site(site_dir: Path, output_dir: Path, enable_draft_dashboard: bool = False) -> SiteManifest:
    """Render a site into an output directory and return its manifest."""
    manifest = _load_manifest(site_dir)

    click.echo(f"OK Loaded manifest: {manifest.display_name}")
    click.echo(f"OK Bundles: {', '.join(manifest.bundles)}")

    renderer = ConfigRenderer(manifest, site_dir)
    renderer.write_to_dir(
        output_dir,
        format="yaml",
        include_dev_draft_dashboard=enable_draft_dashboard,
    )
    click.echo(f"OK Rendered to {output_dir}")
    return manifest


def _copy_operator_secrets(site_dir: Path, build_dir: Path, refresh: bool) -> None:
    """Copy local operator mock secrets into build config, if present."""
    secrets_example = site_dir / "operator" / "secrets.local.example.yaml"
    secrets_target = build_dir / "secrets.yaml"
    if not secrets_example.exists():
        click.echo(f"Note: no operator secrets template at {secrets_example}")
        return

    if refresh or not secrets_target.exists():
        secrets_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(secrets_example, secrets_target)
        click.echo(f"OK Copied local mock secrets to {secrets_target}")


def _ensure_docker_available() -> None:
    """Ensure docker exists on PATH."""
    if shutil.which("docker") is None:
        raise RuntimeError("docker command not found on PATH")


def _docker_capture(args: list[str]) -> str:
    """Run a docker command and return stdout."""
    result = subprocess.run(["docker", *args], check=False, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout).strip())
    return result.stdout.strip()


def _docker_stream(args: list[str]) -> None:
    """Run a docker command attached to current terminal streams."""
    result = subprocess.run(["docker", *args], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"docker {' '.join(args)} failed with code {result.returncode}")


def _container_exists(container_name: str) -> bool:
    """Check whether a docker container exists."""
    output = _docker_capture(["ps", "-a", "--filter", f"name=^/{container_name}$", "--format", "{{.Names}}"])
    return output == container_name


def _remove_container_if_exists(container_name: str) -> None:
    """Remove existing container if present."""
    if _container_exists(container_name):
        _docker_capture(["rm", "-f", container_name])


@click.command()
@click.option(
    "--site-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to site directory",
)
@click.option("--strict", is_flag=True, help="Strict validation mode")
def validate(site_path: str, strict: bool) -> None:
    """Validate site manifest and bundle compatibility."""
    site_dir = Path(site_path)

    try:
        manifest = _load_manifest(site_dir)
        click.echo("OK Manifest schema valid")
        click.echo(f"  Site: {manifest.display_name} ({manifest.site_id})")
        click.echo(f"  Bundles: {', '.join(manifest.bundles)}")
        click.echo(f"  Required secrets: {len(manifest.required_secrets)}")
        click.echo(f"  Required entities: {len(manifest.required_entities)}")

        engine = BundleEngine()
        load_warnings: list[str] = []

        for bundle_name in manifest.bundles:
            try:
                definition = _load_bundle_definition(site_dir, bundle_name)
                engine.load_bundle(definition)
            except Exception as exc:
                load_warnings.append(str(exc))

        is_valid, composition_warnings = engine.validate_composition(manifest.bundles)

        capability_warnings: list[str] = []
        for bundle_name in manifest.bundles:
            bundle_def = engine.bundles.get(bundle_name)
            if not bundle_def:
                continue
            for cap_name, required_state in bundle_def.requires_capabilities.items():
                actual_state = getattr(manifest.capabilities, cap_name, None)
                if actual_state is None:
                    capability_warnings.append(
                        f"Bundle '{bundle_name}' requires capability '{cap_name}', "
                        "but it is not defined in manifest capabilities"
                    )
                elif actual_state != required_state:
                    capability_warnings.append(
                        f"Bundle '{bundle_name}' requires capability '{cap_name}={required_state}', "
                        f"but manifest has '{cap_name}={actual_state}'"
                    )

        all_warnings = load_warnings + composition_warnings + capability_warnings
        if all_warnings:
            click.echo("Warnings:")
            for warning in all_warnings:
                click.echo(f"  - {warning}")

        if strict and (not is_valid or all_warnings):
            click.echo("Validation failed in strict mode", err=True)
            raise click.exceptions.Exit(1)

        click.echo("OK Validation passed")
    except Exception as e:
        click.echo(f"Validation failed: {e}", err=True)
        raise click.exceptions.Exit(1)


@click.command()
@click.option(
    "--site-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to site directory",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(),
    help="Output directory for rendered configs",
)
@click.option(
    "--format",
    default="yaml",
    type=click.Choice(["yaml", "json"]),
    help="Output format",
)
def render(site_path: str, output: str, format: str) -> None:
    """Render bundles + overlays into HAOS config files."""
    site_dir = Path(site_path)
    output_dir = Path(output)

    try:
        manifest = _load_manifest(site_dir)

        click.echo(f"OK Loaded manifest: {manifest.display_name}")
        click.echo(f"OK Bundles: {', '.join(manifest.bundles)}")

        renderer = ConfigRenderer(manifest, site_dir)
        renderer.write_to_dir(output_dir, format=format)

        click.echo(f"OK Rendered to {output_dir}")

    except Exception as e:
        click.echo(f"Render failed: {e}", err=True)
        raise click.exceptions.Exit(1)


@click.command()
@click.option(
    "--site-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to site directory",
)
@click.option(
    "--output",
    required=True,
    type=click.Path(),
    help="Output backup file (.tar.gz)",
)
@click.option("--exclude-media", is_flag=True, help="Exclude media files from backup")
@click.option(
    "--exclude-history",
    default=None,
    type=str,
    help="Exclude history older than this (e.g., '7d')",
)
def bundle_to_backup(
    site_path: str, output: str, exclude_media: bool, exclude_history: Optional[str]
) -> None:
    """Generate HAOS backup artifact from rendered config."""
    site_dir = Path(site_path)
    output_path = Path(output)

    try:
        manifest = _load_manifest(site_dir)

        click.echo(f"OK Loaded manifest: {manifest.display_name}")
        click.echo("OK Rendering bundles...")

        generator = HAOSBackupGenerator(manifest, site_dir)
        result = generator.generate(
            output_path,
            exclude_media=exclude_media,
            exclude_history=exclude_history,
        )

        click.echo(f"OK Generated backup: {output_path}")
        click.echo(f"  Size: {result['file_size_mb']} MB")
        click.echo(f"  Checksum: {result['checksum']}")
        click.echo(f"  Backup ID: {result['backup_id']}")

    except Exception as e:
        click.echo(f"Backup generation failed: {e}", err=True)
        raise click.exceptions.Exit(1)


@click.command()
@click.option(
    "--site-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to site directory",
)
@click.option(
    "--from-version",
    default=None,
    type=str,
    help="Version to diff from (defaults to last deployed)",
)
def diff(site_path: str, from_version: Optional[str]) -> None:
    """Show changes since last deployment."""
    click.echo("diff is not implemented yet", err=True)
    click.echo(f"site_path={site_path}, from_version={from_version}", err=True)
    raise click.exceptions.Exit(2)


@click.command(name="ingest-backup")
@click.option(
    "--site-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to site directory",
)
@click.option(
    "--backup",
    required=True,
    type=click.Path(exists=True, dir_okay=False),
    help="Path to HA backup tar/tar.gz file",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Output snapshot file path (default: <site>/discovery/latest.yaml)",
)
def ingest_backup(site_path: str, backup: str, output: Optional[str]) -> None:
    """Ingest discovery data from an HA backup and write a sanitized snapshot."""
    site_dir = Path(site_path)
    backup_path = Path(backup)
    output_path = Path(output) if output else site_dir / "discovery" / "latest.yaml"

    try:
        manifest = _load_manifest(site_dir)
        ingestor = BackupDiscoveryIngestor()
        snapshot = ingestor.ingest(
            backup_path=backup_path,
            site_id=manifest.site_id,
            backup_filename=backup_path.name,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(snapshot, f, sort_keys=False)

        click.echo(f"OK Ingested backup: {backup_path}")
        click.echo(f"OK Wrote discovery snapshot: {output_path}")
        click.echo(f"  Devices: {snapshot['counts']['devices']}")
        click.echo(f"  Entities: {snapshot['counts']['entities']}")
        click.echo(f"  Config entries: {snapshot['counts']['config_entries']}")
    except Exception as e:
        click.echo(f"Ingest failed: {e}", err=True)
        raise click.exceptions.Exit(1)


@click.command(name="ingest-config-dir")
@click.option(
    "--site-path",
    required=True,
    type=click.Path(exists=True),
    help="Path to site directory",
)
@click.option(
    "--config-dir",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to Home Assistant config directory containing .storage/",
)
@click.option(
    "--output",
    default=None,
    type=click.Path(),
    help="Output snapshot file path (default: <site>/discovery/latest.yaml)",
)
def ingest_config_dir(site_path: str, config_dir: str, output: Optional[str]) -> None:
    """Ingest discovery data from a local Home Assistant config directory."""
    site_dir = Path(site_path)
    config_dir_path = Path(config_dir)
    output_path = Path(output) if output else site_dir / "discovery" / "latest.yaml"

    try:
        manifest = _load_manifest(site_dir)
        ingestor = BackupDiscoveryIngestor()
        snapshot = ingestor.ingest_config_dir(
            config_dir=config_dir_path,
            site_id=manifest.site_id,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(snapshot, f, sort_keys=False)

        click.echo(f"OK Ingested config dir: {config_dir_path}")
        click.echo(f"OK Wrote discovery snapshot: {output_path}")
        click.echo(f"  Devices: {snapshot['counts']['devices']}")
        click.echo(f"  Entities: {snapshot['counts']['entities']}")
        click.echo(f"  Config entries: {snapshot['counts']['config_entries']}")
    except Exception as e:
        click.echo(f"Ingest config-dir failed: {e}", err=True)
        raise click.exceptions.Exit(1)


@click.command(name="new-site")
@click.option(
    "--sites-root",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to sites directory (e.g., ./sites)",
)
@click.option("--site-id", required=True, type=str, help="Site identifier (e.g., site_003)")
@click.option(
    "--display-name",
    default=None,
    type=str,
    help="Display name (default: derived from site-id)",
)
@click.option("--hardware-class", default="lenovo_tiny", type=str, help="Hardware class value")
@click.option("--runtime", default="haos_bare_metal", type=str, help="Runtime value")
@click.option("--dry-run", is_flag=True, help="Print planned files and directories only")
def new_site(
    sites_root: str,
    site_id: str,
    display_name: Optional[str],
    hardware_class: str,
    runtime: str,
    dry_run: bool,
) -> None:
    """Scaffold a new site directory with standard files."""
    try:
        if not all(c.isalnum() or c in {"_", "-"} for c in site_id):
            raise ValueError("site-id may only contain letters, numbers, underscores, and hyphens")

        sites_root_path = Path(sites_root)
        site_path = sites_root_path / site_id
        if site_path.exists():
            raise FileExistsError(f"Site already exists: {site_path}")

        resolved_display_name = display_name or site_id.replace("_", " ").replace("-", " ")

        directories = [
            site_path,
            site_path / "bundles",
            site_path / "overlays",
            site_path / "dashboards",
            site_path / "operator",
            site_path / "discovery",
        ]
        files = {
            site_path / "site_manifest.yaml": f"""site_id: {site_id}
display_name: {resolved_display_name}

hardware_class: {hardware_class}
runtime: {runtime}

bundles: []

capabilities:
  zigbee: false
  mqtt: false
  google_calendar: false

addons: []

required_entities: []
optional_entities: []

required_secrets: []
optional_secrets: []
""",
            site_path / "secrets_contract.yaml": f"""required: []
optional: []
description: Secrets contract for {site_id}
""",
            site_path / "overlays" / "README.md": f"""# Site-specific automation overlays for {site_id}.
# Files matching automations_*.yaml are appended by renderer.
# Optional dashboard overlays live under overlays/dashboards/*.yaml and
# override dashboards with matching relative paths from ../dashboards.
""",
            site_path / "dashboards" / "ui-lovelace.yaml": f"""title: {resolved_display_name}
views:
  - title: Home
    path: home
    icon: mdi:home-assistant
    cards:
      - type: markdown
        title: Fleet Dashboard
        content: |
          Replace this view with site-specific cards.
""",
            site_path / "operator" / "secrets.local.example.yaml": f"""# Operator-only local secrets for dashboard and automation preview.
# Copy this file to build/{site_id}/secrets.yaml before launching local HA.
""",
            site_path / "discovery" / "README.md": f"""# Discovery snapshots

This folder stores operator-ingested discovery snapshots from edge HA backups.

- Primary file: `latest.yaml`
- Generated by:
  - `ha-fleet ingest-backup --site-path ./sites/{site_id} --backup <backup.tar.gz>`

Do not place secrets in this folder.
""",
        }

        if dry_run:
            click.echo(f"[dry-run] Would create site scaffold at {site_path}")
            for directory in directories:
                click.echo(f"[dry-run] mkdir {directory}")
            for file_path in files:
                click.echo(f"[dry-run] write {file_path}")
            return

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        for file_path, content in files.items():
            file_path.write_text(content, encoding="utf-8")

        click.echo(f"OK Created new site scaffold: {site_id}")
        click.echo(f"  Path: {site_path}")
    except Exception as e:
        click.echo(f"New site creation failed: {e}", err=True)
        raise click.exceptions.Exit(1)


@click.command(name="dev-site")
@click.option(
    "--site-path",
    required=True,
    type=click.Path(exists=True, file_okay=False),
    help="Path to site directory",
)
@click.option(
    "--action",
    default="up",
    type=click.Choice(["up", "down", "restart", "render", "logs"]),
    help="Action for local site development",
)
@click.option(
    "--build-path",
    default=None,
    type=click.Path(),
    help="Build output directory (default: inferred from site path)",
)
@click.option("--port", default=8123, type=int, help="Host port for container")
@click.option(
    "--image",
    default="ghcr.io/home-assistant/home-assistant:stable",
    type=str,
    help="Docker image for local Home Assistant",
)
@click.option(
    "--container-name",
    default=None,
    type=str,
    help="Container name (default: ha-fleet-dev-<site-id>)",
)
@click.option(
    "--refresh-secrets",
    is_flag=True,
    help="Overwrite build secrets.yaml from operator template every run",
)
@click.option(
    "--enable-draft-dashboard",
    is_flag=True,
    help="Add an editable 'Fleet Draft' storage dashboard for UI authoring in local dev",
)
def dev_site(
    site_path: str,
    action: str,
    build_path: Optional[str],
    port: int,
    image: str,
    container_name: Optional[str],
    refresh_secrets: bool,
    enable_draft_dashboard: bool,
) -> None:
    """Render and run a local Home Assistant dev container for a site."""
    site_dir = Path(site_path)
    resolved_build_path = Path(build_path) if build_path else _default_build_path(site_dir)
    resolved_container_name = container_name or f"ha-fleet-dev-{site_dir.name}"

    try:
        if action in {"up", "restart", "render"}:
            _render_site(
                site_dir,
                resolved_build_path,
                enable_draft_dashboard=enable_draft_dashboard,
            )
            _copy_operator_secrets(site_dir, resolved_build_path, refresh_secrets)
            if action == "render":
                return

        _ensure_docker_available()

        if action == "down":
            _remove_container_if_exists(resolved_container_name)
            click.echo(f"OK Container removed: {resolved_container_name}")
            return

        if action == "logs":
            _docker_stream(["logs", "-f", resolved_container_name])
            return

        # up / restart
        _remove_container_if_exists(resolved_container_name)
        host_config_path = str(resolved_build_path.resolve())
        _docker_capture(
            [
                "run",
                "-d",
                "--name",
                resolved_container_name,
                "-p",
                f"{port}:8123",
                "-v",
                f"{host_config_path}:/config",
                image,
            ]
        )
        click.echo(f"OK Started {resolved_container_name} on http://localhost:{port}")
    except Exception as e:
        click.echo(f"Dev site action failed: {e}", err=True)
        raise click.exceptions.Exit(1)
