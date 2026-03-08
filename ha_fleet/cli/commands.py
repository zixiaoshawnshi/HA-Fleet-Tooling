"""CLI commands for ha-fleet."""

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
