# ha-fleet: Home Assistant Fleet Management Tooling

Lightweight Python package for managing Home Assistant OS (HAOS) fleet deployments across pilot homes.

## Quick Start

```bash
# Validate a site configuration
ha-fleet validate --site-path ./sites/site_001

# Render bundles + overlays into HAOS config
ha-fleet render --site-path ./sites/site_001 --output ./build/

# Generate HAOS backup artifact
ha-fleet bundle-to-backup --site-path ./sites/site_001 --output ./backup.tar.gz

# Show what changed (not implemented yet)
ha-fleet diff --site-path ./sites/site_001

# Ingest discovery snapshot from an edge backup
ha-fleet ingest-backup --site-path ./sites/site_001 --backup ./site_001_backup.tar.gz

# Ingest discovery snapshot from a local HA config directory
ha-fleet ingest-config-dir --site-path ./sites/site_001 --config-dir ./build/site_001

# Create a new site scaffold
ha-fleet new-site --sites-root ./sites --site-id site_003 --display-name "Pilot Site 003"

# Local operator dev loop (render and/or run Docker-backed HA preview)
ha-fleet dev-site --site-path ./sites/site_001 --action up --port 8123

```

## Current Scope

Implemented:
- Bundle composition and validation primitives
- Site manifest / bundle / secrets schemas
- Rendering for `automations`, `scripts`, and `input_booleans`
- Rendering for YAML dashboards (`dashboards/*.yaml` + `overlays/dashboards/*.yaml`)
- Auto-generated `configuration.yaml` with `lovelace.dashboards` registrations
- Backup artifact generation
- Backup ingestion for operator-side discovery snapshots
- Config-directory ingestion for operator-side discovery snapshots
- Site scaffolding and operator dev-loop commands
- CLI commands: `validate`, `render`, `bundle-to-backup`, `ingest-backup`, `ingest-config-dir`, `new-site`, `dev-site`

Not implemented yet:
- Real `diff` behavior
- Deployment execution CLI

## Installation

```bash
# Development
pip install -e ".[dev]"

# From GitHub
pip install git+https://github.com/zixiaoshawnshi/HA-Fleet-Tooling.git@main
```

## Commands

### validate

```bash
ha-fleet validate --site-path ./sites/site_001 --strict
```

### render

```bash
ha-fleet render --site-path ./sites/site_001 --output ./build/ --format yaml
```

### bundle-to-backup

```bash
ha-fleet bundle-to-backup --site-path ./sites/site_001 \
  --output ./build/site_001_backup.tar.gz \
  --exclude-media \
  --exclude-history 7d
```

### diff

```bash
ha-fleet diff --site-path ./sites/site_001 --from-version v1.2.3
```

Currently returns "not implemented yet" and exits non-zero.

### ingest-backup

```bash
ha-fleet ingest-backup \
  --site-path ./sites/site_001 \
  --backup ./build/site_001_backup.tar.gz \
  --output ./sites/site_001/discovery/latest.yaml
```

Reads HA registry files from backup archives and writes a sanitized discovery
snapshot for operator review.

### new-site

```bash
ha-fleet new-site --sites-root ./sites --site-id site_003 --display-name "Pilot Site 003"
```

Creates a standard site folder scaffold (`manifest`, `secrets contract`,
`dashboards`, `overlays`, `operator`, `discovery`).

### ingest-config-dir

```bash
ha-fleet ingest-config-dir \
  --site-path ./sites/site_001 \
  --config-dir ./build/site_001 \
  --output ./sites/site_001/discovery/latest.yaml
```

Reads HA registry files directly from `<config-dir>/.storage/` and writes a
sanitized discovery snapshot for operator review.

### dev-site

```bash
ha-fleet dev-site --site-path ./sites/site_001 --action up --port 8123
ha-fleet dev-site --site-path ./sites/site_001 --action render
ha-fleet dev-site --site-path ./sites/site_001 --action restart
ha-fleet dev-site --site-path ./sites/site_001 --action down
```

Runs the operator preview loop by rendering to build output, copying local mock
secrets if available, and managing a local Home Assistant container.

## Development

```bash
# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format and lint
black ha_fleet tests
ruff check ha_fleet tests

# Type check
mypy ha_fleet
```

## Project Layout

```text
ha-fleet-tooling/
  ha_fleet/
    backup/
    bundles/
    cli/
    discovery/
    deploy/
    render/
    schemas/
    utils/
  examples/
  tests/
  .github/workflows/
  pyproject.toml
  README.md
```

## CI

- `test.yml`: unit tests on Python 3.10-3.12
- `lint.yml`: black, ruff, mypy

## License

MIT

## References

- Home Assistant docs: https://www.home-assistant.io/docs/
- HA backup models: https://github.com/home-assistant/core/blob/dev/homeassistant/components/backup/models.py
- Device provisioning guide: [docs/DEVICE_PROVISIONING_GUIDE.md](docs/DEVICE_PROVISIONING_GUIDE.md)
