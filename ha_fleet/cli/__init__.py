"""CLI entry point for ha-fleet."""

import click
from ha_fleet.cli.commands import validate, render, bundle_to_backup, diff


@click.group()
@click.version_option(version="0.1.0")
def main() -> None:
    """Home Assistant fleet management CLI."""
    pass


main.add_command(validate)
main.add_command(render)
main.add_command(bundle_to_backup)
main.add_command(diff)

if __name__ == "__main__":
    main()
