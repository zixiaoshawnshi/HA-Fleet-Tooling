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
```

## Current Scope

Implemented:
- Bundle composition and validation primitives
- Site manifest / bundle / secrets schemas
- Rendering for `automations`, `scripts`, and `input_booleans`
- Backup artifact generation
- CLI commands: `validate`, `render`, `bundle-to-backup`

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
