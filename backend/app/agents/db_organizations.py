"""
Database Operations for Organizations.

CRUD operations for organizations in the database.
"""
from typing import List, Dict, Any, Optional

from ..db.base import get_sync_db_session
from ..models.db_models import (
    Organization, TerritorialScope, OrganizationApproach,
    OrganizationLink
)
from .db_common import find_similar_organizations, clear_embeddings_cache


# Department name to code mapping
DEPARTMENT_NAME_TO_CODE = {
    "bogota": "11", "bogotá": "11", "bogota d.c.": "11", "cundinamarca": "25",
    "antioquia": "05", "atlantico": "08", "atlántico": "08", "bolivar": "13", "bolívar": "13",
    "boyaca": "15", "boyacá": "15", "caldas": "17", "caqueta": "18", "caquetá": "18",
    "cauca": "19", "cesar": "20", "cordoba": "23", "córdoba": "23", "choco": "27", "chocó": "27",
    "huila": "41", "la guajira": "44", "guajira": "44", "magdalena": "47", "meta": "50",
    "nariño": "52", "narino": "52", "norte de santander": "54", "quindio": "63", "quindío": "63",
    "risaralda": "66", "santander": "68", "sucre": "70", "tolima": "73", "valle": "76",
    "valle del cauca": "76", "arauca": "81", "casanare": "85", "putumayo": "86",
    "san andres": "88", "san andrés": "88", "amazonas": "91", "guainia": "94", "guainía": "94",
    "guaviare": "95", "vaupes": "97", "vaupés": "97", "vichada": "99",
}


def normalize_department_code(code_or_name: str) -> Optional[str]:
    """Convert department name to code if needed."""
    if not code_or_name:
        return None
    
    code_lower = str(code_or_name).lower().strip()
    
    # If it's already a code (numeric), return it
    if code_lower.isdigit():
        return code_lower[:10]
    
    # Try direct mapping
    if code_lower in DEPARTMENT_NAME_TO_CODE:
        return DEPARTMENT_NAME_TO_CODE[code_lower]
    
    # Try partial match
    for name, code in DEPARTMENT_NAME_TO_CODE.items():
        if code_lower in name or name in code_lower:
            return code
    
    return None


def search_organizations(search_term: str) -> Dict[str, Any]:
    """Search organizations by name with semantic matching."""
    session = get_sync_db_session()
    try:
        # First try exact/partial SQL match
        orgs = session.query(Organization).filter(
            Organization.name.ilike(f"%{search_term}%")
        ).all()
        
        if orgs:
            return {
                "exact": True,
                "results": [{
                    "id": org.id,
                    "name": org.name,
                    "description": org.description,
                    "territorial_scope": org.territorial_scope.value if org.territorial_scope else None,
                    "department_code": org.department_code,
                    "leader_name": org.leader_name,
                    "approach": org.approach.value if org.approach else None,
                } for org in orgs],
                "suggestions": []
            }
        
        # Fall back to semantic search
        session.close()
        similar = find_similar_organizations(search_term, use_embeddings=True)
        return {
            "exact": False,
            "results": [],
            "suggestions": similar
        }
    finally:
        if session.is_active:
            session.close()


def get_all_organizations() -> List[Dict[str, Any]]:
    """Get all organizations."""
    session = get_sync_db_session()
    try:
        orgs = session.query(Organization).order_by(Organization.name).all()
        return [{
            "id": org.id,
            "name": org.name,
            "description": org.description,
            "territorial_scope": org.territorial_scope.value if org.territorial_scope else None,
            "department_code": org.department_code,
            "leader_name": org.leader_name,
            "approach": org.approach.value if org.approach else None,
            "is_peace_building": org.is_peace_building,
        } for org in orgs]
    finally:
        session.close()


def get_organization_by_name(name: str) -> Dict[str, Any]:
    """Get a single organization by name with semantic fallback."""
    session = get_sync_db_session()
    try:
        # Try exact/partial match first
        org = session.query(Organization).filter(
            Organization.name.ilike(f"%{name}%")
        ).first()
        
        if org:
            return {
                "found": True,
                "exact": True,
                "organization": {
                    "id": org.id,
                    "name": org.name,
                    "description": org.description,
                    "territorial_scope": org.territorial_scope.value if org.territorial_scope else None,
                    "department_code": org.department_code,
                    "municipality_code": org.municipality_code,
                    "leader_name": org.leader_name,
                    "leader_is_woman": org.leader_is_woman,
                    "approach": org.approach.value if org.approach else None,
                    "is_peace_building": org.is_peace_building,
                    "latitude": org.latitude,
                    "longitude": org.longitude,
                    "women_count": org.women_count,
                    "years_active": org.years_active,
                    "url": org.url,
                    "created_at": str(org.created_at) if org.created_at else None,
                },
                "suggestions": []
            }
        
        # Fall back to semantic search
        session.close()
        similar = find_similar_organizations(name, use_embeddings=True)
        return {
            "found": False,
            "exact": False,
            "organization": None,
            "suggestions": similar
        }
    finally:
        if session.is_active:
            session.close()


def create_organization(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new organization."""
    session = get_sync_db_session()
    try:
        org_name = data.get('name', '').strip()
        if not org_name:
            return {"success": False, "error": "El nombre de la organización es requerido"}
        
        # Check exact name match only
        existing = session.query(Organization).filter(
            Organization.name.ilike(org_name)
        ).first()
        
        if existing:
            return {"success": False, "error": f"Ya existe una organización con ese nombre: {existing.name}"}
        
        # Process territorial_scope
        territorial_scope = None
        if data.get("territorial_scope"):
            scope_map = {
                "municipal": TerritorialScope.MUNICIPAL,
                "departamental": TerritorialScope.DEPARTAMENTAL,
                "regional": TerritorialScope.REGIONAL,
                "nacional": TerritorialScope.NACIONAL,
                "internacional": TerritorialScope.INTERNACIONAL,
            }
            territorial_scope = scope_map.get(str(data["territorial_scope"]).lower(), TerritorialScope.MUNICIPAL)
        
        # Process approach
        approach = OrganizationApproach.UNKNOWN
        if data.get("approach"):
            approach_map = {
                "bottom_up": OrganizationApproach.BOTTOM_UP,
                "top_down": OrganizationApproach.TOP_DOWN,
                "mixed": OrganizationApproach.MIXED,
                "unknown": OrganizationApproach.UNKNOWN,
            }
            approach = approach_map.get(str(data["approach"]).lower(), OrganizationApproach.UNKNOWN)
        
        # Normalize department code
        department_code = normalize_department_code(data.get("department_code"))
        
        org = Organization(
            name=org_name,
            description=data.get("description"),
            url=data.get("url"),
            territorial_scope=territorial_scope,
            department_code=department_code,
            department_codes=data.get("department_codes"),
            municipality_code=data.get("municipality_code"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            leader_name=data.get("leader_name"),
            leader_is_woman=data.get("leader_is_woman"),
            approach=approach,
            is_peace_building=data.get("is_peace_building", True),
        )
        
        session.add(org)
        session.commit()
        
        # Clear cache so new org can be found
        clear_embeddings_cache()
        
        return {"success": True, "created": org.name, "id": org.id}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def update_organization_by_name(name: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an organization by name with semantic fallback."""
    session = get_sync_db_session()
    try:
        org = session.query(Organization).filter(
            Organization.name.ilike(f"%{name}%")
        ).first()
        
        if not org:
            session.close()
            similar = find_similar_organizations(name, use_embeddings=True)
            if similar:
                return {
                    "success": False,
                    "error": f"No se encontró '{name}' exactamente.",
                    "needs_confirmation": True,
                    "suggestions": similar
                }
            return {"success": False, "error": f"No se encontró la organización '{name}'"}
        
        for key, value in update_data.items():
            if hasattr(org, key) and value is not None:
                if key == "territorial_scope":
                    scope_map = {
                        "municipal": TerritorialScope.MUNICIPAL,
                        "departamental": TerritorialScope.DEPARTAMENTAL,
                        "regional": TerritorialScope.REGIONAL,
                        "nacional": TerritorialScope.NACIONAL,
                        "internacional": TerritorialScope.INTERNACIONAL,
                    }
                    value = scope_map.get(str(value).lower(), TerritorialScope.MUNICIPAL)
                elif key == "approach":
                    approach_map = {
                        "bottom_up": OrganizationApproach.BOTTOM_UP,
                        "top_down": OrganizationApproach.TOP_DOWN,
                        "mixed": OrganizationApproach.MIXED,
                        "unknown": OrganizationApproach.UNKNOWN,
                    }
                    value = approach_map.get(str(value).lower(), OrganizationApproach.UNKNOWN)
                elif key == "department_code":
                    value = normalize_department_code(value)
                setattr(org, key, value)
        
        session.commit()
        clear_embeddings_cache()
        return {"success": True, "updated": org.name}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if session.is_active:
            session.close()


def delete_organization_by_name(name: str) -> Dict[str, Any]:
    """Delete an organization by name with semantic fallback."""
    session = get_sync_db_session()
    try:
        org = session.query(Organization).filter(
            Organization.name.ilike(f"%{name}%")
        ).first()
        
        if org:
            org_name = org.name
            session.delete(org)
            session.commit()
            clear_embeddings_cache()
            return {"success": True, "deleted": org_name}
        
        session.close()
        similar = find_similar_organizations(name, use_embeddings=True)
        if similar:
            return {
                "success": False,
                "error": f"No se encontró '{name}' exactamente.",
                "needs_confirmation": True,
                "suggestions": similar
            }
        return {"success": False, "error": f"No se encontró la organización '{name}'"}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if session.is_active:
            session.close()


def get_organizations_without_location() -> List[Dict[str, Any]]:
    """Get organizations without geographic coordinates."""
    session = get_sync_db_session()
    try:
        orgs = session.query(Organization).filter(
            (Organization.latitude == None) | (Organization.longitude == None)
        ).all()
        return [{
            "id": org.id,
            "name": org.name,
            "department_code": org.department_code,
        } for org in orgs]
    finally:
        session.close()


def get_organizations_with_links() -> List[Dict[str, Any]]:
    """Get organizations that have scraping links configured."""
    session = get_sync_db_session()
    try:
        orgs_with_links = session.query(Organization).join(
            OrganizationLink, Organization.id == OrganizationLink.organization_id
        ).distinct().all()
        
        result = []
        for org in orgs_with_links:
            links = session.query(OrganizationLink).filter(
                OrganizationLink.organization_id == org.id
            ).all()
            result.append({
                "id": org.id,
                "name": org.name,
                "links": [{"url": link.url, "type": link.link_type} for link in links]
            })
        return result
    finally:
        session.close()


def add_link_to_organization(
    org_name: str, 
    url: str, 
    link_type: str = "scraping",
    description: Optional[str] = None
) -> Dict[str, Any]:
    """Add a link to an organization."""
    session = get_sync_db_session()
    try:
        org = session.query(Organization).filter(
            Organization.name.ilike(f"%{org_name}%")
        ).first()
        
        if not org:
            session.close()
            similar = find_similar_organizations(org_name, use_embeddings=True)
            if similar:
                return {
                    "success": False,
                    "error": f"No se encontró '{org_name}'",
                    "suggestions": similar
                }
            return {"success": False, "error": f"No se encontró la organización '{org_name}'"}
        
        # Check if link already exists
        existing = session.query(OrganizationLink).filter(
            OrganizationLink.organization_id == org.id,
            OrganizationLink.url == url
        ).first()
        
        if existing:
            return {"success": False, "error": f"El enlace ya existe para {org.name}"}
        
        link = OrganizationLink(
            organization_id=org.id,
            url=url,
            link_type=link_type,
            description=description
        )
        session.add(link)
        session.commit()
        
        return {"success": True, "organization": org.name, "added_url": url}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if session.is_active:
            session.close()
