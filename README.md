# ha-fleet: Home Assistant Fleet Management Tooling

Lightweight Python package for managing HAOS fleet deployments across 5鈥? pilot homes.

## Quick Start

```bash
# Validate a site configuration
ha-fleet validate --site-path ./sites/site_001

# Render bundles + overlays into HAOS config
ha-fleet render --site-path ./sites/site_001 --output ./build/

# Generate HAOS backup artifact
ha-fleet bundle-to-backup --site-path ./sites/site_001 --output ./backup.tar.gz

# Show what changed
ha-fleet diff --site-path ./sites/site_001  # not implemented yet
```

## Architecture

- **Bundle engine**: Compose reusable bundles (routine, tasks, transit, etc.) with capability gates
- **Schema validation**: Pydantic models for site manifests, bundles, and secrets contracts
- **Rendering**: Jinja2-templated HAOS config generation (automations.yaml, scripts.yaml, etc.)
- **Backup generation**: Package configs into HAOS-compatible `.tar.gz` backups
- **Deployment CLI**: Planned for a later phase

See [design doc](../home_assistant_fleet_architecture_pilot_v2.md) for full architecture.

## Installation

```bash
# Development
pip install -e ".[dev]"

# Production (from GitHub releases)
pip install git+https://github.com/your-org/ha-fleet-tooling.git@v0.1.0
```

## Commands

### validate

Validate site manifest and bundle compatibility.

```bash
ha-fleet validate --site-path ./sites/site_001 --strict
```

### render

Render bundles + overlays into site config files.

```bash
ha-fleet render --site-path ./sites/site_001 --output ./build/ --format yaml
```

### bundle-to-backup

Generate HAOS backup from rendered config.

```bash
ha-fleet bundle-to-backup --site-path ./sites/site_001 \
  --output ./build/site_001_backup.tar.gz \
  --exclude-media \
  --exclude-history 7d
```

### diff

Show changes since last deployment (currently not implemented).

```bash
ha-fleet diff --site-path ./sites/site_001 --from-version v1.2.3  # not implemented yet
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linting
black ha_fleet/
ruff check ha_fleet/

# Type checking
mypy ha_fleet/
```

## Project Structure

```
ha-fleet-tooling/
鈹溾攢鈹€ README.md
鈹溾攢鈹€ docs/
鈹?  鈹溾攢鈹€ architecture.md
鈹?  鈹溾攢鈹€ bundle-guide.md
鈹?  鈹溾攢鈹€ secrets-strategy.md
鈹?  鈹斺攢鈹€ cli-reference.md
鈹溾攢鈹€ ha_fleet/
鈹?  鈹溾攢鈹€ __init__.py
鈹?  鈹溾攢鈹€ cli/
鈹?  鈹?  鈹溾攢鈹€ __init__.py
鈹?  鈹?  鈹斺攢鈹€ main.py
鈹?  鈹溾攢鈹€ schemas/
鈹?  鈹?  鈹溾攢鈹€ __init__.py
鈹?  鈹?  鈹溾攢鈹€ site.py
鈹?  鈹?  鈹溾攢鈹€ bundle.py
鈹?  鈹?  鈹斺攢鈹€ secrets.py
鈹?  鈹溾攢鈹€ bundles/
鈹?  鈹?  鈹溾攢鈹€ __init__.py
鈹?  鈹?  鈹溾攢鈹€ engine.py
鈹?  鈹?  鈹斺攢鈹€ validator.py
鈹?  鈹溾攢鈹€ render/
鈹?  鈹?  鈹溾攢鈹€ __init__.py
鈹?  鈹?  鈹溾攢鈹€ config.py
鈹?  鈹?  鈹斺攢鈹€ templates.py
鈹?  鈹溾攢鈹€ backup/
鈹?  鈹?  鈹溾攢鈹€ __init__.py
鈹?  鈹?  鈹斺攢鈹€ haos.py
鈹?  鈹溾攢鈹€ deploy/
鈹?  鈹?  鈹溾攢鈹€ __init__.py
鈹?  鈹?  鈹斺攢鈹€ client.py
鈹?  鈹斺攢鈹€ utils/
鈹?      鈹溾攢鈹€ __init__.py
鈹?      鈹斺攢鈹€ validators.py
鈹溾攢鈹€ examples/
鈹?  鈹溾攢鈹€ minimal_site/
鈹?  鈹?  鈹斺攢鈹€ site_manifest.yaml
鈹?  鈹溾攢鈹€ bundles/
鈹?  鈹?  鈹溾攢鈹€ routine.yaml
鈹?  鈹?  鈹溾攢鈹€ tasks.yaml
鈹?  鈹?  鈹斺攢鈹€ transit.yaml
鈹?  鈹斺攢鈹€ overlays/
鈹?      鈹斺攢鈹€ site_001_automations.yaml
鈹溾攢鈹€ tests/
鈹?  鈹溾攢鈹€ __init__.py
鈹?  鈹溾攢鈹€ test_schemas.py
鈹?  鈹溾攢鈹€ test_bundle_engine.py
鈹?  鈹溾攢鈹€ test_render.py
鈹?  鈹溾攢鈹€ test_backup.py
鈹?  鈹斺攢鈹€ fixtures/
鈹?      鈹斺攢鈹€ example_manifests.py
鈹溾攢鈹€ .github/
鈹?  鈹斺攢鈹€ workflows/
鈹?      鈹溾攢鈹€ test.yml
鈹?      鈹溾攢鈹€ lint.yml
鈹?      鈹斺攢鈹€ (release workflow planned)
鈹溾攢鈹€ .gitignore
鈹斺攢鈹€ pyproject.toml
```

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=ha_fleet

# Run a specific test
pytest tests/test_schemas.py::test_site_manifest_validation
```

## CI/CD

GitHub Actions workflows:
- **test.yml**: Run unit tests on every push
- **lint.yml**: Black, ruff, mypy before merge

## Deployment Flow

```
Private repo (config) 
    鈫?
CI renders + generates backup
    鈫?
GitHub artifact store
    鈫?
Edge downloads backup
    鈫?
HAOS API restores
    鈫?
Health check
```

## Contributing

1. Create a feature branch
2. Write tests
3. Run lint + tests locally
4. Open PR with description
5. Wait for CI to pass + human review
6. Merge and tag for release

## License

MIT

## See Also

- [HA Fleet Pilot Design Doc](../home_assistant_fleet_architecture_pilot_v2.md)
- [Implementation TODO](../IMPLEMENTATION_TODO.md)
- [Home Assistant Docs](https://www.home-assistant.io/docs/)
- [HAOS Backup Format](https://github.com/home-assistant/core/blob/dev/homeassistant/components/backup/models.py)


