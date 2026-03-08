# ha-fleet: Home Assistant Fleet Management Tooling

Lightweight Python package for managing HAOS fleet deployments across 5–6 pilot homes.

## Quick Start

```bash
# Validate a site configuration
ha-fleet validate --site-path ./sites/site_001

# Render bundles + overlays into HAOS config
ha-fleet render --site-path ./sites/site_001 --output ./build/

# Generate HAOS backup artifact
ha-fleet bundle-to-backup --site-path ./sites/site_001 --output ./backup.tar.gz

# Show what changed
ha-fleet diff --site-path ./sites/site_001
```

## Architecture

- **Bundle engine**: Compose reusable bundles (routine, tasks, transit, etc.) with capability gates
- **Schema validation**: Pydantic models for site manifests, bundles, and secrets contracts
- **Rendering**: Jinja2-templated HAOS config generation (automations.yaml, scripts.yaml, etc.)
- **Backup generation**: Package configs into HAOS-compatible `.tar.gz` backups
- **Deployment CLI**: Trigger remote deployments, track status, manage rollbacks

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

Show changes since last deployment.

```bash
ha-fleet diff --site-path ./sites/site_001 --from-version v1.2.3
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
├── README.md
├── docs/
│   ├── architecture.md
│   ├── bundle-guide.md
│   ├── secrets-strategy.md
│   └── cli-reference.md
├── ha_fleet/
│   ├── __init__.py
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── site.py
│   │   ├── bundle.py
│   │   └── secrets.py
│   ├── bundles/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   └── validator.py
│   ├── render/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   └── templates.py
│   ├── backup/
│   │   ├── __init__.py
│   │   └── haos.py
│   ├── deploy/
│   │   ├── __init__.py
│   │   └── client.py
│   └── utils/
│       ├── __init__.py
│       └── validators.py
├── examples/
│   ├── minimal_site/
│   │   └── site_manifest.yaml
│   ├── bundles/
│   │   ├── routine.yaml
│   │   ├── tasks.yaml
│   │   └── transit.yaml
│   └── overlays/
│       └── site_001_automations.yaml
├── tests/
│   ├── __init__.py
│   ├── test_schemas.py
│   ├── test_bundle_engine.py
│   ├── test_render.py
│   ├── test_backup.py
│   └── fixtures/
│       └── example_manifests.py
├── .github/
│   └── workflows/
│       ├── test.yml
│       ├── lint.yml
│       └── release.yml
├── .gitignore
└── pyproject.toml
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
- **release.yml**: Publish to GitHub Packages on version tag

## Deployment Flow

```
Private repo (config) 
    ↓
CI renders + generates backup
    ↓
GitHub artifact store
    ↓
Edge downloads backup
    ↓
HAOS API restores
    ↓
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
