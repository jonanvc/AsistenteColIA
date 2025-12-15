"""
API routes for managing Venn Results.
Venn Results store the relationship (0 or 1) between organizations and Venn variables.
Results can be:
- Set manually by users
- Calculated automatically by searching for proxy matches in organization data/URLs
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from pydantic import BaseModel
from datetime import datetime
import re

from app.db.base import get_db
from app.models.db_models import (
    VennResult, VennResultSource, VennResultStatus, VennVariable, VennProxy, 
    Organization, ScrapedData
)

router = APIRouter()


# ============== Pydantic Schemas ==============

class VennResultBase(BaseModel):
    """Base schema for VennResult."""
    value: bool = False
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class VennResultCreate(BaseModel):
    """Schema for creating a VennResult manually."""
    organization_id: int
    venn_variable_id: int
    value: bool
    notes: Optional[str] = None


class VennResultUpdate(BaseModel):
    """Schema for updating a VennResult."""
    value: Optional[bool] = None
    notes: Optional[str] = None


class VennResultResponse(BaseModel):
    """Schema for VennResult response."""
    id: int
    organization_id: int
    venn_variable_id: int
    value: bool
    source: str  # manual, automatic, mixed
    search_score: Optional[float] = None
    matched_proxies: Optional[List[str]] = None
    source_urls: Optional[List[str]] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Verification fields
    verification_status: str = "pending"  # pending, verified, rejected, modified
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    verification_notes: Optional[str] = None
    original_value: Optional[bool] = None  # Original auto-detected value before user modification
    
    # Extended info
    organization_name: Optional[str] = None
    variable_name: Optional[str] = None

    class Config:
        from_attributes = True


class VennResultVerification(BaseModel):
    """Schema for verifying a VennResult."""
    verification_status: str  # verified, rejected
    verified_by: str  # Username or identifier of the verifier
    verification_notes: Optional[str] = None
    corrected_value: Optional[bool] = None  # If user wants to correct the auto value


class VennResultMatrix(BaseModel):
    """Schema for a matrix of results (organizations x variables)."""
    organizations: List[dict]  # [{id, name}]
    variables: List[dict]  # [{id, name}]
    results: List[dict]  # [{org_id, var_id, value, verification_status}]


class ProxySearchRequest(BaseModel):
    """Schema for proxy search request."""
    organization_id: int
    venn_variable_id: Optional[int] = None  # If None, search all variables


class ProxySearchResult(BaseModel):
    """Schema for proxy search result."""
    organization_id: int
    venn_variable_id: int
    variable_name: str
    matched: bool
    score: float
    matched_proxies: List[str]
    source_urls: List[str]


# ============== VennResult Endpoints ==============

@router.get("/", response_model=List[VennResultResponse])
async def list_venn_results(
    organization_id: Optional[int] = None,
    venn_variable_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 1000,
    db: AsyncSession = Depends(get_db)
):
    """
    List all Venn results with optional filters.
    """
    query = select(VennResult)
    
    if organization_id is not None:
        query = query.where(VennResult.organization_id == organization_id)
    if venn_variable_id is not None:
        query = query.where(VennResult.venn_variable_id == venn_variable_id)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    results = result.scalars().all()
    
    # Enrich with names
    response = []
    for r in results:
        # Get organization name
        org_result = await db.execute(
            select(Organization.name).where(Organization.id == r.organization_id)
        )
        org_name = org_result.scalar_one_or_none()
        
        # Get variable name
        var_result = await db.execute(
            select(VennVariable.name).where(VennVariable.id == r.venn_variable_id)
        )
        var_name = var_result.scalar_one_or_none()
        
        response.append({
            "id": r.id,
            "organization_id": r.organization_id,
            "venn_variable_id": r.venn_variable_id,
            "value": r.value,
            "source": r.source.value if r.source else "manual",
            "search_score": r.search_score,
            "matched_proxies": r.matched_proxies,
            "source_urls": r.source_urls,
            "notes": r.notes,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "verification_status": r.verification_status.value if r.verification_status else "pending",
            "verified_by": r.verified_by,
            "verified_at": r.verified_at,
            "verification_notes": r.verification_notes,
            "original_value": r.original_value,
            "organization_name": org_name,
            "variable_name": var_name
        })
    
    return response


@router.get("/matrix", response_model=VennResultMatrix)
async def get_results_matrix(db: AsyncSession = Depends(get_db)):
    """
    Get all results as a matrix (organizations x variables).
    Useful for displaying in a table or Venn diagram editor.
    """
    # Get all organizations
    orgs_result = await db.execute(select(Organization.id, Organization.name))
    organizations = [{"id": r[0], "name": r[1]} for r in orgs_result.all()]
    
    # Get all Venn variables
    vars_result = await db.execute(select(VennVariable.id, VennVariable.name))
    variables = [{"id": r[0], "name": r[1]} for r in vars_result.all()]
    
    # Get all results
    results_result = await db.execute(select(VennResult))
    results_raw = results_result.scalars().all()
    results = [
        {
            "org_id": r.organization_id,
            "var_id": r.venn_variable_id,
            "value": r.value,
            "source": r.source.value if r.source else "manual"
        }
        for r in results_raw
    ]
    
    return {
        "organizations": organizations,
        "variables": variables,
        "results": results
    }


# ============== Verification Endpoints (MUST be before /{result_id}) ==============

@router.get("/pending-verification", response_model=List[VennResultResponse])
async def list_pending_verification(
    organization_id: Optional[int] = None,
    venn_variable_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    List all Venn results that are pending verification.
    These are typically results from automatic searches that need user review.
    """
    query = select(VennResult).where(VennResult.verification_status == VennResultStatus.PENDING)
    
    if organization_id is not None:
        query = query.where(VennResult.organization_id == organization_id)
    if venn_variable_id is not None:
        query = query.where(VennResult.venn_variable_id == venn_variable_id)
    
    query = query.order_by(VennResult.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    results = result.scalars().all()
    
    # Enrich with names
    response = []
    for r in results:
        org_result = await db.execute(
            select(Organization.name).where(Organization.id == r.organization_id)
        )
        org_name = org_result.scalar_one_or_none()
        
        var_result = await db.execute(
            select(VennVariable.name).where(VennVariable.id == r.venn_variable_id)
        )
        var_name = var_result.scalar_one_or_none()
        
        response.append({
            "id": r.id,
            "organization_id": r.organization_id,
            "venn_variable_id": r.venn_variable_id,
            "value": r.value,
            "source": r.source.value if r.source else "manual",
            "search_score": r.search_score,
            "matched_proxies": r.matched_proxies,
            "source_urls": r.source_urls,
            "notes": r.notes,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
            "verification_status": r.verification_status.value if r.verification_status else "pending",
            "verified_by": r.verified_by,
            "verified_at": r.verified_at,
            "verification_notes": r.verification_notes,
            "original_value": r.original_value,
            "organization_name": org_name,
            "variable_name": var_name
        })
    
    return response


@router.get("/verification-stats", response_model=dict)
async def get_verification_stats(db: AsyncSession = Depends(get_db)):
    """
    Get statistics about verification status of all Venn results.
    """
    # Count by verification status
    total_result = await db.execute(select(VennResult))
    all_results = total_result.scalars().all()
    
    stats = {
        "total": len(all_results),
        "pending": 0,
        "verified": 0,
        "rejected": 0,
        "by_source": {
            "manual": 0,
            "automatic": 0,
            "mixed": 0
        }
    }
    
    for r in all_results:
        status = r.verification_status.value if r.verification_status else "pending"
        if status in stats:
            stats[status] += 1
        
        source = r.source.value if r.source else "manual"
        if source in stats["by_source"]:
            stats["by_source"][source] += 1
    
    # Calculate percentages
    if stats["total"] > 0:
        stats["verification_rate"] = round(
            (stats["verified"] / stats["total"]) * 100, 2
        )
    else:
        stats["verification_rate"] = 0
    
    return stats


@router.post("/bulk-verify", response_model=dict)
async def bulk_verify_results(
    result_ids: List[int],
    verification_status: str,
    verified_by: str,
    verification_notes: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify multiple results at once.
    Useful for batch approval of search results.
    """
    status_map = {
        "verified": VennResultStatus.VERIFIED,
        "rejected": VennResultStatus.REJECTED,
        "modified": VennResultStatus.MODIFIED
    }
    if verification_status not in status_map:
        raise HTTPException(
            status_code=400, 
            detail="verification_status must be 'verified', 'rejected', or 'modified'"
        )
    
    verified_count = 0
    failed_ids = []
    
    for result_id in result_ids:
        result = await db.execute(
            select(VennResult).where(VennResult.id == result_id)
        )
        venn_result = result.scalar_one_or_none()
        
        if venn_result:
            venn_result.verification_status = status_map[verification_status]
            venn_result.verified_by = verified_by
            venn_result.verified_at = datetime.now()
            if verification_notes:
                venn_result.verification_notes = verification_notes
            verified_count += 1
        else:
            failed_ids.append(result_id)
    
    await db.commit()
    
    return {
        "status": "completed",
        "verified_count": verified_count,
        "failed_ids": failed_ids
    }


# ============== Individual Result Endpoints ==============

@router.get("/{result_id}", response_model=VennResultResponse)
async def get_venn_result(
    result_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific Venn result.
    """
    result = await db.execute(
        select(VennResult).where(VennResult.id == result_id)
    )
    venn_result = result.scalar_one_or_none()
    
    if not venn_result:
        raise HTTPException(status_code=404, detail="Venn result not found")
    
    # Get organization name
    org_result = await db.execute(
        select(Organization.name).where(Organization.id == venn_result.organization_id)
    )
    org_name = org_result.scalar_one_or_none()
    
    # Get variable name
    var_result = await db.execute(
        select(VennVariable.name).where(VennVariable.id == venn_result.venn_variable_id)
    )
    var_name = var_result.scalar_one_or_none()
    
    return {
        "id": venn_result.id,
        "organization_id": venn_result.organization_id,
        "venn_variable_id": venn_result.venn_variable_id,
        "value": venn_result.value,
        "source": venn_result.source.value if venn_result.source else "manual",
        "search_score": venn_result.search_score,
        "matched_proxies": venn_result.matched_proxies,
        "source_urls": venn_result.source_urls,
        "notes": venn_result.notes,
        "created_at": venn_result.created_at,
        "updated_at": venn_result.updated_at,
        "verification_status": venn_result.verification_status.value if venn_result.verification_status else "pending",
        "verified_by": venn_result.verified_by,
        "verified_at": venn_result.verified_at,
        "verification_notes": venn_result.verification_notes,
        "original_value": venn_result.original_value,
        "organization_name": org_name,
        "variable_name": var_name
    }


@router.post("/", response_model=VennResultResponse)
async def create_venn_result(
    data: VennResultCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new Venn result manually.
    """
    # Verify organization exists
    org_result = await db.execute(
        select(Organization).where(Organization.id == data.organization_id)
    )
    organization = org_result.scalar_one_or_none()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Verify variable exists
    var_result = await db.execute(
        select(VennVariable).where(VennVariable.id == data.venn_variable_id)
    )
    variable = var_result.scalar_one_or_none()
    if not variable:
        raise HTTPException(status_code=404, detail="Venn variable not found")
    
    # Check if result already exists for this org-var pair
    existing_result = await db.execute(
        select(VennResult).where(
            and_(
                VennResult.organization_id == data.organization_id,
                VennResult.venn_variable_id == data.venn_variable_id
            )
        )
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400, 
            detail="Result already exists for this organization-variable pair. Use PUT to update."
        )
    
    # Create result
    venn_result = VennResult(
        organization_id=data.organization_id,
        venn_variable_id=data.venn_variable_id,
        value=data.value,
        source=VennResultSource.MANUAL,
        notes=data.notes
    )
    db.add(venn_result)
    await db.commit()
    await db.refresh(venn_result)
    
    return {
        "id": venn_result.id,
        "organization_id": venn_result.organization_id,
        "venn_variable_id": venn_result.venn_variable_id,
        "value": venn_result.value,
        "source": venn_result.source.value,
        "search_score": venn_result.search_score,
        "matched_proxies": venn_result.matched_proxies,
        "source_urls": venn_result.source_urls,
        "notes": venn_result.notes,
        "created_at": venn_result.created_at,
        "updated_at": venn_result.updated_at,
        "verification_status": venn_result.verification_status.value if venn_result.verification_status else "verified",  # Manual = verified
        "verified_by": venn_result.verified_by,
        "verified_at": venn_result.verified_at,
        "verification_notes": venn_result.verification_notes,
        "original_value": venn_result.original_value,
        "organization_name": organization.name,
        "variable_name": variable.name
    }


@router.put("/{result_id}", response_model=VennResultResponse)
async def update_venn_result(
    result_id: int,
    data: VennResultUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a Venn result. Marks source as 'mixed' if it was automatic.
    """
    result = await db.execute(
        select(VennResult).where(VennResult.id == result_id)
    )
    venn_result = result.scalar_one_or_none()
    
    if not venn_result:
        raise HTTPException(status_code=404, detail="Venn result not found")
    
    # Update fields
    if data.value is not None:
        venn_result.value = data.value
        # If the result was automatic, mark it as mixed now
        if venn_result.source == VennResultSource.AUTOMATIC:
            venn_result.source = VennResultSource.MIXED
    if data.notes is not None:
        venn_result.notes = data.notes
    
    await db.commit()
    await db.refresh(venn_result)
    
    # Get organization name
    org_result = await db.execute(
        select(Organization.name).where(Organization.id == venn_result.organization_id)
    )
    org_name = org_result.scalar_one_or_none()
    
    # Get variable name
    var_result = await db.execute(
        select(VennVariable.name).where(VennVariable.id == venn_result.venn_variable_id)
    )
    var_name = var_result.scalar_one_or_none()
    
    return {
        "id": venn_result.id,
        "organization_id": venn_result.organization_id,
        "venn_variable_id": venn_result.venn_variable_id,
        "value": venn_result.value,
        "source": venn_result.source.value,
        "search_score": venn_result.search_score,
        "matched_proxies": venn_result.matched_proxies,
        "source_urls": venn_result.source_urls,
        "notes": venn_result.notes,
        "created_at": venn_result.created_at,
        "updated_at": venn_result.updated_at,
        "verification_status": venn_result.verification_status.value if venn_result.verification_status else "pending",
        "verified_by": venn_result.verified_by,
        "verified_at": venn_result.verified_at,
        "verification_notes": venn_result.verification_notes,
        "original_value": venn_result.original_value,
        "organization_name": org_name,
        "variable_name": var_name
    }


@router.delete("/{result_id}")
async def delete_venn_result(
    result_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a Venn result.
    """
    result = await db.execute(
        select(VennResult).where(VennResult.id == result_id)
    )
    venn_result = result.scalar_one_or_none()
    
    if not venn_result:
        raise HTTPException(status_code=404, detail="Venn result not found")
    
    await db.delete(venn_result)
    await db.commit()
    
    return {"status": "deleted", "id": result_id}


# ============== Bulk Operations ==============

@router.post("/bulk", response_model=List[VennResultResponse])
async def create_or_update_bulk(
    results: List[VennResultCreate],
    db: AsyncSession = Depends(get_db)
):
    """
    Create or update multiple Venn results at once.
    """
    responses = []
    
    for data in results:
        # Check if exists
        existing_result = await db.execute(
            select(VennResult).where(
                and_(
                    VennResult.organization_id == data.organization_id,
                    VennResult.venn_variable_id == data.venn_variable_id
                )
            )
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            # Update
            existing.value = data.value
            existing.notes = data.notes
            if existing.source == VennResultSource.AUTOMATIC:
                existing.source = VennResultSource.MIXED
            venn_result = existing
        else:
            # Create
            venn_result = VennResult(
                organization_id=data.organization_id,
                venn_variable_id=data.venn_variable_id,
                value=data.value,
                source=VennResultSource.MANUAL,
                notes=data.notes
            )
            db.add(venn_result)
        
        await db.flush()
        
        # Get names
        org_result = await db.execute(
            select(Organization.name).where(Organization.id == venn_result.organization_id)
        )
        org_name = org_result.scalar_one_or_none()
        
        var_result = await db.execute(
            select(VennVariable.name).where(VennVariable.id == venn_result.venn_variable_id)
        )
        var_name = var_result.scalar_one_or_none()
        
        responses.append({
            "id": venn_result.id,
            "organization_id": venn_result.organization_id,
            "venn_variable_id": venn_result.venn_variable_id,
            "value": venn_result.value,
            "source": venn_result.source.value if venn_result.source else "manual",
            "search_score": venn_result.search_score,
            "matched_proxies": venn_result.matched_proxies,
            "source_urls": venn_result.source_urls,
            "notes": venn_result.notes,
            "created_at": venn_result.created_at,
            "updated_at": venn_result.updated_at,
            "organization_name": org_name,
            "variable_name": var_name
        })
    
    await db.commit()
    return responses


# ============== Automatic Proxy Search ==============

@router.post("/search", response_model=List[ProxySearchResult])
async def search_proxies_in_organization(
    request: ProxySearchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Search for proxy matches in an organization's scraped data.
    Returns matches but does NOT automatically save results.
    """
    # Verify organization exists
    org_result = await db.execute(
        select(Organization).where(Organization.id == request.organization_id)
    )
    organization = org_result.scalar_one_or_none()
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    # Get scraped data for this organization
    scraped_result = await db.execute(
        select(ScrapedData).where(ScrapedData.organization_id == request.organization_id)
    )
    scraped_data = scraped_result.scalars().all()
    
    # Combine all text content from scraped data
    all_text = ""
    url_to_content = {}
    for sd in scraped_data:
        # variable_value is the JSON field with scraped content
        if sd.variable_value:
            if isinstance(sd.variable_value, dict):
                content_text = sd.variable_value.get("text", sd.variable_value.get("data", str(sd.variable_value)))
            else:
                content_text = str(sd.variable_value)
            all_text += " " + content_text.lower()
            if sd.source_url:
                url_to_content[sd.source_url] = content_text.lower()
    
    # Also check organization description and URL
    if organization.description:
        all_text += " " + organization.description.lower()
    if organization.url:
        all_text += " " + organization.url.lower()
    
    # Get variables to search
    if request.venn_variable_id:
        vars_result = await db.execute(
            select(VennVariable).where(VennVariable.id == request.venn_variable_id)
        )
    else:
        vars_result = await db.execute(select(VennVariable))
    
    variables = vars_result.scalars().all()
    
    results = []
    for variable in variables:
        # Get proxies for this variable
        proxies_result = await db.execute(
            select(VennProxy).where(VennProxy.venn_variable_id == variable.id)
        )
        proxies = proxies_result.scalars().all()
        
        matched_proxies = []
        source_urls = []
        total_score = 0.0
        
        for proxy in proxies:
            term = proxy.term.lower()
            matched = False
            
            if proxy.is_regex:
                try:
                    pattern = re.compile(term, re.IGNORECASE)
                    if pattern.search(all_text):
                        matched = True
                except re.error:
                    pass
            else:
                if term in all_text:
                    matched = True
            
            if matched:
                matched_proxies.append(proxy.term)
                total_score += proxy.weight
                
                # Find which URLs contained this match
                for url, content in url_to_content.items():
                    if proxy.is_regex:
                        try:
                            if re.search(term, content, re.IGNORECASE):
                                if url not in source_urls:
                                    source_urls.append(url)
                        except re.error:
                            pass
                    else:
                        if term in content:
                            if url not in source_urls:
                                source_urls.append(url)
        
        results.append({
            "organization_id": organization.id,
            "venn_variable_id": variable.id,
            "variable_name": variable.name,
            "matched": len(matched_proxies) > 0,
            "score": total_score,
            "matched_proxies": matched_proxies,
            "source_urls": source_urls
        })
    
    return results


@router.post("/search/apply", response_model=List[VennResultResponse])
async def apply_search_results(
    request: ProxySearchRequest,
    threshold: float = 0.0,
    db: AsyncSession = Depends(get_db)
):
    """
    Search for proxy matches and automatically save results.
    Results are saved as 1 if any proxy matched, 0 otherwise.
    
    Args:
        threshold: Minimum score to consider a match (default 0 = any match counts)
    """
    # First, do the search
    search_results = await search_proxies_in_organization(request, db)
    
    responses = []
    for sr in search_results:
        # Determine value based on threshold
        value = sr["score"] > threshold
        
        # Check if result exists
        existing_result = await db.execute(
            select(VennResult).where(
                and_(
                    VennResult.organization_id == sr["organization_id"],
                    VennResult.venn_variable_id == sr["venn_variable_id"]
                )
            )
        )
        existing = existing_result.scalar_one_or_none()
        
        if existing:
            # Update existing
            existing.value = value
            existing.source = VennResultSource.AUTOMATIC
            existing.search_score = sr["score"]
            existing.matched_proxies = sr["matched_proxies"]
            existing.source_urls = sr["source_urls"]
            venn_result = existing
        else:
            # Create new
            venn_result = VennResult(
                organization_id=sr["organization_id"],
                venn_variable_id=sr["venn_variable_id"],
                value=value,
                source=VennResultSource.AUTOMATIC,
                search_score=sr["score"],
                matched_proxies=sr["matched_proxies"],
                source_urls=sr["source_urls"]
            )
            db.add(venn_result)
        
        await db.flush()
        
        # Get organization name
        org_result = await db.execute(
            select(Organization.name).where(Organization.id == venn_result.organization_id)
        )
        org_name = org_result.scalar_one_or_none()
        
        responses.append({
            "id": venn_result.id,
            "organization_id": venn_result.organization_id,
            "venn_variable_id": venn_result.venn_variable_id,
            "value": venn_result.value,
            "source": venn_result.source.value,
            "search_score": venn_result.search_score,
            "matched_proxies": venn_result.matched_proxies,
            "source_urls": venn_result.source_urls,
            "notes": venn_result.notes,
            "created_at": venn_result.created_at,
            "updated_at": venn_result.updated_at,
            "organization_name": org_name,
            "variable_name": sr["variable_name"]
        })
    
    await db.commit()
    return responses


@router.post("/search/apply-all", response_model=dict)
async def apply_search_to_all_organizations(
    venn_variable_id: Optional[int] = None,
    threshold: float = 0.0,
    db: AsyncSession = Depends(get_db)
):
    """
    Run proxy search on ALL organizations and save results.
    Useful for batch processing.
    """
    # Get all organizations
    orgs_result = await db.execute(select(Organization))
    organizations = orgs_result.scalars().all()
    
    total_results = 0
    total_matched = 0
    
    for org in organizations:
        search_request = ProxySearchRequest(
            organization_id=org.id,
            venn_variable_id=venn_variable_id
        )
        results = await apply_search_results(search_request, threshold, db)
        total_results += len(results)
        total_matched += sum(1 for r in results if r["value"])
    
    return {
        "status": "completed",
        "organizations_processed": len(organizations),
        "total_results": total_results,
        "total_matched": total_matched
    }
