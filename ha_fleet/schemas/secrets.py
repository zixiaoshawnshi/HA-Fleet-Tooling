"""Secrets contract schema."""

from typing import List, Optional
from pydantic import BaseModel, Field


class SecretsContract(BaseModel):
    """Secrets contract specifying required and optional secrets."""

    required: List[str] = Field(default_factory=list, description="Required secret keys")
    optional: List[str] = Field(default_factory=list, description="Optional secret keys")
    description: Optional[str] = None

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "required": [
                    "notify_mobile_target",
                    "google_calendar_api_key",
                ],
                "optional": ["zigbee_backup_password"],
                "description": "Secrets contract for site_001",
            }
        }
