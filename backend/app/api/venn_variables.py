"""
API routes for managing Venn variables and their proxies.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime

from app.db.base import get_db
from app.models.db_models import VennVariable, VennProxy

router = APIRouter()


# ============== Pydantic Schemas ==============

class VennProxyBase(BaseModel):
    """Base schema for VennProxy."""
    term: str
    is_regex: bool = False
    weight: float = 1.0

    class Config:
        from_attributes = True


class VennProxyCreate(VennProxyBase):
    """Schema for creating a VennProxy."""
    pass


class VennProxyResponse(VennProxyBase):
    """Schema for VennProxy response."""
    id: int
    venn_variable_id: int
    created_at: datetime


class VennVariableBase(BaseModel):
    """Base schema for VennVariable."""
    name: str
    description: Optional[str] = None
    data_type: str = "list"

    class Config:
        from_attributes = True


class VennVariableCreate(VennVariableBase):
    """Schema for creating a VennVariable with proxies."""
    proxies: List[VennProxyCreate] = []


class VennVariableResponse(VennVariableBase):
    """Schema for VennVariable response."""
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    proxies: List[VennProxyResponse] = []


class VennVariableUpdate(BaseModel):
    """Schema for updating a VennVariable."""
    name: Optional[str] = None
    description: Optional[str] = None
    data_type: Optional[str] = None


# ============== VennVariable Endpoints ==============

@router.get("/", response_model=List[VennVariableResponse])
async def list_venn_variables(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """
    List all Venn variables with their proxies.
    """
    result = await db.execute(
        select(VennVariable).offset(skip).limit(limit)
    )
    variables = result.scalars().all()
    
    # Load proxies for each variable
    response = []
    for var in variables:
        proxies_result = await db.execute(
            select(VennProxy).where(VennProxy.venn_variable_id == var.id)
        )
        proxies = proxies_result.scalars().all()
        
        response.append({
            "id": var.id,
            "name": var.name,
            "description": var.description,
            "data_type": var.data_type,
            "created_at": var.created_at,
            "updated_at": var.updated_at,
            "proxies": proxies
        })
    
    return response


@router.get("/{variable_id}", response_model=VennVariableResponse)
async def get_venn_variable(
    variable_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a specific Venn variable with its proxies.
    """
    result = await db.execute(
        select(VennVariable).where(VennVariable.id == variable_id)
    )
    variable = result.scalar_one_or_none()
    
    if not variable:
        raise HTTPException(status_code=404, detail="Venn variable not found")
    
    # Get proxies
    proxies_result = await db.execute(
        select(VennProxy).where(VennProxy.venn_variable_id == variable.id)
    )
    proxies = proxies_result.scalars().all()
    
    return {
        "id": variable.id,
        "name": variable.name,
        "description": variable.description,
        "data_type": variable.data_type,
        "created_at": variable.created_at,
        "updated_at": variable.updated_at,
        "proxies": proxies
    }


@router.post("/", response_model=VennVariableResponse)
async def create_venn_variable(
    data: VennVariableCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new Venn variable with its proxies.
    """
    # Check if name already exists
    existing = await db.execute(
        select(VennVariable).where(VennVariable.name == data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Variable with this name already exists")
    
    # Create variable
    variable = VennVariable(
        name=data.name,
        description=data.description,
        data_type=data.data_type
    )
    db.add(variable)
    await db.flush()
    
    # Create proxies
    created_proxies = []
    for proxy_data in data.proxies:
        proxy = VennProxy(
            venn_variable_id=variable.id,
            term=proxy_data.term,
            is_regex=proxy_data.is_regex,
            weight=proxy_data.weight
        )
        db.add(proxy)
        created_proxies.append(proxy)
    
    await db.commit()
    await db.refresh(variable)
    
    return {
        "id": variable.id,
        "name": variable.name,
        "description": variable.description,
        "data_type": variable.data_type,
        "created_at": variable.created_at,
        "updated_at": variable.updated_at,
        "proxies": created_proxies
    }


@router.put("/{variable_id}", response_model=VennVariableResponse)
async def update_venn_variable(
    variable_id: int,
    data: VennVariableUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a Venn variable.
    """
    result = await db.execute(
        select(VennVariable).where(VennVariable.id == variable_id)
    )
    variable = result.scalar_one_or_none()
    
    if not variable:
        raise HTTPException(status_code=404, detail="Venn variable not found")
    
    # Update fields
    if data.name is not None:
        # Check if new name conflicts
        if data.name != variable.name:
            existing = await db.execute(
                select(VennVariable).where(VennVariable.name == data.name)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(status_code=400, detail="Variable with this name already exists")
        variable.name = data.name
    if data.description is not None:
        variable.description = data.description
    if data.data_type is not None:
        variable.data_type = data.data_type
    
    await db.commit()
    await db.refresh(variable)
    
    # Get proxies
    proxies_result = await db.execute(
        select(VennProxy).where(VennProxy.venn_variable_id == variable.id)
    )
    proxies = proxies_result.scalars().all()
    
    return {
        "id": variable.id,
        "name": variable.name,
        "description": variable.description,
        "data_type": variable.data_type,
        "created_at": variable.created_at,
        "updated_at": variable.updated_at,
        "proxies": proxies
    }


@router.delete("/{variable_id}")
async def delete_venn_variable(
    variable_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a Venn variable and all its proxies.
    """
    result = await db.execute(
        select(VennVariable).where(VennVariable.id == variable_id)
    )
    variable = result.scalar_one_or_none()
    
    if not variable:
        raise HTTPException(status_code=404, detail="Venn variable not found")
    
    await db.delete(variable)
    await db.commit()
    
    return {"status": "deleted", "id": variable_id}


# ============== Proxy Endpoints ==============

@router.post("/{variable_id}/proxies", response_model=VennProxyResponse)
async def add_proxy(
    variable_id: int,
    data: VennProxyCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Add a proxy to a Venn variable.
    """
    # Verify variable exists
    result = await db.execute(
        select(VennVariable).where(VennVariable.id == variable_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Venn variable not found")
    
    proxy = VennProxy(
        venn_variable_id=variable_id,
        term=data.term,
        is_regex=data.is_regex,
        weight=data.weight
    )
    db.add(proxy)
    await db.commit()
    await db.refresh(proxy)
    
    return proxy


@router.put("/proxies/{proxy_id}", response_model=VennProxyResponse)
async def update_proxy(
    proxy_id: int,
    data: VennProxyCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a proxy.
    """
    result = await db.execute(
        select(VennProxy).where(VennProxy.id == proxy_id)
    )
    proxy = result.scalar_one_or_none()
    
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    
    proxy.term = data.term
    proxy.is_regex = data.is_regex
    proxy.weight = data.weight
    
    await db.commit()
    await db.refresh(proxy)
    
    return proxy


@router.delete("/proxies/{proxy_id}")
async def delete_proxy(
    proxy_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a proxy.
    """
    result = await db.execute(
        select(VennProxy).where(VennProxy.id == proxy_id)
    )
    proxy = result.scalar_one_or_none()
    
    if not proxy:
        raise HTTPException(status_code=404, detail="Proxy not found")
    
    await db.delete(proxy)
    await db.commit()
    
    return {"status": "deleted", "id": proxy_id}
