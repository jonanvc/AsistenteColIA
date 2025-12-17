"""
Database Operations for Venn Variables and Proxies.

CRUD operations for Venn variables and their proxies.
"""
from typing import List, Dict, Any

from ..db.base import get_sync_db_session
from ..models.db_models import VennVariable, VennProxy
from .db_common import find_similar_venn_variables, find_similar_venn_proxies, clear_embeddings_cache


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


def get_venn_variable(name: str) -> Dict[str, Any]:
    """Get a single Venn variable with all its proxies using semantic search."""
    session = get_sync_db_session()
    try:
        # Try partial match first
        var = session.query(VennVariable).filter(
            VennVariable.name.ilike(f"%{name}%")
        ).first()
        
        if not var:
            # Try semantic search
            similar = find_similar_venn_variables(name, use_embeddings=True)
            if similar:
                # Try to find the best match
                best_match = similar[0]
                if best_match['similarity'] > 0.6:
                    var = session.query(VennVariable).filter(
                        VennVariable.id == best_match['id']
                    ).first()
        
        if not var:
            session.close()
            similar = find_similar_venn_variables(name, use_embeddings=True)
            if similar:
                return {
                    "found": False,
                    "suggestions": similar,
                    "error": f"No se encontró '{name}' exactamente."
                }
            return {"found": False, "error": f"No se encontró la variable '{name}'"}
        
        # Get all proxies
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
        if session.is_active:
            session.close()


def create_venn_variable(data: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Venn variable."""
    session = get_sync_db_session()
    try:
        var_name = data.get('name', '').strip()
        if not var_name:
            return {"success": False, "error": "El nombre de la variable es requerido"}
        
        # Check exact name match
        existing = session.query(VennVariable).filter(
            VennVariable.name.ilike(var_name)
        ).first()
        
        if existing:
            return {"success": False, "error": f"Ya existe una variable con ese nombre: {existing.name}"}
        
        var = VennVariable(
            name=var_name,
            description=data.get("description"),
        )
        
        session.add(var)
        session.commit()
        clear_embeddings_cache()
        
        return {"success": True, "created": var.name, "id": var.id}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def update_venn_variable(name: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update a Venn variable by name with semantic fallback."""
    session = get_sync_db_session()
    try:
        var = session.query(VennVariable).filter(
            VennVariable.name.ilike(f"%{name}%")
        ).first()
        
        if not var:
            # Try semantic search
            similar = find_similar_venn_variables(name, use_embeddings=True)
            if similar and similar[0]['similarity'] > 0.6:
                var = session.query(VennVariable).filter(
                    VennVariable.id == similar[0]['id']
                ).first()
        
        if not var:
            session.close()
            similar = find_similar_venn_variables(name, use_embeddings=True)
            if similar:
                return {
                    "success": False,
                    "error": f"No se encontró '{name}' exactamente.",
                    "needs_confirmation": True,
                    "suggestions": similar
                }
            return {"success": False, "error": f"No se encontró la variable '{name}'"}
        
        for key, value in update_data.items():
            if hasattr(var, key) and value is not None:
                setattr(var, key, value)
        
        session.commit()
        clear_embeddings_cache()
        return {"success": True, "updated": var.name}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if session.is_active:
            session.close()


def delete_venn_variable(name: str) -> Dict[str, Any]:
    """Delete a Venn variable by name with semantic fallback."""
    session = get_sync_db_session()
    try:
        var = session.query(VennVariable).filter(
            VennVariable.name.ilike(f"%{name}%")
        ).first()
        
        if not var:
            # Try semantic search
            similar = find_similar_venn_variables(name, use_embeddings=True)
            if similar and similar[0]['similarity'] > 0.7:
                var = session.query(VennVariable).filter(
                    VennVariable.id == similar[0]['id']
                ).first()
        
        if not var:
            session.close()
            similar = find_similar_venn_variables(name, use_embeddings=True)
            if similar:
                return {
                    "success": False,
                    "error": f"No se encontró '{name}' exactamente.",
                    "needs_confirmation": True,
                    "suggestions": similar
                }
            return {"success": False, "error": f"No se encontró la variable '{name}'"}
        
        # Delete associated proxies first
        session.query(VennProxy).filter(VennProxy.venn_variable_id == var.id).delete()
        
        var_name = var.name
        session.delete(var)
        session.commit()
        clear_embeddings_cache()
        
        return {"success": True, "deleted": var_name}
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        if session.is_active:
            session.close()


def add_venn_proxy(variable_name: str, proxy_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add a proxy to a Venn variable with semantic matching."""
    session = get_sync_db_session()
    try:
        var = session.query(VennVariable).filter(
            VennVariable.name.ilike(f"%{variable_name}%")
        ).first()
        
        if not var:
            # Try semantic search
            similar = find_similar_venn_variables(variable_name, use_embeddings=True)
            if similar and similar[0]['similarity'] > 0.6:
                var = session.query(VennVariable).filter(
                    VennVariable.id == similar[0]['id']
                ).first()
        
        if not var:
            session.close()
            similar = find_similar_venn_variables(variable_name, use_embeddings=True)
            if similar:
                return {
                    "success": False,
                    "error": f"No se encontró la variable '{variable_name}'",
                    "needs_confirmation": True,
                    "suggestions": similar
                }
            return {"success": False, "error": f"No se encontró la variable '{variable_name}'"}
        
        proxy_term = proxy_data.get("name") or proxy_data.get("term")
        if not proxy_term:
            return {"success": False, "error": "El texto del proxy es requerido"}
        
        proxy = VennProxy(
            venn_variable_id=var.id,
            term=proxy_term,
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
    """Delete a proxy from a Venn variable."""
    session = get_sync_db_session()
    try:
        var = session.query(VennVariable).filter(
            VennVariable.name.ilike(f"%{variable_name}%")
        ).first()
        
        if not var:
            similar = find_similar_venn_variables(variable_name, use_embeddings=True)
            if similar and similar[0]['similarity'] > 0.6:
                var = session.query(VennVariable).filter(
                    VennVariable.id == similar[0]['id']
                ).first()
        
        if not var:
            session.close()
            similar = find_similar_venn_variables(variable_name, use_embeddings=True)
            if similar:
                return {
                    "success": False,
                    "error": f"No se encontró la variable '{variable_name}'",
                    "suggestions": similar
                }
            return {"success": False, "error": f"No se encontró la variable '{variable_name}'"}
        
        proxy = session.query(VennProxy).filter(
            VennProxy.venn_variable_id == var.id,
            VennProxy.term.ilike(f"%{proxy_name}%")
        ).first()
        
        if not proxy:
            similar_proxies = find_similar_venn_proxies(var.id, proxy_name)
            if similar_proxies:
                return {
                    "success": False,
                    "error": f"No se encontró el proxy '{proxy_name}'",
                    "suggestions": similar_proxies,
                    "variable": var.name
                }
            return {"success": False, "error": f"No se encontró el proxy '{proxy_name}' en '{var.name}'"}
        
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


def get_venn_data() -> Dict[str, Any]:
    """Get all Venn variables, proxies for overview."""
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
