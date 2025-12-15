"""
Information Sources API Routes

Provides endpoints for managing general information sources
used by the scraper agent.
"""
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload

from ..db.base import get_db
from ..models.db_models import InformationSource, PendingValidation, PendingItemType

router = APIRouter(prefix="/info-sources", tags=["Information Sources"])


# Request/Response Models
class InfoSourceCreate(BaseModel):
    """Request model for creating an information source."""
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    source_type: Optional[str] = Field(None, description="government, ngo, news, academic, registry, etc.")
    reliability_score: float = Field(0.5, ge=0.0, le=1.0)
    priority: int = Field(5, ge=1, le=10)


class InfoSourceUpdate(BaseModel):
    """Request model for updating an information source."""
    name: Optional[str] = Field(None, max_length=255)
    url: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    source_type: Optional[str] = None
    reliability_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    priority: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None


class InfoSourceResponse(BaseModel):
    """Response model for an information source."""
    id: int
    name: str
    url: str
    description: Optional[str]
    source_type: Optional[str]
    reliability_score: float
    priority: int
    verified: bool
    verified_at: Optional[datetime]
    suggested_by_agent: bool
    is_active: bool
    last_checked_at: Optional[datetime]
    last_successful_scrape: Optional[datetime]
    error_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class InfoSourceListResponse(BaseModel):
    """Response for list of information sources."""
    sources: List[InfoSourceResponse]
    total: int
    verified_count: int
    active_count: int


# Endpoints
@router.get("/", response_model=InfoSourceListResponse)
async def list_info_sources(
    active_only: bool = Query(False, description="Only return active sources"),
    verified_only: bool = Query(False, description="Only return verified sources"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    db: AsyncSession = Depends(get_db),
) -> InfoSourceListResponse:
    """
    List all information sources.
    
    Can filter by active status, verification status, and source type.
    """
    query = select(InformationSource)
    
    if active_only:
        query = query.where(InformationSource.is_active == True)
    if verified_only:
        query = query.where(InformationSource.verified == True)
    if source_type:
        query = query.where(InformationSource.source_type == source_type)
    
    query = query.order_by(InformationSource.priority.desc(), InformationSource.reliability_score.desc())
    
    result = await db.execute(query)
    sources = result.scalars().all()
    
    # Count stats
    total = len(sources)
    verified_count = sum(1 for s in sources if s.verified)
    active_count = sum(1 for s in sources if s.is_active)
    
    return InfoSourceListResponse(
        sources=[InfoSourceResponse.model_validate(s) for s in sources],
        total=total,
        verified_count=verified_count,
        active_count=active_count,
    )


@router.post("/", response_model=InfoSourceResponse)
async def create_info_source(
    source: InfoSourceCreate,
    db: AsyncSession = Depends(get_db),
) -> InfoSourceResponse:
    """
    Create a new information source.
    """
    # Check if URL already exists
    existing = await db.execute(
        select(InformationSource).where(InformationSource.url == source.url)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Source with this URL already exists")
    
    db_source = InformationSource(
        name=source.name,
        url=source.url,
        description=source.description,
        source_type=source.source_type,
        reliability_score=source.reliability_score,
        priority=source.priority,
        verified=True,  # User-created sources are verified by default
        verified_at=datetime.utcnow(),
    )
    
    db.add(db_source)
    await db.commit()
    await db.refresh(db_source)
    
    return InfoSourceResponse.model_validate(db_source)


@router.get("/{source_id}", response_model=InfoSourceResponse)
async def get_info_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> InfoSourceResponse:
    """
    Get a specific information source by ID.
    """
    result = await db.execute(
        select(InformationSource).where(InformationSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Information source not found")
    
    return InfoSourceResponse.model_validate(source)


@router.put("/{source_id}", response_model=InfoSourceResponse)
async def update_info_source(
    source_id: int,
    source_update: InfoSourceUpdate,
    db: AsyncSession = Depends(get_db),
) -> InfoSourceResponse:
    """
    Update an information source.
    """
    result = await db.execute(
        select(InformationSource).where(InformationSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Information source not found")
    
    # Update fields
    update_data = source_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(source, key, value)
    
    await db.commit()
    await db.refresh(source)
    
    return InfoSourceResponse.model_validate(source)


@router.delete("/{source_id}")
async def delete_info_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Delete an information source.
    """
    result = await db.execute(
        select(InformationSource).where(InformationSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Information source not found")
    
    await db.delete(source)
    await db.commit()
    
    return {"message": "Information source deleted", "id": source_id}


@router.post("/{source_id}/verify", response_model=InfoSourceResponse)
async def verify_info_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> InfoSourceResponse:
    """
    Verify an information source (mark as trusted).
    """
    result = await db.execute(
        select(InformationSource).where(InformationSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Information source not found")
    
    source.verified = True
    source.verified_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(source)
    
    return InfoSourceResponse.model_validate(source)


@router.post("/{source_id}/toggle-active", response_model=InfoSourceResponse)
async def toggle_info_source_active(
    source_id: int,
    db: AsyncSession = Depends(get_db),
) -> InfoSourceResponse:
    """
    Toggle the active status of an information source.
    """
    result = await db.execute(
        select(InformationSource).where(InformationSource.id == source_id)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Information source not found")
    
    source.is_active = not source.is_active
    
    await db.commit()
    await db.refresh(source)
    
    return InfoSourceResponse.model_validate(source)


# Source types endpoint
@router.get("/types/all")
async def get_source_types() -> dict:
    """
    Get all available source types.
    """
    return {
        "types": [
            {"value": "government", "label": "🏛️ Gobierno", "description": "Fuentes gubernamentales oficiales"},
            {"value": "registry", "label": "📋 Registro", "description": "Registros oficiales (RUES, Cámaras de Comercio)"},
            {"value": "ngo", "label": "🌱 ONG", "description": "Organizaciones no gubernamentales"},
            {"value": "academic", "label": "🎓 Académico", "description": "Universidades e instituciones de investigación"},
            {"value": "news", "label": "📰 Noticias", "description": "Medios de comunicación"},
            {"value": "cooperative", "label": "🤝 Cooperativa", "description": "Federaciones y confederaciones de cooperativas"},
            {"value": "international", "label": "🌍 Internacional", "description": "Organizaciones internacionales (FAO, BID, etc.)"},
            {"value": "other", "label": "📎 Otro", "description": "Otras fuentes"},
        ]
    }
