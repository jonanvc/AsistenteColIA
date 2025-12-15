"""
API routes for scraping configuration, execution, and progress tracking.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pydantic import BaseModel
from datetime import datetime
import asyncio
import json

from app.db.base import get_db, async_session_maker
from app.models.db_models import (
    ScrapingConfig, ScrapingSession, ScrapedData,
    Organization, OrganizationLink
)

router = APIRouter()

# Store active WebSocket connections for progress updates
active_connections: dict = {}


# ============== Pydantic Schemas ==============

class ScrapingConfigBase(BaseModel):
    """Base schema for ScrapingConfig."""
    name: str = "default"
    max_depth: int = 2
    timeout: int = 30000
    wait_time: int = 2000
    max_pages_per_association: int = 10
    follow_external_links: bool = False
    respect_robots_txt: bool = True
    headless: bool = True
    user_agent: Optional[str] = None
    viewport_width: int = 1280
    viewport_height: int = 720
    delay_between_requests: int = 1000
    max_concurrent_pages: int = 3

    class Config:
        from_attributes = True


class ScrapingConfigCreate(ScrapingConfigBase):
    """Schema for creating ScrapingConfig."""
    pass


class ScrapingConfigResponse(ScrapingConfigBase):
    """Schema for ScrapingConfig response."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None


class ScrapingSessionResponse(BaseModel):
    """Schema for ScrapingSession response."""
    id: int
    status: str
    total_associations: int
    processed_associations: int
    total_links: int
    processed_links: int
    variables_found: int
    errors_count: int
    current_association_id: Optional[int] = None
    current_url: Optional[str] = None
    progress_percent: float
    config_id: Optional[int] = None
    results_summary: Optional[dict] = None
    error_log: Optional[dict] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ScrapedDataResponse(BaseModel):
    """Schema for ScrapedData response."""
    id: int
    session_id: int
    association_id: int
    variable_key: str
    variable_value: dict
    source_url: str
    source_context: Optional[str] = None
    auto_verified: bool
    auto_verification_score: Optional[float] = None
    auto_verification_reason: Optional[str] = None
    manually_verified: Optional[bool] = None
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    scraped_at: datetime

    class Config:
        from_attributes = True


class ScrapedDataWithOrganization(ScrapedDataResponse):
    """Schema for ScrapedData with organization name."""
    organization_name: str


class LaunchScrapingRequest(BaseModel):
    """Schema for launching a scraping session."""
    config_id: Optional[int] = None
    organization_ids: Optional[List[int]] = None  # None = all organizations


class VerifyDataRequest(BaseModel):
    """Schema for manually verifying scraped data."""
    verified: bool
    verified_by: Optional[str] = "user"


# ============== Scraping Config Endpoints ==============

@router.get("/configs", response_model=List[ScrapingConfigResponse])
async def list_scraping_configs(
    db: AsyncSession = Depends(get_db)
):
    """
    List all scraping configurations.
    """
    result = await db.execute(select(ScrapingConfig))
    configs = result.scalars().all()
    return configs


@router.get("/configs/active", response_model=ScrapingConfigResponse)
async def get_active_config(
    db: AsyncSession = Depends(get_db)
):
    """
    Get the currently active scraping configuration.
    """
    result = await db.execute(
        select(ScrapingConfig).where(ScrapingConfig.is_active == True)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        # Create default config if none exists
        config = ScrapingConfig(name="default", is_active=True)
        db.add(config)
        await db.commit()
        await db.refresh(config)
    
    return config


@router.post("/configs", response_model=ScrapingConfigResponse)
async def create_scraping_config(
    data: ScrapingConfigCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new scraping configuration.
    """
    config = ScrapingConfig(**data.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


@router.put("/configs/{config_id}", response_model=ScrapingConfigResponse)
async def update_scraping_config(
    config_id: int,
    data: ScrapingConfigCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a scraping configuration.
    """
    result = await db.execute(
        select(ScrapingConfig).where(ScrapingConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    for key, value in data.model_dump().items():
        setattr(config, key, value)
    
    await db.commit()
    await db.refresh(config)
    return config


@router.post("/configs/{config_id}/activate", response_model=ScrapingConfigResponse)
async def activate_config(
    config_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Set a configuration as the active one.
    """
    # Deactivate all configs
    result = await db.execute(select(ScrapingConfig))
    all_configs = result.scalars().all()
    for c in all_configs:
        c.is_active = False
    
    # Activate the selected config
    result = await db.execute(
        select(ScrapingConfig).where(ScrapingConfig.id == config_id)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    
    config.is_active = True
    await db.commit()
    await db.refresh(config)
    return config


# ============== Scraping Session Endpoints ==============

@router.get("/sessions", response_model=List[ScrapingSessionResponse])
async def list_scraping_sessions(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    List recent scraping sessions.
    """
    result = await db.execute(
        select(ScrapingSession).order_by(desc(ScrapingSession.created_at)).limit(limit)
    )
    sessions = result.scalars().all()
    return sessions


@router.get("/sessions/{session_id}", response_model=ScrapingSessionResponse)
async def get_scraping_session(
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific scraping session.
    """
    result = await db.execute(
        select(ScrapingSession).where(ScrapingSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return session


@router.post("/sessions/launch", response_model=ScrapingSessionResponse)
async def launch_scraping_session(
    request: LaunchScrapingRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Launch a new scraping session.
    """
    # Get config
    if request.config_id:
        config_result = await db.execute(
            select(ScrapingConfig).where(ScrapingConfig.id == request.config_id)
        )
        config = config_result.scalar_one_or_none()
    else:
        config_result = await db.execute(
            select(ScrapingConfig).where(ScrapingConfig.is_active == True)
        )
        config = config_result.scalar_one_or_none()
    
    if not config:
        # Create default config
        config = ScrapingConfig(name="default", is_active=True)
        db.add(config)
        await db.flush()
    
    # Get organizations to scrape
    if request.organization_ids:
        org_result = await db.execute(
            select(Organization).where(Organization.id.in_(request.organization_ids))
        )
    else:
        org_result = await db.execute(select(Organization))
    
    organizations = org_result.scalars().all()
    
    if not organizations:
        raise HTTPException(status_code=400, detail="No organizations to scrape")
    
    # Count total links
    total_links = 0
    for org in organizations:
        links_result = await db.execute(
            select(OrganizationLink).where(OrganizationLink.organization_id == org.id)
        )
        links = links_result.scalars().all()
        total_links += len(links)
        if org.url:
            total_links += 1
    
    # Create session
    session = ScrapingSession(
        status="pending",
        total_organizations=len(organizations),
        total_links=total_links,
        config_id=config.id
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    # Start scraping in background (simulated for now)
    asyncio.create_task(run_scraping_session(session.id, [o.id for o in organizations], config.id))
    
    return session


@router.post("/sessions/{session_id}/cancel")
async def cancel_scraping_session(
    session_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Cancel a running scraping session.
    """
    result = await db.execute(
        select(ScrapingSession).where(ScrapingSession.id == session_id)
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if session.status not in ["pending", "running"]:
        raise HTTPException(status_code=400, detail="Session cannot be cancelled")
    
    session.status = "cancelled"
    session.completed_at = datetime.utcnow()
    await db.commit()
    
    return {"status": "cancelled", "id": session_id}


# ============== Scraped Data Endpoints ==============

@router.get("/sessions/{session_id}/data", response_model=List[ScrapedDataWithOrganization])
async def get_session_data(
    session_id: int,
    verified_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all scraped data from a session.
    """
    query = select(ScrapedData, Organization.name).join(
        Organization, ScrapedData.organization_id == Organization.id
    ).where(ScrapedData.session_id == session_id)
    
    if verified_only:
        query = query.where(ScrapedData.auto_verified == True)
    
    result = await db.execute(query)
    rows = result.all()
    
    response = []
    for data, org_name in rows:
        item = {
            **{c.name: getattr(data, c.name) for c in data.__table__.columns},
            "organization_name": org_name
        }
        response.append(item)
    
    return response


@router.get("/data/summary")
async def get_data_summary(
    session_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a summary of scraped data.
    """
    query = select(ScrapedData)
    if session_id:
        query = query.where(ScrapedData.session_id == session_id)
    
    result = await db.execute(query)
    all_data = result.scalars().all()
    
    # Calculate summary
    total = len(all_data)
    auto_verified = sum(1 for d in all_data if d.auto_verified)
    manually_verified = sum(1 for d in all_data if d.manually_verified is True)
    manually_rejected = sum(1 for d in all_data if d.manually_verified is False)
    pending_review = sum(1 for d in all_data if d.manually_verified is None)
    
    # Group by variable key
    by_variable = {}
    for d in all_data:
        if d.variable_key not in by_variable:
            by_variable[d.variable_key] = {"total": 0, "auto_verified": 0}
        by_variable[d.variable_key]["total"] += 1
        if d.auto_verified:
            by_variable[d.variable_key]["auto_verified"] += 1
    
    return {
        "total": total,
        "auto_verified": auto_verified,
        "manually_verified": manually_verified,
        "manually_rejected": manually_rejected,
        "pending_review": pending_review,
        "by_variable": by_variable
    }


@router.patch("/data/{data_id}/verify", response_model=ScrapedDataResponse)
async def verify_scraped_data(
    data_id: int,
    request: VerifyDataRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Manually verify or reject scraped data.
    """
    result = await db.execute(
        select(ScrapedData).where(ScrapedData.id == data_id)
    )
    data = result.scalar_one_or_none()
    
    if not data:
        raise HTTPException(status_code=404, detail="Data not found")
    
    data.manually_verified = request.verified
    data.verified_by = request.verified_by
    data.verified_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(data)
    
    return data


# ============== WebSocket for Progress ==============

@router.websocket("/ws/progress/{session_id}")
async def websocket_progress(
    websocket: WebSocket,
    session_id: int
):
    """
    WebSocket endpoint for real-time scraping progress updates.
    """
    await websocket.accept()
    
    # Register connection
    if session_id not in active_connections:
        active_connections[session_id] = []
    active_connections[session_id].append(websocket)
    
    try:
        while True:
            # Keep connection alive and send periodic updates
            async with async_session_maker() as db:
                result = await db.execute(
                    select(ScrapingSession).where(ScrapingSession.id == session_id)
                )
                session = result.scalar_one_or_none()
                
                if session:
                    await websocket.send_json({
                        "status": session.status,
                        "progress_percent": session.progress_percent,
                        "processed_associations": session.processed_associations,
                        "total_associations": session.total_associations,
                        "processed_links": session.processed_links,
                        "total_links": session.total_links,
                        "variables_found": session.variables_found,
                        "errors_count": session.errors_count,
                        "current_url": session.current_url
                    })
                    
                    if session.status in ["completed", "failed", "cancelled"]:
                        break
            
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        if session_id in active_connections:
            active_connections[session_id].remove(websocket)


# ============== Background Scraping Task ==============

async def run_scraping_session(session_id: int, organization_ids: List[int], config_id: int):
    """
    Run the actual scraping session in the background.
    This is a simplified version - in production, use Celery.
    """
    async with async_session_maker() as db:
        # Get session and config
        session_result = await db.execute(
            select(ScrapingSession).where(ScrapingSession.id == session_id)
        )
        session = session_result.scalar_one()
        
        config_result = await db.execute(
            select(ScrapingConfig).where(ScrapingConfig.id == config_id)
        )
        config = config_result.scalar_one()
        
        # Update session status
        session.status = "running"
        session.started_at = datetime.utcnow()
        await db.commit()
        
        try:
            processed = 0
            for org_id in organization_ids:
                # Get organization
                org_result = await db.execute(
                    select(Organization).where(Organization.id == org_id)
                )
                org = org_result.scalar_one_or_none()
                
                if not org:
                    continue
                
                session.current_organization_id = org_id
                
                # Get links for this organization
                links_result = await db.execute(
                    select(OrganizationLink).where(OrganizationLink.organization_id == org_id)
                )
                links = links_result.scalars().all()
                
                # Add main URL if exists
                urls_to_scrape = []
                if org.url:
                    urls_to_scrape.append(org.url)
                urls_to_scrape.extend([link.url for link in links])
                
                for url in urls_to_scrape:
                    session.current_url = url
                    session.processed_links += 1
                    
                    # Simulate scraping delay
                    await asyncio.sleep(config.delay_between_requests / 1000)
                    
                    # Here would be actual scraping logic with Playwright
                    # For now, create sample scraped data
                    scraped_item = ScrapedData(
                        session_id=session_id,
                        association_id=assoc_id,
                        variable_key="sample_data",
                        variable_value={"sample": "value"},
                        source_url=url,
                        auto_verified=True,
                        auto_verification_score=0.85,
                        auto_verification_reason="Sample auto-verification"
                    )
                    db.add(scraped_item)
                    session.variables_found += 1
                    
                    # Update progress
                    session.progress_percent = (
                        session.processed_links / session.total_links * 100
                        if session.total_links > 0 else 0
                    )
                    await db.commit()
                
                processed += 1
                session.processed_associations = processed
                await db.commit()
            
            # Mark as completed
            session.status = "completed"
            session.completed_at = datetime.utcnow()
            session.progress_percent = 100.0
            await db.commit()
            
        except Exception as e:
            session.status = "failed"
            session.completed_at = datetime.utcnow()
            session.error_log = {"error": str(e)}
            await db.commit()
