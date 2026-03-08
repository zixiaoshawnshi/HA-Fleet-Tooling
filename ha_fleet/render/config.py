"""Configuration rendering engine for HAOS config generation."""

from pathlib import Path
from typing import Dict, Any, List, Optional
import yaml
import json
from jinja2 import Environment, FileSystemLoader, Template
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
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(site_path)), trim_blocks=True
        )

    def load_bundle(self, bundle_name: str) -> Dict[str, Any]:
        """Load bundle definition from YAML."""
        bundle_file = self.bundles_path / f"{bundle_name}.yaml"
        if not bundle_file.exists():
            raise FileNotFoundError(f"Bundle not found: {bundle_file}")

        with open(bundle_file, "r") as f:
            return yaml.safe_load(f) or {}

    def load_overlay(self, overlay_name: str) -> Dict[str, Any]:
        """Load overlay definition from YAML."""
        overlay_file = self.overlays_path / f"{overlay_name}.yaml"
        if not overlay_file.exists():
            return {}

        with open(overlay_file, "r") as f:
            return yaml.safe_load(f) or {}

    def render_config_file(
        self, template_dir: str, filename: str, context: Dict[str, Any]
    ) -> str:
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

        with open(template_path, "r") as f:
            template_str = f.read()

        template = self.jinja_env.from_string(template_str)
        return template.render(
            manifest=self.manifest,
            site=self.manifest,
            **context,
        )

    def _merge_yaml_dicts(self, base: Dict, override: Dict) -> Dict:
        """Deep merge YAML dicts (override extends base)."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_yaml_dicts(base[key], value)
            else:
                base[key] = value
        return base

    def render_automations(self) -> List[Dict[str, Any]]:
        """Render automations from bundles + overlays."""
        automations = []

        for bundle_name in self.manifest.bundles:
            bundle = self.load_bundle(bundle_name)
            # Load bundle automations if they exist
            bundle_auto_file = self.bundles_path / bundle_name / "automations.yaml"
            if bundle_auto_file.exists():
                with open(bundle_auto_file, "r") as f:
                    automations.extend(yaml.safe_load(f) or [])

        # Apply overlays
        for overlay_file in (self.overlays_path).glob("automations_*.yaml"):
            with open(overlay_file, "r") as f:
                automations.extend(yaml.safe_load(f) or [])

        return automations

    def render_scripts(self) -> Dict[str, Any]:
        """Render scripts from bundles + overlays."""
        scripts = {}

        for bundle_name in self.manifest.bundles:
            bundle_script_file = self.bundles_path / bundle_name / "scripts.yaml"
            if bundle_script_file.exists():
                with open(bundle_script_file, "r") as f:
                    bundle_scripts = yaml.safe_load(f) or {}
                    scripts.update(bundle_scripts)

        # Apply overlays
        overlay_script_file = self.overlays_path / "scripts.yaml"
        if overlay_script_file.exists():
            with open(overlay_script_file, "r") as f:
                overlay_scripts = yaml.safe_load(f) or {}
                scripts = self._merge_yaml_dicts(scripts, overlay_scripts)

        return scripts

    def render_input_booleans(self) -> Dict[str, Any]:
        """Render input booleans (helpers) from bundles."""
        input_booleans = {}

        for bundle_name in self.manifest.bundles:
            bundle_ib_file = self.bundles_path / bundle_name / "input_booleans.yaml"
            if bundle_ib_file.exists():
                with open(bundle_ib_file, "r") as f:
                    bundle_ib = yaml.safe_load(f) or {}
                    input_booleans.update(bundle_ib)

        overlay_ib_file = self.overlays_path / "input_booleans.yaml"
        if overlay_ib_file.exists():
            with open(overlay_ib_file, "r") as f:
                overlay_ib = yaml.safe_load(f) or {}
                input_booleans = self._merge_yaml_dicts(input_booleans, overlay_ib)

        return input_booleans

    def render_all(self) -> Dict[str, Any]:
        """
        Render all config sections.

        Returns:
            Dict with keys: automations, scripts, input_booleans, etc.
        """
        config = {
            "automations": self.render_automations(),
            "scripts": self.render_scripts(),
            "input_booleans": self.render_input_booleans(),
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
            if not config_data:
                continue

            if format == "yaml":
                output_file = output_dir / f"{section_name}.yaml"
                with open(output_file, "w") as f:
                    yaml.dump(config_data, f, default_flow_style=False)
            elif format == "json":
                output_file = output_dir / f"{section_name}.json"
                with open(output_file, "w") as f:
                    json.dump(config_data, f, indent=2)

        print(f"Rendered {len(config)} config files to {output_dir}")
