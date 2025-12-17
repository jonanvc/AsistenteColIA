"""
Database Agent

Responsible for querying, creating, updating, and deleting organizations
directly from the database. Also handles scraping triggers for specific organizations.

This agent provides direct database access for the chat interface.
"""
import os
import json
from typing import TYPE_CHECKING, List, Dict, Any, Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable

if TYPE_CHECKING:
    from .graph import AgentState

# Initialize ChatOpenAI client
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    max_tokens=8000,  # Increased for batch operations with many organizations
)

# Synchronous database imports
from ..db.base import get_sync_db_session
from ..models.db_models import (
    Organization, TerritorialScope, OrganizationApproach,
    VennVariable, VennProxy, VennResult, OrganizationLink,
    InformationSource, VennIntersection, VennIntersectionResult,
    VennOperationType
)


DB_AGENT_SYSTEM_PROMPT = """Eres un agente de BD para organizaciones de mujeres constructoras de paz en Colombia.

OPERACIONES DISPONIBLES:
1. ORGANIZACIONES:
   - query_organizations: Buscar varias organizaciones por término
   - get_organization: Obtener detalles COMPLETOS de UNA organización específica
   - list_all_organizations: Listar TODAS las organizaciones
   - delete_organization, update_organization, create_organization

2. VENN (variables, proxies, intersecciones):
   - list_venn_variables: Listar TODAS las variables Venn (solo nombres)
   - get_venn_variable: Obtener UNA variable específica con sus proxies (usar variable_name)
   - create_venn_variable, update_venn_variable, delete_venn_variable
   - add_venn_proxy, delete_venn_proxy
   - list_venn_intersections: Listar TODAS las intersecciones
   - create_venn_intersection, update_venn_intersection, delete_venn_intersection
   - calculate_intersection

3. OTROS: add_link_to_organization, trigger_scrape, no_db_action

CONSULTA: {user_input}

Responde SOLO JSON válido:
{{
    "action": "accion",
    "organization_name": "nombre org",
    "variable_name": "variable Venn específica",
    "intersection_name": "intersección específica",
    "include_proxies": ["proxy1", "proxy2"],
    "logic_expression_text": "expr con paréntesis",
    "intersection_operation": "union|intersection",
    "data": {{}},
    "update_data": {{}},
    "proxy_data": {{}},
    "reasoning": "explicación"
}}

REGLAS CRÍTICAS - ORGANIZACIONES:
- "Dame info de X" / "Qué es X" / "Muestra X" → get_organization (organization_name: "X")
- "Lista organizaciones" / "Cuántas hay" → list_all_organizations

REGLAS CRÍTICAS - VENN:
- "Lista las variables Venn" / "Qué variables hay" → list_venn_variables
- "Muestra la variable X" / "Dame info de variable X" / "Variable X" → get_venn_variable (variable_name: "X")
- "Lista las intersecciones" / "Qué intersecciones hay" → list_venn_intersections
- "Añade proxy Y a variable X" → add_venn_proxy (variable_name: "X", proxy_data: {{"name": "Y"}})

CREAR:
- create_organization: data con name, description, territorial_scope, department_code, leader_name, leader_is_woman
- create_venn_variable: data con name, description
- add_venn_proxy: variable_name + proxy_data con name (texto)
"""


# ============ FUZZY SEARCH HELPERS ============

def calculate_similarity(s1: str, s2: str) -> float:
    """Calculate similarity ratio between two strings (0.0 to 1.0)."""
    from difflib import SequenceMatcher
    s1_lower = s1.lower().strip()
    s2_lower = s2.lower().strip()
    return SequenceMatcher(None, s1_lower, s2_lower).ratio()


def find_similar_organizations(search_term: str, threshold: float = 0.4) -> List[Dict[str, Any]]:
    """Find organizations with fuzzy matching when exact match fails."""
    session = get_sync_db_session()
    try:
        all_orgs = session.query(Organization).all()
        
        matches = []
        for org in all_orgs:
            # Check name similarity
            name_sim = calculate_similarity(search_term, org.name)
            
            # Check if search term is contained in name or vice versa
            search_lower = search_term.lower()
            name_lower = org.name.lower()
            contains_match = search_lower in name_lower or name_lower in search_lower
            
            # Check first letters/acronym match
            search_words = search_lower.split()
            name_words = name_lower.split()
            acronym_match = len(search_words) > 0 and len(name_words) > 0 and (
                search_words[0][:3] == name_words[0][:3] if len(search_words[0]) >= 3 and len(name_words[0]) >= 3 else False
            )
            
            if name_sim >= threshold or contains_match or acronym_match:
                matches.append({
                    "id": org.id,
                    "name": org.name,
                    "description": org.description,
                    "territorial_scope": org.territorial_scope.value if org.territorial_scope else None,
                    "department_code": org.department_code,
                    "leader_name": org.leader_name,
                    "similarity": name_sim,
                    "exact_match": contains_match,
                })
        
        # Sort by similarity (highest first)
        matches.sort(key=lambda x: (x["exact_match"], x["similarity"]), reverse=True)
        return matches[:5]  # Return top 5 matches
    finally:
        session.close()


def find_similar_venn_variables(search_term: str, threshold: float = 0.4) -> List[Dict[str, Any]]:
    """Find Venn variables with fuzzy matching."""
    session = get_sync_db_session()
    try:
        all_vars = session.query(VennVariable).all()
        
        matches = []
        for var in all_vars:
            name_sim = calculate_similarity(search_term, var.name)
            search_lower = search_term.lower()
            name_lower = var.name.lower()
            contains_match = search_lower in name_lower or name_lower in search_lower
            
            if name_sim >= threshold or contains_match:
                matches.append({
                    "id": var.id,
                    "name": var.name,
                    "description": var.description,
                    "similarity": name_sim,
                    "exact_match": contains_match,
                })
        
        matches.sort(key=lambda x: (x["exact_match"], x["similarity"]), reverse=True)
        return matches[:5]
    finally:
        session.close()


def find_similar_venn_proxies(variable_id: int, search_term: str, threshold: float = 0.4) -> List[Dict[str, Any]]:
    """Find Venn proxies with fuzzy matching within a variable."""
    session = get_sync_db_session()
    try:
        all_proxies = session.query(VennProxy).filter(VennProxy.venn_variable_id == variable_id).all()
        
        matches = []
        for proxy in all_proxies:
            term_sim = calculate_similarity(search_term, proxy.term)
            search_lower = search_term.lower()
            term_lower = proxy.term.lower()
            contains_match = search_lower in term_lower or term_lower in search_lower
            
            if term_sim >= threshold or contains_match:
                matches.append({
                    "id": proxy.id,
                    "term": proxy.term,
                    "weight": proxy.weight,
                    "similarity": term_sim,
                    "exact_match": contains_match,
                })
        
        matches.sort(key=lambda x: (x["exact_match"], x["similarity"]), reverse=True)
        return matches[:5]
    finally:
        session.close()


# ============ ORGANIZATION FUNCTIONS ============

def search_organizations(search_term: str) -> Dict[str, Any]:
    """Search organizations by name with fuzzy matching."""
    session = get_sync_db_session()
    try:
        # First try exact/partial match
        orgs = session.query(Organization).filter(
            Organization.name.ilike(f"%{search_term}%")
        ).all()
        
        if orgs:
            results = []
            for org in orgs:
                results.append({
                    "id": org.id,
                    "name": org.name,
                    "description": org.description,
                    "territorial_scope": org.territorial_scope.value if org.territorial_scope else None,
                    "department_code": org.department_code,
                    "leader_name": org.leader_name,
                    "leader_is_woman": org.leader_is_woman,
                    "approach": org.approach.value if org.approach else None,
                    "is_peace_building": org.is_peace_building,
                    "latitude": org.latitude,
                    "longitude": org.longitude,
                })
            return {"exact": True, "results": results, "suggestions": []}
        
        # No exact match - try fuzzy search
        session.close()
        similar = find_similar_organizations(search_term)
        return {"exact": False, "results": [], "suggestions": similar}
    finally:
        if session.is_active:
            session.close()


def get_all_organizations() -> List[Dict[str, Any]]:
    """Get all organizations from database."""
    session = get_sync_db_session()
    try:
        orgs = session.query(Organization).all()
        
        results = []
        for org in orgs:
            results.append({
                "id": org.id,
                "name": org.name,
                "description": org.description[:100] if org.description else None,
                "territorial_scope": org.territorial_scope.value if org.territorial_scope else None,
                "department_code": org.department_code,
                "leader_name": org.leader_name,
            })
        return results
    finally:
        session.close()


def get_organizations_without_location() -> List[Dict[str, Any]]:
    """Get organizations that don't have coordinates set."""
    session = get_sync_db_session()
    try:
        from sqlalchemy import or_
        orgs = session.query(Organization).filter(
            or_(
                Organization.latitude.is_(None),
                Organization.longitude.is_(None)
            )
        ).all()
        
        results = []
        for org in orgs:
            results.append({
                "id": org.id,
                "name": org.name,
                "description": org.description[:100] if org.description else None,
                "territorial_scope": org.territorial_scope.value if org.territorial_scope else None,
                "department_code": org.department_code,
                "latitude": org.latitude,
                "longitude": org.longitude,
            })
        return results
    finally:
        session.close()


def get_organizations_with_links() -> List[Dict[str, Any]]:
    """Get organizations that have scraping URLs/links configured."""
    session = get_sync_db_session()
    try:
        from sqlalchemy import exists
        
        # Subquery to check if org has any links
        has_links = session.query(OrganizationLink.organization_id).distinct()
        
        orgs = session.query(Organization).filter(
            Organization.id.in_(has_links)
        ).all()
        
        results = []
        for org in orgs:
            link_count = session.query(OrganizationLink).filter(
                OrganizationLink.organization_id == org.id
            ).count()
            
            results.append({
                "id": org.id,
                "name": org.name,
                "territorial_scope": org.territorial_scope.value if org.territorial_scope else None,
                "link_count": link_count,
            })
        return results
    finally:
        session.close()


def get_organizations_without_links() -> List[Dict[str, Any]]:
    """Get organizations that don't have any scraping URLs/links configured."""
    session = get_sync_db_session()
    try:
        # Subquery to get org IDs that have links
        orgs_with_links = session.query(OrganizationLink.organization_id).distinct()
        
        orgs = session.query(Organization).filter(
            ~Organization.id.in_(orgs_with_links)
        ).all()
        
        results = []
        for org in orgs:
            results.append({
                "id": org.id,
                "name": org.name,
                "territorial_scope": org.territorial_scope.value if org.territorial_scope else None,
            })
        return results
    finally:
        session.close()


def get_organization_by_name(name: str) -> Dict[str, Any]:
    """Get a single organization by exact or partial name match with fuzzy fallback."""
    session = get_sync_db_session()
    try:
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
        
        # No exact match - try fuzzy search
        session.close()
        similar = find_similar_organizations(name)
        return {
            "found": False,
            "exact": False,
            "organization": None,
            "suggestions": similar
        }
    finally:
        if session.is_active:
            session.close()


def delete_organization_by_name(name: str) -> Dict[str, Any]:
    """Delete an organization by name with fuzzy matching fallback."""
    session = get_sync_db_session()
    try:
        org = session.query(Organization).filter(
            Organization.name.ilike(f"%{name}%")
        ).first()
        
        if org:
            org_name = org.name
            session.delete(org)
            session.commit()
            return {"success": True, "deleted": org_name}
        
        # No exact match - try fuzzy search
        session.close()
        similar = find_similar_organizations(name)
        if similar:
            return {
                "success": False, 
                "error": f"No se encontró '{name}' exactamente.",
                "needs_confirmation": True,
                "suggestions": similar
            }
        return {"success": False, "error": f"No se encontró la organización '{name}' ni ninguna similar."}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if session.is_active:
            session.close()


def update_organization_by_name(name: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update an organization by name with fuzzy matching fallback."""
    session = get_sync_db_session()
    try:
        org = session.query(Organization).filter(
            Organization.name.ilike(f"%{name}%")
        ).first()
        
        if not org:
            # No exact match - try fuzzy search
            session.close()
            similar = find_similar_organizations(name)
            if similar:
                return {
                    "success": False, 
                    "error": f"No se encontró '{name}' exactamente.",
                    "needs_confirmation": True,
                    "suggestions": similar
                }
            return {"success": False, "error": f"No se encontró la organización '{name}' ni ninguna similar."}
        
        # Update fields
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
                setattr(org, key, value)
        
        session.commit()
        return {"success": True, "updated": org.name}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def create_organization(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new organization."""
    session = get_sync_db_session()
    try:
        # Check if organization already exists (exact match, case-insensitive)
        org_name = data.get('name', '').strip()
        if not org_name:
            return {"success": False, "error": "El nombre de la organización es requerido"}
        
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
        
        # Process department_code - convert name to code if needed
        department_code = data.get("department_code")
        if department_code:
            dept_name_to_code = {
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
            dept_lower = str(department_code).lower().strip()
            # If it's a name, convert to code; if already a code (numeric), keep it
            if dept_lower in dept_name_to_code:
                department_code = dept_name_to_code[dept_lower]
            elif not dept_lower.isdigit():
                # Try partial match
                for name, code in dept_name_to_code.items():
                    if dept_lower in name or name in dept_lower:
                        department_code = code
                        break
                else:
                    department_code = None  # Invalid department name
            # Ensure it's max 10 chars
            if department_code and len(str(department_code)) > 10:
                department_code = str(department_code)[:10]
        
        org = Organization(
            name=data.get("name"),
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
        return {"success": True, "created": org.name, "id": org.id}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def get_venn_variable(name: str) -> Dict[str, Any]:
    """Get a single Venn variable with all its proxies."""
    session = get_sync_db_session()
    try:
        var = session.query(VennVariable).filter(
            VennVariable.name.ilike(f"%{name}%")
        ).first()
        
        if not var:
            # Try fuzzy search
            similar = find_similar_venn_variables(name)
            if similar:
                return {
                    "found": False,
                    "suggestions": similar,
                    "error": f"No se encontró '{name}' exactamente."
                }
            return {"found": False, "error": f"No se encontró la variable '{name}'"}
        
        # Get all proxies for this variable
        proxies = session.query(VennProxy).filter(
            VennProxy.venn_variable_id == var.id
        ).all()
        
        return {
            "found": True,
            "variable": {
                "id": var.id,
                "name": var.name,
                "description": var.description,
                "proxies": [
                    {"id": p.id, "term": p.term, "weight": p.weight, "is_regex": p.is_regex}
                    for p in proxies
                ]
            }
        }
    finally:
        session.close()


def list_all_venn_variables() -> Dict[str, Any]:
    """List all Venn variables with summary info."""
    session = get_sync_db_session()
    try:
        variables = session.query(VennVariable).all()
        result = []
        for var in variables:
            proxy_count = session.query(VennProxy).filter(
                VennProxy.venn_variable_id == var.id
            ).count()
            result.append({
                "id": var.id,
                "name": var.name,
                "description": var.description,
                "proxy_count": proxy_count
            })
        return {"success": True, "variables": result, "total": len(result)}
    finally:
        session.close()


def create_venn_variable(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Venn variable."""
    session = get_sync_db_session()
    try:
        # Check if variable already exists (exact match, case-insensitive)
        var_name = data.get('name', '').strip()
        if not var_name:
            return {"success": False, "error": "El nombre de la variable es requerido"}
        
        existing = session.query(VennVariable).filter(
            VennVariable.name.ilike(var_name)
        ).first()
        
        if existing:
            return {"success": False, "error": f"Ya existe una variable con ese nombre: {existing.name}"}
        
        var = VennVariable(
            name=data.get("name"),
            description=data.get("description"),
        )
        
        session.add(var)
        session.commit()
        return {"success": True, "created": var.name, "id": var.id}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def update_venn_variable(name: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Venn variable by name with fuzzy matching."""
    session = get_sync_db_session()
    try:
        var = session.query(VennVariable).filter(
            VennVariable.name.ilike(f"%{name}%")
        ).first()
        
        if not var:
            # No exact match - try fuzzy search
            session.close()
            similar = find_similar_venn_variables(name)
            if similar:
                return {
                    "success": False, 
                    "error": f"No se encontró '{name}' exactamente.",
                    "needs_confirmation": True,
                    "suggestions": similar
                }
            return {"success": False, "error": f"No se encontró la variable '{name}' ni ninguna similar."}
        
        for key, value in update_data.items():
            if hasattr(var, key) and value is not None:
                setattr(var, key, value)
        
        session.commit()
        return {"success": True, "updated": var.name}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if session.is_active:
            session.close()


def delete_venn_variable(name: str) -> Dict[str, Any]:
    """Delete a Venn variable by name with fuzzy matching."""
    session = get_sync_db_session()
    try:
        var = session.query(VennVariable).filter(
            VennVariable.name.ilike(f"%{name}%")
        ).first()
        
        if not var:
            # No exact match - try fuzzy search
            session.close()
            similar = find_similar_venn_variables(name)
            if similar:
                return {
                    "success": False, 
                    "error": f"No se encontró '{name}' exactamente.",
                    "needs_confirmation": True,
                    "suggestions": similar
                }
            return {"success": False, "error": f"No se encontró la variable '{name}' ni ninguna similar."}
        
        # Delete associated proxies first
        session.query(VennProxy).filter(VennProxy.venn_variable_id == var.id).delete()
        
        var_name = var.name
        session.delete(var)
        session.commit()
        return {"success": True, "deleted": var_name}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if session.is_active:
            session.close()


def add_venn_proxy(variable_name: str, proxy_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a proxy to a Venn variable with fuzzy matching."""
    session = get_sync_db_session()
    try:
        var = session.query(VennVariable).filter(
            VennVariable.name.ilike(f"%{variable_name}%")
        ).first()
        
        if not var:
            # No exact match - try fuzzy search
            session.close()
            similar = find_similar_venn_variables(variable_name)
            if similar:
                return {
                    "success": False, 
                    "error": f"No se encontró la variable '{variable_name}' exactamente.",
                    "needs_confirmation": True,
                    "suggestions": similar
                }
            return {"success": False, "error": f"No se encontró la variable '{variable_name}' ni ninguna similar."}
        
        proxy = VennProxy(
            venn_variable_id=var.id,
            term=proxy_data.get("name") or proxy_data.get("term"),
            is_regex=proxy_data.get("is_regex", False),
            weight=proxy_data.get("weight", 1.0),
        )
        
        session.add(proxy)
        session.commit()
        return {"success": True, "created": proxy.term, "variable": var.name}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if session.is_active:
            session.close()


def delete_venn_proxy(variable_name: str, proxy_name: str) -> Dict[str, Any]:
    """Delete a proxy from a Venn variable with fuzzy matching."""
    session = get_sync_db_session()
    try:
        var = session.query(VennVariable).filter(
            VennVariable.name.ilike(f"%{variable_name}%")
        ).first()
        
        if not var:
            # No exact match for variable - try fuzzy search
            session.close()
            similar = find_similar_venn_variables(variable_name)
            if similar:
                return {
                    "success": False, 
                    "error": f"No se encontró la variable '{variable_name}' exactamente.",
                    "needs_confirmation": True,
                    "suggestions": similar
                }
            return {"success": False, "error": f"No se encontró la variable '{variable_name}' ni ninguna similar."}
        
        proxy = session.query(VennProxy).filter(
            VennProxy.venn_variable_id == var.id,
            VennProxy.term.ilike(f"%{proxy_name}%")
        ).first()
        
        if not proxy:
            # No exact match for proxy - try fuzzy search
            similar_proxies = find_similar_venn_proxies(var.id, proxy_name)
            if similar_proxies:
                return {
                    "success": False, 
                    "error": f"No se encontró el proxy '{proxy_name}' exactamente en '{var.name}'.",
                    "needs_confirmation": True,
                    "suggestions": similar_proxies,
                    "variable": var.name
                }
            return {"success": False, "error": f"No se encontró el proxy '{proxy_name}' en la variable '{var.name}'"}
        
        proxy_term = proxy.term
        session.delete(proxy)
        session.commit()
        return {"success": True, "deleted": proxy_term, "variable": var.name}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if session.is_active:
            session.close()


def list_venn_results(organization_id: int = None, variable_id: int = None, limit: int = 50) -> Dict[str, Any]:
    """List Venn evaluation results, optionally filtered by organization or variable."""
    session = get_sync_db_session()
    try:
        query = session.query(VennResult)
        
        if organization_id:
            query = query.filter(VennResult.organization_id == organization_id)
        if variable_id:
            query = query.filter(VennResult.venn_variable_id == variable_id)
        
        results = query.order_by(VennResult.created_at.desc()).limit(limit).all()
        
        results_data = []
        for r in results:
            # Get related organization and variable names
            org = session.query(Organization).filter(Organization.id == r.organization_id).first()
            var = session.query(VennVariable).filter(VennVariable.id == r.venn_variable_id).first()
            
            results_data.append({
                "id": r.id,
                "organization_id": r.organization_id,
                "organization_name": org.name if org else "Desconocida",
                "variable_id": r.venn_variable_id,
                "variable_name": var.name if var else "Desconocida",
                "score": r.score,
                "matched_proxies": r.matched_proxies,
                "evidence_snippets": r.evidence_snippets,
                "source_url": r.source_url,
                "created_at": str(r.created_at) if r.created_at else None,
            })
        
        return {
            "success": True,
            "results": results_data,
            "total": len(results_data),
        }
    finally:
        session.close()


def delete_venn_result(result_id: int = None, organization_name: str = None, variable_name: str = None) -> Dict[str, Any]:
    """Delete a Venn result by ID, or all results for an organization/variable."""
    session = get_sync_db_session()
    try:
        deleted_count = 0
        
        if result_id:
            result = session.query(VennResult).filter(VennResult.id == result_id).first()
            if not result:
                return {"success": False, "error": f"No se encontró el resultado con ID {result_id}"}
            session.delete(result)
            deleted_count = 1
        elif organization_name:
            org = session.query(Organization).filter(
                Organization.name.ilike(f"%{organization_name}%")
            ).first()
            if not org:
                return {"success": False, "error": f"No se encontró la organización '{organization_name}'"}
            deleted_count = session.query(VennResult).filter(
                VennResult.organization_id == org.id
            ).delete()
        elif variable_name:
            var = session.query(VennVariable).filter(
                VennVariable.name.ilike(f"%{variable_name}%")
            ).first()
            if not var:
                return {"success": False, "error": f"No se encontró la variable '{variable_name}'"}
            deleted_count = session.query(VennResult).filter(
                VennResult.venn_variable_id == var.id
            ).delete()
        else:
            return {"success": False, "error": "Especifica result_id, organization_name o variable_name"}
        
        session.commit()
        return {"success": True, "deleted_count": deleted_count}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


# ============ LOGIC EXPRESSION SYSTEM ============

def parse_logic_expression_text(expression_text: str, session) -> Dict[str, Any]:
    """
    Parse a text-based logic expression into a structured logic_expression with proxy IDs.
    
    Input format examples:
    - '"Proxy A" OR "Proxy B"'
    - '"Proxy A" AND "Proxy B"'
    - '"Proxy A" OR "Proxy B" OR ("Proxy C" AND "Proxy D")'
    - '("Proxy A" OR "Proxy B") AND "Proxy C"'
    
    Returns:
        Dict with structure: {"type": "AND|OR", "children": [...], "matched_proxies": [...]}
    """
    import re
    
    # Track matched proxies for reporting
    matched_proxies = []
    
    def find_proxy_by_text(text: str):
        """Find a proxy by its text (partial match)."""
        text = text.strip().strip('"').strip("'")
        if not text:
            return None
        
        # Try partial match first
        proxy = session.query(VennProxy).filter(
            VennProxy.term.ilike(f"%{text[:50]}%")
        ).first()
        
        if proxy:
            var = session.query(VennVariable).filter(VennVariable.id == proxy.venn_variable_id).first()
            matched_proxies.append({
                "proxy_id": proxy.id,
                "term": proxy.term[:80],
                "variable": var.name if var else "?"
            })
            return {"type": "proxy", "id": proxy.id}
        
        # Try exact match
        proxy = session.query(VennProxy).filter(VennProxy.term == text).first()
        if proxy:
            var = session.query(VennVariable).filter(VennVariable.id == proxy.venn_variable_id).first()
            matched_proxies.append({
                "proxy_id": proxy.id,
                "term": proxy.term[:80],
                "variable": var.name if var else "?"
            })
            return {"type": "proxy", "id": proxy.id}
        
        return None
    
    def tokenize(text: str) -> list:
        """Tokenize the expression into components."""
        tokens = []
        i = 0
        while i < len(text):
            # Skip whitespace
            while i < len(text) and text[i].isspace():
                i += 1
            if i >= len(text):
                break
            
            # Check for parentheses
            if text[i] == '(':
                tokens.append('(')
                i += 1
            elif text[i] == ')':
                tokens.append(')')
                i += 1
            # Check for quoted strings
            elif text[i] == '"':
                j = i + 1
                while j < len(text) and text[j] != '"':
                    j += 1
                tokens.append(text[i:j+1])  # Include quotes
                i = j + 1
            # Check for operators
            elif text[i:i+3].upper() == 'AND':
                tokens.append('AND')
                i += 3
            elif text[i:i+2].upper() == 'OR':
                tokens.append('OR')
                i += 2
            else:
                # Collect non-quoted text until we hit something else
                j = i
                while j < len(text) and text[j] not in '()"' and not text[j].isspace() and text[j:j+3].upper() != 'AND' and text[j:j+2].upper() != 'OR':
                    j += 1
                if j > i:
                    tokens.append(text[i:j])
                i = j
        
        return tokens
    
    def parse_expression(tokens: list, pos: int = 0):
        """Parse tokens into an expression tree."""
        result, pos = parse_or(tokens, pos)
        return result, pos
    
    def parse_or(tokens: list, pos: int):
        """Parse OR expressions (lowest precedence)."""
        left, pos = parse_and(tokens, pos)
        
        while pos < len(tokens) and tokens[pos].upper() == 'OR':
            pos += 1  # Skip OR
            right, pos = parse_and(tokens, pos)
            
            # Combine with OR
            if left.get('type') == 'OR':
                left['children'].append(right)
            else:
                left = {'type': 'OR', 'children': [left, right]}
        
        return left, pos
    
    def parse_and(tokens: list, pos: int):
        """Parse AND expressions (higher precedence than OR)."""
        left, pos = parse_primary(tokens, pos)
        
        while pos < len(tokens) and tokens[pos].upper() == 'AND':
            pos += 1  # Skip AND
            right, pos = parse_primary(tokens, pos)
            
            # Combine with AND
            if left.get('type') == 'AND':
                left['children'].append(right)
            else:
                left = {'type': 'AND', 'children': [left, right]}
        
        return left, pos
    
    def parse_primary(tokens: list, pos: int):
        """Parse primary expressions (parenthesized or leaf)."""
        if pos >= len(tokens):
            return {'type': 'empty'}, pos
        
        token = tokens[pos]
        
        if token == '(':
            pos += 1  # Skip (
            result, pos = parse_or(tokens, pos)  # Start from OR for correct precedence
            if pos < len(tokens) and tokens[pos] == ')':
                pos += 1  # Skip )
            return result, pos
        elif token.startswith('"'):
            # Quoted proxy term
            proxy_node = find_proxy_by_text(token)
            if proxy_node:
                return proxy_node, pos + 1
            else:
                # Return a placeholder with the text
                return {'type': 'unknown', 'text': token}, pos + 1
        else:
            # Unquoted text - try to find as proxy
            proxy_node = find_proxy_by_text(token)
            if proxy_node:
                return proxy_node, pos + 1
            else:
                return {'type': 'unknown', 'text': token}, pos + 1
    
    # Parse the expression
    tokens = tokenize(expression_text)
    if not tokens:
        return {'type': 'empty', 'children': [], 'matched_proxies': []}
    
    result, _ = parse_expression(tokens)
    result['matched_proxies'] = matched_proxies
    
    return result


def evaluate_logic_expression(
    expression: Dict[str, Any],
    organization_id: int,
    session,
    cache: Dict[str, bool] = None
) -> bool:
    """
    Recursively evaluate a logic expression tree for an organization.
    
    Expression format:
    {
        "type": "AND|OR|proxy|variable|NOT",
        "children": [...],  // For AND/OR operators
        "id": <int>,        // For proxy/variable leaf nodes
        "negate": <bool>    // Optional, to negate the result
    }
    
    Args:
        expression: The logic expression tree (JSON dict)
        organization_id: The organization to evaluate against
        session: Database session
        cache: Optional cache for proxy/variable lookups
    
    Returns:
        bool: The evaluated result
    """
    if cache is None:
        cache = {}
    
    # Handle case where expression might be a string (JSON)
    if isinstance(expression, str):
        try:
            expression = json.loads(expression)
        except json.JSONDecodeError:
            return False
    
    if not isinstance(expression, dict):
        return False
    
    expr_type = expression.get("type", "").upper()
    negate = expression.get("negate", False)
    
    result = False
    
    if expr_type == "AND":
        # All children must be True
        children = expression.get("children", [])
        if not children:
            result = False
        else:
            result = all(evaluate_logic_expression(child, organization_id, session, cache) for child in children)
    
    elif expr_type == "OR":
        # At least one child must be True
        children = expression.get("children", [])
        if not children:
            result = False
        else:
            result = any(evaluate_logic_expression(child, organization_id, session, cache) for child in children)
    
    elif expr_type == "NOT":
        # Negate the single child
        children = expression.get("children", [])
        if children:
            result = not evaluate_logic_expression(children[0], organization_id, session, cache)
        else:
            result = False
    
    elif expr_type == "PROXY":
        # Check if this proxy matches for the organization
        proxy_id = expression.get("id")
        cache_key = f"proxy_{proxy_id}"
        
        if cache_key in cache:
            result = cache[cache_key]
        else:
            # Get the proxy's variable
            proxy = session.query(VennProxy).filter(VennProxy.id == proxy_id).first()
            if proxy:
                # Check if there's a VennResult for this variable
                venn_result = session.query(VennResult).filter(
                    VennResult.organization_id == organization_id,
                    VennResult.venn_variable_id == proxy.venn_variable_id
                ).first()
                
                # A proxy is "matched" if the variable result is True AND the proxy was detected
                # For simplicity, we check if the variable result is True
                # In a more sophisticated system, we'd track individual proxy matches
                result = venn_result.value if venn_result else False
                
                # TODO: Implement per-proxy matching by checking VennMatchEvidence
                # evidence = session.query(VennMatchEvidence).filter(
                #     VennMatchEvidence.venn_result_id == venn_result.id,
                #     VennMatchEvidence.venn_proxy_id == proxy_id
                # ).first()
                # result = evidence is not None
            else:
                result = False
            
            cache[cache_key] = result
    
    elif expr_type == "VARIABLE":
        # Check if this variable is True for the organization
        var_id = expression.get("id")
        cache_key = f"variable_{var_id}"
        
        if cache_key in cache:
            result = cache[cache_key]
        else:
            venn_result = session.query(VennResult).filter(
                VennResult.organization_id == organization_id,
                VennResult.venn_variable_id == var_id
            ).first()
            result = venn_result.value if venn_result else False
            cache[cache_key] = result
    
    else:
        # Unknown type, return False
        result = False
    
    # Apply negation if specified
    if negate:
        result = not result
    
    return result


def build_expression_display(expression: Dict[str, Any], session) -> str:
    """
    Build a human-readable string representation of a logic expression.
    
    Example output: "(Justicia OR Verdad) AND Seguridad"
    """
    if not expression:
        return ""
    
    # Handle case where expression might be a string (JSON)
    if isinstance(expression, str):
        try:
            expression = json.loads(expression)
        except json.JSONDecodeError:
            return str(expression)[:50]
    
    if not isinstance(expression, dict):
        return str(expression)[:50]
    
    expr_type = expression.get("type", "").upper()
    negate = expression.get("negate", False)
    
    result = ""
    
    if expr_type in ("AND", "OR"):
        children = expression.get("children", [])
        child_strings = [build_expression_display(child, session) for child in children]
        child_strings = [s for s in child_strings if s]  # Remove empty strings
        
        if len(child_strings) == 0:
            result = ""
        elif len(child_strings) == 1:
            result = child_strings[0]
        else:
            separator = f" {expr_type} "
            # Add parentheses for nested expressions
            result = separator.join(child_strings)
            if len(children) > 1:
                result = f"({result})"
    
    elif expr_type == "NOT":
        children = expression.get("children", [])
        if children:
            child_str = build_expression_display(children[0], session)
            result = f"NOT {child_str}"
    
    elif expr_type == "PROXY":
        proxy_id = expression.get("id")
        proxy = session.query(VennProxy).filter(VennProxy.id == proxy_id).first()
        if proxy:
            # Show abbreviated term
            term = proxy.term[:40] + "..." if len(proxy.term) > 40 else proxy.term
            result = f'"{term}"'
        else:
            result = f"proxy_{proxy_id}"
    
    elif expr_type == "VARIABLE":
        var_id = expression.get("id")
        var = session.query(VennVariable).filter(VennVariable.id == var_id).first()
        if var:
            result = var.name
        else:
            result = f"var_{var_id}"
    
    if negate and result:
        result = f"NOT({result})"
    
    return result


def parse_expression_from_text(
    text: str,
    session
) -> Dict[str, Any]:
    """
    Parse a natural language expression into a logic expression tree.
    
    Supported patterns:
    - "A AND B" -> {"type": "AND", "children": [A, B]}
    - "A OR B" -> {"type": "OR", "children": [A, B]}
    - "(A OR B) AND C" -> {"type": "AND", "children": [{"type": "OR", "children": [A, B]}, C]}
    - "NOT A" -> {"type": "proxy/variable", "id": X, "negate": true}
    
    This is a simplified parser. For complex expressions, the agent should
    construct the JSON directly.
    """
    # This is a placeholder for more sophisticated parsing
    # For now, we rely on the agent to construct the expression directly
    return None


# ============ VENN INTERSECTION FUNCTIONS ============

def create_venn_intersection(
    name: str, 
    operation: str = "intersection",
    include_variables: List[str] = None,
    exclude_variables: List[str] = None,
    include_proxies: List[str] = None,
    exclude_proxies: List[str] = None,
    description: str = None,
    display_label: str = None,
    color: str = None,
    logic_expression: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Create a Venn intersection (logical combination of variables OR proxies).
    
    NEW SYSTEM: Use logic_expression for complex boolean expressions with nested AND/OR.
    
    Logic Expression Format:
    {
        "type": "AND|OR",
        "children": [
            {"type": "proxy", "id": 6},
            {"type": "variable", "id": 2},
            {
                "type": "OR",
                "children": [{"type": "proxy", "id": 7}, {"type": "proxy", "id": 13}]
            }
        ]
    }
    
    LEGACY MODES (still supported):
    1. Variable-based: Combine full Venn variables (e.g., "Justicia", "Verdad")
    2. Proxy-based: Combine specific proxy terms from any variable
    
    Examples with logic_expression:
    - (A OR B) AND C:
      {"type": "AND", "children": [
          {"type": "OR", "children": [{"type": "proxy", "id": 1}, {"type": "proxy", "id": 2}]},
          {"type": "proxy", "id": 3}
      ]}
    """
    session = get_sync_db_session()
    try:
        # Check if name already exists
        existing = session.query(VennIntersection).filter(
            VennIntersection.name.ilike(name)
        ).first()
        if existing:
            return {"success": False, "error": f"Ya existe una intersección con el nombre '{name}'"}
        
        # NEW SYSTEM: If logic_expression is provided, use it directly
        if logic_expression:
            # Build the expression display string
            expr_display = build_expression_display(logic_expression, session)
            
            intersection = VennIntersection(
                name=name,
                description=description,
                display_label=display_label or name[:20],
                color=color,
                logic_expression=logic_expression,
                use_logic_expression=True,
                expression_display=expr_display,
                operation=VennOperationType.INTERSECTION,  # Default, actual logic is in expression
            )
            
            session.add(intersection)
            session.commit()
            session.refresh(intersection)
            
            return {
                "success": True,
                "created": name,
                "id": intersection.id,
                "mode": "logic_expression",
                "expression_display": expr_display,
                "logic_expression": logic_expression
            }
        
        # LEGACY SYSTEM: variable/proxy-based with single operation
        # Determine mode: proxy-based or variable-based
        use_proxies = bool(include_proxies or exclude_proxies)
        
        # Resolve variable names to IDs (if variable-based)
        include_var_ids = []
        exclude_var_ids = []
        
        # Resolve proxy terms to IDs (if proxy-based)
        include_proxy_ids = []
        exclude_proxy_ids = []
        matched_proxy_info = []
        
        # Build logic expression from legacy format
        children = []
        
        if use_proxies:
            # Proxy-based mode: search for proxy terms
            if include_proxies:
                for proxy_term in include_proxies:
                    # Search for proxy by term (partial match)
                    proxy = session.query(VennProxy).filter(
                        VennProxy.term.ilike(f"%{proxy_term[:50]}%")
                    ).first()
                    if proxy:
                        include_proxy_ids.append(proxy.id)
                        children.append({"type": "proxy", "id": proxy.id})
                        # Get variable name for this proxy
                        var = session.query(VennVariable).filter(VennVariable.id == proxy.venn_variable_id).first()
                        matched_proxy_info.append({
                            "proxy_id": proxy.id,
                            "term": proxy.term[:80],
                            "variable": var.name if var else "?"
                        })
                    else:
                        # Try exact match
                        proxy = session.query(VennProxy).filter(
                            VennProxy.term == proxy_term
                        ).first()
                        if proxy:
                            include_proxy_ids.append(proxy.id)
                            children.append({"type": "proxy", "id": proxy.id})
                            var = session.query(VennVariable).filter(VennVariable.id == proxy.venn_variable_id).first()
                            matched_proxy_info.append({
                                "proxy_id": proxy.id,
                                "term": proxy.term[:80],
                                "variable": var.name if var else "?"
                            })
                        else:
                            return {"success": False, "error": f"No se encontró el proxy con texto similar a: '{proxy_term[:60]}...'"}
            
            if exclude_proxies:
                for proxy_term in exclude_proxies:
                    proxy = session.query(VennProxy).filter(
                        VennProxy.term.ilike(f"%{proxy_term[:50]}%")
                    ).first()
                    if proxy:
                        exclude_proxy_ids.append(proxy.id)
                        children.append({"type": "proxy", "id": proxy.id, "negate": True})
                    else:
                        return {"success": False, "error": f"No se encontró el proxy con texto similar a: '{proxy_term[:60]}...'"}
        else:
            # Variable-based mode
            if include_variables:
                for var_name in include_variables:
                    var = session.query(VennVariable).filter(
                        VennVariable.name.ilike(f"%{var_name}%")
                    ).first()
                    if not var:
                        return {"success": False, "error": f"No se encontró la variable '{var_name}'"}
                    include_var_ids.append(var.id)
                    children.append({"type": "variable", "id": var.id})
            
            if exclude_variables:
                for var_name in exclude_variables:
                    var = session.query(VennVariable).filter(
                        VennVariable.name.ilike(f"%{var_name}%")
                    ).first()
                    if not var:
                        return {"success": False, "error": f"No se encontró la variable '{var_name}'"}
                    exclude_var_ids.append(var.id)
                    children.append({"type": "variable", "id": var.id, "negate": True})
        
        # Map operation string to enum and logic type
        op_map = {
            "intersection": VennOperationType.INTERSECTION,
            "interseccion": VennOperationType.INTERSECTION,
            "and": VennOperationType.INTERSECTION,
            "y": VennOperationType.INTERSECTION,
            "union": VennOperationType.UNION,
            "or": VennOperationType.UNION,
            "o": VennOperationType.UNION,
            "difference": VennOperationType.DIFFERENCE,
            "diferencia": VennOperationType.DIFFERENCE,
            "minus": VennOperationType.DIFFERENCE,
            "menos": VennOperationType.DIFFERENCE,
            "exclusive": VennOperationType.EXCLUSIVE,
            "xor": VennOperationType.EXCLUSIVE,
        }
        op_enum = op_map.get(operation.lower(), VennOperationType.INTERSECTION)
        
        # Build logic expression from children
        logic_type = "AND" if op_enum == VennOperationType.INTERSECTION else "OR"
        built_logic_expression = {"type": logic_type, "children": children} if children else None
        expr_display = build_expression_display(built_logic_expression, session) if built_logic_expression else None
        
        intersection = VennIntersection(
            name=name,
            description=description,
            display_label=display_label or name[:20],
            color=color,
            operation=op_enum,
            use_proxies=use_proxies,
            include_ids=include_var_ids if include_var_ids else None,
            exclude_ids=exclude_var_ids if exclude_var_ids else None,
            variable_ids=include_var_ids if include_var_ids else None,
            include_proxy_ids=include_proxy_ids if include_proxy_ids else None,
            exclude_proxy_ids=exclude_proxy_ids if exclude_proxy_ids else None,
            # NEW: Also store as logic expression
            logic_expression=built_logic_expression,
            use_logic_expression=True,
            expression_display=expr_display,
        )
        
        session.add(intersection)
        session.commit()
        session.refresh(intersection)
        
        result = {
            "success": True, 
            "created": name, 
            "id": intersection.id,
            "operation": op_enum.value,
            "mode": "proxy-based" if use_proxies else "variable-based",
            "expression_display": expr_display,
        }
        
        if use_proxies:
            result["matched_proxies"] = matched_proxy_info
            result["include_proxy_count"] = len(include_proxy_ids)
        else:
            result["include_variables"] = include_variables
            result["exclude_variables"] = exclude_variables
        
        return result
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def list_venn_intersections() -> Dict[str, Any]:
    """List all Venn intersections with their configurations."""
    session = get_sync_db_session()
    try:
        intersections = session.query(VennIntersection).filter(
            VennIntersection.is_active == True
        ).all()
        
        result = []
        for inter in intersections:
            # NEW SYSTEM: Check if using logic expressions
            if inter.use_logic_expression and inter.logic_expression:
                # Build expression display if not already set
                expr_display = inter.expression_display or build_expression_display(inter.logic_expression, session)
                
                result.append({
                    "id": inter.id,
                    "name": inter.name,
                    "description": inter.description,
                    "use_logic_expression": True,
                    "expression_display": expr_display,
                    "logic_expression": inter.logic_expression,
                    "display_label": inter.display_label,
                    "color": inter.color,
                })
            else:
                # LEGACY SYSTEM: Resolve variable/proxy IDs
                include_names = []
                exclude_names = []
                include_proxy_info = []
                exclude_proxy_info = []
                
                uses_proxies = inter.use_proxies
                
                if uses_proxies:
                    # Resolve proxy IDs to terms
                    if inter.include_proxy_ids:
                        for proxy_id in inter.include_proxy_ids:
                            proxy = session.query(VennProxy).filter(VennProxy.id == proxy_id).first()
                            if proxy:
                                var = session.query(VennVariable).filter(VennVariable.id == proxy.venn_variable_id).first()
                                include_proxy_info.append({
                                    "id": proxy.id,
                                    "term": proxy.term,
                                    "variable": var.name if var else "Desconocida"
                                })
                    
                    if inter.exclude_proxy_ids:
                        for proxy_id in inter.exclude_proxy_ids:
                            proxy = session.query(VennProxy).filter(VennProxy.id == proxy_id).first()
                            if proxy:
                                var = session.query(VennVariable).filter(VennVariable.id == proxy.venn_variable_id).first()
                                exclude_proxy_info.append({
                                    "id": proxy.id,
                                    "term": proxy.term,
                                    "variable": var.name if var else "Desconocida"
                                })
                else:
                    # Resolve variable IDs to names
                    if inter.include_ids:
                        for var_id in inter.include_ids:
                            var = session.query(VennVariable).filter(VennVariable.id == var_id).first()
                            if var:
                                include_names.append(var.name)
                    
                    if inter.exclude_ids:
                        for var_id in inter.exclude_ids:
                            var = session.query(VennVariable).filter(VennVariable.id == var_id).first()
                            if var:
                                exclude_names.append(var.name)
                
                result.append({
                    "id": inter.id,
                    "name": inter.name,
                    "description": inter.description,
                    "operation": inter.operation.value if inter.operation else "intersection",
                    "use_proxies": uses_proxies,
                    "use_logic_expression": False,
                    "include_variables": include_names,
                    "exclude_variables": exclude_names,
                    "include_proxies": include_proxy_info,
                    "exclude_proxies": exclude_proxy_info,
                    "display_label": inter.display_label,
                    "color": inter.color,
                })
        
        return {"success": True, "intersections": result, "total": len(result)}
    finally:
        session.close()


def delete_venn_intersection(name: str = None, intersection_id: int = None) -> Dict[str, Any]:
    """Delete a Venn intersection by name or ID."""
    session = get_sync_db_session()
    try:
        intersection = None
        if intersection_id:
            intersection = session.query(VennIntersection).filter(
                VennIntersection.id == intersection_id
            ).first()
        elif name:
            intersection = session.query(VennIntersection).filter(
                VennIntersection.name.ilike(f"%{name}%")
            ).first()
        
        if not intersection:
            return {"success": False, "error": "No se encontró la intersección especificada"}
        
        deleted_name = intersection.name
        session.delete(intersection)
        session.commit()
        return {"success": True, "deleted": deleted_name}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def update_venn_intersection(
    name: str = None,
    intersection_id: int = None,
    new_name: str = None,
    new_operation: str = None,
    include_variables: List[str] = None,
    exclude_variables: List[str] = None,
    include_proxies: List[str] = None,
    exclude_proxies: List[str] = None,
    description: str = None,
    logic_expression: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Update an existing Venn intersection.
    
    NEW SYSTEM: Use logic_expression to set complex boolean expressions.
    
    Can change:
    - name: rename the intersection
    - operation: change from AND to OR (updates the root operator of expression)
    - logic_expression: set a new complex expression tree
    - include_variables/exclude_variables: rebuild expression from variables
    - include_proxies/exclude_proxies: rebuild expression from proxies
    - description: update description text
    
    Examples:
    - Change operation from AND to OR
    - Set complex expression: logic_expression = {"type": "AND", "children": [...]}
    """
    session = get_sync_db_session()
    try:
        # Find the intersection
        intersection = None
        if intersection_id:
            intersection = session.query(VennIntersection).filter(
                VennIntersection.id == intersection_id
            ).first()
        elif name:
            intersection = session.query(VennIntersection).filter(
                VennIntersection.name.ilike(f"%{name}%")
            ).first()
        
        if not intersection:
            return {"success": False, "error": f"No se encontró la intersección '{name or intersection_id}'"}
        
        old_name = intersection.name
        changes = []
        
        # Update name if provided
        if new_name and new_name != intersection.name:
            intersection.name = new_name
            changes.append(f"Nombre: '{old_name}' → '{new_name}'")
        
        # Update description if provided
        if description is not None:
            intersection.description = description
            changes.append("Descripción actualizada")
        
        # NEW SYSTEM: If logic_expression is provided, use it directly
        if logic_expression:
            intersection.logic_expression = logic_expression
            intersection.use_logic_expression = True
            intersection.expression_display = build_expression_display(logic_expression, session)
            changes.append(f"Expresión lógica actualizada: {intersection.expression_display}")
        
        # If new_operation is provided, update the root operator of the expression
        elif new_operation:
            op_map = {
                "intersection": ("INTERSECTION", "AND"),
                "interseccion": ("INTERSECTION", "AND"),
                "and": ("INTERSECTION", "AND"),
                "y": ("INTERSECTION", "AND"),
                "union": ("UNION", "OR"),
                "or": ("UNION", "OR"),
                "o": ("UNION", "OR"),
            }
            op_info = op_map.get(new_operation.lower())
            
            if op_info:
                old_op = intersection.operation.value if intersection.operation else "intersection"
                new_op_value, logic_type = op_info
                
                # Update legacy operation field
                intersection.operation = VennOperationType[op_info[0]]
                
                # Update logic expression if it exists
                if intersection.logic_expression:
                    # Ensure logic_expression is a dict (parse if string)
                    logic_expr = intersection.logic_expression
                    if isinstance(logic_expr, str):
                        try:
                            logic_expr = json.loads(logic_expr)
                        except json.JSONDecodeError:
                            logic_expr = {"type": "AND", "children": []}
                    
                    # Change the root operator type
                    updated_expr = logic_expr.copy() if isinstance(logic_expr, dict) else {"type": "AND", "children": []}
                    updated_expr["type"] = logic_type
                    intersection.logic_expression = updated_expr
                    intersection.expression_display = build_expression_display(updated_expr, session)
                    changes.append(f"Operación: '{old_op}' → '{new_op_value}' (expresión: {intersection.expression_display})")
                else:
                    changes.append(f"Operación: '{old_op}' → '{new_op_value}'")
        
        # Rebuild expression from variables/proxies if provided
        use_proxies = bool(include_proxies or exclude_proxies)
        children = []
        
        if use_proxies:
            # Proxy-based update
            include_proxy_ids = []
            exclude_proxy_ids = []
            
            if include_proxies:
                for proxy_term in include_proxies:
                    proxy = session.query(VennProxy).filter(
                        VennProxy.term.ilike(f"%{proxy_term[:50]}%")
                    ).first()
                    if proxy:
                        include_proxy_ids.append(proxy.id)
                        children.append({"type": "proxy", "id": proxy.id})
                    else:
                        return {"success": False, "error": f"No se encontró el proxy: '{proxy_term[:60]}...'"}
            
            if exclude_proxies:
                for proxy_term in exclude_proxies:
                    proxy = session.query(VennProxy).filter(
                        VennProxy.term.ilike(f"%{proxy_term[:50]}%")
                    ).first()
                    if proxy:
                        exclude_proxy_ids.append(proxy.id)
                        children.append({"type": "proxy", "id": proxy.id, "negate": True})
                    else:
                        return {"success": False, "error": f"No se encontró el proxy: '{proxy_term[:60]}...'"}
            
            # Build new logic expression
            logic_type = "AND" if intersection.operation == VennOperationType.INTERSECTION else "OR"
            new_expr = {"type": logic_type, "children": children}
            
            intersection.use_proxies = True
            intersection.include_proxy_ids = include_proxy_ids if include_proxy_ids else None
            intersection.exclude_proxy_ids = exclude_proxy_ids if exclude_proxy_ids else None
            intersection.include_ids = None
            intersection.exclude_ids = None
            intersection.logic_expression = new_expr
            intersection.use_logic_expression = True
            intersection.expression_display = build_expression_display(new_expr, session)
            changes.append(f"Proxies actualizados: {len(include_proxy_ids)} incluidos")
        
        elif include_variables or exclude_variables:
            # Variable-based update
            include_var_ids = []
            exclude_var_ids = []
            
            if include_variables:
                for var_name in include_variables:
                    var = session.query(VennVariable).filter(
                        VennVariable.name.ilike(f"%{var_name}%")
                    ).first()
                    if not var:
                        return {"success": False, "error": f"No se encontró la variable '{var_name}'"}
                    include_var_ids.append(var.id)
                    children.append({"type": "variable", "id": var.id})
            
            if exclude_variables:
                for var_name in exclude_variables:
                    var = session.query(VennVariable).filter(
                        VennVariable.name.ilike(f"%{var_name}%")
                    ).first()
                    if not var:
                        return {"success": False, "error": f"No se encontró la variable '{var_name}'"}
                    exclude_var_ids.append(var.id)
                    children.append({"type": "variable", "id": var.id, "negate": True})
            
            # Build new logic expression
            logic_type = "AND" if intersection.operation == VennOperationType.INTERSECTION else "OR"
            new_expr = {"type": logic_type, "children": children}
            
            intersection.use_proxies = False
            intersection.include_ids = include_var_ids if include_var_ids else None
            intersection.exclude_ids = exclude_var_ids if exclude_var_ids else None
            intersection.include_proxy_ids = None
            intersection.exclude_proxy_ids = None
            intersection.logic_expression = new_expr
            intersection.use_logic_expression = True
            intersection.expression_display = build_expression_display(new_expr, session)
            changes.append(f"Variables actualizadas: {', '.join(include_variables or [])}")
        
        if not changes:
            return {"success": False, "error": "No se especificaron cambios para realizar"}
        
        session.commit()
        session.refresh(intersection)
        
        return {
            "success": True,
            "updated": intersection.name,
            "id": intersection.id,
            "changes": changes,
            "new_operation": intersection.operation.value if intersection.operation else "intersection",
            "expression_display": intersection.expression_display
        }
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def calculate_intersection_result(intersection_id: int, organization_id: int) -> Dict[str, Any]:
    """
    Calculate the result of a Venn intersection for a specific organization.
    
    NEW SYSTEM: Uses logic_expression for complex boolean evaluation.
    LEGACY SYSTEM: Uses operation type with include/exclude IDs.
    """
    session = get_sync_db_session()
    try:
        intersection = session.query(VennIntersection).filter(
            VennIntersection.id == intersection_id
        ).first()
        
        if not intersection:
            return {"success": False, "error": f"No se encontró la intersección {intersection_id}"}
        
        final_value = False
        component_values = {}
        
        # NEW SYSTEM: Use logic expression if available
        if intersection.use_logic_expression and intersection.logic_expression:
            cache = {}
            final_value = evaluate_logic_expression(
                intersection.logic_expression,
                organization_id,
                session,
                cache
            )
            # Store cached values as components
            component_values = cache
            
        else:
            # LEGACY SYSTEM: Use operation type with include/exclude IDs
            include_values = []
            exclude_values = []
            
            # Get include variable results
            if intersection.include_ids:
                for var_id in intersection.include_ids:
                    result = session.query(VennResult).filter(
                        VennResult.organization_id == organization_id,
                        VennResult.venn_variable_id == var_id
                    ).first()
                    
                    var = session.query(VennVariable).filter(VennVariable.id == var_id).first()
                    var_name = var.name if var else f"var_{var_id}"
                    
                    value = result.value if result else False
                    component_values[var_name] = value
                    include_values.append(value)
            
            # Get exclude variable results
            if intersection.exclude_ids:
                for var_id in intersection.exclude_ids:
                    result = session.query(VennResult).filter(
                        VennResult.organization_id == organization_id,
                        VennResult.venn_variable_id == var_id
                    ).first()
                    
                    var = session.query(VennVariable).filter(VennVariable.id == var_id).first()
                    var_name = var.name if var else f"var_{var_id}"
                    
                    value = result.value if result else False
                    component_values[f"NOT_{var_name}"] = not value
                    exclude_values.append(value)
            
            # Calculate based on operation
            op = intersection.operation
            
            if op == VennOperationType.INTERSECTION:
                final_value = all(include_values) if include_values else False
            elif op == VennOperationType.UNION:
                final_value = any(include_values) if include_values else False
            elif op == VennOperationType.DIFFERENCE:
                includes_ok = all(include_values) if include_values else True
                excludes_ok = not any(exclude_values) if exclude_values else True
                final_value = includes_ok and excludes_ok
            elif op == VennOperationType.EXCLUSIVE:
                final_value = sum(include_values) == 1 if include_values else False
        
        # Store or update the result
        existing = session.query(VennIntersectionResult).filter(
            VennIntersectionResult.organization_id == organization_id,
            VennIntersectionResult.intersection_id == intersection_id
        ).first()
        
        if existing:
            existing.value = final_value
            existing.component_values = component_values
            existing.is_stale = False
        else:
            new_result = VennIntersectionResult(
                organization_id=organization_id,
                intersection_id=intersection_id,
                value=final_value,
                component_values=component_values,
            )
            session.add(new_result)
        
        session.commit()
        
        return {
            "success": True,
            "intersection": intersection.name,
            "organization_id": organization_id,
            "value": final_value,
            "components": component_values,
            "use_logic_expression": intersection.use_logic_expression,
            "expression_display": intersection.expression_display,
        }
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def calculate_all_intersections_for_org(organization_id: int) -> Dict[str, Any]:
    """Calculate all Venn intersection results for an organization."""
    session = get_sync_db_session()
    try:
        intersections = session.query(VennIntersection).filter(
            VennIntersection.is_active == True
        ).all()
        
        results = []
        for inter in intersections:
            result = calculate_intersection_result(inter.id, organization_id)
            if result["success"]:
                results.append({
                    "intersection": inter.name,
                    "value": result["value"],
                    "components": result.get("components", {}),
                })
        
        return {"success": True, "organization_id": organization_id, "results": results}
    finally:
        session.close()


def calculate_intersection_for_all_orgs(intersection_id: int) -> Dict[str, Any]:
    """Calculate a Venn intersection result for all organizations."""
    session = get_sync_db_session()
    try:
        orgs = session.query(Organization).all()
        
        results = []
        for org in orgs:
            result = calculate_intersection_result(intersection_id, org.id)
            if result["success"]:
                results.append({
                    "organization": org.name,
                    "organization_id": org.id,
                    "value": result["value"],
                })
        
        # Count statistics
        true_count = sum(1 for r in results if r["value"])
        false_count = len(results) - true_count
        
        return {
            "success": True,
            "intersection_id": intersection_id,
            "total_organizations": len(results),
            "true_count": true_count,
            "false_count": false_count,
            "results": results,
        }
    finally:
        session.close()


def get_venn_diagram_data() -> Dict[str, Any]:
    """
    Get complete data for rendering a Venn diagram.
    Returns variables, intersections, and counts for each region.
    """
    session = get_sync_db_session()
    try:
        # Get all variables
        variables = session.query(VennVariable).all()
        var_data = []
        for var in variables:
            # Count organizations with this variable = 1
            count = session.query(VennResult).filter(
                VennResult.venn_variable_id == var.id,
                VennResult.value == True
            ).count()
            var_data.append({
                "id": var.id,
                "name": var.name,
                "description": var.description,
                "count": count,
            })
        
        # Get all intersections
        intersections = session.query(VennIntersection).filter(
            VennIntersection.is_active == True
        ).all()
        inter_data = []
        for inter in intersections:
            # Count organizations with this intersection = 1
            count = session.query(VennIntersectionResult).filter(
                VennIntersectionResult.intersection_id == inter.id,
                VennIntersectionResult.value == True
            ).count()
            inter_data.append({
                "id": inter.id,
                "name": inter.name,
                "operation": inter.operation.value if inter.operation else "intersection",
                "display_label": inter.display_label,
                "color": inter.color,
                "count": count,
            })
        
        return {
            "success": True,
            "variables": var_data,
            "intersections": inter_data,
            "total_variables": len(var_data),
            "total_intersections": len(inter_data),
        }
    finally:
        session.close()


# ============ ORGANIZATION LINK FUNCTIONS ============

def add_link_to_organization(org_name: str, url: str, link_type: str = "scraping", description: str = None) -> Dict[str, Any]:
    """Add a scraping URL/link to an organization."""
    session = get_sync_db_session()
    try:
        org = session.query(Organization).filter(
            Organization.name.ilike(f"%{org_name}%")
        ).first()
        
        if not org:
            return {"success": False, "error": f"No se encontró la organización '{org_name}'"}
        
        # Check if URL already exists for this org
        existing = session.query(OrganizationLink).filter(
            OrganizationLink.organization_id == org.id,
            OrganizationLink.url == url
        ).first()
        
        if existing:
            return {"success": False, "error": f"La URL '{url}' ya existe para la organización '{org.name}'"}
        
        link = OrganizationLink(
            organization_id=org.id,
            url=url,
            link_type=link_type,
            description=description,
        )
        
        session.add(link)
        session.commit()
        return {"success": True, "added_url": url, "organization": org.name, "link_id": link.id}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def get_organization_links(org_name: str) -> Dict[str, Any]:
    """Get all links/URLs for an organization."""
    session = get_sync_db_session()
    try:
        org = session.query(Organization).filter(
            Organization.name.ilike(f"%{org_name}%")
        ).first()
        
        if not org:
            return {"success": False, "error": f"No se encontró la organización '{org_name}'", "links": []}
        
        links = session.query(OrganizationLink).filter(
            OrganizationLink.organization_id == org.id
        ).all()
        
        links_data = []
        for link in links:
            links_data.append({
                "id": link.id,
                "url": link.url,
                "link_type": link.link_type,
                "description": link.description,
                "scrape_status": link.scrape_status,
                "last_scraped_at": str(link.last_scraped_at) if link.last_scraped_at else None,
            })
        
        return {
            "success": True,
            "organization": org.name,
            "organization_id": org.id,
            "links": links_data,
            "total": len(links_data)
        }
    finally:
        session.close()


def delete_organization_link(org_name: str, url: str = None, link_id: int = None) -> Dict[str, Any]:
    """Delete a link from an organization by URL or ID."""
    session = get_sync_db_session()
    try:
        org = session.query(Organization).filter(
            Organization.name.ilike(f"%{org_name}%")
        ).first()
        
        if not org:
            return {"success": False, "error": f"No se encontró la organización '{org_name}'"}
        
        link = None
        if link_id:
            link = session.query(OrganizationLink).filter(
                OrganizationLink.id == link_id,
                OrganizationLink.organization_id == org.id
            ).first()
        elif url:
            link = session.query(OrganizationLink).filter(
                OrganizationLink.organization_id == org.id,
                OrganizationLink.url.ilike(f"%{url}%")
            ).first()
        
        if not link:
            return {"success": False, "error": f"No se encontró el enlace especificado para '{org.name}'"}
        
        deleted_url = link.url
        session.delete(link)
        session.commit()
        return {"success": True, "deleted_url": deleted_url, "organization": org.name}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


# ============ INFORMATION SOURCE (GLOBAL) FUNCTIONS ============

def add_info_source(name: str, url: str, source_type: str = None, description: str = None, priority: int = 5) -> Dict[str, Any]:
    """Add a global information source for the scraper."""
    from datetime import datetime
    session = get_sync_db_session()
    try:
        # Check if URL already exists
        existing = session.query(InformationSource).filter(
            InformationSource.url == url
        ).first()
        
        if existing:
            return {"success": False, "error": f"La fuente con URL '{url}' ya existe: {existing.name}"}
        
        source = InformationSource(
            name=name,
            url=url,
            source_type=source_type,
            description=description,
            priority=priority,
            reliability_score=0.5,
            verified=True,  # User-added sources are verified
            verified_at=datetime.utcnow(),
            is_active=True,
        )
        
        session.add(source)
        session.commit()
        return {"success": True, "created": name, "url": url, "id": source.id}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def get_all_info_sources(active_only: bool = True) -> Dict[str, Any]:
    """Get all global information sources."""
    session = get_sync_db_session()
    try:
        query = session.query(InformationSource)
        if active_only:
            query = query.filter(InformationSource.is_active == True)
        
        sources = query.order_by(InformationSource.priority.desc()).all()
        
        sources_data = []
        for s in sources:
            sources_data.append({
                "id": s.id,
                "name": s.name,
                "url": s.url,
                "source_type": s.source_type,
                "description": s.description,
                "priority": s.priority,
                "verified": s.verified,
                "is_active": s.is_active,
                "last_scraped": str(s.last_successful_scrape) if s.last_successful_scrape else None,
            })
        
        return {
            "success": True,
            "sources": sources_data,
            "total": len(sources_data),
            "active_count": sum(1 for s in sources_data if s["is_active"]),
            "verified_count": sum(1 for s in sources_data if s["verified"]),
        }
    finally:
        session.close()


def delete_info_source(url: str = None, source_id: int = None, name: str = None) -> Dict[str, Any]:
    """Delete a global information source."""
    session = get_sync_db_session()
    try:
        source = None
        if source_id:
            source = session.query(InformationSource).filter(
                InformationSource.id == source_id
            ).first()
        elif url:
            source = session.query(InformationSource).filter(
                InformationSource.url.ilike(f"%{url}%")
            ).first()
        elif name:
            source = session.query(InformationSource).filter(
                InformationSource.name.ilike(f"%{name}%")
            ).first()
        
        if not source:
            return {"success": False, "error": "No se encontró la fuente de información especificada"}
        
        deleted_name = source.name
        deleted_url = source.url
        session.delete(source)
        session.commit()
        return {"success": True, "deleted_name": deleted_name, "deleted_url": deleted_url}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def get_venn_data() -> Dict[str, Any]:
    """Get all Venn variables, proxies and results."""
    session = get_sync_db_session()
    try:
        variables = session.query(VennVariable).all()
        
        result = {
            "variables": [],
            "total_variables": len(variables),
        }
        
        for var in variables:
            proxies = session.query(VennProxy).filter(
                VennProxy.venn_variable_id == var.id
            ).all()
            
            var_data = {
                "id": var.id,
                "name": var.name,
                "description": var.description,
                "proxies": [{"id": p.id, "term": p.term, "weight": p.weight} for p in proxies],
            }
            result["variables"].append(var_data)
        
        return result
    finally:
        session.close()


def execute_batch_operations(operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Execute multiple database operations."""
    results = {
        "successful": [],
        "failed": [],
        "total": len(operations),
    }
    
    for op in operations:
        action = op.get("action", "")
        result = None
        
        try:
            if action == "create_organization":
                result = create_organization(op.get("data", {}))
                if result["success"]:
                    results["successful"].append(f"✅ Creada: {result['created']}")
                else:
                    results["failed"].append(f"❌ Error creando organización: {result['error']}")
                    
            elif action == "update_organization":
                result = update_organization_by_name(op.get("organization_name", ""), op.get("update_data", {}))
                if result["success"]:
                    results["successful"].append(f"✅ Actualizada: {result['updated']}")
                else:
                    results["failed"].append(f"❌ Error actualizando: {result['error']}")
                    
            elif action == "delete_organization":
                result = delete_organization_by_name(op.get("organization_name", ""))
                if result["success"]:
                    results["successful"].append(f"🗑️ Eliminada: {result['deleted']}")
                else:
                    results["failed"].append(f"❌ Error eliminando: {result['error']}")
                    
            elif action == "create_venn_variable":
                result = create_venn_variable(op.get("data", {}))
                if result["success"]:
                    results["successful"].append(f"✅ Variable creada: {result['created']}")
                else:
                    results["failed"].append(f"❌ Error creando variable: {result['error']}")
                    
            elif action == "update_venn_variable":
                result = update_venn_variable(op.get("variable_name", ""), op.get("update_data", {}))
                if result["success"]:
                    results["successful"].append(f"✅ Variable actualizada: {result['updated']}")
                else:
                    results["failed"].append(f"❌ Error actualizando variable: {result['error']}")
                    
            elif action == "delete_venn_variable":
                result = delete_venn_variable(op.get("variable_name", ""))
                if result["success"]:
                    results["successful"].append(f"🗑️ Variable eliminada: {result['deleted']}")
                else:
                    results["failed"].append(f"❌ Error eliminando variable: {result['error']}")
                    
            elif action == "add_venn_proxy":
                result = add_venn_proxy(op.get("variable_name", ""), op.get("proxy_data", {}))
                if result["success"]:
                    results["successful"].append(f"✅ Proxy añadido: {result['created']} a {result['variable']}")
                else:
                    results["failed"].append(f"❌ Error añadiendo proxy: {result['error']}")
                    
            elif action == "delete_venn_proxy":
                result = delete_venn_proxy(op.get("variable_name", ""), op.get("proxy_name", ""))
                if result["success"]:
                    results["successful"].append(f"🗑️ Proxy eliminado: {result['deleted']} de {result['variable']}")
                else:
                    results["failed"].append(f"❌ Error eliminando proxy: {result['error']}")
            
            elif action == "add_link_to_organization":
                result = add_link_to_organization(
                    op.get("organization_name", ""),
                    op.get("url", ""),
                    op.get("link_type", "scraping"),
                    op.get("description")
                )
                if result["success"]:
                    results["successful"].append(f"🔗 Enlace añadido: {result['added_url']} a {result['organization']}")
                else:
                    results["failed"].append(f"❌ Error añadiendo enlace: {result['error']}")
            
            elif action == "delete_organization_link":
                result = delete_organization_link(
                    op.get("organization_name", ""),
                    op.get("url"),
                    op.get("link_id")
                )
                if result["success"]:
                    results["successful"].append(f"🗑️ Enlace eliminado: {result['deleted_url']} de {result['organization']}")
                else:
                    results["failed"].append(f"❌ Error eliminando enlace: {result['error']}")
            
            elif action == "add_info_source":
                source_url = op.get("url", "")
                source_name = op.get("name", "") or op.get("source_name", "") or source_url[:50]
                source_type = op.get("source_type", "")
                source_description = op.get("description", "")
                result = add_info_source(source_name, source_url, source_type, source_description)
                if result["success"]:
                    results["successful"].append(f"🌐 Fuente añadida: {result['created']}")
                else:
                    results["failed"].append(f"❌ Error añadiendo fuente: {result['error']}")
            
            elif action == "delete_info_source":
                result = delete_info_source(
                    op.get("url"),
                    op.get("source_id"),
                    op.get("name") or op.get("source_name")
                )
                if result["success"]:
                    results["successful"].append(f"🗑️ Fuente eliminada: {result['deleted_name']}")
                else:
                    results["failed"].append(f"❌ Error eliminando fuente: {result['error']}")
            
            else:
                results["failed"].append(f"❌ Acción desconocida: {action}")
                
        except Exception as e:
            results["failed"].append(f"❌ Error en {action}: {str(e)}")
    
    return results


@traceable(name="db_agent")
def db_agent_node(state: "AgentState") -> "AgentState":
    """
    Database agent node that handles DB queries and operations.
    """
    user_input = state.get("user_input", "")
    
    # Get context from previous operations
    previous_db_response = state.get("db_response", "")
    task_description = state.get("task_description", "")
    conversation_history = state.get("conversation_history", [])
    
    # Build context about which organization is being discussed
    context = ""
    
    # Add conversation history for context (last 6 exchanges)
    if conversation_history:
        context += "\nHISTORIAL DE CONVERSACIÓN (para contexto):\n"
        for msg in conversation_history[-6:]:
            # Ensure msg is a dictionary before accessing properties
            if isinstance(msg, dict):
                role = "Usuario" if msg.get("role") == "user" else "Asistente"
                content = msg.get("content", "")[:300]  # Truncate long messages
                context += f"  {role}: {content}\n"
            elif isinstance(msg, str):
                # Handle case where msg is a string instead of dict
                context += f"  Mensaje: {msg[:300]}\n"
        context += "\n"
    
    if previous_db_response:
        context += f"\nÚLTIMA OPERACIÓN DE BD:\n{previous_db_response}\n"
    if task_description:
        context += f"\nTAREA ACTUAL: {task_description}\n"
    
    # Use LLM to determine the action
    try:
        messages = [
            SystemMessage(content=DB_AGENT_SYSTEM_PROMPT.format(user_input=user_input)),
            HumanMessage(content=f"CONTEXTO PREVIO:{context}\n\nCONSULTA ACTUAL: {user_input}\n\nAnaliza esta consulta y determina la acción a realizar.")
        ]
        
        llm_json = llm.bind(response_format={"type": "json_object"})
        response = llm_json.invoke(messages)
        decision = json.loads(response.content)
        
        action = decision.get("action", "no_db_action")
        search_term = decision.get("search_term", "")
        org_name = decision.get("organization_name", "")
        update_data = decision.get("update_data", {})
        
        db_response = None
        
        if action == "query_organizations":
            result = search_organizations(search_term or org_name)
            if result["exact"] and result["results"]:
                results = result["results"]
                db_response = f"✅ Encontré {len(results)} organización(es) con '{search_term or org_name}':\n\n"
                for org in results:
                    db_response += f"**{org['name']}**\n"
                    db_response += f"  - Alcance: {org['territorial_scope'] or 'No especificado'}\n"
                    db_response += f"  - Líder: {org['leader_name'] or 'No especificado'}\n"
                    db_response += f"  - Enfoque: {org['approach'] or 'No especificado'}\n\n"
            elif result["suggestions"]:
                # No exact match but found similar
                db_response = f"🔍 No encontré exactamente '{search_term or org_name}', pero encontré organizaciones similares:\n\n"
                for i, org in enumerate(result["suggestions"], 1):
                    similarity_pct = int(org['similarity'] * 100)
                    db_response += f"{i}. **{org['name']}** ({similarity_pct}% similar)\n"
                    db_response += f"   - Alcance: {org['territorial_scope'] or 'No especificado'}\n\n"
                db_response += "\n💡 ¿Te refieres a alguna de estas organizaciones?"
            else:
                db_response = f"❌ No encontré organizaciones con '{search_term or org_name}' en la base de datos."
        
        elif action == "list_all_organizations":
            results = get_all_organizations()
            if results:
                db_response = f"📋 **{len(results)} organizaciones registradas:**\n\n"
                for i, org in enumerate(results, 1):
                    db_response += f"{i}. **{org['name']}** - {org['territorial_scope'] or 'Sin alcance'}\n"
            else:
                db_response = "📭 No hay organizaciones registradas en el sistema."
        
        elif action == "list_organizations_without_location":
            results = get_organizations_without_location()
            if results:
                db_response = f"📍 **{len(results)} organizaciones SIN localización:**\n\n"
                for i, org in enumerate(results, 1):
                    db_response += f"{i}. **{org['name']}** - Depto: {org['department_code'] or 'No especificado'}\n"
                db_response += "\n💡 *Puedes decirme qué localización asignar a cada una.*"
            else:
                db_response = "✅ Todas las organizaciones tienen localización asignada."
        
        elif action == "list_organizations_with_links":
            results = get_organizations_with_links()
            if results:
                db_response = f"🔗 **{len(results)} organizaciones CON URLs de scraping:**\n\n"
                for i, org in enumerate(results, 1):
                    db_response += f"{i}. **{org['name']}** - {org['link_count']} enlace(s)\n"
            else:
                db_response = "📭 Ninguna organización tiene URLs de scraping configuradas."
        
        elif action == "list_organizations_without_links":
            results = get_organizations_without_links()
            if results:
                db_response = f"📭 **{len(results)} organizaciones SIN URLs de scraping:**\n\n"
                for i, org in enumerate(results, 1):
                    db_response += f"{i}. **{org['name']}** - {org['territorial_scope'] or 'Sin alcance'}\n"
                db_response += "\n💡 *Puedes añadir URLs con: 'Añade la URL https://... a [nombre_org]'*"
            else:
                db_response = "✅ Todas las organizaciones tienen URLs de scraping configuradas."
        
        elif action == "get_organization":
            result = get_organization_by_name(org_name or search_term)
            if result["found"] and result["organization"]:
                org = result["organization"]
                db_response = f"📍 **{org['name']}**\n\n"
                db_response += f"- **Descripción:** {org['description'] or 'Sin descripción'}\n"
                db_response += f"- **Alcance territorial:** {org['territorial_scope'] or 'No especificado'}\n"
                db_response += f"- **Departamento:** {org['department_code'] or 'No especificado'}\n"
                db_response += f"- **Líder:** {org['leader_name'] or 'No especificado'}\n"
                db_response += f"- **Líder es mujer:** {'Sí' if org['leader_is_woman'] else 'No' if org['leader_is_woman'] is False else 'No especificado'}\n"
                db_response += f"- **Enfoque:** {org['approach'] or 'No especificado'}\n"
                db_response += f"- **Construcción de paz:** {'Sí' if org['is_peace_building'] else 'No'}\n"
            elif result["suggestions"]:
                # No exact match but found similar
                db_response = f"🔍 No encontré exactamente '{org_name or search_term}', pero encontré organizaciones similares:\n\n"
                for i, org in enumerate(result["suggestions"], 1):
                    similarity_pct = int(org['similarity'] * 100)
                    db_response += f"{i}. **{org['name']}** ({similarity_pct}% similar)\n"
                db_response += "\n💡 ¿Te refieres a alguna de estas? Por favor especifica el nombre exacto."
            else:
                db_response = f"❌ No encontré la organización '{org_name or search_term}'."
        
        elif action == "delete_organization":
            result = delete_organization_by_name(org_name)
            if result["success"]:
                db_response = f"🗑️ Organización **{result['deleted']}** eliminada correctamente."
            elif result.get("needs_confirmation") and result.get("suggestions"):
                db_response = f"🔍 No encontré exactamente '{org_name}', pero encontré organizaciones similares:\n\n"
                for i, org in enumerate(result["suggestions"], 1):
                    similarity_pct = int(org['similarity'] * 100)
                    db_response += f"{i}. **{org['name']}** ({similarity_pct}% similar)\n"
                db_response += "\n⚠️ ¿Cuál de estas deseas eliminar? Por favor confirma el nombre exacto."
            else:
                db_response = f"❌ Error al eliminar: {result['error']}"
        
        elif action == "update_organization":
            # Log for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"DB Agent update: org_name='{org_name}', update_data={update_data}")
            
            # If no org_name provided, try to extract from search_term or task_description
            if not org_name:
                org_name = search_term
            
            if not org_name:
                # Try to find from previous context
                prev_db = state.get("db_response", "")
                task_desc = state.get("task_description", "")
                if "Asmubuli" in task_desc or "Asmubuli" in str(prev_db):
                    org_name = "Asmubuli"
            
            if org_name and update_data:
                result = update_organization_by_name(org_name, update_data)
                if result["success"]:
                    # Show what was updated
                    updated_fields = ", ".join([f"{k}={v}" for k, v in update_data.items()])
                    db_response = f"✅ Organización **{result['updated']}** actualizada correctamente.\n\n**Campos actualizados:** {updated_fields}"
                elif result.get("needs_confirmation") and result.get("suggestions"):
                    db_response = f"🔍 No encontré exactamente '{org_name}', pero encontré organizaciones similares:\n\n"
                    for i, org in enumerate(result["suggestions"], 1):
                        similarity_pct = int(org['similarity'] * 100)
                        db_response += f"{i}. **{org['name']}** ({similarity_pct}% similar)\n"
                    db_response += "\n💡 ¿Cuál de estas deseas actualizar? Por favor especifica el nombre exacto."
                else:
                    db_response = f"❌ Error al actualizar: {result['error']}"
            else:
                db_response = f"❌ No se pudo actualizar. Especifica el nombre de la organización. org_name='{org_name}', update_data={update_data}"
        
        elif action == "trigger_scrape":
            result = get_organization_by_name(org_name or search_term)
            if result["found"] and result["organization"]:
                org = result["organization"]
                # Set state to trigger scraping
                return {
                    **state,
                    "current_agent": "scraper",
                    "task_description": f"Buscar información actualizada sobre {org['name']}",
                    "scraped_data": [],
                    "db_response": f"🔍 Iniciando búsqueda de información para **{org['name']}**...",
                }
            elif result["suggestions"]:
                db_response = f"🔍 No encontré exactamente '{org_name or search_term}', pero encontré organizaciones similares:\n\n"
                for i, org in enumerate(result["suggestions"], 1):
                    similarity_pct = int(org['similarity'] * 100)
                    db_response += f"{i}. **{org['name']}** ({similarity_pct}% similar)\n"
                db_response += "\n💡 ¿Para cuál de estas quieres hacer scraping?"
            else:
                db_response = f"❌ No encontré la organización '{org_name}' para hacer scraping."
        
        elif action == "query_venn" or action == "list_venn_variables":
            # List all Venn variables (summary)
            result = list_all_venn_variables()
            if result["success"] and result["variables"]:
                db_response = f"📊 **{result['total']} variables Venn:**\n\n"
                for var in result["variables"]:
                    db_response += f"• **{var['name']}** ({var['proxy_count']} proxies)\n"
                    if var['description']:
                        db_response += f"  _{var['description']}_\n"
                db_response += "\n💡 Para ver los proxies de una variable: 'Muestra la variable X'"
            else:
                db_response = "📭 No hay variables Venn registradas."
        
        elif action == "get_venn_variable":
            # Get ONE specific Venn variable with all proxies
            var_name = decision.get("variable_name", "")
            if not var_name:
                db_response = "❌ Especifica el nombre de la variable Venn."
            else:
                result = get_venn_variable(var_name)
                if result.get("found"):
                    var = result["variable"]
                    db_response = f"📊 **Variable Venn: {var['name']}**\n\n"
                    db_response += f"📝 Descripción: {var['description'] or 'Sin descripción'}\n\n"
                    if var['proxies']:
                        db_response += f"**Proxies ({len(var['proxies'])}):**\n"
                        for i, p in enumerate(var['proxies'], 1):
                            term_preview = p['term'][:100] + "..." if len(p['term']) > 100 else p['term']
                            db_response += f"{i}. {term_preview}\n"
                    else:
                        db_response += "⚠️ Esta variable no tiene proxies definidos."
                elif result.get("suggestions"):
                    db_response = f"🔍 No encontré '{var_name}', pero encontré variables similares:\n\n"
                    for i, s in enumerate(result["suggestions"], 1):
                        db_response += f"{i}. **{s['name']}**\n"
                    db_response += "\n💡 ¿Te refieres a alguna de estas?"
                else:
                    db_response = f"❌ No encontré la variable '{var_name}'."
        
        elif action == "create_organization":
            data = decision.get("data", {})
            result = create_organization(data)
            if result["success"]:
                db_response = f"✅ Organización **{result['created']}** creada correctamente (ID: {result['id']})."
            else:
                db_response = f"❌ Error al crear organización: {result['error']}"
        
        elif action == "create_venn_variable":
            data = decision.get("data", {})
            result = create_venn_variable(data)
            if result["success"]:
                db_response = f"✅ Variable Venn **{result['created']}** creada correctamente."
            else:
                db_response = f"❌ Error al crear variable: {result['error']}"
        
        elif action == "delete_venn_variable":
            var_name = decision.get("variable_name", "")
            result = delete_venn_variable(var_name)
            if result["success"]:
                db_response = f"🗑️ Variable **{result['deleted']}** eliminada correctamente."
            elif result.get("needs_confirmation") and result.get("suggestions"):
                db_response = f"🔍 No encontré exactamente '{var_name}', pero encontré variables similares:\n\n"
                for i, var in enumerate(result["suggestions"], 1):
                    similarity_pct = int(var['similarity'] * 100)
                    db_response += f"{i}. **{var['name']}** ({similarity_pct}% similar)\n"
                db_response += "\n⚠️ ¿Cuál de estas deseas eliminar? Por favor confirma el nombre exacto."
            else:
                db_response = f"❌ Error al eliminar variable: {result['error']}"
        
        elif action == "add_venn_proxy":
            var_name = decision.get("variable_name", "")
            proxy_data = decision.get("proxy_data", {})
            result = add_venn_proxy(var_name, proxy_data)
            if result["success"]:
                db_response = f"✅ Proxy **{result['created']}** añadido a la variable **{result['variable']}**."
            elif result.get("needs_confirmation") and result.get("suggestions"):
                db_response = f"🔍 No encontré exactamente la variable '{var_name}', pero encontré variables similares:\n\n"
                for i, var in enumerate(result["suggestions"], 1):
                    similarity_pct = int(var['similarity'] * 100)
                    db_response += f"{i}. **{var['name']}** ({similarity_pct}% similar)\n"
                db_response += "\n💡 ¿A cuál de estas quieres añadir el proxy?"
            else:
                db_response = f"❌ Error al añadir proxy: {result['error']}"
        
        elif action == "update_venn_variable":
            var_name = decision.get("variable_name", "")
            update_data = decision.get("update_data", {})
            if not var_name:
                db_response = "❌ No se especificó el nombre de la variable a actualizar."
            elif not update_data:
                db_response = "❌ No se especificaron datos para actualizar."
            else:
                result = update_venn_variable(var_name, update_data)
                if result["success"]:
                    updated_fields = ", ".join([f"{k}={v}" for k, v in update_data.items()])
                    db_response = f"✅ Variable **{result['updated']}** actualizada correctamente.\n\n**Campos actualizados:** {updated_fields}"
                elif result.get("needs_confirmation") and result.get("suggestions"):
                    db_response = f"🔍 No encontré exactamente '{var_name}', pero encontré variables similares:\n\n"
                    for i, var in enumerate(result["suggestions"], 1):
                        similarity_pct = int(var['similarity'] * 100)
                        db_response += f"{i}. **{var['name']}** ({similarity_pct}% similar)\n"
                    db_response += "\n💡 ¿Cuál de estas deseas actualizar?"
                else:
                    db_response = f"❌ Error al actualizar variable: {result['error']}"
        
        elif action == "delete_venn_proxy":
            var_name = decision.get("variable_name", "")
            proxy_name = decision.get("proxy_name", "")
            if not var_name:
                db_response = "❌ No se especificó la variable."
            elif not proxy_name:
                db_response = "❌ No se especificó el proxy a eliminar."
            else:
                result = delete_venn_proxy(var_name, proxy_name)
                if result["success"]:
                    db_response = f"🗑️ Proxy **{result['deleted']}** eliminado de la variable **{result['variable']}**."
                elif result.get("needs_confirmation") and result.get("suggestions"):
                    db_response = f"🔍 No encontré exactamente '{proxy_name}', pero encontré proxies similares:\n\n"
                    for i, p in enumerate(result["suggestions"], 1):
                        similarity_pct = int(p['similarity'] * 100)
                        db_response += f"{i}. **{p['term']}** ({similarity_pct}% similar)\n"
                    db_response += "\n💡 ¿Cuál de estos deseas eliminar?"
                else:
                    db_response = f"❌ Error al eliminar proxy: {result['error']}"
        
        elif action == "list_venn_results":
            org_id = decision.get("organization_id")
            var_id = decision.get("variable_id")
            result = list_venn_results(org_id, var_id)
            if result["success"]:
                if result["results"]:
                    db_response = f"📊 **Resultados Venn** ({result['total']} registros):\n\n"
                    for r in result["results"][:20]:  # Limit display
                        score_pct = int(r['score'] * 100) if r['score'] else 0
                        db_response += f"- **{r['organization_name']}** - {r['variable_name']}: {score_pct}%\n"
                        if r['matched_proxies']:
                            db_response += f"  Proxies: {', '.join(r['matched_proxies'][:3])}\n"
                    if result['total'] > 20:
                        db_response += f"\n... y {result['total'] - 20} más"
                else:
                    db_response = "📭 No hay resultados Venn registrados."
            else:
                db_response = f"❌ Error: {result.get('error', 'Error desconocido')}"
        
        elif action == "delete_venn_result":
            result_id = decision.get("result_id")
            org_name = decision.get("organization_name")
            var_name = decision.get("variable_name")
            result = delete_venn_result(result_id, org_name, var_name)
            if result["success"]:
                db_response = f"🗑️ Se eliminaron **{result['deleted_count']}** resultado(s) Venn."
            else:
                db_response = f"❌ Error al eliminar: {result['error']}"
        
        elif action == "add_link_to_organization":
            link_org_name = decision.get("organization_name", org_name)
            link_url = decision.get("url", "")
            link_type = decision.get("link_type", "scraping")
            link_description = decision.get("description", None)
            
            if not link_url:
                db_response = "❌ No se especificó la URL a añadir."
            elif not link_org_name:
                db_response = "❌ No se especificó la organización."
            else:
                result = add_link_to_organization(link_org_name, link_url, link_type, link_description)
                if result["success"]:
                    db_response = f"🔗 URL **{result['added_url']}** añadida a la organización **{result['organization']}**."
                else:
                    db_response = f"❌ Error al añadir enlace: {result['error']}"
        
        elif action == "list_organization_links":
            link_org_name = decision.get("organization_name", org_name)
            if not link_org_name:
                db_response = "❌ No se especificó la organización."
            else:
                result = get_organization_links(link_org_name)
                if result["success"]:
                    if result["links"]:
                        db_response = f"🔗 **Enlaces de {result['organization']}** ({result['total']} enlaces):\n\n"
                        for i, link in enumerate(result["links"], 1):
                            db_response += f"{i}. **{link['url']}**\n"
                            db_response += f"   - Tipo: {link['link_type'] or 'scraping'}\n"
                            if link['description']:
                                db_response += f"   - Descripción: {link['description']}\n"
                            db_response += f"   - Estado: {link['scrape_status'] or 'pendiente'}\n\n"
                    else:
                        db_response = f"📭 La organización **{result['organization']}** no tiene enlaces registrados."
                else:
                    db_response = f"❌ Error: {result['error']}"
        
        elif action == "delete_organization_link":
            link_org_name = decision.get("organization_name", org_name)
            link_url = decision.get("url", "")
            link_id = decision.get("link_id")
            
            if not link_org_name:
                db_response = "❌ No se especificó la organización."
            else:
                result = delete_organization_link(link_org_name, link_url, link_id)
                if result["success"]:
                    db_response = f"🗑️ Enlace **{result['deleted_url']}** eliminado de **{result['organization']}**."
                else:
                    db_response = f"❌ Error al eliminar enlace: {result['error']}"
        
        elif action == "add_info_source":
            source_url = decision.get("url", "")
            source_name = decision.get("source_name", "") or decision.get("name", "") or source_url[:50]
            source_type = decision.get("source_type", "")
            source_description = decision.get("description", "")
            
            if not source_url:
                db_response = "❌ No se especificó la URL de la fuente."
            else:
                result = add_info_source(source_name, source_url, source_type, source_description)
                if result["success"]:
                    db_response = f"🌐 Fuente de información **{result['created']}** añadida correctamente.\n\n"
                    db_response += f"- **URL:** {result['url']}\n"
                    db_response += f"- **ID:** {result['id']}\n\n"
                    db_response += "Esta fuente se usará para el scraping de TODAS las organizaciones."
                else:
                    db_response = f"❌ Error al añadir fuente: {result['error']}"
        
        elif action == "list_info_sources":
            result = get_all_info_sources(active_only=False)
            if result["success"]:
                if result["sources"]:
                    db_response = f"🌐 **Fuentes de Información Globales** ({result['total']} fuentes):\n\n"
                    for i, source in enumerate(result["sources"], 1):
                        status = "✅" if source["is_active"] else "⏸️"
                        verified = "🔒" if source["verified"] else "❓"
                        db_response += f"{i}. {status} **{source['name']}** {verified}\n"
                        db_response += f"   - URL: {source['url']}\n"
                        if source["source_type"]:
                            db_response += f"   - Tipo: {source['source_type']}\n"
                        db_response += f"   - Prioridad: {source['priority']}/10\n\n"
                    db_response += f"\n📊 **Resumen:** {result['active_count']} activas, {result['verified_count']} verificadas"
                else:
                    db_response = "📭 No hay fuentes de información globales registradas.\n\n"
                    db_response += "💡 Puedes añadir una diciendo: 'Añade esta URL como fuente de búsqueda: https://...'"
            else:
                db_response = f"❌ Error: {result.get('error', 'Error desconocido')}"
        
        elif action == "delete_info_source":
            source_url = decision.get("url", "")
            source_name = decision.get("source_name", "")
            source_id = decision.get("source_id")
            
            result = delete_info_source(source_url, source_id, source_name)
            if result["success"]:
                db_response = f"🗑️ Fuente **{result['deleted_name']}** eliminada correctamente.\n\n"
                db_response += f"URL eliminada: {result['deleted_url']}"
            else:
                db_response = f"❌ Error al eliminar fuente: {result['error']}"
        
        # ============ VENN INTERSECTION HANDLERS ============
        elif action == "create_venn_intersection":
            inter_name = decision.get("intersection_name", "")
            inter_op = decision.get("intersection_operation", "intersection")
            include_vars = decision.get("include_variables", [])
            exclude_vars = decision.get("exclude_variables", [])
            include_proxies = decision.get("include_proxies", [])
            exclude_proxies = decision.get("exclude_proxies", [])
            inter_desc = decision.get("description", "")
            logic_expr = decision.get("logic_expression")  # Structured logic expression
            logic_expr_text = decision.get("logic_expression_text", "")  # Text-based expression
            
            # FALLBACK: If user input has parentheses with AND/OR and no logic_expression_text,
            # try to extract the expression from user_input
            if not logic_expr_text and not logic_expr and '(' in user_input and (') AND' in user_input.upper() or ') OR' in user_input.upper() or 'AND (' in user_input.upper() or 'OR (' in user_input.upper()):
                # Extract the part after "combinación" or similar keywords
                import re
                patterns = [
                    r'combinaci[oó]n[^:]*:\s*(.+)',
                    r'es la siguiente:\s*(.+)',
                    r'siguiente:\s*(.+)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, user_input, re.IGNORECASE | re.DOTALL)
                    if match:
                        logic_expr_text = match.group(1).strip()
                        break
            
            # NEW: Parse logic_expression_text if provided
            parsed_expr = None
            parsed_proxies = []
            db_response = ""  # Initialize
            if logic_expr_text:
                # Get a session to parse the expression
                from ..db.base import get_sync_db_session
                parse_session = get_sync_db_session()
                try:
                    parsed_expr = parse_logic_expression_text(logic_expr_text, parse_session)
                    parsed_proxies = parsed_expr.pop('matched_proxies', [])
                    
                    # Check for unknown proxies
                    def find_unknown(node):
                        unknowns = []
                        if node.get('type') == 'unknown':
                            unknowns.append(node.get('text', '?'))
                        for child in node.get('children', []):
                            unknowns.extend(find_unknown(child))
                        return unknowns
                    
                    unknown_proxies = find_unknown(parsed_expr)
                    if unknown_proxies:
                        db_response = f"❌ No se encontraron estos proxies: {', '.join(unknown_proxies[:3])}..."
                        # Skip creation
                        logic_expr = None
                    else:
                        logic_expr = parsed_expr
                finally:
                    parse_session.close()
            
            # Auto-generate name if not provided
            if not inter_name:
                if include_proxies:
                    inter_name = f"Intersección de {len(include_proxies)} proxies"
                elif include_vars:
                    inter_name = " ∩ ".join(include_vars[:3])
                elif logic_expr:
                    inter_name = f"Expresión lógica {datetime.now().strftime('%Y%m%d_%H%M')}"
                else:
                    inter_name = f"Intersección {datetime.now().strftime('%Y%m%d_%H%M')}"
            
            # Must have either variables, proxies, or logic expression
            if not include_vars and not include_proxies and not logic_expr:
                if not db_response:  # Don't overwrite error from above
                    db_response = "❌ Se requiere al menos una variable, proxy o expresión lógica."
            elif logic_expr or include_vars or include_proxies:
                result = create_venn_intersection(
                    name=inter_name,
                    operation=inter_op,
                    include_variables=include_vars if include_vars else None,
                    exclude_variables=exclude_vars if exclude_vars else None,
                    include_proxies=include_proxies if include_proxies else None,
                    exclude_proxies=exclude_proxies if exclude_proxies else None,
                    description=inter_desc,
                    logic_expression=logic_expr  # Pass parsed or provided logic expression
                )
                if result["success"]:
                    db_response = f"✅ Intersección **{result['created']}** creada correctamente.\n\n"
                    db_response += f"- **Modo:** {result['mode']}\n"
                    
                    if result['mode'] == 'logic_expression':
                        db_response += f"- **Expresión:** `{result.get('expression_display', '')}`\n"
                        # Show matched proxies from parsing
                        if parsed_proxies:
                            db_response += "- **Proxies utilizados:**\n"
                            for p in parsed_proxies:
                                db_response += f"  - {p['term'][:60]}... (Variable: {p['variable']})\n"
                    elif result['mode'] == 'proxy-based':
                        db_response += f"- **Operación:** {result.get('operation', 'intersection')}\n"
                        db_response += f"- **Proxies encontrados:** {result.get('include_proxy_count', 0)}\n"
                        if result.get('expression_display'):
                            db_response += f"- **Expresión:** `{result['expression_display']}`\n"
                        if result.get('matched_proxies'):
                            db_response += "- **Detalles de proxies:**\n"
                            for p in result['matched_proxies']:
                                db_response += f"  - {p['term'][:60]}... (Variable: {p['variable']})\n"
                    else:
                        db_response += f"- **Operación:** {result.get('operation', 'intersection')}\n"
                        db_response += f"- **Variables incluidas:** {', '.join(result.get('include_variables') or [])}\n"
                        if result.get('expression_display'):
                            db_response += f"- **Expresión:** `{result['expression_display']}`\n"
                        if result.get('exclude_variables'):
                            db_response += f"- **Variables excluidas:** {', '.join(result['exclude_variables'])}\n"
                else:
                    db_response = f"❌ Error al crear intersección: {result['error']}"
        
        elif action == "list_venn_intersections":
            result = list_venn_intersections()
            if result["success"]:
                if result["intersections"]:
                    db_response = f"🔷 **Intersecciones Venn** ({result['total']} configuradas):\n\n"
                    for inter in result["intersections"]:
                        db_response += f"**{inter['name']}** (ID: {inter['id']})\n"
                        
                        # NEW SYSTEM: Show logic expression
                        if inter.get('use_logic_expression'):
                            db_response += f"  - 🧮 Modo: Expresión lógica\n"
                            if inter.get('expression_display'):
                                db_response += f"  - 📐 Expresión: `{inter['expression_display']}`\n"
                        else:
                            # LEGACY SYSTEM
                            op_display = "AND (todos deben cumplirse)" if inter.get('operation') == "intersection" else "OR (al menos uno debe cumplirse)"
                            db_response += f"  - Operación: {op_display}\n"
                            
                            if inter.get('use_proxies'):
                                db_response += f"  - 📝 Modo: Basado en proxies\n"
                                if inter.get('include_proxies'):
                                    db_response += f"  - ✅ Proxies incluidos ({len(inter['include_proxies'])}):\n"
                                    for p in inter['include_proxies']:
                                        term_preview = p['term'][:80] + "..." if len(p['term']) > 80 else p['term']
                                        db_response += f"    • [{p['variable']}] {term_preview}\n"
                                if inter.get('exclude_proxies'):
                                    db_response += f"  - ❌ Proxies excluidos ({len(inter['exclude_proxies'])}):\n"
                                    for p in inter['exclude_proxies']:
                                        term_preview = p['term'][:80] + "..." if len(p['term']) > 80 else p['term']
                                        db_response += f"    • [{p['variable']}] {term_preview}\n"
                            else:
                                if inter.get('include_variables'):
                                    db_response += f"  - ✅ Variables incluidas: {', '.join(inter['include_variables'])}\n"
                                if inter.get('exclude_variables'):
                                    db_response += f"  - ❌ Variables excluidas: {', '.join(inter['exclude_variables'])}\n"
                        
                        if inter.get('description'):
                            db_response += f"  - 📋 {inter['description']}\n"
                        db_response += "\n"
                else:
                    db_response = "📭 No hay intersecciones Venn configuradas.\n\n"
                    db_response += "💡 Crea una con: 'Crea una intersección de Paz y Liderazgo'"
            else:
                db_response = f"❌ Error: {result.get('error', 'Error desconocido')}"
        
        elif action == "delete_venn_intersection":
            inter_name = decision.get("intersection_name", "")
            inter_id = decision.get("intersection_id")
            
            result = delete_venn_intersection(inter_name, inter_id)
            if result["success"]:
                db_response = f"🗑️ Intersección **{result['deleted']}** eliminada correctamente."
            else:
                db_response = f"❌ Error al eliminar: {result['error']}"
        
        elif action == "update_venn_intersection":
            inter_name = decision.get("intersection_name", "")
            inter_id = decision.get("intersection_id")
            new_operation = decision.get("new_operation")
            include_variables = decision.get("include_variables", [])
            exclude_variables = decision.get("exclude_variables", [])
            include_proxies = decision.get("include_proxies", [])
            exclude_proxies = decision.get("exclude_proxies", [])
            description = decision.get("description")
            
            result = update_venn_intersection(
                name=inter_name,
                intersection_id=inter_id,
                new_operation=new_operation,
                include_variables=include_variables if include_variables else None,
                exclude_variables=exclude_variables if exclude_variables else None,
                include_proxies=include_proxies if include_proxies else None,
                exclude_proxies=exclude_proxies if exclude_proxies else None,
                description=description
            )
            if result["success"]:
                updated_name = result["updated"]
                new_op = result.get("new_operation", "intersection")
                op_display = "AND (todos deben cumplirse)" if new_op == "intersection" else "OR (al menos uno debe cumplirse)"
                db_response = f"✅ Intersección **{updated_name}** actualizada correctamente.\n\n"
                db_response += f"📊 Operación: {op_display}\n"
                if result.get('changes'):
                    db_response += f"📝 Cambios realizados:\n"
                    for change in result['changes']:
                        db_response += f"  • {change}\n"
            else:
                db_response = f"❌ Error al actualizar: {result['error']}"
        
        elif action == "calculate_intersection":
            inter_name = decision.get("intersection_name", "")
            org_id = decision.get("organization_id")
            
            # First find the intersection
            session = get_sync_db_session()
            try:
                inter = session.query(VennIntersection).filter(
                    VennIntersection.name.ilike(f"%{inter_name}%")
                ).first()
                
                if not inter:
                    db_response = f"❌ No se encontró la intersección '{inter_name}'"
                elif org_id:
                    # Calculate for single org
                    result = calculate_intersection_result(inter.id, org_id)
                    if result["success"]:
                        value_str = "✅ SÍ" if result["value"] else "❌ NO"
                        db_response = f"📊 **Resultado de {result['intersection']}**\n\n"
                        db_response += f"Organización #{org_id}: {value_str}\n\n"
                        db_response += "**Componentes:**\n"
                        for var_name, val in result.get("components", {}).items():
                            val_str = "✓" if val else "✗"
                            db_response += f"  - {var_name}: {val_str}\n"
                    else:
                        db_response = f"❌ Error: {result['error']}"
                else:
                    # Calculate for all orgs
                    result = calculate_intersection_for_all_orgs(inter.id)
                    if result["success"]:
                        db_response = f"📊 **Resultados de intersección calculados**\n\n"
                        db_response += f"- **Total organizaciones:** {result['total_organizations']}\n"
                        db_response += f"- **Cumplen (TRUE):** {result['true_count']}\n"
                        db_response += f"- **No cumplen (FALSE):** {result['false_count']}\n"
                    else:
                        db_response = f"❌ Error: {result.get('error', 'Error desconocido')}"
            finally:
                session.close()
        
        elif action == "get_venn_diagram":
            result = get_venn_diagram_data()
            if result["success"]:
                db_response = "📊 **Datos del Diagrama Venn**\n\n"
                
                db_response += f"### Variables Base ({result['total_variables']}):\n"
                for var in result["variables"]:
                    db_response += f"- **{var['name']}**: {var['count']} organizaciones\n"
                
                if result["intersections"]:
                    db_response += f"\n### Intersecciones ({result['total_intersections']}):\n"
                    for inter in result["intersections"]:
                        db_response += f"- **{inter['name']}** ({inter['operation']}): {inter['count']} organizaciones\n"
                else:
                    db_response += "\n_No hay intersecciones configuradas._"
            else:
                db_response = f"❌ Error: {result.get('error', 'Error desconocido')}"
        
        elif action == "batch_operations":
            operations = decision.get("operations", [])
            if operations:
                results = execute_batch_operations(operations)
                db_response = f"## 📦 Operaciones en lote completadas\n\n"
                db_response += f"**Total:** {results['total']} operaciones\n\n"
                
                if results["successful"]:
                    db_response += "### ✅ Exitosas:\n"
                    for msg in results["successful"]:
                        db_response += f"- {msg}\n"
                    db_response += "\n"
                
                if results["failed"]:
                    db_response += "### ❌ Fallidas:\n"
                    for msg in results["failed"]:
                        db_response += f"- {msg}\n"
            else:
                db_response = "❌ No se especificaron operaciones a ejecutar."
        
        else:
            # no_db_action - pass to another agent
            return {
                **state,
                "db_response": None,
                "current_agent": "classifier",  # Default to classifier for create operations
            }
        
        # Return response directly to finalizer
        return {
            **state,
            "db_response": db_response,
            "final_response": db_response,
            "response_ready": True,
            "current_agent": "finalizer",
        }
        
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"DB_AGENT ERROR: {error_trace}")
        return {
            **state,
            "db_response": f"Error en consulta de BD: {str(e)}",
            "errors": state.get("errors", []) + [str(e)],
            "current_agent": "finalizer",
        }
