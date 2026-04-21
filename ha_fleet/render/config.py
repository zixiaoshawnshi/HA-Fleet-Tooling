"""Configuration rendering engine for HAOS config generation."""

from pathlib import Path
from typing import Dict, Any, List, cast
import shutil
import yaml
import json
from jinja2 import Environment, FileSystemLoader
from ha_fleet.schemas.site import SiteManifest


class ConfigRenderer:
    """Render bundles + overlays into HAOS config files."""

    def __init__(self, site_manifest: SiteManifest, site_path: Path) -> None:
        """
        Initialize renderer.

        Args:
            site_manifest: Loaded site manifest
            site_path: Root path to site directory
        """
        self.manifest = site_manifest
        self.site_path = site_path
        self.bundles_path = site_path / "bundles"
        self.overlays_path = site_path / "overlays"
        self.output_config: Dict[str, Any] = {}

        # Setup Jinja2 environment
        self.jinja_env = Environment(loader=FileSystemLoader(str(site_path)), trim_blocks=True)

    def load_bundle(self, bundle_name: str) -> Dict[str, Any]:
        """Load bundle definition from YAML."""
        bundle_file = self.bundles_path / bundle_name / "bundle.yaml"
        if not bundle_file.exists():
            bundle_file = self.bundles_path / f"{bundle_name}.yaml"
        if not bundle_file.exists():
            raise FileNotFoundError(f"Bundle not found: {bundle_file}")

        with open(bundle_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def load_overlay(self, overlay_name: str) -> Dict[str, Any]:
        """Load overlay definition from YAML."""
        overlay_file = self.overlays_path / f"{overlay_name}.yaml"
        if not overlay_file.exists():
            return {}

        with open(overlay_file, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def render_config_file(self, template_dir: str, filename: str, context: Dict[str, Any]) -> str:
        """
        Render a config file using Jinja2.

        Args:
            template_dir: Directory containing templates (relative to site_path)
            filename: Template filename (e.g., 'automations.yaml.j2')
            context: Jinja2 context variables

        Returns:
            Rendered YAML as string
        """
        template_path = self.site_path / template_dir / filename
        if not template_path.exists():
            return ""

        with open(template_path, "r", encoding="utf-8") as f:
            template_str = f.read()

        template = self.jinja_env.from_string(template_str)
        rendered = template.render(
            manifest=self.manifest,
            site=self.manifest,
            **context,
        )
        return cast(str, rendered)

    def _merge_yaml_dicts(self, base: Dict, override: Dict) -> Dict:
        """Deep merge YAML dicts (override extends base)."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_yaml_dicts(base[key], value)
            else:
                base[key] = value
        return base

    def _parse_input_helpers(
        self, filepath: Path
    ) -> tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """Parse an input_helpers.yaml file and split entities by HA domain.

        Detection rules:
          - has ``options``        → input_select
          - has ``min`` or ``max`` → input_number
          - otherwise              → input_boolean

        Returns:
            (booleans, selects, numbers)
        """
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        booleans: Dict[str, Any] = {}
        selects: Dict[str, Any] = {}
        numbers: Dict[str, Any] = {}

        for key, config in data.items():
            if not isinstance(config, dict):
                continue
            if "options" in config:
                selects[key] = config
            elif "min" in config or "max" in config:
                numbers[key] = config
            else:
                booleans[key] = config

        return booleans, selects, numbers

    def render_automations(self) -> List[Dict[str, Any]]:
        """Render automations from bundles + overlays."""
        automations: List[Dict[str, Any]] = []

        for bundle_name in self.manifest.bundles:
            # Load bundle automations if they exist
            bundle_auto_file = self.bundles_path / bundle_name / "automations.yaml"
            if bundle_auto_file.exists():
                with open(bundle_auto_file, "r", encoding="utf-8") as f:
                    automations.extend(yaml.safe_load(f) or [])

        # Apply overlays
        for overlay_file in (self.overlays_path).glob("automations_*.yaml"):
            with open(overlay_file, "r", encoding="utf-8") as f:
                automations.extend(yaml.safe_load(f) or [])

        return automations

    def render_scripts(self) -> Dict[str, Any]:
        """Render scripts from bundles + overlays."""
        scripts: Dict[str, Any] = {}

        for bundle_name in self.manifest.bundles:
            bundle_script_file = self.bundles_path / bundle_name / "scripts.yaml"
            if bundle_script_file.exists():
                with open(bundle_script_file, "r", encoding="utf-8") as f:
                    bundle_scripts = yaml.safe_load(f) or {}
                    scripts.update(bundle_scripts)

        # Apply overlays
        overlay_script_file = self.overlays_path / "scripts.yaml"
        if overlay_script_file.exists():
            with open(overlay_script_file, "r", encoding="utf-8") as f:
                overlay_scripts = yaml.safe_load(f) or {}
                scripts = self._merge_yaml_dicts(scripts, overlay_scripts)

        return scripts

    def render_input_booleans(self) -> Dict[str, Any]:
        """Render input_boolean entities from bundles (input_booleans.yaml and input_helpers.yaml)."""
        input_booleans: Dict[str, Any] = {}

        for bundle_name in self.manifest.bundles:
            # Dedicated file takes first pass
            bundle_ib_file = self.bundles_path / bundle_name / "input_booleans.yaml"
            if bundle_ib_file.exists():
                with open(bundle_ib_file, "r", encoding="utf-8") as f:
                    input_booleans.update(yaml.safe_load(f) or {})

            # input_helpers.yaml — extract boolean-typed entities
            bundle_helpers_file = self.bundles_path / bundle_name / "input_helpers.yaml"
            if bundle_helpers_file.exists():
                booleans, _, _ = self._parse_input_helpers(bundle_helpers_file)
                input_booleans.update(booleans)

        overlay_ib_file = self.overlays_path / "input_booleans.yaml"
        if overlay_ib_file.exists():
            with open(overlay_ib_file, "r", encoding="utf-8") as f:
                input_booleans = self._merge_yaml_dicts(input_booleans, yaml.safe_load(f) or {})

        return input_booleans

    def render_input_selects(self) -> Dict[str, Any]:
        """Render input_select entities from bundles (input_helpers.yaml)."""
        input_selects: Dict[str, Any] = {}

        for bundle_name in self.manifest.bundles:
            bundle_helpers_file = self.bundles_path / bundle_name / "input_helpers.yaml"
            if bundle_helpers_file.exists():
                _, selects, _ = self._parse_input_helpers(bundle_helpers_file)
                input_selects.update(selects)

        overlay_helpers_file = self.overlays_path / "input_helpers.yaml"
        if overlay_helpers_file.exists():
            _, selects, _ = self._parse_input_helpers(overlay_helpers_file)
            input_selects = self._merge_yaml_dicts(input_selects, selects)

        return input_selects

    def render_input_numbers(self) -> Dict[str, Any]:
        """Render input_number entities from bundles (input_helpers.yaml)."""
        input_numbers: Dict[str, Any] = {}

        for bundle_name in self.manifest.bundles:
            bundle_helpers_file = self.bundles_path / bundle_name / "input_helpers.yaml"
            if bundle_helpers_file.exists():
                _, _, numbers = self._parse_input_helpers(bundle_helpers_file)
                input_numbers.update(numbers)

        overlay_helpers_file = self.overlays_path / "input_helpers.yaml"
        if overlay_helpers_file.exists():
            _, _, numbers = self._parse_input_helpers(overlay_helpers_file)
            input_numbers = self._merge_yaml_dicts(input_numbers, numbers)

        return input_numbers

    def render_dashboards(self) -> Dict[str, Any]:
        """Collect dashboard YAML files from site and overlay directories.

        Returns a dict mapping relative path → dict with keys:
          - "source": Path to the source file (for verbatim copy at write time)
          - all top-level parsed YAML keys (for title extraction in render_configuration)

        Files are copied verbatim at write time to avoid yaml.dump() mangling.
        """
        dashboards: Dict[str, Any] = {}
        site_dashboards_path = self.site_path / "dashboards"
        overlay_dashboards_path = self.overlays_path / "dashboards"

        if site_dashboards_path.exists():
            for dashboard_file in sorted(site_dashboards_path.rglob("*.yaml")):
                rel_path = dashboard_file.relative_to(site_dashboards_path).as_posix()
                with open(dashboard_file, "r", encoding="utf-8") as f:
                    parsed = yaml.safe_load(f) or {}
                dashboards[rel_path] = {"source": dashboard_file, **parsed}

        # Overlay dashboard files override site dashboard files with same relative path.
        if overlay_dashboards_path.exists():
            for dashboard_file in sorted(overlay_dashboards_path.rglob("*.yaml")):
                rel_path = dashboard_file.relative_to(overlay_dashboards_path).as_posix()
                with open(dashboard_file, "r", encoding="utf-8") as f:
                    parsed = yaml.safe_load(f) or {}
                dashboards[rel_path] = {"source": dashboard_file, **parsed}

        return dashboards

    def render_configuration_overrides(self) -> str:
        """Render raw configuration override snippets from site and overlays."""
        snippets: List[str] = []
        site_override = self.site_path / "configuration_overrides.yaml"
        overlay_override = self.overlays_path / "configuration_overrides.yaml"

        if site_override.exists():
            with open(site_override, "r", encoding="utf-8") as f:
                text = f.read().strip()
                if text:
                    snippets.append(text)

        if overlay_override.exists():
            with open(overlay_override, "r", encoding="utf-8") as f:
                text = f.read().strip()
                if text:
                    snippets.append(text)

        if not snippets:
            return ""

        return "\n\n".join(snippets) + "\n"

    def _dashboard_slug(self, rel_path: str) -> str:
        """Build a stable dashboard key from relative file path."""
        slug = rel_path.replace("\\", "-").replace("/", "-").replace("_", "-").replace(".", "-")
        return slug.lower()

    def render_configuration(self, dashboards: Dict[str, Any], overrides: str) -> str:
        """Render configuration.yaml text with lovelace dashboard registrations."""
        lines = [
            "default_config:",
            "",
            "automation: !include automations.yaml",
            "script: !include scripts.yaml",
            "input_boolean: !include input_booleans.yaml",
            "input_select: !include input_selects.yaml",
            "input_number: !include input_numbers.yaml",
            "",
        ]

        if dashboards:
            lines.extend(
                [
                    "lovelace:",
                    "  mode: storage",
                    "  dashboards:",
                ]
            )
            for rel_path, dashboard_data in sorted(dashboards.items()):
                site_slug = self.manifest.site_id.replace("_", "-").lower()
                key = f"fleet-{site_slug}-{self._dashboard_slug(rel_path)}"
                title = "Fleet Dashboard"
                if isinstance(dashboard_data, dict):
                    maybe_title = dashboard_data.get("title")
                    if isinstance(maybe_title, str) and maybe_title.strip():
                        title = maybe_title.strip()
                lines.extend(
                    [
                        f"    {key}:",
                        "      mode: yaml",
                        f"      title: {title}",
                        "      icon: mdi:view-dashboard",
                        "      show_in_sidebar: true",
                        "      require_admin: false",
                        f"      filename: dashboards/{rel_path}",
                    ]
                )
        config_text = "\n".join(lines) + "\n"
        if overrides:
            config_text += "\n" + overrides
        return config_text

    def render_all(self) -> Dict[str, Any]:
        """
        Render all config sections.

        Returns:
            Dict with keys: automations, scripts, input_booleans, etc.
        """
        dashboards = self.render_dashboards()
        overrides = self.render_configuration_overrides()
        config = {
            "automations": self.render_automations(),
            "scripts": self.render_scripts(),
            "input_booleans": self.render_input_booleans(),
            "input_selects": self.render_input_selects(),
            "input_numbers": self.render_input_numbers(),
            "dashboards": dashboards,
            "configuration": self.render_configuration(dashboards, overrides),
            "configuration_overrides": overrides,
        }
        return config

    def write_to_dir(self, output_dir: Path, format: str = "yaml") -> None:
        """
        Write rendered config to directory.

        Args:
            output_dir: Directory to write config files to
            format: Output format ('yaml' or 'json')
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        config = self.render_all()

        for section_name, config_data in config.items():
            if section_name == "dashboards":
                if not config_data:
                    continue
                dashboards_dir = output_dir / "dashboards"
                dashboards_dir.mkdir(parents=True, exist_ok=True)
                for dashboard_rel_path, dashboard_data in config_data.items():
                    output_file = dashboards_dir / dashboard_rel_path
                    output_file.parent.mkdir(parents=True, exist_ok=True)
                    # Copy verbatim from source to preserve formatting and avoid
                    # yaml.dump() mangling (key reordering, backslash continuations).
                    source_file = dashboard_data.get("source") if isinstance(dashboard_data, dict) else None
                    if source_file and Path(source_file).exists():
                        shutil.copy2(source_file, output_file)
                    elif format == "yaml":
                        with open(output_file, "w", encoding="utf-8") as f:
                            yaml.dump(dashboard_data, f, default_flow_style=False)
                    elif format == "json":
                        output_file = output_file.with_suffix(".json")
                        with open(output_file, "w", encoding="utf-8") as f:
                            json.dump(dashboard_data, f, indent=2)
                continue

            if section_name == "configuration":
                output_file = output_dir / "configuration.yaml"
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(str(config_data))
                continue

            if section_name == "configuration_overrides":
                continue

            # Keep these include targets present, even when empty.
            should_write_empty = section_name in {
                "automations", "scripts", "input_booleans", "input_selects", "input_numbers"
            }
            if not config_data and not should_write_empty:
                continue

            if format == "yaml":
                output_file = output_dir / f"{section_name}.yaml"
                with open(output_file, "w", encoding="utf-8") as f:
                    yaml.dump(config_data, f, default_flow_style=False)
            elif format == "json":
                output_file = output_dir / f"{section_name}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(config_data, f, indent=2)

        print(f"Rendered {len(config)} config files to {output_dir}")
