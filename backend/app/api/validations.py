"""
Pending Validations API Routes

Provides endpoints for managing pending validations from the chat.
Users validate organizations and information sources suggested by agents.
"""
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_
from sqlalchemy.orm import selectinload

from ..db.base import get_db
from ..models.db_models import (
    PendingValidation, PendingItemType, 
    Organization, OrganizationApproach, TerritorialScope,
    InformationSource
)

router = APIRouter(prefix="/validations", tags=["Pending Validations"])


# Request/Response Models
class PendingValidationResponse(BaseModel):
    """Response model for a pending validation item."""
    id: int
    item_type: str
    session_id: str
    pending_data: dict
    agent_reasoning: Optional[str]
    confidence_score: Optional[float]
    source_urls: Optional[List[str]]
    status: str
    user_decision: Optional[str]
    user_modifications: Optional[dict]
    decision_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True


class PendingValidationListResponse(BaseModel):
    """Response for list of pending validations."""
    validations: List[PendingValidationResponse]
    total: int
    pending_count: int


class ValidationDecision(BaseModel):
    """Request model for user validation decision."""
    decision: str = Field(..., pattern="^(approved|rejected|modified)$")
    modifications: Optional[dict] = None


class CreatePendingValidation(BaseModel):
    """Request model for creating a pending validation (internal use)."""
    item_type: str = Field(..., pattern="^(organization|info_source|organization_update)$")
    session_id: str
    pending_data: dict
    agent_reasoning: Optional[str] = None
    confidence_score: Optional[float] = None
    source_urls: Optional[List[str]] = None
    expires_hours: int = Field(24, ge=1, le=168)  # 1 hour to 1 week


# Endpoints
@router.get("/", response_model=PendingValidationListResponse)
async def list_pending_validations(
    session_id: Optional[str] = Query(None, description="Filter by session ID"),
    item_type: Optional[str] = Query(None, description="Filter by item type"),
    status: str = Query("pending", description="Filter by status"),
    db: AsyncSession = Depends(get_db),
) -> PendingValidationListResponse:
    """
    List pending validations.
    
    Can filter by session ID, item type, and status.
    """
    query = select(PendingValidation).where(PendingValidation.status == status)
    
    if session_id:
        query = query.where(PendingValidation.session_id == session_id)
    if item_type:
        query = query.where(PendingValidation.item_type == PendingItemType(item_type))
    
    query = query.order_by(PendingValidation.created_at.desc())
    
    result = await db.execute(query)
    validations = result.scalars().all()
    
    total = len(validations)
    pending_count = sum(1 for v in validations if v.status == "pending")
    
    return PendingValidationListResponse(
        validations=[
            PendingValidationResponse(
                id=v.id,
                item_type=v.item_type.value,
                session_id=v.session_id,
                pending_data=v.pending_data,
                agent_reasoning=v.agent_reasoning,
                confidence_score=v.confidence_score,
                source_urls=v.source_urls,
                status=v.status,
                user_decision=v.user_decision,
                user_modifications=v.user_modifications,
                decision_at=v.decision_at,
                created_at=v.created_at,
                expires_at=v.expires_at,
            )
            for v in validations
        ],
        total=total,
        pending_count=pending_count,
    )


@router.get("/session/{session_id}", response_model=PendingValidationListResponse)
async def get_session_validations(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> PendingValidationListResponse:
    """
    Get all pending validations for a specific chat session.
    """
    query = select(PendingValidation).where(
        and_(
            PendingValidation.session_id == session_id,
            PendingValidation.status == "pending"
        )
    ).order_by(PendingValidation.created_at.desc())
    
    result = await db.execute(query)
    validations = result.scalars().all()
    
    return PendingValidationListResponse(
        validations=[
            PendingValidationResponse(
                id=v.id,
                item_type=v.item_type.value,
                session_id=v.session_id,
                pending_data=v.pending_data,
                agent_reasoning=v.agent_reasoning,
                confidence_score=v.confidence_score,
                source_urls=v.source_urls,
                status=v.status,
                user_decision=v.user_decision,
                user_modifications=v.user_modifications,
                decision_at=v.decision_at,
                created_at=v.created_at,
                expires_at=v.expires_at,
            )
            for v in validations
        ],
        total=len(validations),
        pending_count=len(validations),
    )


@router.get("/{validation_id}", response_model=PendingValidationResponse)
async def get_validation(
    validation_id: int,
    db: AsyncSession = Depends(get_db),
) -> PendingValidationResponse:
    """
    Get a specific pending validation by ID.
    """
    result = await db.execute(
        select(PendingValidation).where(PendingValidation.id == validation_id)
    )
    validation = result.scalar_one_or_none()
    
    if not validation:
        raise HTTPException(status_code=404, detail="Validation not found")
    
    return PendingValidationResponse(
        id=validation.id,
        item_type=validation.item_type.value,
        session_id=validation.session_id,
        pending_data=validation.pending_data,
        agent_reasoning=validation.agent_reasoning,
        confidence_score=validation.confidence_score,
        source_urls=validation.source_urls,
        status=validation.status,
        user_decision=validation.user_decision,
        user_modifications=validation.user_modifications,
        decision_at=validation.decision_at,
        created_at=validation.created_at,
        expires_at=validation.expires_at,
    )


@router.post("/{validation_id}/decide", response_model=dict)
async def decide_validation(
    validation_id: int,
    decision: ValidationDecision,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Submit a user decision for a pending validation.
    
    Decisions:
    - approved: Accept and save the data as-is
    - rejected: Discard the data
    - modified: Accept with user modifications
    """
    result = await db.execute(
        select(PendingValidation).where(PendingValidation.id == validation_id)
    )
    validation = result.scalar_one_or_none()
    
    if not validation:
        raise HTTPException(status_code=404, detail="Validation not found")
    
    if validation.status != "pending":
        raise HTTPException(status_code=400, detail="Validation already processed")
    
    # Update validation record
    validation.status = decision.decision
    validation.user_decision = decision.decision
    validation.user_modifications = decision.modifications
    validation.decision_at = datetime.utcnow()
    
    created_item = None
    
    # Process the decision
    if decision.decision in ["approved", "modified"]:
        data = decision.modifications if decision.modifications else validation.pending_data
        
        if validation.item_type == PendingItemType.ORGANIZATION:
            # Create organization
            created_item = await _create_organization_from_validation(db, data)
        elif validation.item_type == PendingItemType.INFO_SOURCE:
            # Create information source
            created_item = await _create_info_source_from_validation(db, data)
        elif validation.item_type == PendingItemType.ORGANIZATION_UPDATE:
            # Update existing organization
            created_item = await _update_organization_from_validation(db, data)
    
    await db.commit()
    
    return {
        "message": f"Validation {decision.decision}",
        "validation_id": validation_id,
        "created_item": created_item,
    }


@router.post("/", response_model=PendingValidationResponse)
async def create_pending_validation(
    validation: CreatePendingValidation,
    db: AsyncSession = Depends(get_db),
) -> PendingValidationResponse:
    """
    Create a new pending validation (used by agents).
    """
    expires_at = datetime.utcnow() + timedelta(hours=validation.expires_hours)
    
    db_validation = PendingValidation(
        item_type=PendingItemType(validation.item_type),
        session_id=validation.session_id,
        pending_data=validation.pending_data,
        agent_reasoning=validation.agent_reasoning,
        confidence_score=validation.confidence_score,
        source_urls=validation.source_urls,
        status="pending",
        expires_at=expires_at,
    )
    
    db.add(db_validation)
    await db.commit()
    await db.refresh(db_validation)
    
    return PendingValidationResponse(
        id=db_validation.id,
        item_type=db_validation.item_type.value,
        session_id=db_validation.session_id,
        pending_data=db_validation.pending_data,
        agent_reasoning=db_validation.agent_reasoning,
        confidence_score=db_validation.confidence_score,
        source_urls=db_validation.source_urls,
        status=db_validation.status,
        user_decision=db_validation.user_decision,
        user_modifications=db_validation.user_modifications,
        decision_at=db_validation.decision_at,
        created_at=db_validation.created_at,
        expires_at=db_validation.expires_at,
    )


@router.delete("/expired")
async def cleanup_expired_validations(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Clean up expired pending validations.
    """
    result = await db.execute(
        update(PendingValidation)
        .where(
            and_(
                PendingValidation.status == "pending",
                PendingValidation.expires_at < datetime.utcnow()
            )
        )
        .values(status="expired")
    )
    
    await db.commit()
    
    return {"message": "Expired validations cleaned up", "count": result.rowcount}


# Helper functions
async def _create_organization_from_validation(db: AsyncSession, data: dict) -> dict:
    """Create an organization from validated data."""
    # Map approach string to enum
    approach = OrganizationApproach.UNKNOWN
    if data.get("approach"):
        approach_map = {
            "bottom_up": OrganizationApproach.BOTTOM_UP,
            "top_down": OrganizationApproach.TOP_DOWN,
            "mixed": OrganizationApproach.MIXED,
            "abajo": OrganizationApproach.BOTTOM_UP,
            "arriba": OrganizationApproach.TOP_DOWN,
        }
        approach = approach_map.get(data["approach"].lower(), OrganizationApproach.UNKNOWN)
    
    # Map territorial scope
    scope = TerritorialScope.MUNICIPAL
    if data.get("territorial_scope"):
        scope_map = {
            "municipal": TerritorialScope.MUNICIPAL,
            "departamental": TerritorialScope.DEPARTAMENTAL,
            "regional": TerritorialScope.REGIONAL,
            "nacional": TerritorialScope.NACIONAL,
        }
        scope = scope_map.get(data["territorial_scope"].lower(), TerritorialScope.MUNICIPAL)
    
    organization = Organization(
        name=data.get("name", "Sin nombre"),
        url=data.get("url"),
        description=data.get("description"),
        latitude=data.get("latitude"),
        longitude=data.get("longitude"),
        territorial_scope=scope,
        department_code=data.get("department_code"),
        municipality_code=data.get("municipality_code"),
        department_codes=data.get("department_codes"),
        years_active=data.get("years_active"),
        women_count=data.get("women_count"),
        leader_is_woman=data.get("leader_is_woman"),
        leader_name=data.get("leader_name"),
        approach=approach,
        is_peace_building=data.get("is_peace_building", True),
        verified=True,
        verified_at=datetime.utcnow(),
    )
    
    db.add(organization)
    await db.flush()
    
    return {"type": "organization", "id": organization.id, "name": organization.name}


async def _create_info_source_from_validation(db: AsyncSession, data: dict) -> dict:
    """Create an information source from validated data."""
    # Check if URL already exists
    existing = await db.execute(
        select(InformationSource).where(InformationSource.url == data.get("url"))
    )
    if existing.scalar_one_or_none():
        return {"type": "info_source", "error": "URL already exists"}
    
    source = InformationSource(
        name=data.get("name", "Sin nombre"),
        url=data.get("url"),
        description=data.get("description"),
        source_type=data.get("source_type"),
        reliability_score=data.get("reliability_score", 0.5),
        priority=data.get("priority", 5),
        verified=True,
        verified_at=datetime.utcnow(),
        suggested_by_agent=True,
    )
    
    db.add(source)
    await db.flush()
    
    return {"type": "info_source", "id": source.id, "name": source.name}


async def _update_organization_from_validation(db: AsyncSession, data: dict) -> dict:
    """Update an existing organization from validated data."""
    organization_id = data.get("organization_id")
    if not organization_id:
        return {"type": "organization_update", "error": "No organization ID provided"}
    
    result = await db.execute(
        select(Organization).where(Organization.id == organization_id)
    )
    organization = result.scalar_one_or_none()
    
    if not organization:
        return {"type": "organization_update", "error": "Organization not found"}
    
    # Update fields that are provided
    update_fields = [
        "name", "url", "description", "latitude", "longitude",
        "department_code", "municipality_code", "department_codes",
        "years_active", "women_count", "leader_is_woman", "leader_name",
        "is_peace_building"
    ]
    
    for field in update_fields:
        if field in data and data[field] is not None:
            setattr(organization, field, data[field])
    
    # Handle approach separately
    if data.get("approach"):
        approach_map = {
            "bottom_up": OrganizationApproach.BOTTOM_UP,
            "top_down": OrganizationApproach.TOP_DOWN,
            "mixed": OrganizationApproach.MIXED,
        }
        organization.approach = approach_map.get(data["approach"].lower(), OrganizationApproach.UNKNOWN)
    
    # Handle territorial scope separately
    if data.get("territorial_scope"):
        scope_map = {
            "municipal": TerritorialScope.MUNICIPAL,
            "departamental": TerritorialScope.DEPARTAMENTAL,
            "regional": TerritorialScope.REGIONAL,
            "nacional": TerritorialScope.NACIONAL,
        }
        organization.territorial_scope = scope_map.get(data["territorial_scope"].lower(), organization.territorial_scope)
    
    organization.verified = True
    organization.verified_at = datetime.utcnow()
    
    return {"type": "organization_update", "id": organization.id, "name": organization.name}
