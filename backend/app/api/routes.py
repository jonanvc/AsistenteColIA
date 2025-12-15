"""
API routes for organizations, scraping, and data operations.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from app.db.base import get_db
from app.models.db_models import Organization, Variable, Location
from app.services.scraper import scrape_organization

router = APIRouter()


# ============== Pydantic Schemas ==============

class OrganizationBase(BaseModel):
    """Base schema for Organization."""
    name: str
    url: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    class Config:
        from_attributes = True


class OrganizationCreate(OrganizationBase):
    """Schema for creating an Organization."""
    pass


class OrganizationResponse(OrganizationBase):
    """Schema for Organization response."""
    id: int
    is_international: Optional[bool] = False
    territorial_scope: Optional[str] = None
    department_code: Optional[str] = None
    municipality_code: Optional[str] = None
    years_active: Optional[int] = None
    women_count: Optional[int] = None
    leader_is_woman: Optional[bool] = None
    leader_name: Optional[str] = None
    approach: Optional[str] = None
    is_peace_building: Optional[bool] = None
    verified: Optional[bool] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class VariableBase(BaseModel):
    """Base schema for Variable."""
    key: str
    value: dict
    source_url: Optional[str] = None
    verified: bool = False


class VariableCreate(VariableBase):
    """Schema for creating a Variable."""
    organization_id: int


class VariableResponse(VariableBase):
    """Schema for Variable response."""
    id: int
    organization_id: int
    scraped_at: datetime


class VariableVerify(BaseModel):
    """Schema for verifying a variable."""
    verified: bool


class LocationResponse(BaseModel):
    """Schema for Location response."""
    id: int
    organization_id: int
    name: str
    geojson: dict
    properties: Optional[dict] = None

    class Config:
        from_attributes = True


class ScrapeRequest(BaseModel):
    """Schema for scrape request."""
    organization_id: Optional[int] = None
    all_organizations: bool = False


class ScrapeResponse(BaseModel):
    """Schema for scrape response."""
    status: str
    message: str
    task_id: Optional[str] = None


# ============== Organization Endpoints ==============

@router.get("/organizations", response_model=List[OrganizationResponse])
async def list_organizations(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    List all organizations with pagination.
    """
    result = await db.execute(
        select(Organization).offset(skip).limit(limit)
    )
    organizations = result.scalars().all()
    return organizations


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
async def get_organization(
    organization_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific organization by ID.
    """
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    return organization


@router.post("/organizations", response_model=OrganizationResponse)
async def create_organization(
    organization: OrganizationCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new organization.
    """
    db_organization = Organization(**organization.model_dump())
    db.add(db_organization)
    await db.commit()
    await db.refresh(db_organization)
    return db_organization


# ============== Variable Endpoints ==============

@router.get("/organizations/{organization_id}/variables", response_model=List[VariableResponse])
async def list_variables(
    organization_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    List all variables for a specific organization.
    """
    result = await db.execute(
        select(Variable).where(Variable.organization_id == organization_id)
    )
    variables = result.scalars().all()
    return variables


@router.post("/variables", response_model=VariableResponse)
async def save_variable(
    variable: VariableCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Save a new variable for an organization.
    """
    db_variable = Variable(**variable.model_dump())
    db.add(db_variable)
    await db.commit()
    await db.refresh(db_variable)
    return db_variable


@router.patch("/variables/{variable_id}/verify", response_model=VariableResponse)
async def verify_variable(
    variable_id: int,
    verification: VariableVerify,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify or unverify a variable.
    """
    result = await db.execute(
        select(Variable).where(Variable.id == variable_id)
    )
    variable = result.scalar_one_or_none()
    if not variable:
        raise HTTPException(status_code=404, detail="Variable not found")
    
    variable.verified = verification.verified
    await db.commit()
    await db.refresh(variable)
    return variable


@router.get("/variables/keys")
async def get_variable_keys(db: AsyncSession = Depends(get_db)):
    """
    Get all unique variable keys.
    """
    result = await db.execute(
        select(Variable.key).distinct()
    )
    keys = result.scalars().all()
    return {"keys": keys}


# ============== Scraping Endpoints ==============

@router.post("/scrape", response_model=ScrapeResponse)
async def launch_scraping(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Launch scraping for one or all organizations.
    Uses Celery task if available, otherwise runs in background.
    """
    try:
        # Try to use Celery
        from worker.worker import scrape_task
        
        if request.all_organizations:
            result = await db.execute(select(Organization.id))
            organization_ids = result.scalars().all()
            for oid in organization_ids:
                scrape_task.delay(oid)
            return ScrapeResponse(
                status="queued",
                message=f"Scraping queued for {len(organization_ids)} organizations"
            )
        elif request.organization_id:
            task = scrape_task.delay(request.organization_id)
            return ScrapeResponse(
                status="queued",
                message=f"Scraping queued for organization {request.organization_id}",
                task_id=task.id
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Provide organization_id or set all_organizations=true"
            )
    except ImportError:
        # Celery not available, run in background
        if request.organization_id:
            background_tasks.add_task(scrape_organization, request.organization_id)
            return ScrapeResponse(
                status="running",
                message=f"Scraping started for organization {request.organization_id}"
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Celery not available for batch scraping. Provide organization_id."
            )


# ============== Map Data Endpoints ==============

@router.get("/map/locations")
async def get_map_data(
    vars: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get location data for map visualization.
    Optionally filter by variable keys.
    """
    # Get all locations with their organizations
    result = await db.execute(
        select(Location, Organization)
        .join(Organization, Location.organization_id == Organization.id)
    )
    rows = result.all()
    
    # Build GeoJSON FeatureCollection
    features = []
    for location, organization in rows:
        # Get variables for this organization if filter is specified
        properties = {
            "organization_id": organization.id,
            "organization_name": organization.name,
            "location_name": location.name,
            **(location.properties or {})
        }
        
        if vars:
            var_keys = vars.split(",")
            var_result = await db.execute(
                select(Variable)
                .where(Variable.organization_id == organization.id)
                .where(Variable.key.in_(var_keys))
            )
            variables = var_result.scalars().all()
            for v in variables:
                properties[v.key] = v.value
        
        feature = {
            "type": "Feature",
            "geometry": location.geojson,
            "properties": properties
        }
        features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


@router.get("/map/organizations")
async def get_organizations_for_map(db: AsyncSession = Depends(get_db)):
    """
    Get organizations with coordinates for simple marker map.
    """
    result = await db.execute(
        select(Organization).where(
            Organization.latitude.isnot(None),
            Organization.longitude.isnot(None)
        )
    )
    organizations = result.scalars().all()
    
    features = []
    for org in organizations:
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [org.longitude, org.latitude]
            },
            "properties": {
                "id": org.id,
                "name": org.name,
                "description": org.description,
                "url": org.url
            }
        }
        features.append(feature)
    
    return {
        "type": "FeatureCollection",
        "features": features
    }
