"""
API routes for managing Venn Match Evidence.
Provides endpoints for viewing and validating match evidence with full traceability.
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.db.base import get_db
from app.models.db_models import (
    VennMatchEvidence, SourceType, VennResult, VennProxy,
    VennVariable, Organization
)

router = APIRouter()


# ============== Pydantic Schemas ==============

class MatchEvidenceResponse(BaseModel):
    """Response schema for match evidence."""
    id: int
    venn_result_id: int
    venn_proxy_id: int
    proxy_term: Optional[str] = None
    
    # Source info
    source_url: str
    source_type: str
    
    # Location
    text_fragment: Optional[str] = None
    matched_text: Optional[str] = None
    xpath: Optional[str] = None
    css_selector: Optional[str] = None
    paragraph_number: Optional[int] = None
    section_title: Optional[str] = None
    
    # Match quality
    match_score: float = 1.0
    is_exact_match: bool = True
    
    # Scraping context
    scraped_at: Optional[datetime] = None
    page_title: Optional[str] = None
    
    # Validation
    is_valid: Optional[bool] = None
    validated_by: Optional[str] = None
    validated_at: Optional[datetime] = None
    validation_notes: Optional[str] = None
    
    # Extended info
    organization_name: Optional[str] = None
    variable_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class EvidenceValidationRequest(BaseModel):
    """Request schema for validating evidence."""
    is_valid: bool
    validated_by: str
    validation_notes: Optional[str] = None


class EvidenceBulkValidationRequest(BaseModel):
    """Request schema for bulk validation."""
    evidence_ids: List[int]
    is_valid: bool
    validated_by: str
    validation_notes: Optional[str] = None


class EvidenceStatsResponse(BaseModel):
    """Statistics about match evidence."""
    total_evidence: int
    pending_validation: int
    validated_positive: int
    validated_negative: int
    validation_rate: float
    by_source_type: dict
    by_variable: dict


# ============== Endpoints ==============

@router.get("/", response_model=List[MatchEvidenceResponse])
async def list_match_evidence(
    venn_result_id: Optional[int] = None,
    organization_id: Optional[int] = None,
    venn_variable_id: Optional[int] = None,
    is_valid: Optional[bool] = None,
    source_type: Optional[str] = None,
    pending_only: bool = False,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    List match evidence with filters.
    
    Filters:
    - venn_result_id: Filter by specific result
    - organization_id: Filter by organization
    - venn_variable_id: Filter by Venn variable
    - is_valid: Filter by validation status (True/False/None for pending)
    - source_type: Filter by source type (main_page, pdf, etc.)
    - pending_only: Only show pending validations
    """
    # Build query with joins for extended info
    query = select(VennMatchEvidence)
    
    # Join to get organization and variable info
    if organization_id or venn_variable_id:
        query = query.join(VennResult, VennMatchEvidence.venn_result_id == VennResult.id)
    
    # Apply filters
    conditions = []
    
    if venn_result_id:
        conditions.append(VennMatchEvidence.venn_result_id == venn_result_id)
    
    if organization_id:
        conditions.append(VennResult.organization_id == organization_id)
    
    if venn_variable_id:
        conditions.append(VennResult.venn_variable_id == venn_variable_id)
    
    if pending_only:
        conditions.append(VennMatchEvidence.is_valid.is_(None))
    elif is_valid is not None:
        conditions.append(VennMatchEvidence.is_valid == is_valid)
    
    if source_type:
        try:
            st = SourceType(source_type)
            conditions.append(VennMatchEvidence.source_type == st)
        except ValueError:
            pass
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.order_by(VennMatchEvidence.created_at.desc())
    query = query.offset(skip).limit(limit)
    
    result = await db.execute(query)
    evidences = result.scalars().all()
    
    # Enrich with proxy terms, org names, and variable names
    response = []
    for ev in evidences:
        ev_dict = {
            "id": ev.id,
            "venn_result_id": ev.venn_result_id,
            "venn_proxy_id": ev.venn_proxy_id,
            "source_url": ev.source_url,
            "source_type": ev.source_type.value if ev.source_type else "other",
            "text_fragment": ev.text_fragment,
            "matched_text": ev.matched_text,
            "xpath": ev.xpath,
            "css_selector": ev.css_selector,
            "paragraph_number": ev.paragraph_number,
            "section_title": ev.section_title,
            "match_score": ev.match_score or 1.0,
            "is_exact_match": ev.is_exact_match if ev.is_exact_match is not None else True,
            "scraped_at": ev.scraped_at,
            "page_title": ev.page_title,
            "is_valid": ev.is_valid,
            "validated_by": ev.validated_by,
            "validated_at": ev.validated_at,
            "validation_notes": ev.validation_notes,
        }
        
        # Get proxy term
        proxy_result = await db.execute(
            select(VennProxy.term).where(VennProxy.id == ev.venn_proxy_id)
        )
        ev_dict["proxy_term"] = proxy_result.scalar_one_or_none()
        
        # Get result info for org and variable names
        result_info = await db.execute(
            select(VennResult.organization_id, VennResult.venn_variable_id)
            .where(VennResult.id == ev.venn_result_id)
        )
        result_row = result_info.first()
        if result_row:
            # Get org name
            org_result = await db.execute(
                select(Organization.name).where(Organization.id == result_row[0])
            )
            ev_dict["organization_name"] = org_result.scalar_one_or_none()
            
            # Get variable name
            var_result = await db.execute(
                select(VennVariable.name).where(VennVariable.id == result_row[1])
            )
            ev_dict["variable_name"] = var_result.scalar_one_or_none()
        
        response.append(MatchEvidenceResponse(**ev_dict))
    
    return response


@router.get("/stats", response_model=EvidenceStatsResponse)
async def get_evidence_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get statistics about match evidence for dashboard."""
    
    # Total count
    total_result = await db.execute(select(func.count(VennMatchEvidence.id)))
    total = total_result.scalar() or 0
    
    # Pending validation
    pending_result = await db.execute(
        select(func.count(VennMatchEvidence.id))
        .where(VennMatchEvidence.is_valid.is_(None))
    )
    pending = pending_result.scalar() or 0
    
    # Validated positive
    valid_result = await db.execute(
        select(func.count(VennMatchEvidence.id))
        .where(VennMatchEvidence.is_valid == True)
    )
    validated_positive = valid_result.scalar() or 0
    
    # Validated negative
    invalid_result = await db.execute(
        select(func.count(VennMatchEvidence.id))
        .where(VennMatchEvidence.is_valid == False)
    )
    validated_negative = invalid_result.scalar() or 0
    
    # By source type
    source_counts = {}
    for st in SourceType:
        count_result = await db.execute(
            select(func.count(VennMatchEvidence.id))
            .where(VennMatchEvidence.source_type == st)
        )
        source_counts[st.value] = count_result.scalar() or 0
    
    # By variable (top 10)
    var_counts_result = await db.execute(
        select(VennVariable.name, func.count(VennMatchEvidence.id))
        .select_from(VennMatchEvidence)
        .join(VennResult, VennMatchEvidence.venn_result_id == VennResult.id)
        .join(VennVariable, VennResult.venn_variable_id == VennVariable.id)
        .group_by(VennVariable.name)
        .order_by(func.count(VennMatchEvidence.id).desc())
        .limit(10)
    )
    var_counts = {row[0]: row[1] for row in var_counts_result.all()}
    
    validation_rate = 0.0
    if total > 0:
        validation_rate = ((validated_positive + validated_negative) / total) * 100
    
    return EvidenceStatsResponse(
        total_evidence=total,
        pending_validation=pending,
        validated_positive=validated_positive,
        validated_negative=validated_negative,
        validation_rate=round(validation_rate, 1),
        by_source_type=source_counts,
        by_variable=var_counts
    )


@router.get("/{evidence_id}", response_model=MatchEvidenceResponse)
async def get_evidence_detail(
    evidence_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information about a specific evidence record."""
    result = await db.execute(
        select(VennMatchEvidence).where(VennMatchEvidence.id == evidence_id)
    )
    evidence = result.scalar_one_or_none()
    
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    
    # Build response with enriched data
    ev_dict = {
        "id": evidence.id,
        "venn_result_id": evidence.venn_result_id,
        "venn_proxy_id": evidence.venn_proxy_id,
        "source_url": evidence.source_url,
        "source_type": evidence.source_type.value if evidence.source_type else "other",
        "text_fragment": evidence.text_fragment,
        "matched_text": evidence.matched_text,
        "xpath": evidence.xpath,
        "css_selector": evidence.css_selector,
        "paragraph_number": evidence.paragraph_number,
        "section_title": evidence.section_title,
        "match_score": evidence.match_score or 1.0,
        "is_exact_match": evidence.is_exact_match if evidence.is_exact_match is not None else True,
        "scraped_at": evidence.scraped_at,
        "page_title": evidence.page_title,
        "is_valid": evidence.is_valid,
        "validated_by": evidence.validated_by,
        "validated_at": evidence.validated_at,
        "validation_notes": evidence.validation_notes,
    }
    
    # Get proxy term
    proxy_result = await db.execute(
        select(VennProxy.term).where(VennProxy.id == evidence.venn_proxy_id)
    )
    ev_dict["proxy_term"] = proxy_result.scalar_one_or_none()
    
    return MatchEvidenceResponse(**ev_dict)


@router.put("/{evidence_id}/validate", response_model=MatchEvidenceResponse)
async def validate_evidence(
    evidence_id: int,
    validation: EvidenceValidationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Validate a match evidence record.
    
    Set is_valid=True to confirm the match is genuine.
    Set is_valid=False to mark as false positive.
    """
    result = await db.execute(
        select(VennMatchEvidence).where(VennMatchEvidence.id == evidence_id)
    )
    evidence = result.scalar_one_or_none()
    
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    
    # Update validation fields
    evidence.is_valid = validation.is_valid
    evidence.validated_by = validation.validated_by
    evidence.validated_at = datetime.utcnow()
    evidence.validation_notes = validation.validation_notes
    
    await db.commit()
    await db.refresh(evidence)
    
    # Get proxy term for response
    proxy_result = await db.execute(
        select(VennProxy.term).where(VennProxy.id == evidence.venn_proxy_id)
    )
    
    return MatchEvidenceResponse(
        id=evidence.id,
        venn_result_id=evidence.venn_result_id,
        venn_proxy_id=evidence.venn_proxy_id,
        proxy_term=proxy_result.scalar_one_or_none(),
        source_url=evidence.source_url,
        source_type=evidence.source_type.value if evidence.source_type else "other",
        text_fragment=evidence.text_fragment,
        matched_text=evidence.matched_text,
        xpath=evidence.xpath,
        css_selector=evidence.css_selector,
        paragraph_number=evidence.paragraph_number,
        section_title=evidence.section_title,
        match_score=evidence.match_score or 1.0,
        is_exact_match=evidence.is_exact_match if evidence.is_exact_match is not None else True,
        scraped_at=evidence.scraped_at,
        page_title=evidence.page_title,
        is_valid=evidence.is_valid,
        validated_by=evidence.validated_by,
        validated_at=evidence.validated_at,
        validation_notes=evidence.validation_notes
    )


@router.post("/bulk-validate")
async def bulk_validate_evidence(
    request: EvidenceBulkValidationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Validate multiple evidence records at once."""
    updated_count = 0
    
    for evidence_id in request.evidence_ids:
        result = await db.execute(
            select(VennMatchEvidence).where(VennMatchEvidence.id == evidence_id)
        )
        evidence = result.scalar_one_or_none()
        
        if evidence:
            evidence.is_valid = request.is_valid
            evidence.validated_by = request.validated_by
            evidence.validated_at = datetime.utcnow()
            evidence.validation_notes = request.validation_notes
            updated_count += 1
    
    await db.commit()
    
    return {
        "message": f"Validated {updated_count} evidence records",
        "updated_count": updated_count,
        "is_valid": request.is_valid
    }


@router.get("/by-result/{venn_result_id}", response_model=List[MatchEvidenceResponse])
async def get_evidence_by_result(
    venn_result_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get all evidence records for a specific VennResult."""
    result = await db.execute(
        select(VennMatchEvidence)
        .where(VennMatchEvidence.venn_result_id == venn_result_id)
        .order_by(VennMatchEvidence.match_score.desc())
    )
    evidences = result.scalars().all()
    
    response = []
    for ev in evidences:
        # Get proxy term
        proxy_result = await db.execute(
            select(VennProxy.term).where(VennProxy.id == ev.venn_proxy_id)
        )
        
        response.append(MatchEvidenceResponse(
            id=ev.id,
            venn_result_id=ev.venn_result_id,
            venn_proxy_id=ev.venn_proxy_id,
            proxy_term=proxy_result.scalar_one_or_none(),
            source_url=ev.source_url,
            source_type=ev.source_type.value if ev.source_type else "other",
            text_fragment=ev.text_fragment,
            matched_text=ev.matched_text,
            xpath=ev.xpath,
            css_selector=ev.css_selector,
            paragraph_number=ev.paragraph_number,
            section_title=ev.section_title,
            match_score=ev.match_score or 1.0,
            is_exact_match=ev.is_exact_match if ev.is_exact_match is not None else True,
            scraped_at=ev.scraped_at,
            page_title=ev.page_title,
            is_valid=ev.is_valid,
            validated_by=ev.validated_by,
            validated_at=ev.validated_at,
            validation_notes=ev.validation_notes
        ))
    
    return response
