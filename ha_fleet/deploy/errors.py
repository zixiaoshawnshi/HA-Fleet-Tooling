"""Shared exception type for the deploy module."""


class DeployError(Exception):
    """Raised when any step of a deploy/rollback/verify operation fails."""
