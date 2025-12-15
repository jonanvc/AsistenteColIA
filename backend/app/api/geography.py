"""
API routes for Colombian geography data.
Provides endpoints for departments, municipalities, and regions.
"""
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from ..data.colombia_geo import (
    DEPARTMENTS, 
    get_department_by_code,
    get_departments_list,
    get_department_center,
    get_department_bounds
)
from ..data.colombia_municipalities import (
    get_all_municipalities,
    get_municipalities_by_department_code,
    find_nearest_municipality,
    get_municipality_by_code,
    get_municipalities_count
)


router = APIRouter(prefix="/api/geography", tags=["geography"])


# Colombia geographic center (approximate)
COLOMBIA_CENTER = {"lat": 4.5709, "lon": -74.2973}
COLOMBIA_BOUNDS = {
    "north": 13.4,
    "south": -4.2,
    "east": -66.8,
    "west": -79.0
}


# ==================== Pydantic Schemas ====================

class DepartmentBase(BaseModel):
    """Base schema for department data."""
    code: str
    name: str
    capital: str
    lat: float
    lon: float


class DepartmentGeoJSON(BaseModel):
    """GeoJSON Feature for a department."""
    type: str = "Feature"
    properties: dict
    geometry: dict


class RegionInfo(BaseModel):
    """Information about a Colombian region."""
    code: str
    name: str
    departments: List[str]  # List of department codes
    center: dict


class ColombiaInfo(BaseModel):
    """Basic Colombia geographic information."""
    center: dict
    bounds: dict
    total_departments: int


class MunicipalityBase(BaseModel):
    """Base schema for municipality data."""
    code: str
    name: str
    department_code: str
    department_name: str
    lat: Optional[float] = None
    lon: Optional[float] = None


# Colombian Regions (natural/cultural grouping of departments)
REGIONS = {
    "caribe": {
        "code": "caribe",
        "name": "Región Caribe",
        "departments": ["08", "13", "20", "23", "44", "47", "70", "88"],
        "center": {"lat": 10.5, "lon": -74.5}
    },
    "pacifico": {
        "code": "pacifico",
        "name": "Región Pacífico",
        "departments": ["19", "27", "52", "76"],
        "center": {"lat": 4.0, "lon": -77.0}
    },
    "andina": {
        "code": "andina",
        "name": "Región Andina",
        "departments": ["05", "11", "15", "17", "25", "41", "54", "63", "66", "68", "73"],
        "center": {"lat": 5.5, "lon": -74.0}
    },
    "orinoquia": {
        "code": "orinoquia",
        "name": "Región Orinoquía (Llanos)",
        "departments": ["50", "81", "85", "95", "99"],
        "center": {"lat": 5.0, "lon": -70.0}
    },
    "amazonia": {
        "code": "amazonia",
        "name": "Región Amazonía",
        "departments": ["18", "86", "91", "94", "97"],
        "center": {"lat": 0.5, "lon": -72.0}
    },
    "insular": {
        "code": "insular",
        "name": "Región Insular",
        "departments": ["88"],
        "center": {"lat": 12.5, "lon": -81.7}
    }
}


# ==================== Endpoints ====================

@router.get("/info", response_model=ColombiaInfo)
async def get_colombia_info():
    """Get basic Colombia geographic information."""
    return ColombiaInfo(
        center=COLOMBIA_CENTER,
        bounds=COLOMBIA_BOUNDS,
        total_departments=len(DEPARTMENTS)
    )


@router.get("/departments", response_model=List[DepartmentBase])
async def list_departments():
    """Get list of all Colombian departments."""
    return get_departments_list()


@router.get("/departments/{code}", response_model=DepartmentBase)
async def get_department(code: str):
    """Get department by DANE code."""
    department = get_department_by_code(code)
    if not department:
        raise HTTPException(status_code=404, detail=f"Department with code {code} not found")
    return department


@router.get("/departments/{code}/geojson")
async def get_department_geojson(code: str):
    """
    Get GeoJSON Feature for a department.
    Returns a point geometry with department properties.
    For full polygon geometries, load external GeoJSON files.
    """
    department = get_department_by_code(code)
    if not department:
        raise HTTPException(status_code=404, detail=f"Department with code {code} not found")
    
    return {
        "type": "Feature",
        "properties": {
            "code": department["code"],
            "name": department["name"],
            "capital": department["capital"],
            "type": "department"
        },
        "geometry": {
            "type": "Point",
            "coordinates": [department["lon"], department["lat"]]
        }
    }


@router.get("/departments/geojson/all")
async def get_all_departments_geojson():
    """
    Get GeoJSON FeatureCollection for all departments.
    Returns point geometries for each department capital.
    """
    features = []
    for dept in get_departments_list():
        features.append({
            "type": "Feature",
            "properties": {
                "code": dept["code"],
                "name": dept["name"],
                "capital": dept["capital"],
                "type": "department"
            },
            "geometry": {
                "type": "Point",
                "coordinates": [dept["lon"], dept["lat"]]
            }
        })
    
    return {
        "type": "FeatureCollection",
        "features": features
    }


@router.get("/regions", response_model=List[RegionInfo])
async def list_regions():
    """Get list of Colombian natural regions."""
    return [RegionInfo(**region) for region in REGIONS.values()]


@router.get("/regions/{code}", response_model=RegionInfo)
async def get_region(code: str):
    """Get region by code."""
    region = REGIONS.get(code.lower())
    if not region:
        raise HTTPException(status_code=404, detail=f"Region with code {code} not found")
    return RegionInfo(**region)


@router.get("/regions/{code}/departments", response_model=List[DepartmentBase])
async def get_region_departments(code: str):
    """Get all departments in a region."""
    region = REGIONS.get(code.lower())
    if not region:
        raise HTTPException(status_code=404, detail=f"Region with code {code} not found")
    
    departments = []
    for dept_code in region["departments"]:
        dept = get_department_by_code(dept_code)
        if dept:
            departments.append(dept)
    return departments


@router.get("/municipalities", response_model=List[MunicipalityBase])
async def list_municipalities(
    department_code: Optional[str] = Query(None, description="Filter by department code")
):
    """Get list of all municipalities (~1,122 municipalities in Colombia)."""
    if department_code:
        municipalities = get_municipalities_by_department_code(department_code)
    else:
        municipalities = get_all_municipalities()
    
    result = []
    for mun in municipalities:
        dept = get_department_by_code(mun["department_code"])
        result.append(MunicipalityBase(
            code=mun["code"],
            name=mun["name"],
            department_code=mun["department_code"],
            department_name=dept["name"] if dept else "Unknown",
            lat=mun.get("lat"),
            lon=mun.get("lng")  # Note: source uses 'lng', we expose as 'lon'
        ))
    return result


@router.get("/municipalities/nearest")
async def find_nearest_municipality_endpoint(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    max_distance_km: float = Query(100, description="Maximum search radius in km")
):
    """
    Find the nearest municipality to given coordinates.
    Useful for map click-to-select functionality.
    """
    result = find_nearest_municipality(lat, lng, max_distance_km)
    if not result:
        raise HTTPException(
            status_code=404, 
            detail=f"No municipality found within {max_distance_km}km of coordinates ({lat}, {lng})"
        )
    
    dept = get_department_by_code(result["department_code"])
    return {
        "code": result["code"],
        "name": result["name"],
        "department_code": result["department_code"],
        "department_name": dept["name"] if dept else "Unknown",
        "lat": result["lat"],
        "lon": result["lng"],
        "distance_km": result["distance_deg"] * 111  # Approximate conversion
    }


@router.get("/municipalities/count")
async def get_municipality_count():
    """Get total count of municipalities in the database."""
    return {"total": get_municipalities_count()}


@router.get("/municipalities/{code}", response_model=MunicipalityBase)
async def get_municipality_endpoint(code: str):
    """Get municipality by DANE code."""
    municipality = get_municipality_by_code(code)
    if not municipality:
        raise HTTPException(status_code=404, detail=f"Municipality with code {code} not found")
    
    dept = get_department_by_code(municipality["department_code"])
    return MunicipalityBase(
        code=municipality["code"],
        name=municipality["name"],
        department_code=municipality["department_code"],
        department_name=dept["name"] if dept else "Unknown",
        lat=municipality.get("lat"),
        lon=municipality.get("lng")
    )


@router.get("/municipalities/geojson/all")
async def get_all_municipalities_geojson():
    """Get GeoJSON FeatureCollection for all municipalities."""
    municipalities = get_all_municipalities()
    features = []
    for mun in municipalities:
        dept = get_department_by_code(mun["department_code"])
        features.append({
            "type": "Feature",
            "properties": {
                "code": mun["code"],
                "name": mun["name"],
                "department_code": mun["department_code"],
                "department_name": dept["name"] if dept else "Unknown",
                "type": "municipality"
            },
            "geometry": {
                "type": "Point",
                "coordinates": [mun["lng"], mun["lat"]]
            }
        })
    
    return {
        "type": "FeatureCollection",
        "count": len(features),
        "features": features
    }


@router.get("/search")
async def search_locations(
    q: str = Query(..., min_length=2, description="Search query"),
    limit: int = Query(50, description="Maximum results to return")
):
    """
    Search departments and municipalities by name.
    Returns matching locations with their geographic data.
    """
    query_lower = q.lower()
    results = []
    
    # Search departments
    for dept in get_departments_list():
        if query_lower in dept["name"].lower() or query_lower in dept["capital"].lower():
            results.append({
                "type": "department",
                "code": dept["code"],
                "name": dept["name"],
                "display_name": f"{dept['name']} (Departamento)",
                "lat": dept["lat"],
                "lon": dept["lon"]
            })
    
    # Search municipalities
    for mun in get_all_municipalities():
        if query_lower in mun["name"].lower():
            dept = get_department_by_code(mun["department_code"])
            results.append({
                "type": "municipality",
                "code": mun["code"],
                "name": mun["name"],
                "display_name": f"{mun['name']}, {dept['name'] if dept else ''}",
                "department_code": mun["department_code"],
                "lat": mun.get("lat"),
                "lon": mun.get("lng")
            })
            if len(results) >= limit:
                break
    
    return {
        "query": q,
        "count": len(results),
        "results": results[:limit]
    }
