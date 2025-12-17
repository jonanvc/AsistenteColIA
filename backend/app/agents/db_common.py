"""
Common utilities for database agents.

Provides shared functionality like similarity search, embeddings,
and database session management.
"""
import os
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher

from langchain_openai import OpenAIEmbeddings
import numpy as np

from ..db.base import get_sync_db_session
from ..models.db_models import Organization, VennVariable, VennProxy

# Initialize embeddings model (lazy loading)
_embeddings_model = None
_org_embeddings_cache = {}
_var_embeddings_cache = {}


def get_embeddings_model():
    """Get or create the embeddings model."""
    global _embeddings_model
    if _embeddings_model is None:
        _embeddings_model = OpenAIEmbeddings(
            model="text-embedding-3-small",
            dimensions=256  # Smaller dimensions for faster comparison
        )
    return _embeddings_model


def calculate_similarity(s1: str, s2: str) -> float:
    """Calculate similarity ratio between two strings (0.0 to 1.0)."""
    s1_lower = s1.lower().strip()
    s2_lower = s2.lower().strip()
    return SequenceMatcher(None, s1_lower, s2_lower).ratio()


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def get_embedding(text: str) -> List[float]:
    """Get embedding for a text string."""
    model = get_embeddings_model()
    return model.embed_query(text)


def find_similar_organizations(
    search_term: str, 
    threshold: float = 0.4,
    use_embeddings: bool = True,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Find organizations with fuzzy matching using embeddings + text similarity.
    
    Args:
        search_term: The search term to match
        threshold: Minimum similarity threshold
        use_embeddings: Whether to use semantic embeddings
        top_k: Number of top matches to return
    """
    session = get_sync_db_session()
    try:
        all_orgs = session.query(Organization).all()
        
        if not all_orgs:
            return []
        
        matches = []
        search_lower = search_term.lower().strip()
        
        # Try embeddings-based search first
        search_embedding = None
        if use_embeddings:
            try:
                search_embedding = get_embedding(search_term)
            except Exception:
                pass  # Fall back to text similarity
        
        for org in all_orgs:
            name_lower = org.name.lower().strip()
            
            # Text-based similarity
            text_sim = calculate_similarity(search_term, org.name)
            
            # Check containment
            contains_match = search_lower in name_lower or name_lower in search_lower
            
            # Embedding-based similarity
            embed_sim = 0.0
            if search_embedding:
                try:
                    # Get or compute org embedding
                    if org.id not in _org_embeddings_cache:
                        _org_embeddings_cache[org.id] = get_embedding(org.name)
                    org_embedding = _org_embeddings_cache[org.id]
                    embed_sim = cosine_similarity(search_embedding, org_embedding)
                except Exception:
                    pass
            
            # Combined score (weighted average)
            if search_embedding:
                combined_sim = 0.4 * text_sim + 0.6 * embed_sim
            else:
                combined_sim = text_sim
            
            # Boost for containment
            if contains_match:
                combined_sim = max(combined_sim, 0.8)
            
            if combined_sim >= threshold or contains_match:
                matches.append({
                    "id": org.id,
                    "name": org.name,
                    "description": org.description,
                    "territorial_scope": org.territorial_scope.value if org.territorial_scope else None,
                    "department_code": org.department_code,
                    "leader_name": org.leader_name,
                    "similarity": combined_sim,
                    "exact_match": contains_match,
                })
        
        # Sort by similarity (highest first)
        matches.sort(key=lambda x: (x["exact_match"], x["similarity"]), reverse=True)
        return matches[:top_k]
    finally:
        session.close()


def find_similar_venn_variables(
    search_term: str, 
    threshold: float = 0.3,
    use_embeddings: bool = True,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Find Venn variables with fuzzy matching using embeddings + text similarity.
    """
    session = get_sync_db_session()
    try:
        all_vars = session.query(VennVariable).all()
        
        if not all_vars:
            return []
        
        matches = []
        search_lower = search_term.lower().strip()
        
        # Try embeddings-based search
        search_embedding = None
        if use_embeddings:
            try:
                search_embedding = get_embedding(search_term)
            except Exception:
                pass
        
        for var in all_vars:
            name_lower = var.name.lower().strip()
            
            # Text-based similarity
            text_sim = calculate_similarity(search_term, var.name)
            
            # Check containment
            contains_match = search_lower in name_lower or name_lower in search_lower
            
            # Embedding-based similarity
            embed_sim = 0.0
            if search_embedding:
                try:
                    if var.id not in _var_embeddings_cache:
                        _var_embeddings_cache[var.id] = get_embedding(var.name)
                    var_embedding = _var_embeddings_cache[var.id]
                    embed_sim = cosine_similarity(search_embedding, var_embedding)
                except Exception:
                    pass
            
            # Combined score
            if search_embedding:
                combined_sim = 0.4 * text_sim + 0.6 * embed_sim
            else:
                combined_sim = text_sim
            
            if contains_match:
                combined_sim = max(combined_sim, 0.8)
            
            if combined_sim >= threshold or contains_match:
                matches.append({
                    "id": var.id,
                    "name": var.name,
                    "description": var.description,
                    "similarity": combined_sim,
                    "exact_match": contains_match,
                })
        
        matches.sort(key=lambda x: (x["exact_match"], x["similarity"]), reverse=True)
        return matches[:top_k]
    finally:
        session.close()


def find_similar_venn_proxies(
    variable_id: int, 
    search_term: str, 
    threshold: float = 0.3,
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """Find Venn proxies with fuzzy matching."""
    session = get_sync_db_session()
    try:
        proxies = session.query(VennProxy).filter(
            VennProxy.venn_variable_id == variable_id
        ).all()
        
        matches = []
        search_lower = search_term.lower().strip()
        
        for proxy in proxies:
            term_lower = proxy.term.lower().strip()
            text_sim = calculate_similarity(search_term, proxy.term)
            contains_match = search_lower in term_lower or term_lower in search_lower
            
            if text_sim >= threshold or contains_match:
                matches.append({
                    "id": proxy.id,
                    "term": proxy.term,
                    "weight": proxy.weight,
                    "similarity": text_sim,
                    "exact_match": contains_match,
                })
        
        matches.sort(key=lambda x: (x["exact_match"], x["similarity"]), reverse=True)
        return matches[:top_k]
    finally:
        session.close()


def clear_embeddings_cache():
    """Clear the embeddings cache (useful after adding new items)."""
    global _org_embeddings_cache, _var_embeddings_cache
    _org_embeddings_cache = {}
    _var_embeddings_cache = {}
