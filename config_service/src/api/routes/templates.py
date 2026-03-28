"""Template marketplace API routes."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ...core.hierarchical_config import get_default_agent_config
from ...db.models import (
    OrgNode,
    Template,
    TemplateAnalytics,
    TemplateApplication,
)
from ...db.session import get_db
from ..auth import AdminPrincipal, TeamPrincipal, require_admin, require_team_auth

router = APIRouter(tags=["templates"])


# =============================================================================
# Helper Functions
# =============================================================================


def apply_template_with_agent_replacement(
    existing_config: Dict[str, Any], template_json: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Apply template to config with automatic built-in agent replacement.

    Strategy:
    1. Start with existing config (preserves non-agent settings)
    2. Disable all built-in agents not in template
    3. Merge template config (includes template agents)

    This ensures templates define EXACTLY what agents you get, not additive merge.

    Example:
        Built-in: [planner, aws, k8s, metrics, investigation, coding]
        Template: [coordinator, joke_writer, news_searcher]
        Result: 6 built-ins disabled + 3 template enabled = only 3 visible
    """
    # Get built-in agent IDs
    default_agents = get_default_agent_config().get("agents", {})
    builtin_agent_ids = set(default_agents.keys())

    # Get template agent IDs
    template_agents = template_json.get("agents", {})
    template_agent_ids = set(template_agents.keys())

    # Start with existing config
    merged_config = dict(existing_config)

    # Ensure agents section exists
    if "agents" not in merged_config:
        merged_config["agents"] = {}

    # Disable built-in agents NOT in template
    for agent_id in builtin_agent_ids:
        if agent_id not in template_agent_ids:
            # Disable this built-in agent
            if agent_id not in merged_config["agents"]:
                merged_config["agents"][agent_id] = {}
            merged_config["agents"][agent_id]["enabled"] = False

    # Now merge template config (template takes precedence)
    # This will add/update template agents and override other settings
    for key, value in template_json.items():
        if key == "agents":
            # For agents, merge at agent level (not full replacement)
            for agent_id, agent_config in value.items():
                merged_config["agents"][agent_id] = agent_config
        else:
            # For other keys, template takes precedence
            merged_config[key] = value

    return merged_config


# =============================================================================
# Response Models
# =============================================================================


class TemplateListResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    category: str
    icon_url: Optional[str]
    example_scenarios: List[str]
    required_mcps: List[str]
    usage_count: int
    avg_rating: Optional[float]
    version: str

    class Config:
        from_attributes = True


class TemplateDetailResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: str
    detailed_description: Optional[str]
    category: str
    template_json: Dict[str, Any]
    icon_url: Optional[str]
    example_scenarios: List[str]
    demo_video_url: Optional[str]
    required_mcps: List[str]
    required_tools: List[str]
    version: str
    usage_count: int
    avg_rating: Optional[float]

    class Config:
        from_attributes = True


class TemplateApplicationRequest(BaseModel):
    customize: Optional[Dict[str, Any]] = None


class TemplateApplicationResponse(BaseModel):
    id: str
    template_id: str
    template_name: str
    applied_at: str
    template_version: str
    has_customizations: bool
    customization_summary: Optional[Dict[str, Any]]


class TemplateCreateRequest(BaseModel):
    name: str
    slug: str
    description: str
    detailed_description: Optional[str] = None
    category: str
    template_json: Dict[str, Any]
    icon_url: Optional[str] = None
    example_scenarios: List[str] = []
    demo_video_url: Optional[str] = None
    required_mcps: List[str] = []
    required_tools: List[str] = []
    is_published: bool = False
    version: str = "1.0.0"


# =============================================================================
# Public Template Browsing (Team Auth)
# =============================================================================


@router.get("/api/v1/templates", response_model=Dict[str, List[TemplateListResponse]])
async def list_templates(
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    team: TeamPrincipal = Depends(require_team_auth),
):
    """
    List all published templates available to browse.

    Filters:
    - category: Filter by use_case_category
    - search: Search in name and description
    """
    query = db.query(Template).filter(
        and_(
            Template.is_published == True,
            or_(
                Template.is_system_template == True,
                Template.org_id == team.org_id,
            ),
        )
    )

    if category:
        query = query.filter(Template.use_case_category == category)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Template.name.ilike(search_pattern),
                Template.description.ilike(search_pattern),
            )
        )

    templates = query.order_by(Template.usage_count.desc()).all()

    return {
        "templates": [
            TemplateListResponse(
                id=t.id,
                name=t.name,
                slug=t.slug,
                description=t.description,
                category=t.use_case_category,
                icon_url=t.icon_url,
                example_scenarios=t.example_scenarios or [],
                required_mcps=t.required_mcps or [],
                usage_count=t.usage_count or 0,
                avg_rating=t.avg_rating,
                version=t.version,
            )
            for t in templates
        ]
    }


@router.get("/api/v1/templates/{template_id}", response_model=TemplateDetailResponse)
async def get_template_details(
    template_id: str,
    db: Session = Depends(get_db),
    team: TeamPrincipal = Depends(require_team_auth),
):
    """Get detailed information about a specific template."""
    template = (
        db.query(Template)
        .filter(
            and_(
                Template.id == template_id,
                Template.is_published == True,
                or_(
                    Template.is_system_template == True,
                    Template.org_id == team.org_id,
                ),
            )
        )
        .first()
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return TemplateDetailResponse(
        id=template.id,
        name=template.name,
        slug=template.slug,
        description=template.description,
        detailed_description=template.detailed_description,
        category=template.use_case_category,
        template_json=template.template_json,
        icon_url=template.icon_url,
        example_scenarios=template.example_scenarios or [],
        demo_video_url=template.demo_video_url,
        required_mcps=template.required_mcps or [],
        required_tools=template.required_tools or [],
        version=template.version,
        usage_count=template.usage_count or 0,
        avg_rating=template.avg_rating,
    )


# =============================================================================
# Template Application (Team Auth)
# =============================================================================


@router.post("/api/v1/team/templates/{template_id}/apply")
async def apply_template_to_team(
    template_id: str,
    body: TemplateApplicationRequest,
    db: Session = Depends(get_db),
    team: TeamPrincipal = Depends(require_team_auth),
):
    """
    Apply a template to the current team's configuration.

    This merges the template JSON into the team's NodeConfiguration (v2 table).
    Uses v2 table with effective config caching.
    """
    # Check if template exists and is published
    template = (
        db.query(Template)
        .filter(
            and_(
                Template.id == template_id,
                Template.is_published == True,
                or_(
                    Template.is_system_template == True,
                    Template.org_id == team.org_id,
                ),
            )
        )
        .first()
    )

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Check if team already has an active template
    existing_app = (
        db.query(TemplateApplication)
        .filter(
            and_(
                TemplateApplication.team_node_id == team.team_node_id,
                TemplateApplication.is_active == True,
            )
        )
        .first()
    )

    if existing_app:
        # Deactivate existing template
        existing_app.is_active = False
        existing_app.deactivated_at = datetime.utcnow()

    # Create template application record
    application_id = f"app_{uuid.uuid4().hex[:12]}"
    application = TemplateApplication(
        id=application_id,
        template_id=template_id,
        team_node_id=team.team_node_id,
        applied_at=datetime.utcnow(),
        applied_by=team.subject or team.email or "unknown",
        template_version=template.version,
        is_active=True,
    )
    db.add(application)

    # Get or create team's node config (using NodeConfiguration v2)
    from ...db.config_models import NodeConfiguration

    node_config = (
        db.query(NodeConfiguration)
        .filter(
            and_(
                NodeConfiguration.org_id == team.org_id,
                NodeConfiguration.node_id == team.team_node_id,
            )
        )
        .first()
    )

    if not node_config:
        # Create new config with agent replacement logic
        merged_config = apply_template_with_agent_replacement(
            {}, template.template_json
        )
        node_config = NodeConfiguration(
            id=f"cfg-{uuid.uuid4().hex[:12]}",
            org_id=team.org_id,
            node_id=team.team_node_id,
            node_type="team",  # Team-level config
            config_json=merged_config,
            version=1,
            updated_by=team.subject or team.email or "unknown",
        )
        db.add(node_config)
    else:
        # Merge template into existing config with agent replacement
        # This disables built-in agents not in template, then applies template
        merged_config = apply_template_with_agent_replacement(
            node_config.config_json, template.template_json
        )
        node_config.config_json = merged_config
        node_config.version += 1
        node_config.updated_by = team.subject or team.email or "unknown"
        node_config.updated_at = datetime.utcnow()

    # Update template usage count
    template.usage_count = (template.usage_count or 0) + 1

    # Create analytics record
    analytics_id = f"analytics_{uuid.uuid4().hex[:12]}"
    analytics = TemplateAnalytics(
        id=analytics_id,
        template_id=template_id,
        team_node_id=team.team_node_id,
    )
    db.add(analytics)

    db.commit()

    return {
        "success": True,
        "application_id": application_id,
        "message": f"Template '{template.name}' applied successfully",
        "next_steps": [
            f"Configure required integrations: {', '.join(template.required_mcps or [])}",
            "Test your agents with a sample query",
            "Customize agents at /team/agents (optional)",
        ],
    }


@router.get("/api/v1/team/template")
async def get_team_applied_template(
    db: Session = Depends(get_db),
    team: TeamPrincipal = Depends(require_team_auth),
):
    """Get the currently applied template for this team."""
    application = (
        db.query(TemplateApplication)
        .filter(
            and_(
                TemplateApplication.team_node_id == team.team_node_id,
                TemplateApplication.is_active == True,
            )
        )
        .first()
    )

    if not application:
        return {
            "application": None,
            "message": "No template applied. Browse templates at /team/templates",
        }

    template = db.query(Template).filter(Template.id == application.template_id).first()

    return {
        "application": {
            "id": application.id,
            "template_id": application.template_id,
            "template_name": template.name if template else "Unknown",
            "applied_at": application.applied_at.isoformat(),
            "template_version": application.template_version,
            "has_customizations": application.has_customizations,
            "customization_summary": application.customization_summary,
        }
    }


@router.delete("/api/v1/team/template")
async def deactivate_template(
    db: Session = Depends(get_db),
    team: TeamPrincipal = Depends(require_team_auth),
):
    """Deactivate the current template and revert to org defaults."""
    application = (
        db.query(TemplateApplication)
        .filter(
            and_(
                TemplateApplication.team_node_id == team.team_node_id,
                TemplateApplication.is_active == True,
            )
        )
        .first()
    )

    if not application:
        raise HTTPException(status_code=404, detail="No active template found")

    application.is_active = False
    application.deactivated_at = datetime.utcnow()

    db.commit()

    return {
        "success": True,
        "message": "Template deactivated. Team now uses org default configuration.",
    }


# =============================================================================
# Admin Template Management
# =============================================================================


@router.get(
    "/api/v1/admin/templates", response_model=Dict[str, List[TemplateListResponse]]
)
async def list_templates_admin(
    category: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    admin: AdminPrincipal = Depends(require_admin),
):
    """
    List all templates (admin view).

    Shows all templates including unpublished drafts.

    Filters:
    - category: Filter by use_case_category
    - search: Search in name and description
    """
    query = db.query(Template)

    if category:
        query = query.filter(Template.use_case_category == category)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Template.name.ilike(search_pattern),
                Template.description.ilike(search_pattern),
            )
        )

    templates = query.order_by(Template.usage_count.desc()).all()

    return {
        "templates": [
            TemplateListResponse(
                id=t.id,
                name=t.name,
                slug=t.slug,
                description=t.description,
                category=t.use_case_category,
                icon_url=t.icon_url,
                example_scenarios=t.example_scenarios or [],
                required_mcps=t.required_mcps or [],
                usage_count=t.usage_count or 0,
                avg_rating=t.avg_rating,
                version=t.version,
            )
            for t in templates
        ]
    }


@router.get(
    "/api/v1/admin/templates/{template_id}", response_model=TemplateDetailResponse
)
async def get_template_details_admin(
    template_id: str,
    db: Session = Depends(get_db),
    admin: AdminPrincipal = Depends(require_admin),
):
    """Get detailed information about a specific template (admin view)."""
    template = db.query(Template).filter(Template.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return TemplateDetailResponse(
        id=template.id,
        name=template.name,
        slug=template.slug,
        description=template.description,
        detailed_description=template.detailed_description,
        category=template.use_case_category,
        template_json=template.template_json,
        icon_url=template.icon_url,
        example_scenarios=template.example_scenarios or [],
        demo_video_url=template.demo_video_url,
        required_mcps=template.required_mcps or [],
        required_tools=template.required_tools or [],
        version=template.version,
        usage_count=template.usage_count or 0,
        avg_rating=template.avg_rating,
    )


@router.post("/api/v1/admin/templates", response_model=Dict[str, Any])
async def create_template(
    body: TemplateCreateRequest,
    db: Session = Depends(get_db),
    admin: AdminPrincipal = Depends(require_admin),
):
    """Create a new template (admin only)."""
    # Check if slug already exists
    existing = db.query(Template).filter(Template.slug == body.slug).first()
    if existing:
        raise HTTPException(
            status_code=409, detail=f"Template with slug '{body.slug}' already exists"
        )

    template_id = f"tmpl_{uuid.uuid4().hex[:12]}"
    template = Template(
        id=template_id,
        name=body.name,
        slug=body.slug,
        description=body.description,
        detailed_description=body.detailed_description,
        use_case_category=body.category,
        template_json=body.template_json,
        icon_url=body.icon_url,
        example_scenarios=body.example_scenarios,
        demo_video_url=body.demo_video_url,
        is_system_template=True,
        is_published=body.is_published,
        version=body.version,
        required_mcps=body.required_mcps,
        required_tools=body.required_tools,
        created_by=admin.subject or "admin",
    )
    db.add(template)
    db.commit()

    return {
        "id": template_id,
        "slug": body.slug,
        "message": f"Template created successfully ({'published' if body.is_published else 'draft mode'})",
    }


@router.put("/api/v1/admin/templates/{template_id}")
async def update_template(
    template_id: str,
    body: TemplateCreateRequest,
    db: Session = Depends(get_db),
    admin: AdminPrincipal = Depends(require_admin),
):
    """Update an existing template (admin only)."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Count affected teams
    affected_teams = (
        db.query(TemplateApplication)
        .filter(
            and_(
                TemplateApplication.template_id == template_id,
                TemplateApplication.is_active == True,
            )
        )
        .count()
    )

    # Update template fields
    template.name = body.name
    template.description = body.description
    template.detailed_description = body.detailed_description
    template.use_case_category = body.category
    template.template_json = body.template_json
    template.icon_url = body.icon_url
    template.example_scenarios = body.example_scenarios
    template.demo_video_url = body.demo_video_url
    template.is_published = body.is_published
    template.version = body.version
    template.required_mcps = body.required_mcps
    template.required_tools = body.required_tools
    template.updated_at = datetime.utcnow()

    db.commit()

    return {
        "success": True,
        "message": "Template updated",
        "affected_teams": affected_teams,
        "requires_migration": False,  # Future: detect breaking changes
    }


@router.post("/api/v1/admin/templates/{template_id}/apply")
async def apply_template_to_org(
    template_id: str,
    db: Session = Depends(get_db),
    admin: AdminPrincipal = Depends(require_admin),
):
    """
    Apply a template to the organization-level configuration (admin only).

    This merges the template JSON into the org's NodeConfiguration (v2 table).
    All teams will inherit this configuration via the config hierarchy.

    Uses NodeConfiguration (v2) which has effective config caching and better validation.
    """
    # Check if template exists and is published
    template = (
        db.query(Template)
        .filter(
            Template.id == template_id,
            Template.is_published == True,
        )
        .first()
    )

    if not template:
        raise HTTPException(
            status_code=404, detail="Template not found or not published"
        )

    # Get org_id from admin principal
    org_id = admin.org_id

    # Get org node (root node for the organization)
    org_node = (
        db.query(OrgNode)
        .filter(
            and_(
                OrgNode.org_id == org_id,
                OrgNode.parent_id == None,  # Root node
            )
        )
        .first()
    )

    if not org_node:
        raise HTTPException(status_code=404, detail="Organization root node not found")

    # Get or create org's node config (using NodeConfiguration v2)
    from ...db.config_models import NodeConfiguration

    node_config = (
        db.query(NodeConfiguration)
        .filter(
            and_(
                NodeConfiguration.org_id == org_id,
                NodeConfiguration.node_id == org_node.node_id,
            )
        )
        .first()
    )

    if not node_config:
        # Create new config with agent replacement logic
        merged_config = apply_template_with_agent_replacement(
            {}, template.template_json
        )
        node_config = NodeConfiguration(
            id=f"cfg-{uuid.uuid4().hex[:12]}",
            org_id=org_id,
            node_id=org_node.node_id,
            node_type="org",
            config_json=merged_config,
            version=1,
            updated_by=admin.subject or "admin",
        )
        db.add(node_config)
    else:
        # Merge template into existing config with agent replacement
        # This disables built-in agents not in template, then applies template
        merged_config = apply_template_with_agent_replacement(
            node_config.config_json, template.template_json
        )
        node_config.config_json = merged_config
        node_config.version += 1
        node_config.updated_by = admin.subject or "admin"
        node_config.updated_at = datetime.utcnow()

    # Update template usage count
    template.usage_count = (template.usage_count or 0) + 1

    db.commit()

    return {
        "success": True,
        "message": f"Template '{template.name}' applied to organization successfully",
        "next_steps": [
            f"Configure required integrations: {', '.join(template.required_mcps or [])}",
            "All teams will now inherit this agent configuration",
            "Teams can still customize their configurations as needed",
        ],
    }


@router.get("/api/v1/admin/templates/{template_id}/analytics")
async def get_template_analytics(
    template_id: str,
    db: Session = Depends(get_db),
    admin: AdminPrincipal = Depends(require_admin),
):
    """Get usage analytics for a template (admin only)."""
    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # Get all applications
    applications = (
        db.query(TemplateApplication)
        .filter(TemplateApplication.template_id == template_id)
        .all()
    )

    active_applications = [app for app in applications if app.is_active]

    # Get analytics data
    analytics_records = (
        db.query(TemplateAnalytics)
        .filter(TemplateAnalytics.template_id == template_id)
        .all()
    )

    total_runs = sum(a.total_agent_runs for a in analytics_records)
    avg_success_rate = (
        sum(
            a.avg_agent_success_rate
            for a in analytics_records
            if a.avg_agent_success_rate
        )
        / len([a for a in analytics_records if a.avg_agent_success_rate])
        if any(a.avg_agent_success_rate for a in analytics_records)
        else None
    )

    return {
        "template_id": template_id,
        "template_name": template.name,
        "total_applications": len(applications),
        "active_applications": len(active_applications),
        "avg_rating": template.avg_rating,
        "usage_stats": {
            "total_agent_runs": total_runs,
            "avg_runs_per_team": total_runs / len(applications) if applications else 0,
            "avg_success_rate": avg_success_rate,
        },
    }
