"""Utility functions and validators."""

from typing import List


def validate_entity_names(entities: List[str]) -> tuple[bool, List[str]]:
    """
    Validate Home Assistant entity names.

    Entity format: domain.entity_name
    """
    errors = []
    for entity in entities:
        if "." not in entity:
            errors.append(f"Invalid entity name: {entity} (missing domain)")
        parts = entity.split(".")
        if len(parts) != 2:
            errors.append(f"Invalid entity name: {entity} (too many parts)")
        domain, name = parts
        if not domain or not name:
            errors.append(f"Invalid entity name: {entity} (empty domain or name)")

    return len(errors) == 0, errors


def validate_secret_names(secrets: List[str]) -> tuple[bool, List[str]]:
    """Validate secret key names (alphanumeric + underscore)."""
    errors = []
    for secret in secrets:
        if not secret.replace("_", "").isalnum():
            errors.append(f"Invalid secret name: {secret}")
    return len(errors) == 0, errors
