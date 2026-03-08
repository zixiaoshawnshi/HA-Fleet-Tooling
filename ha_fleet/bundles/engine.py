"""Bundle engine for composing and validating bundles."""

from typing import List, Dict
from ha_fleet.schemas.bundle import BundleDefinition


class BundleEngine:
    """Engine for loading, validating, and composing bundles."""

    def __init__(self) -> None:
        """Initialize bundle engine."""
        self.bundles: Dict[str, BundleDefinition] = {}

    def load_bundle(self, definition: BundleDefinition) -> None:
        """Load a bundle definition."""
        self.bundles[definition.name] = definition

    def validate_composition(self, bundle_names: List[str]) -> tuple[bool, List[str]]:
        """
        Validate that bundles can be composed together.

        Returns:
            (is_valid, list_of_warnings)
        """
        warnings = []

        # Check for conflicts
        for bundle_name in bundle_names:
            if bundle_name not in self.bundles:
                warnings.append(f"Bundle '{bundle_name}' not found")
                continue

            bundle = self.bundles[bundle_name]
            for conflict in bundle.conflicts:
                if conflict in bundle_names:
                    warnings.append(
                        f"Bundle '{bundle_name}' conflicts with '{conflict}'"
                    )

        # Check for missing requirements
        for bundle_name in bundle_names:
            if bundle_name not in self.bundles:
                continue

            bundle = self.bundles[bundle_name]
            for req in bundle.requires:
                if req not in bundle_names:
                    warnings.append(
                        f"Bundle '{bundle_name}' requires '{req}' (missing)"
                    )

        return len(warnings) == 0, warnings
