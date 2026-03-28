"""
Integration Schemas API Routes

Provides REST API for querying global integration schema definitions.
These are the built-in integration types (Coralogix, Snowflake, GitHub, etc.)
that teams can configure with their actual credentials.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db.config_models import IntegrationSchema
from ...db.session import get_db

logger = structlog.get_logger(__name__)


# =============================================================================
# Response Models
# =============================================================================


class IntegrationFieldSchema(BaseModel):
    """Schema for a single integration field."""

    name: str
    type: str
    required: bool
    level: str
    description: str
    placeholder: Optional[str] = None
    default_value: Optional[str] = None


class IntegrationSchemaResponse(BaseModel):
    """Integration schema response."""

    id: str
    name: str
    category: str
    description: str
    docs_url: Optional[str] = None
    icon_url: Optional[str] = None
    display_order: int
    featured: bool
    fields: List[dict]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IntegrationSchemasListResponse(BaseModel):
    """List of integration schemas."""

    integrations: List[IntegrationSchemaResponse]
    total: int


# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/api/v1/integrations/schemas", tags=["integration-schemas"])


@router.get("", response_model=IntegrationSchemasListResponse)
async def list_integration_schemas(
    category: Optional[str] = Query(None, description="Filter by category"),
    featured: Optional[bool] = Query(None, description="Filter by featured status"),
    db: Session = Depends(get_db),
):
    """
    List all available integration schemas.

    These are the global integration definitions (not per-org).
    Teams can then configure these integrations with their actual credentials.
    """
    logger.info("list_integration_schemas", category=category, featured=featured)

    # Build query
    query = select(IntegrationSchema).order_by(
        IntegrationSchema.display_order, IntegrationSchema.name
    )

    # Apply filters
    if category:
        query = query.where(IntegrationSchema.category == category)
    if featured is not None:
        query = query.where(IntegrationSchema.featured == featured)

    # Execute
    result = db.execute(query)
    schemas = result.scalars().all()

    return IntegrationSchemasListResponse(
        integrations=[IntegrationSchemaResponse.model_validate(s) for s in schemas],
        total=len(schemas),
    )


@router.get("/{integration_id}", response_model=IntegrationSchemaResponse)
async def get_integration_schema(integration_id: str, db: Session = Depends(get_db)):
    """
    Get a specific integration schema by ID.

    Returns the schema definition including all required fields,
    documentation links, and configuration details.
    """
    logger.info("get_integration_schema", integration_id=integration_id)

    schema = db.get(IntegrationSchema, integration_id)
    if not schema:
        raise HTTPException(
            status_code=404, detail=f"Integration schema '{integration_id}' not found"
        )

    return IntegrationSchemaResponse.model_validate(schema)


@router.get("/categories/list")
async def list_categories(db: Session = Depends(get_db)):
    """
    List all unique integration categories.

    Returns the distinct categories with count of integrations in each.
    """
    logger.info("list_integration_categories")

    # Get all schemas
    result = db.execute(select(IntegrationSchema))
    schemas = result.scalars().all()

    # Count by category
    categories = {}
    for schema in schemas:
        if schema.category not in categories:
            categories[schema.category] = {
                "category": schema.category,
                "count": 0,
                "featured_count": 0,
            }
        categories[schema.category]["count"] += 1
        if schema.featured:
            categories[schema.category]["featured_count"] += 1

    return {"categories": list(categories.values()), "total": len(categories)}
