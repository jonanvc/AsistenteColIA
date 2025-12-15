"""
Venn Diagram API - Generates intersection data for Venn diagrams.
"""
from typing import List, Dict, Any, Set
from itertools import combinations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.base import get_db
from app.models.db_models import Organization, Variable

router = APIRouter()


def calculate_intersections(
    sets_data: Dict[str, Set[Any]]
) -> Dict[str, Any]:
    """
    Calculate all possible intersections between sets.
    
    Args:
        sets_data: Dictionary mapping set ID to set of elements
        
    Returns:
        Dictionary with 'sets' and 'intersections' for Venn diagram
    """
    set_ids = list(sets_data.keys())
    
    # Build sets array with sizes
    sets_array = []
    for set_id in set_ids:
        sets_array.append({
            "id": set_id,
            "name": set_id,
            "size": len(sets_data[set_id])
        })
    
    # Calculate all intersections (2 to n sets)
    intersections = []
    
    for r in range(2, len(set_ids) + 1):
        for combo in combinations(set_ids, r):
            # Calculate intersection of all sets in this combination
            intersection_set = sets_data[combo[0]]
            for set_id in combo[1:]:
                intersection_set = intersection_set & sets_data[set_id]
            
            if len(intersection_set) > 0:
                intersections.append({
                    "sets": list(combo),
                    "size": len(intersection_set),
                    "elements": list(intersection_set)[:10]  # Limit elements for response
                })
    
    return {
        "sets": sets_array,
        "intersections": intersections
    }


def extract_elements_from_value(value: Any) -> Set[str]:
    """
    Extract set elements from a variable value.
    Handles different value formats (list, dict, string).
    
    Args:
        value: Variable value (can be list, dict, or string)
        
    Returns:
        Set of string elements
    """
    elements = set()
    
    if isinstance(value, list):
        # If it's a list, use each item as an element
        for item in value:
            if isinstance(item, str):
                elements.add(item)
            elif isinstance(item, dict) and "name" in item:
                elements.add(str(item["name"]))
            else:
                elements.add(str(item))
    elif isinstance(value, dict):
        # If it's a dict, use keys or look for specific fields
        if "items" in value:
            return extract_elements_from_value(value["items"])
        elif "elements" in value:
            return extract_elements_from_value(value["elements"])
        else:
            for key, val in value.items():
                elements.add(f"{key}: {val}")
    elif isinstance(value, str):
        # If it's a string, split by common delimiters
        for delimiter in [",", ";", "|"]:
            if delimiter in value:
                elements = set(v.strip() for v in value.split(delimiter))
                break
        else:
            elements.add(value)
    else:
        elements.add(str(value))
    
    return elements


@router.get("/data")
async def get_venn_data(
    vars: str = Query(..., description="Comma-separated list of variable keys"),
    db: AsyncSession = Depends(get_db)
):
    """
    Generate Venn diagram data for specified variables.
    
    For each organization, builds a set of elements based on the specified
    variable keys. Calculates intersections between all organizations.
    
    Args:
        vars: Comma-separated list of variable keys (e.g., "servicios,productos")
        
    Returns:
        JSON with structure:
        {
            "sets": [{"id": str, "name": str, "size": int}, ...],
            "intersections": [{"sets": [ids], "size": int, "elements": [...]}, ...]
        }
    """
    var_keys = [v.strip() for v in vars.split(",") if v.strip()]
    
    if not var_keys:
        return {"sets": [], "intersections": [], "error": "No variable keys provided"}
    
    # Get all organizations
    org_result = await db.execute(select(Organization))
    organizations = org_result.scalars().all()
    
    # Build sets for each organization based on specified variables
    sets_data: Dict[str, Set[str]] = {}
    
    for org in organizations:
        # Get variables for this organization matching the requested keys
        var_result = await db.execute(
            select(Variable)
            .where(Variable.organization_id == org.id)
            .where(Variable.key.in_(var_keys))
        )
        variables = var_result.scalars().all()
        
        # Combine all elements from all matching variables
        elements: Set[str] = set()
        for var in variables:
            var_elements = extract_elements_from_value(var.value)
            elements.update(var_elements)
        
        if elements:  # Only include organizations with elements
            sets_data[org.name] = elements
    
    if not sets_data:
        return {
            "sets": [],
            "intersections": [],
            "message": "No data found for specified variables"
        }
    
    # Calculate intersections
    result = calculate_intersections(sets_data)
    result["variable_keys"] = var_keys
    result["total_organizations"] = len(sets_data)
    
    return result


@router.get("/available-keys")
async def get_available_keys(db: AsyncSession = Depends(get_db)):
    """
    Get all unique variable keys available for Venn diagram.
    """
    result = await db.execute(
        select(Variable.key).distinct()
    )
    keys = result.scalars().all()
    
    # Count how many organizations have each key
    key_stats = []
    for key in keys:
        count_result = await db.execute(
            select(Variable.organization_id)
            .where(Variable.key == key)
            .distinct()
        )
        count = len(count_result.scalars().all())
        key_stats.append({
            "key": key,
            "organization_count": count
        })
    
    return {"keys": key_stats}


@router.get("/preview")
async def preview_venn_data(
    vars: str = Query(..., description="Comma-separated list of variable keys"),
    limit: int = Query(5, description="Max number of organizations to preview"),
    db: AsyncSession = Depends(get_db)
):
    """
    Preview what data will be used for Venn diagram.
    Useful for debugging and understanding the data.
    """
    var_keys = [v.strip() for v in vars.split(",") if v.strip()]
    
    result = await db.execute(
        select(Organization).limit(limit)
    )
    organizations = result.scalars().all()
    
    preview = []
    for org in organizations:
        var_result = await db.execute(
            select(Variable)
            .where(Variable.organization_id == org.id)
            .where(Variable.key.in_(var_keys))
        )
        variables = var_result.scalars().all()
        
        org_data = {
            "organization": org.name,
            "variables": {}
        }
        for var in variables:
            elements = extract_elements_from_value(var.value)
            org_data["variables"][var.key] = {
                "raw_value": var.value,
                "extracted_elements": list(elements)
            }
        preview.append(org_data)
    
    return {"preview": preview, "variable_keys": var_keys}
