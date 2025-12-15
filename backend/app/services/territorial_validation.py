"""
Territorial Validation Module

Validates that proxy matches respect the organizational territorial scope hierarchy.

HIERARCHY RULES:
- MUNICIPAL: Most restrictive. Only matches proxies applicable to MUNICIPAL scope.
- DEPARTAMENTAL: Contains municipalities. Can match DEPARTAMENTAL or MUNICIPAL proxies.
- REGIONAL: Multiple departments. Can match REGIONAL, DEPARTAMENTAL, or MUNICIPAL proxies.
- NACIONAL: National level. Can match ALL scope types.
- INTERNACIONAL: Treated as NACIONAL for matching purposes.

VALIDATION LOGIC:
1. Universal proxies (applicable_scopes = null/empty): Always match regardless of org scope.
2. Scope-restricted proxies: Match only if org scope is compatible.
3. Location-restricted proxies: Match only if org location codes match.

DECISION TABLE:
+------------------+----------------------+---------------------------+
| Org Scope        | Proxy applicable_scopes | Result                    |
+------------------+----------------------+---------------------------+
| MUNICIPAL        | null                 | ✓ Match (universal)       |
| MUNICIPAL        | ["MUNICIPAL"]        | ✓ Match                   |
| MUNICIPAL        | ["DEPARTAMENTAL"]    | ✗ No match (scope higher) |
| MUNICIPAL        | ["NACIONAL"]         | ✗ No match (scope higher) |
+------------------+----------------------+---------------------------+
| DEPARTAMENTAL    | null                 | ✓ Match (universal)       |
| DEPARTAMENTAL    | ["MUNICIPAL"]        | ✓ Match (contains munic.) |
| DEPARTAMENTAL    | ["DEPARTAMENTAL"]    | ✓ Match                   |
| DEPARTAMENTAL    | ["REGIONAL"]         | ✗ No match (scope higher) |
+------------------+----------------------+---------------------------+
| REGIONAL         | null                 | ✓ Match (universal)       |
| REGIONAL         | ["MUNICIPAL"]        | ✓ Match                   |
| REGIONAL         | ["DEPARTAMENTAL"]    | ✓ Match                   |
| REGIONAL         | ["REGIONAL"]         | ✓ Match                   |
| REGIONAL         | ["NACIONAL"]         | ✗ No match (scope higher) |
+------------------+----------------------+---------------------------+
| NACIONAL/INTL    | [any]                | ✓ Match (all scopes)      |
+------------------+----------------------+---------------------------+
"""
from typing import Optional, List, Dict, Any
from enum import Enum

from ..models.db_models import TerritorialScope, VennProxy, Organization


# Define scope hierarchy (higher index = higher/broader scope)
SCOPE_HIERARCHY: Dict[TerritorialScope, int] = {
    TerritorialScope.MUNICIPAL: 1,
    TerritorialScope.DEPARTAMENTAL: 2,
    TerritorialScope.REGIONAL: 3,
    TerritorialScope.NACIONAL: 4,
    TerritorialScope.INTERNACIONAL: 4,  # Same as NACIONAL for matching
}

# Scopes that each org scope can "contain" or match with
# An org can match proxies at its level or BELOW
SCOPE_CAN_MATCH: Dict[TerritorialScope, List[TerritorialScope]] = {
    TerritorialScope.MUNICIPAL: [TerritorialScope.MUNICIPAL],
    TerritorialScope.DEPARTAMENTAL: [TerritorialScope.MUNICIPAL, TerritorialScope.DEPARTAMENTAL],
    TerritorialScope.REGIONAL: [TerritorialScope.MUNICIPAL, TerritorialScope.DEPARTAMENTAL, TerritorialScope.REGIONAL],
    TerritorialScope.NACIONAL: [TerritorialScope.MUNICIPAL, TerritorialScope.DEPARTAMENTAL, TerritorialScope.REGIONAL, TerritorialScope.NACIONAL],
    TerritorialScope.INTERNACIONAL: [TerritorialScope.MUNICIPAL, TerritorialScope.DEPARTAMENTAL, TerritorialScope.REGIONAL, TerritorialScope.NACIONAL, TerritorialScope.INTERNACIONAL],
}


def get_scope_level(scope: TerritorialScope) -> int:
    """Get the hierarchy level of a scope (1=lowest/most specific, 4=highest/broadest)."""
    return SCOPE_HIERARCHY.get(scope, 0)


def scope_from_string(scope_str: str) -> Optional[TerritorialScope]:
    """Convert a string to TerritorialScope enum, handling case variations."""
    if not scope_str:
        return None
    try:
        return TerritorialScope(scope_str.upper())
    except ValueError:
        return None


def validate_proxy_scope(
    org_scope: TerritorialScope,
    proxy_applicable_scopes: Optional[List[str]]
) -> bool:
    """
    Validate if an organization's scope is compatible with a proxy's applicable scopes.
    
    Args:
        org_scope: The territorial scope of the organization
        proxy_applicable_scopes: List of scope strings the proxy applies to (null = universal)
    
    Returns:
        True if the proxy can be activated for this organization, False otherwise
    """
    # Universal proxy: null or empty applicable_scopes
    if not proxy_applicable_scopes:
        return True
    
    # Get scopes this organization can match with
    matchable_scopes = SCOPE_CAN_MATCH.get(org_scope, [])
    
    # Check if any of the proxy's applicable scopes are matchable by the org
    for scope_str in proxy_applicable_scopes:
        proxy_scope = scope_from_string(scope_str)
        if proxy_scope and proxy_scope in matchable_scopes:
            return True
    
    return False


def validate_location_restriction(
    org: Organization,
    location_restriction: Optional[Dict[str, str]]
) -> bool:
    """
    Validate if an organization's location matches a proxy's location restriction.
    
    Args:
        org: The organization object
        location_restriction: Dict with department_code and/or municipality_code
    
    Returns:
        True if the location matches or no restriction exists, False otherwise
    """
    # No restriction: always matches
    if not location_restriction:
        return True
    
    # Check department code
    if "department_code" in location_restriction:
        required_dept = location_restriction["department_code"]
        
        # Check organization's main department
        if org.department_code and org.department_code == required_dept:
            pass  # Matches, continue to check municipality
        # Check regional organization's department list
        elif org.department_codes and required_dept in org.department_codes:
            pass  # Matches
        else:
            return False  # Department doesn't match
    
    # Check municipality code
    if "municipality_code" in location_restriction:
        required_muni = location_restriction["municipality_code"]
        if not org.municipality_code or org.municipality_code != required_muni:
            return False  # Municipality doesn't match
    
    return True


def validate_proxy_for_organization(
    org: Organization,
    proxy: VennProxy
) -> Dict[str, Any]:
    """
    Full validation of a proxy for an organization.
    
    Returns a dict with:
    - is_valid: bool - whether the proxy can be activated
    - reason: str - explanation of the decision
    - scope_valid: bool - scope validation result
    - location_valid: bool - location validation result
    """
    result = {
        "is_valid": False,
        "reason": "",
        "scope_valid": False,
        "location_valid": False,
        "org_scope": org.territorial_scope.value if org.territorial_scope else None,
        "proxy_scopes": proxy.applicable_scopes,
        "proxy_location": proxy.location_restriction,
    }
    
    # Default to MUNICIPAL if org has no scope
    org_scope = org.territorial_scope or TerritorialScope.MUNICIPAL
    
    # Step 1: Validate territorial scope
    result["scope_valid"] = validate_proxy_scope(org_scope, proxy.applicable_scopes)
    if not result["scope_valid"]:
        result["reason"] = f"Scope incompatible: org scope '{org_scope.value}' cannot match proxy scopes {proxy.applicable_scopes}"
        return result
    
    # Step 2: Validate location restriction
    result["location_valid"] = validate_location_restriction(org, proxy.location_restriction)
    if not result["location_valid"]:
        result["reason"] = f"Location mismatch: org location does not match proxy restriction {proxy.location_restriction}"
        return result
    
    # All validations passed
    result["is_valid"] = True
    result["reason"] = "Proxy is valid for this organization"
    return result


def filter_proxies_for_organization(
    org: Organization,
    proxies: List[VennProxy]
) -> List[Dict[str, Any]]:
    """
    Filter a list of proxies to only those valid for an organization.
    
    Returns list of dicts with proxy info and validation details.
    """
    results = []
    for proxy in proxies:
        validation = validate_proxy_for_organization(org, proxy)
        if validation["is_valid"]:
            results.append({
                "proxy": proxy,
                "proxy_id": proxy.id,
                "term": proxy.term,
                "weight": proxy.weight,
                "validation": validation
            })
    return results


def explain_scope_compatibility(org_scope: TerritorialScope) -> str:
    """
    Generate a human-readable explanation of which proxy scopes an organization can match.
    """
    matchable = SCOPE_CAN_MATCH.get(org_scope, [])
    scope_names = [s.value for s in matchable]
    
    explanations = {
        TerritorialScope.MUNICIPAL: (
            f"Una organización MUNICIPAL solo puede activar proxies específicamente "
            f"municipales o proxies universales (sin restricción de scope)."
        ),
        TerritorialScope.DEPARTAMENTAL: (
            f"Una organización DEPARTAMENTAL puede activar proxies municipales, "
            f"departamentales, o universales. Puede representar las iniciativas "
            f"de sus municipios contenidos."
        ),
        TerritorialScope.REGIONAL: (
            f"Una organización REGIONAL puede activar proxies municipales, "
            f"departamentales, regionales, o universales. Abarca múltiples "
            f"departamentos y sus subdivisiones."
        ),
        TerritorialScope.NACIONAL: (
            f"Una organización NACIONAL puede activar TODOS los tipos de proxies. "
            f"Tiene alcance sobre todo el territorio colombiano."
        ),
        TerritorialScope.INTERNACIONAL: (
            f"Una organización INTERNACIONAL se trata como NACIONAL para fines "
            f"de matching de proxies. Puede activar todos los tipos de proxies."
        ),
    }
    
    return explanations.get(org_scope, f"Scopes compatibles: {scope_names}")


# ============================================================================
# DATA SCOPE VALIDATION (for scraped content)
# ============================================================================

def validate_data_scope_for_organization(
    org_scope: TerritorialScope,
    data_scope: Optional[TerritorialScope]
) -> bool:
    """
    Validate if scraped data's territorial scope is relevant for an organization.
    
    Rules:
    - Data without scope (null): Can be used by any organization
    - Municipal data: Only relevant to municipal or higher scoped orgs in same location
    - National data: Relevant to all organizations
    
    This is a softer validation than proxy matching - it determines relevance, not eligibility.
    """
    # Data without specified scope: universally relevant
    if data_scope is None:
        return True
    
    # National/International data: relevant to all
    if data_scope in [TerritorialScope.NACIONAL, TerritorialScope.INTERNACIONAL]:
        return True
    
    # For other data scopes, org must have equal or higher scope
    org_level = get_scope_level(org_scope)
    data_level = get_scope_level(data_scope)
    
    return org_level >= data_level
