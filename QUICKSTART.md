# Phase 1: Quick Start Guide

This folder contains the `ha-fleet-tooling` public package for HA Fleet management.

## Setup (Local Development)

### Prerequisites

- **Python 3.10+** (required by project dependencies)
  - Check your version: `python --version`
  - If you have Python 3.8 or earlier, you'll need to install a newer version
  - [Download Python](https://www.python.org/downloads/) or use your system package manager

### 1. Create Python Environment

```bash
cd ha-fleet-tooling

# Using venv (ensure you're using Python 3.10+)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Or using conda (recommended if managing multiple Python versions)
conda create -n ha-fleet python=3.12
conda activate ha-fleet
```

**Troubleshooting:** If you have multiple Python versions installed:
- Windows: Use the specific version path, e.g., `py -3.12 -m venv venv`
- Linux/macOS: Use `python3.12 -m venv venv`

### 2. Install Package in Dev Mode

```bash
pip install -e ".[dev]"
```

This installs:
- Core dependencies: `pydantic`, `click`, `PyYAML`, `jinja2`, `requests`
- Dev dependencies: `pytest`, `pytest-cov`, `black`, `ruff`, `mypy`

### 3. Verify Installation

```bash
ha-fleet --version
ha-fleet validate --help
```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=ha_fleet

# Run a specific test file
pytest tests/test_schemas.py

# Run a specific test
pytest tests/test_schemas.py::test_site_manifest_minimal
```

## Code Quality

```bash
# Format code
black ha_fleet/ tests/

# Lint
ruff check ha_fleet/ tests/

# Type check
mypy ha_fleet/
```

## Current Status (Phase 1.0)

✅ **Complete:**
- Project structure
- `pyproject.toml` (dependencies, metadata)
- CLI skeleton with 7 main commands:
  - `ha-fleet new-site` — scaffold a new site directory
  - `ha-fleet dev-site` — local operator dev loop (render/docker preview)
  - `ha-fleet ingest-backup` — extract discovery snapshot from HA backup
  - `ha-fleet validate` — validate site configs
  - `ha-fleet render` — render bundles to YAML
  - `ha-fleet bundle-to-backup` — generate HAOS backups
  - `ha-fleet diff` — show config changes
- Pydantic schemas:
  - `SiteManifest` — site configuration
  - `BundleDefinition` — bundle metadata
  - `SecretsContract` — secret requirements
- Bundle engine (loading, validation, composition)
- Render engine for:
  - `automations.yaml`
  - `scripts.yaml`
  - `input_booleans.yaml`
  - `dashboards/*.yaml`
- Backup generation
- Unit tests (schemas, bundle engine)
- CI/CD workflows (test.yml, lint.yml)
- Examples (minimal site, bundle definitions)

⏳ **TODO (Next Steps):**
- Implement diff logic (git-based change detection)
- Add more comprehensive tests
- Add documentation (bundle guide, secrets strategy, etc.)

## Next Phase: Private Site Repo

Once this tooling is stable:
1. Create private GitHub repo `ha-fleet-pilot-sites`
2. Reference this package as a versioned dependency
3. Create site manifests, overlays, and CI workflows
4. Run first deployment tests

## Directory Structure

```
ha-fleet-tooling/
├── ha_fleet/              # Main package
│   ├── cli/              # CLI commands
│   ├── schemas/          # Pydantic models
│   ├── bundles/          # Bundle engine
│   ├── render/           # Config rendering (TODO)
│   ├── backup/           # Backup generation (TODO)
│   ├── deploy/           # Deployment client (TODO)
│   └── utils/            # Helpers
├── tests/                # Unit tests
├── examples/             # Example configs
├── .github/workflows/    # CI/CD
├── pyproject.toml        # Dependencies
├── README.md             # Full documentation
└── .gitignore
```

## Tips

- Always install in edit mode: `pip install -e .`
- Run tests before pushing: `pytest`
- Run linting before PRs: `black && ruff check`
- Check the README.md for full documentation

## Questions?

Refer to:
- [Design Doc](../home_assistant_fleet_architecture_pilot_v2.md)
- [Implementation TODO](../IMPLEMENTATION_TODO.md)
- [Python Docs](https://docs.python.org/3.12/)
- [Pydantic Docs](https://docs.pydantic.dev/)
- [Click Docs](https://click.palletsprojects.com/)
