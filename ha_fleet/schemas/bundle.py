"""Bundle definition schema."""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class BundleDefinition(BaseModel):
    """Bundle definition schema."""

    name: str = Field(..., description="Bundle name")
    version: str = Field("1.0.0", description="Bundle version")
    description: Optional[str] = None
    requires: List[str] = Field(default_factory=list, description="Required bundles")
    conflicts: List[str] = Field(default_factory=list, description="Conflicting bundles")
    requires_secrets: List[str] = Field(
        default_factory=list, description="Required secrets"
    )
    requires_entities: List[str] = Field(default_factory=list)
    optional_entities: List[str] = Field(default_factory=list)
    requires_addons: List[str] = Field(default_factory=list)
    optional_addons: List[str] = Field(default_factory=list)
    requires_capabilities: Dict[str, bool] = Field(default_factory=dict)

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "routine",
                "version": "1.0.0",
                "description": "Morning and evening routines",
                "requires_secrets": ["notify_mobile_target"],
                "requires_entities": ["input_boolean.morning_routine"],
                "requires_addons": ["google_calendar"],
                "requires_capabilities": {"google_calendar": True},
            }
        }
