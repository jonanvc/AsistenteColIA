"""
API routes for managing organizations and their links.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel
from datetime import datetime

from app.db.base import get_db
from app.models.db_models import Organization, OrganizationLink, TerritorialScope, OrganizationApproach

router = APIRouter()


# ============== Pydantic Schemas ==============

class OrganizationLinkBase(BaseModel):
    """Base schema for OrganizationLink."""
    url: str
    link_type: Optional[str] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class OrganizationLinkCreate(OrganizationLinkBase):
    """Schema for creating an OrganizationLink."""
    pass


class OrganizationLinkResponse(OrganizationLinkBase):
    """Schema for OrganizationLink response."""
    id: int
    organization_id: int
    last_scraped_at: Optional[datetime] = None
    scrape_status: Optional[str] = None
    created_at: datetime


class OrganizationWithLinks(BaseModel):
    """Schema for Organization with its links."""
    id: int
    name: str
    url: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_international: Optional[bool] = False
    territorial_scope: Optional[str] = None
    department_code: Optional[str] = None
    municipality_code: Optional[str] = None
    department_codes: Optional[List[str]] = None
    years_active: Optional[int] = None
    women_count: Optional[int] = None
    leader_is_woman: Optional[bool] = None
    leader_name: Optional[str] = None
    approach: Optional[str] = None
    is_peace_building: Optional[bool] = None
    verified: Optional[bool] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    links: List[OrganizationLinkResponse] = []

    class Config:
        from_attributes = True


class OrganizationCreateWithLinks(BaseModel):
    """Schema for creating Organization with links."""
    name: str
    url: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_international: Optional[bool] = False
    territorial_scope: Optional[str] = None
    department_code: Optional[str] = None
    municipality_code: Optional[str] = None
    department_codes: Optional[List[str]] = None
    years_active: Optional[int] = None
    women_count: Optional[int] = None
    leader_is_woman: Optional[bool] = None
    leader_name: Optional[str] = None
    approach: Optional[str] = None
    is_peace_building: Optional[bool] = True
    links: List[OrganizationLinkCreate] = []


class OrganizationUpdate(BaseModel):
    """Schema for updating Organization."""
    name: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    is_international: Optional[bool] = None
    territorial_scope: Optional[str] = None
    department_code: Optional[str] = None
    municipality_code: Optional[str] = None
    department_codes: Optional[List[str]] = None
    years_active: Optional[int] = None
    women_count: Optional[int] = None
    leader_is_woman: Optional[bool] = None
    leader_name: Optional[str] = None
    approach: Optional[str] = None
    is_peace_building: Optional[bool] = None
    links: Optional[List[OrganizationLinkCreate]] = None


# ============== Organization Management Endpoints ==============

@router.get("/full", response_model=List[OrganizationWithLinks])
async def list_organizations_with_links(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    List all organizations with their links.
    """
    result = await db.execute(
        select(Organization).offset(skip).limit(limit)
    )
    organizations = result.scalars().all()
    
    # Load links for each organization
    response = []
    for org in organizations:
        links_result = await db.execute(
            select(OrganizationLink).where(OrganizationLink.organization_id == org.id)
        )
        links = links_result.scalars().all()
        
        org_dict = {
            "id": org.id,
            "name": org.name,
            "url": org.url,
            "description": org.description,
            "latitude": org.latitude,
            "longitude": org.longitude,
            "is_international": org.is_international,
            "territorial_scope": org.territorial_scope.value if org.territorial_scope else None,
            "department_code": org.department_code,
            "municipality_code": org.municipality_code,
            "department_codes": org.department_codes,
            "years_active": org.years_active,
            "women_count": org.women_count,
            "leader_is_woman": org.leader_is_woman,
            "leader_name": org.leader_name,
            "approach": org.approach.value if org.approach else None,
            "is_peace_building": org.is_peace_building,
            "verified": org.verified,
            "created_at": org.created_at,
            "updated_at": org.updated_at,
            "links": links
        }
        response.append(org_dict)
    
    return response


@router.post("/full", response_model=OrganizationWithLinks)
async def create_organization_with_links(
    data: OrganizationCreateWithLinks,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new organization with its links.
    """
    # Map territorial_scope string to enum
    territorial_scope = None
    if data.territorial_scope:
        scope_map = {
            "municipal": TerritorialScope.MUNICIPAL,
            "departamental": TerritorialScope.DEPARTAMENTAL,
            "regional": TerritorialScope.REGIONAL,
            "nacional": TerritorialScope.NACIONAL,
            "internacional": TerritorialScope.INTERNACIONAL,
        }
        territorial_scope = scope_map.get(data.territorial_scope.lower(), TerritorialScope.MUNICIPAL)
    
    # Map approach string to enum
    approach = OrganizationApproach.UNKNOWN
    if data.approach:
        approach_map = {
            "bottom_up": OrganizationApproach.BOTTOM_UP,
            "top_down": OrganizationApproach.TOP_DOWN,
            "mixed": OrganizationApproach.MIXED,
            "unknown": OrganizationApproach.UNKNOWN,
        }
        approach = approach_map.get(data.approach.lower(), OrganizationApproach.UNKNOWN)
    
    # Create organization
    organization = Organization(
        name=data.name,
        url=data.url,
        description=data.description,
        latitude=data.latitude,
        longitude=data.longitude,
        is_international=data.is_international,
        territorial_scope=territorial_scope,
        department_code=data.department_code,
        municipality_code=data.municipality_code,
        department_codes=data.department_codes,
        years_active=data.years_active,
        women_count=data.women_count,
        leader_is_woman=data.leader_is_woman,
        leader_name=data.leader_name,
        approach=approach,
        is_peace_building=data.is_peace_building if data.is_peace_building is not None else True,
    )
    db.add(organization)
    await db.flush()
    
    # Create links
    created_links = []
    for link_data in data.links:
        link = OrganizationLink(
            organization_id=organization.id,
            url=link_data.url,
            link_type=link_data.link_type,
            description=link_data.description
        )
        db.add(link)
        created_links.append(link)
    
    await db.commit()
    await db.refresh(organization)
    
    return {
        "id": organization.id,
        "name": organization.name,
        "url": organization.url,
        "description": organization.description,
        "latitude": organization.latitude,
        "longitude": organization.longitude,
        "is_international": organization.is_international,
        "territorial_scope": organization.territorial_scope.value if organization.territorial_scope else None,
        "department_code": organization.department_code,
        "municipality_code": organization.municipality_code,
        "department_codes": organization.department_codes,
        "years_active": organization.years_active,
        "women_count": organization.women_count,
        "leader_is_woman": organization.leader_is_woman,
        "leader_name": organization.leader_name,
        "approach": organization.approach.value if organization.approach else None,
        "is_peace_building": organization.is_peace_building,
        "verified": organization.verified,
        "created_at": organization.created_at,
        "updated_at": organization.updated_at,
        "links": created_links
    }


@router.put("/{organization_id}", response_model=OrganizationWithLinks)
async def update_organization(
    organization_id: int,
    data: OrganizationUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update an organization with all its fields.
    """
    from app.models.db_models import TerritorialScope, OrganizationApproach
    
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Update basic fields
    if data.name is not None:
        organization.name = data.name
    if data.url is not None:
        organization.url = data.url
    if data.description is not None:
        organization.description = data.description
    if data.latitude is not None:
        organization.latitude = data.latitude
    if data.longitude is not None:
        organization.longitude = data.longitude
    if data.is_international is not None:
        organization.is_international = data.is_international
    
    # Update territorial scope
    if data.territorial_scope is not None:
        scope_map = {
            "municipal": TerritorialScope.MUNICIPAL,
            "departamental": TerritorialScope.DEPARTAMENTAL,
            "regional": TerritorialScope.REGIONAL,
            "nacional": TerritorialScope.NACIONAL,
            "internacional": TerritorialScope.INTERNACIONAL,
        }
        organization.territorial_scope = scope_map.get(data.territorial_scope.lower(), TerritorialScope.MUNICIPAL)
    
    # Update location codes
    if data.department_code is not None:
        organization.department_code = data.department_code if data.department_code else None
    if data.municipality_code is not None:
        organization.municipality_code = data.municipality_code if data.municipality_code else None
    if data.department_codes is not None:
        organization.department_codes = data.department_codes if data.department_codes else None
    
    # Update organization details
    if data.years_active is not None:
        organization.years_active = data.years_active
    if data.women_count is not None:
        organization.women_count = data.women_count
    if data.leader_is_woman is not None:
        organization.leader_is_woman = data.leader_is_woman
    if data.leader_name is not None:
        organization.leader_name = data.leader_name
    if data.is_peace_building is not None:
        organization.is_peace_building = data.is_peace_building
    
    # Update approach
    if data.approach is not None:
        approach_map = {
            "bottom_up": OrganizationApproach.BOTTOM_UP,
            "top_down": OrganizationApproach.TOP_DOWN,
            "mixed": OrganizationApproach.MIXED,
            "unknown": OrganizationApproach.UNKNOWN,
        }
        organization.approach = approach_map.get(data.approach.lower(), OrganizationApproach.UNKNOWN)
    
    # Handle links if provided
    if data.links is not None:
        # Delete existing links
        await db.execute(
            delete(OrganizationLink).where(OrganizationLink.organization_id == organization_id)
        )
        # Create new links
        for link_data in data.links:
            if link_data.url:
                link = OrganizationLink(
                    organization_id=organization_id,
                    url=link_data.url,
                    link_type=link_data.link_type,
                    description=link_data.description
                )
                db.add(link)
    
    await db.commit()
    await db.refresh(organization)
    
    # Get links
    links_result = await db.execute(
        select(OrganizationLink).where(OrganizationLink.organization_id == organization.id)
    )
    links = links_result.scalars().all()
    
    return {
        "id": organization.id,
        "name": organization.name,
        "url": organization.url,
        "description": organization.description,
        "latitude": organization.latitude,
        "longitude": organization.longitude,
        "is_international": organization.is_international,
        "created_at": organization.created_at,
        "updated_at": organization.updated_at,
        "links": links
    }


@router.delete("/{organization_id}")
async def delete_organization(
    organization_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete an organization and all its related data.
    """
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    await db.delete(organization)
    await db.commit()
    
    return {"status": "deleted", "id": organization_id}


# ============== Link Management Endpoints ==============

@router.get("/{organization_id}/links", response_model=List[OrganizationLinkResponse])
async def list_organization_links(
    organization_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    List all links for an organization.
    """
    result = await db.execute(
        select(OrganizationLink).where(OrganizationLink.organization_id == organization_id)
    )
    links = result.scalars().all()
    return links


@router.post("/{organization_id}/links", response_model=OrganizationLinkResponse)
async def add_organization_link(
    organization_id: int,
    data: OrganizationLinkCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Add a link to an organization.
    """
    # Verify organization exists
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Organization not found")
    
    link = OrganizationLink(
        organization_id=organization_id,
        url=data.url,
        link_type=data.link_type,
        description=data.description
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    
    return link


@router.delete("/links/{link_id}")
async def delete_organization_link(
    link_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a link.
    """
    result = await db.execute(
        select(OrganizationLink).where(OrganizationLink.id == link_id)
    )
    link = result.scalar_one_or_none()
    
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    
    await db.delete(link)
    await db.commit()
    
    return {"status": "deleted", "id": link_id}
