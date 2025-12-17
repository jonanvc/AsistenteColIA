"""
Database Operations for Venn Intersections.

Handles Venn intersections with support for complex nested boolean expressions.
Supports unlimited nesting: A AND (B OR (C AND (D OR E)))
"""
import json
import re
from typing import List, Dict, Any, Optional
from datetime import datetime

from ..db.base import get_sync_db_session
from ..models.db_models import (
    VennVariable, VennProxy, VennIntersection, 
    VennIntersectionResult, VennOperationType
)


def parse_logic_expression_text(expression_text: str, session) -> Dict[str, Any]:
    """
    Parse a text expression like '"A" OR "B" OR ("C" AND "D")' into a nested tree structure.
    
    Supports UNLIMITED nesting levels:
    - "A" AND "B"
    - "A" OR ("B" AND "C")
    - "A" AND (("B" OR "C") AND ("D" OR "E"))
    - ((("A" AND "B") OR "C") AND "D")
    
    Returns a tree structure:
    {
        "type": "AND" | "OR" | "proxy",
        "id": proxy_id (for proxy nodes),
        "children": [...] (for AND/OR nodes)
    }
    """
    expression_text = expression_text.strip()
    
    # Get all proxies for matching
    all_proxies = session.query(VennProxy).all()
    proxy_lookup = {}
    for p in all_proxies:
        var = session.query(VennVariable).filter(VennVariable.id == p.venn_variable_id).first()
        proxy_lookup[p.term.lower()] = {
            "id": p.id,
            "term": p.term,
            "variable": var.name if var else "Unknown"
        }
    
    matched_proxies = []
    
    def find_proxy_by_text(text: str) -> Dict[str, Any]:
        """Find a proxy by partial text match."""
        text_lower = text.lower().strip()
        
        # Try exact match first
        if text_lower in proxy_lookup:
            proxy_info = proxy_lookup[text_lower]
            matched_proxies.append(proxy_info)
            return {"type": "proxy", "id": proxy_info["id"]}
        
        # Try partial match
        for term, info in proxy_lookup.items():
            if text_lower in term or term in text_lower:
                matched_proxies.append(info)
                return {"type": "proxy", "id": info["id"]}
        
        # Not found
        return {"type": "unknown", "text": text}
    
    def tokenize(expr: str) -> List[str]:
        """
        Tokenize the expression into components:
        - Quoted strings: "text here"
        - Operators: AND, OR
        - Parentheses: (, )
        """
        tokens = []
        i = 0
        while i < len(expr):
            # Skip whitespace
            if expr[i].isspace():
                i += 1
                continue
            
            # Quoted string
            if expr[i] == '"':
                j = i + 1
                while j < len(expr) and expr[j] != '"':
                    j += 1
                tokens.append(('PROXY', expr[i+1:j]))
                i = j + 1
                continue
            
            # Parentheses
            if expr[i] == '(':
                tokens.append(('LPAREN', '('))
                i += 1
                continue
            if expr[i] == ')':
                tokens.append(('RPAREN', ')'))
                i += 1
                continue
            
            # Check for AND/OR operators
            rest = expr[i:].upper()
            if rest.startswith('AND'):
                tokens.append(('AND', 'AND'))
                i += 3
                continue
            if rest.startswith('OR'):
                tokens.append(('OR', 'OR'))
                i += 2
                continue
            
            # Unknown character, skip
            i += 1
        
        return tokens
    
    def parse_expression(tokens: List[tuple], pos: int = 0) -> tuple:
        """
        Recursive descent parser for boolean expressions.
        
        Grammar:
            expr     -> or_expr
            or_expr  -> and_expr (OR and_expr)*
            and_expr -> primary (AND primary)*
            primary  -> PROXY | LPAREN expr RPAREN
        """
        return parse_or_expr(tokens, pos)
    
    def parse_or_expr(tokens: List[tuple], pos: int) -> tuple:
        """Parse OR expressions (lowest precedence)."""
        left, pos = parse_and_expr(tokens, pos)
        
        children = [left]
        while pos < len(tokens) and tokens[pos][0] == 'OR':
            pos += 1  # consume OR
            right, pos = parse_and_expr(tokens, pos)
            children.append(right)
        
        if len(children) == 1:
            return children[0], pos
        return {"type": "OR", "children": children}, pos
    
    def parse_and_expr(tokens: List[tuple], pos: int) -> tuple:
        """Parse AND expressions (higher precedence than OR)."""
        left, pos = parse_primary(tokens, pos)
        
        children = [left]
        while pos < len(tokens) and tokens[pos][0] == 'AND':
            pos += 1  # consume AND
            right, pos = parse_primary(tokens, pos)
            children.append(right)
        
        if len(children) == 1:
            return children[0], pos
        return {"type": "AND", "children": children}, pos
    
    def parse_primary(tokens: List[tuple], pos: int) -> tuple:
        """Parse primary expressions: proxies or parenthesized expressions."""
        if pos >= len(tokens):
            return {"type": "unknown", "text": "empty"}, pos
        
        token_type, token_value = tokens[pos]
        
        if token_type == 'PROXY':
            return find_proxy_by_text(token_value), pos + 1
        
        if token_type == 'LPAREN':
            pos += 1  # consume (
            expr, pos = parse_expression(tokens, pos)
            if pos < len(tokens) and tokens[pos][0] == 'RPAREN':
                pos += 1  # consume )
            return expr, pos
        
        # Unexpected token
        return {"type": "unknown", "text": str(token_value)}, pos + 1
    
    # Tokenize and parse
    tokens = tokenize(expression_text)
    
    if not tokens:
        return {"type": "unknown", "text": expression_text, "matched_proxies": []}
    
    tree, _ = parse_expression(tokens, 0)
    tree["matched_proxies"] = matched_proxies
    
    return tree


def evaluate_logic_expression(
    expression: Dict[str, Any],
    organization_id: int,
    session
) -> Dict[str, Any]:
    """
    Evaluate a logic expression tree for an organization.
    
    Returns:
        {
            "result": True/False,
            "details": {...}  # Evaluation details for debugging
        }
    """
    from ..models.db_models import VennResult
    
    # Handle JSON string input
    if isinstance(expression, str):
        try:
            expression = json.loads(expression)
        except json.JSONDecodeError:
            return {"result": False, "error": "Invalid JSON expression"}
    
    def evaluate_node(node: Dict[str, Any]) -> tuple:
        """Recursively evaluate a node. Returns (result, details)."""
        node_type = node.get("type")
        
        if node_type == "proxy":
            proxy_id = node.get("id")
            # Check if organization has a result for this proxy
            result = session.query(VennResult).filter(
                VennResult.organization_id == organization_id,
                VennResult.venn_proxy_id == proxy_id
            ).first()
            
            value = result is not None and result.value == True
            proxy = session.query(VennProxy).filter(VennProxy.id == proxy_id).first()
            proxy_name = proxy.term[:50] if proxy else f"Proxy {proxy_id}"
            
            return value, {"proxy_id": proxy_id, "name": proxy_name, "value": value}
        
        elif node_type == "AND":
            children_results = []
            all_true = True
            for child in node.get("children", []):
                child_result, child_details = evaluate_node(child)
                children_results.append(child_details)
                if not child_result:
                    all_true = False
            return all_true, {"type": "AND", "result": all_true, "children": children_results}
        
        elif node_type == "OR":
            children_results = []
            any_true = False
            for child in node.get("children", []):
                child_result, child_details = evaluate_node(child)
                children_results.append(child_details)
                if child_result:
                    any_true = True
            return any_true, {"type": "OR", "result": any_true, "children": children_results}
        
        elif node_type == "unknown":
            return False, {"type": "unknown", "text": node.get("text"), "value": False}
        
        return False, {"error": f"Unknown node type: {node_type}"}
    
    result, details = evaluate_node(expression)
    return {"result": result, "details": details}


def build_expression_display(expression: Dict[str, Any], session) -> str:
    """Build a human-readable display of the expression."""
    # Handle JSON string input
    if isinstance(expression, str):
        try:
            expression = json.loads(expression)
        except json.JSONDecodeError:
            return "[Invalid Expression]"
    
    def build_node(node: Dict[str, Any], depth: int = 0) -> str:
        node_type = node.get("type")
        
        if node_type == "proxy":
            proxy_id = node.get("id")
            proxy = session.query(VennProxy).filter(VennProxy.id == proxy_id).first()
            if proxy:
                term_short = proxy.term[:30] + "..." if len(proxy.term) > 30 else proxy.term
                return f'"{term_short}"'
            return f"[Proxy {proxy_id}]"
        
        elif node_type in ("AND", "OR"):
            children = node.get("children", [])
            child_strs = [build_node(c, depth + 1) for c in children]
            joined = f" {node_type} ".join(child_strs)
            # Add parentheses if nested
            if depth > 0:
                return f"({joined})"
            return joined
        
        elif node_type == "unknown":
            return f"[?{node.get('text', '')}]"
        
        return "[?]"
    
    return build_node(expression)


def create_venn_intersection(
    name: str,
    operation: str = "intersection",
    include_variables: Optional[List[str]] = None,
    exclude_variables: Optional[List[str]] = None,
    include_proxies: Optional[List[str]] = None,
    exclude_proxies: Optional[List[str]] = None,
    description: str = "",
    logic_expression: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a Venn intersection.
    
    Supports three modes:
    1. Logic expression mode: Complex nested AND/OR expressions
    2. Proxy-based mode: Simple list of proxies with single operation
    3. Variable-based mode: Based on variable IDs (legacy)
    """
    session = get_sync_db_session()
    try:
        # Determine the mode
        use_logic_expression = logic_expression is not None
        use_proxies = bool(include_proxies) or bool(exclude_proxies)
        
        # Resolve proxy texts to IDs
        include_proxy_ids = []
        exclude_proxy_ids = []
        
        if include_proxies:
            for proxy_text in include_proxies:
                proxy = session.query(VennProxy).filter(
                    VennProxy.term.ilike(f"%{proxy_text}%")
                ).first()
                if proxy:
                    include_proxy_ids.append(proxy.id)
        
        if exclude_proxies:
            for proxy_text in exclude_proxies:
                proxy = session.query(VennProxy).filter(
                    VennProxy.term.ilike(f"%{proxy_text}%")
                ).first()
                if proxy:
                    exclude_proxy_ids.append(proxy.id)
        
        # Resolve variable names to IDs
        include_ids = []
        exclude_ids = []
        
        if include_variables:
            for var_name in include_variables:
                var = session.query(VennVariable).filter(
                    VennVariable.name.ilike(f"%{var_name}%")
                ).first()
                if var:
                    include_ids.append(var.id)
        
        if exclude_variables:
            for var_name in exclude_variables:
                var = session.query(VennVariable).filter(
                    VennVariable.name.ilike(f"%{var_name}%")
                ).first()
                if var:
                    exclude_ids.append(var.id)
        
        # Build expression display
        expression_display = ""
        if use_logic_expression:
            expression_display = build_expression_display(logic_expression, session)
        
        # Convert logic_expression to JSON string for storage
        logic_expr_json = None
        if logic_expression:
            # Remove matched_proxies before storing
            expr_to_store = {k: v for k, v in logic_expression.items() if k != 'matched_proxies'}
            logic_expr_json = json.dumps(expr_to_store)
        
        # Determine operation type
        op_type = VennOperationType.INTERSECTION
        if operation and operation.lower() == "union":
            op_type = VennOperationType.UNION
        
        intersection = VennIntersection(
            name=name,
            description=description,
            operation=op_type,
            include_ids=include_ids if include_ids else None,
            exclude_ids=exclude_ids if exclude_ids else None,
            use_proxies=use_proxies,
            include_proxy_ids=include_proxy_ids if include_proxy_ids else None,
            exclude_proxy_ids=exclude_proxy_ids if exclude_proxy_ids else None,
            use_logic_expression=use_logic_expression,
            logic_expression=logic_expr_json,
            expression_display=expression_display,
            is_active=True,
        )
        
        session.add(intersection)
        session.commit()
        
        mode = "logic_expression" if use_logic_expression else ("proxy-based" if use_proxies else "variable-based")
        
        return {
            "success": True,
            "created": intersection.name,
            "id": intersection.id,
            "mode": mode,
            "expression_display": expression_display,
            "operation": operation,
            "include_proxy_count": len(include_proxy_ids),
            "exclude_proxy_count": len(exclude_proxy_ids),
        }
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def list_venn_intersections() -> Dict[str, Any]:
    """List all active Venn intersections."""
    session = get_sync_db_session()
    try:
        intersections = session.query(VennIntersection).filter(
            VennIntersection.is_active == True
        ).all()
        
        result = []
        for inter in intersections:
            if inter.use_logic_expression and inter.logic_expression:
                expr_display = inter.expression_display or build_expression_display(inter.logic_expression, session)
                result.append({
                    "id": inter.id,
                    "name": inter.name,
                    "description": inter.description,
                    "use_logic_expression": True,
                    "expression_display": expr_display,
                    "display_label": inter.display_label,
                    "color": inter.color,
                })
            else:
                # Legacy/simple mode
                include_names = []
                include_proxy_info = []
                
                if inter.use_proxies and inter.include_proxy_ids:
                    for proxy_id in inter.include_proxy_ids:
                        proxy = session.query(VennProxy).filter(VennProxy.id == proxy_id).first()
                        if proxy:
                            var = session.query(VennVariable).filter(VennVariable.id == proxy.venn_variable_id).first()
                            include_proxy_info.append({
                                "id": proxy.id,
                                "term": proxy.term,
                                "variable": var.name if var else "Unknown"
                            })
                
                if inter.include_ids:
                    for var_id in inter.include_ids:
                        var = session.query(VennVariable).filter(VennVariable.id == var_id).first()
                        if var:
                            include_names.append(var.name)
                
                result.append({
                    "id": inter.id,
                    "name": inter.name,
                    "description": inter.description,
                    "operation": inter.operation.value if inter.operation else "intersection",
                    "use_proxies": inter.use_proxies,
                    "use_logic_expression": False,
                    "include_variables": include_names,
                    "include_proxies": include_proxy_info,
                    "display_label": inter.display_label,
                    "color": inter.color,
                })
        
        return {"success": True, "intersections": result, "total": len(result)}
    finally:
        session.close()


def delete_venn_intersection(name: str = None, intersection_id: int = None) -> Dict[str, Any]:
    """Delete a Venn intersection."""
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
            return {"success": False, "error": "No se encontró la intersección"}
        
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
    new_operation: str = None,
    include_variables: Optional[List[str]] = None,
    exclude_variables: Optional[List[str]] = None,
    include_proxies: Optional[List[str]] = None,
    exclude_proxies: Optional[List[str]] = None,
    description: str = None,
    logic_expression: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Update a Venn intersection."""
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
            return {"success": False, "error": "No se encontró la intersección"}
        
        changes = []
        
        if new_operation:
            op_type = VennOperationType.UNION if new_operation.lower() == "union" else VennOperationType.INTERSECTION
            intersection.operation = op_type
            changes.append(f"Operación: {new_operation}")
        
        if description is not None:
            intersection.description = description
            changes.append("Descripción actualizada")
        
        if logic_expression:
            expr_to_store = {k: v for k, v in logic_expression.items() if k != 'matched_proxies'}
            intersection.logic_expression = json.dumps(expr_to_store)
            intersection.use_logic_expression = True
            intersection.expression_display = build_expression_display(logic_expression, session)
            changes.append("Expresión lógica actualizada")
        
        if include_proxies is not None:
            include_proxy_ids = []
            for proxy_text in include_proxies:
                proxy = session.query(VennProxy).filter(
                    VennProxy.term.ilike(f"%{proxy_text}%")
                ).first()
                if proxy:
                    include_proxy_ids.append(proxy.id)
            intersection.include_proxy_ids = include_proxy_ids
            intersection.use_proxies = True
            changes.append(f"Proxies incluidos: {len(include_proxy_ids)}")
        
        session.commit()
        
        return {
            "success": True,
            "updated": intersection.name,
            "new_operation": intersection.operation.value if intersection.operation else "intersection",
            "changes": changes
        }
    except Exception as e:
        session.rollback()
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def calculate_intersection_result(intersection_id: int, organization_id: int) -> Dict[str, Any]:
    """Calculate the intersection result for a specific organization."""
    session = get_sync_db_session()
    try:
        intersection = session.query(VennIntersection).filter(
            VennIntersection.id == intersection_id
        ).first()
        
        if not intersection:
            return {"success": False, "error": "Intersección no encontrada"}
        
        if intersection.use_logic_expression and intersection.logic_expression:
            # Use logic expression evaluation
            result = evaluate_logic_expression(
                intersection.logic_expression,
                organization_id,
                session
            )
            return {
                "success": True,
                "intersection": intersection.name,
                "organization_id": organization_id,
                "value": result["result"],
                "details": result.get("details"),
                "mode": "logic_expression"
            }
        
        # Legacy mode - not implemented here for brevity
        return {"success": False, "error": "Legacy mode not supported in this version"}
    finally:
        session.close()


# ============================================================================
# HIGH-LEVEL FUNCTIONS FOR CHAT AGENT
# ============================================================================

def create_intersection_from_text(
    name: str,
    expression_text: str = None,
    include_proxies: List[str] = None,
    operation: str = "intersection",
    user_input: str = ""
) -> Dict[str, Any]:
    """
    High-level function to create a Venn intersection from user text.
    Handles parsing, validation, and creation in one call.
    
    Args:
        name: Intersection name
        expression_text: Logic expression like '"A" AND "B"' or '"A" OR ("B" AND "C")'
        include_proxies: Simple list of proxy texts for non-expression mode
        operation: 'intersection' (AND) or 'union' (OR) for simple mode
        user_input: Original user input for fallback extraction
    
    Returns:
        Dict with success status, created intersection info, or error
    """
    session = get_sync_db_session()
    try:
        parsed_expr = None
        unknowns = []
        
        # Try to extract expression from user_input if not provided
        if not expression_text and user_input:
            # Look for patterns like: expresión: "A" AND "B"
            patterns = [
                r'expresi[oó]n[:\s]+(.+?)(?:$|\n)',
                r'con expresi[oó]n[:\s]+(.+?)(?:$|\n)',
                r':\s*(["\(].+)$',
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    expression_text = match.group(1).strip()
                    break
        
        # Parse logic expression if provided
        if expression_text:
            parsed_expr = parse_logic_expression_text(expression_text, session)
            matched = parsed_expr.pop('matched_proxies', [])
            
            # Check for unknown proxies
            def find_unknown(node):
                result = []
                if node.get('type') == 'unknown':
                    result.append(node.get('text', '?'))
                for child in node.get('children', []):
                    result.extend(find_unknown(child))
                return result
            
            unknowns = find_unknown(parsed_expr)
            if unknowns:
                return {
                    "success": False,
                    "error": f"Proxies no encontrados: {', '.join(unknowns[:5])}",
                    "unknowns": unknowns
                }
        
        # Create intersection
        if parsed_expr or include_proxies:
            result = create_venn_intersection(
                name=name,
                operation=operation,
                include_proxies=include_proxies if include_proxies else None,
                logic_expression=parsed_expr
            )
            return result
        else:
            return {
                "success": False,
                "error": "Se requiere expresión lógica o lista de proxies"
            }
    
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        session.close()


def format_intersections_list(result: Dict[str, Any]) -> str:
    """Format the intersections list for chat response."""
    if not result.get("success"):
        return f"❌ Error: {result.get('error', 'Unknown error')}"
    
    if not result.get("intersections"):
        return "📭 No hay intersecciones configuradas."
    
    response = f"🔷 **{result['total']} intersecciones:**\n\n"
    for inter in result["intersections"]:
        response += f"**{inter['name']}** (ID: {inter['id']})\n"
        if inter.get('use_logic_expression'):
            response += f"  🧮 Expresión: `{inter.get('expression_display', 'N/A')}`\n"
        elif inter.get('include_proxies'):
            op = inter.get('operation', 'intersection')
            response += f"  📝 {len(inter['include_proxies'])} proxies ({op})\n"
        response += "\n"
    
    return response


def format_intersection_created(result: Dict[str, Any]) -> str:
    """Format the intersection creation result for chat response."""
    if not result.get("success"):
        return f"❌ Error: {result.get('error', 'Unknown error')}"
    
    response = f"✅ Intersección **{result['created']}** creada.\n"
    response += f"- Modo: {result['mode']}\n"
    if result.get('expression_display'):
        response += f"- Expresión: `{result['expression_display']}`\n"
    
    return response


def format_intersection_deleted(result: Dict[str, Any]) -> str:
    """Format the intersection deletion result for chat response."""
    if not result.get("success"):
        return f"❌ Error: {result.get('error', 'Unknown error')}"
    return f"🗑️ Intersección **{result['deleted']}** eliminada."


def format_intersection_updated(result: Dict[str, Any]) -> str:
    """Format the intersection update result for chat response."""
    if not result.get("success"):
        return f"❌ Error: {result.get('error', 'Unknown error')}"
    return f"✅ Intersección **{result['updated']}** actualizada."
