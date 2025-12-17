"""
Database Agent - Orchestrator

Main entry point for database operations. Routes requests to specialized modules:
- db_organizations: Organization CRUD
- db_venn_variables: Variables and proxies
- db_venn_intersections: Intersections and logic expressions

This agent provides direct database access for the chat interface.
"""
import json
from typing import TYPE_CHECKING, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable

if TYPE_CHECKING:
    from .graph import AgentState

# Import specialized modules
from .db_organizations import (
    search_organizations,
    get_all_organizations,
    get_organization_by_name,
    create_organization,
    update_organization_by_name,
    delete_organization_by_name,
    get_organizations_without_location,
    get_organizations_with_links,
    add_link_to_organization,
)
from .db_venn_variables import (
    list_all_venn_variables,
    get_venn_variable,
    create_venn_variable,
    update_venn_variable,
    delete_venn_variable,
    add_venn_proxy,
    delete_venn_proxy,
    get_venn_data,
)
from .db_venn_intersections import (
    parse_logic_expression_text,
    create_venn_intersection,
    list_venn_intersections,
    delete_venn_intersection,
    update_venn_intersection,
    calculate_intersection_result,
)
from ..db.base import get_sync_db_session

# Initialize ChatOpenAI client
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.1,
    max_tokens=4000,
)

DB_AGENT_SYSTEM_PROMPT = """Eres un agente de BD para organizaciones de mujeres constructoras de paz en Colombia.

OPERACIONES:

1. ORGANIZACIONES:
   - query_organizations: Buscar por término
   - get_organization: Detalles de UNA org (organization_name)
   - list_all_organizations: Listar TODAS
   - create_organization: Crear (data: name, description, territorial_scope, department_code, leader_name, leader_is_woman)
   - update_organization: Actualizar (organization_name + update_data)
   - delete_organization: Eliminar (organization_name)

2. VARIABLES VENN:
   - list_venn_variables: Listar todas
   - get_venn_variable: Ver UNA variable con proxies (variable_name)
   - create_venn_variable: Crear (data: name, description)
   - update_venn_variable: Actualizar (variable_name + update_data)
   - delete_venn_variable: Eliminar (variable_name)
   - add_venn_proxy: Añadir proxy (variable_name + proxy_data: name)
   - delete_venn_proxy: Eliminar proxy (variable_name + proxy_name)

3. INTERSECCIONES VENN:
   - list_venn_intersections: Listar todas
   - create_venn_intersection: Crear con expresión lógica
   - update_venn_intersection: Actualizar
   - delete_venn_intersection: Eliminar (intersection_name)
   - calculate_intersection: Calcular para organización

4. OTROS: no_db_action, trigger_scrape

CONSULTA: {user_input}

Responde SOLO JSON:
{{
    "action": "accion",
    "organization_name": "nombre",
    "variable_name": "variable",
    "intersection_name": "intersección",
    "proxy_name": "proxy a eliminar",
    "include_proxies": ["p1", "p2"],
    "logic_expression_text": "expr con paréntesis",
    "intersection_operation": "union|intersection",
    "data": {{}},
    "update_data": {{}},
    "proxy_data": {{}},
    "reasoning": "explicación"
}}

REGLAS:
- "Dame info de X" / "Muestra X" → get_organization (organization_name: "X")
- "Busca X" → query_organizations (search_term: "X")
- "Lista organizaciones" → list_all_organizations
- "Lista variables" → list_venn_variables
- "Muestra variable X" → get_venn_variable (variable_name: "X")
- "Lista intersecciones" → list_venn_intersections
- "Crea intersección: A AND (B OR C)" → create_venn_intersection con logic_expression_text

EXPRESIONES LÓGICAS (soporta niveles ilimitados):
- "A" AND "B"
- "A" OR ("B" AND "C")
- "A" AND (("B" OR "C") AND ("D" OR "E"))
"""


@traceable(name="db_agent_node")
def db_agent_node(state: "AgentState") -> "AgentState":
    """
    Database agent node - routes to specialized modules.
    """
    user_input = state.get("user_input", "")
    previous_db_response = state.get("db_response", "")
    conversation_history = state.get("conversation_history", [])
    
    # Build context
    context = ""
    if conversation_history:
        context += "\nHISTORIAL (últimos 4):\n"
        for msg in conversation_history[-4:]:
            if isinstance(msg, dict):
                role = "Usuario" if msg.get("role") == "user" else "Asistente"
                content = msg.get("content", "")[:200]
                context += f"  {role}: {content}\n"
    
    if previous_db_response:
        context += f"\nÚLTIMA BD: {previous_db_response[:300]}\n"
    
    # Get LLM decision
    try:
        messages = [
            SystemMessage(content=DB_AGENT_SYSTEM_PROMPT.format(user_input=user_input)),
            HumanMessage(content=f"CONTEXTO:{context}\n\nCONSULTA: {user_input}")
        ]
        
        llm_json = llm.bind(response_format={"type": "json_object"})
        response = llm_json.invoke(messages)
        decision = json.loads(response.content)
        
        action = decision.get("action", "no_db_action")
        org_name = decision.get("organization_name", "")
        var_name = decision.get("variable_name", "")
        inter_name = decision.get("intersection_name", "")
        search_term = decision.get("search_term", "")
        
        db_response = None
        
        # ==================== ORGANIZATIONS ====================
        
        if action == "query_organizations":
            term = search_term or org_name
            result = search_organizations(term)
            if result["exact"] and result["results"]:
                db_response = f"✅ Encontré {len(result['results'])} organización(es):\n\n"
                for org in result["results"][:10]:
                    db_response += f"**{org['name']}**\n"
                    db_response += f"  - Alcance: {org.get('territorial_scope') or 'N/A'}\n"
                    db_response += f"  - Líder: {org.get('leader_name') or 'N/A'}\n\n"
            elif result["suggestions"]:
                db_response = f"🔍 No encontré '{term}', pero hay similares:\n\n"
                for i, org in enumerate(result["suggestions"][:5], 1):
                    sim = int(org['similarity'] * 100)
                    db_response += f"{i}. **{org['name']}** ({sim}% similar)\n"
            else:
                db_response = f"❌ No encontré organizaciones con '{term}'."
        
        elif action == "get_organization":
            result = get_organization_by_name(org_name or search_term)
            if result["found"]:
                org = result["organization"]
                db_response = f"📍 **{org['name']}**\n\n"
                db_response += f"- **Descripción:** {org.get('description') or 'Sin descripción'}\n"
                db_response += f"- **Alcance:** {org.get('territorial_scope') or 'N/A'}\n"
                db_response += f"- **Departamento:** {org.get('department_code') or 'N/A'}\n"
                db_response += f"- **Líder:** {org.get('leader_name') or 'N/A'}\n"
                db_response += f"- **Líder mujer:** {'Sí' if org.get('leader_is_woman') else 'No' if org.get('leader_is_woman') is False else 'N/A'}\n"
            elif result.get("suggestions"):
                db_response = f"🔍 No encontré '{org_name}', pero encontré similares:\n\n"
                for i, s in enumerate(result["suggestions"][:5], 1):
                    sim = int(s['similarity'] * 100)
                    db_response += f"{i}. **{s['name']}** ({sim}%)\n"
            else:
                db_response = f"❌ No encontré la organización '{org_name}'."
        
        elif action == "list_all_organizations":
            orgs = get_all_organizations()
            if orgs:
                db_response = f"📋 **{len(orgs)} organizaciones registradas:**\n\n"
                for org in orgs[:20]:
                    db_response += f"• **{org['name']}** - {org.get('territorial_scope') or 'N/A'}\n"
                if len(orgs) > 20:
                    db_response += f"\n... y {len(orgs) - 20} más."
            else:
                db_response = "📭 No hay organizaciones registradas."
        
        elif action == "create_organization":
            data = decision.get("data", {})
            result = create_organization(data)
            if result["success"]:
                db_response = f"✅ Organización **{result['created']}** creada (ID: {result['id']})."
            else:
                db_response = f"❌ Error: {result['error']}"
        
        elif action == "update_organization":
            update_data = decision.get("update_data", {})
            result = update_organization_by_name(org_name, update_data)
            if result["success"]:
                db_response = f"✅ Organización **{result['updated']}** actualizada."
            elif result.get("suggestions"):
                db_response = f"🔍 No encontré '{org_name}'. Similares:\n"
                for s in result["suggestions"][:3]:
                    db_response += f"• {s['name']}\n"
            else:
                db_response = f"❌ Error: {result['error']}"
        
        elif action == "delete_organization":
            result = delete_organization_by_name(org_name)
            if result["success"]:
                db_response = f"🗑️ Organización **{result['deleted']}** eliminada."
            elif result.get("suggestions"):
                db_response = f"🔍 No encontré '{org_name}'. ¿Te refieres a alguna de estas?\n"
                for s in result["suggestions"][:3]:
                    db_response += f"• {s['name']}\n"
            else:
                db_response = f"❌ Error: {result['error']}"
        
        # ==================== VENN VARIABLES ====================
        
        elif action == "list_venn_variables" or action == "query_venn":
            result = list_all_venn_variables()
            if result["success"] and result["variables"]:
                db_response = f"📊 **{result['total']} variables Venn:**\n\n"
                for var in result["variables"]:
                    db_response += f"• **{var['name']}** ({var['proxy_count']} proxies)\n"
                    if var.get('description'):
                        db_response += f"  _{var['description']}_\n"
                db_response += "\n💡 Para ver proxies: 'Muestra la variable X'"
            else:
                db_response = "📭 No hay variables Venn registradas."
        
        elif action == "get_venn_variable":
            result = get_venn_variable(var_name)
            if result.get("found"):
                var = result["variable"]
                db_response = f"📊 **{var['name']}**\n\n"
                db_response += f"📝 {var.get('description') or 'Sin descripción'}\n\n"
                if var['proxies']:
                    db_response += f"**Proxies ({len(var['proxies'])}):**\n"
                    for i, p in enumerate(var['proxies'], 1):
                        term = p['term'][:80] + "..." if len(p['term']) > 80 else p['term']
                        db_response += f"{i}. {term}\n"
                else:
                    db_response += "⚠️ Sin proxies definidos."
            elif result.get("suggestions"):
                db_response = f"🔍 No encontré '{var_name}'. Similares:\n"
                for s in result["suggestions"][:5]:
                    db_response += f"• **{s['name']}**\n"
            else:
                db_response = f"❌ No encontré la variable '{var_name}'."
        
        elif action == "create_venn_variable":
            data = decision.get("data", {})
            result = create_venn_variable(data)
            if result["success"]:
                db_response = f"✅ Variable **{result['created']}** creada."
            else:
                db_response = f"❌ Error: {result['error']}"
        
        elif action == "update_venn_variable":
            update_data = decision.get("update_data", {})
            result = update_venn_variable(var_name, update_data)
            if result["success"]:
                db_response = f"✅ Variable **{result['updated']}** actualizada."
            else:
                db_response = f"❌ Error: {result['error']}"
        
        elif action == "delete_venn_variable":
            result = delete_venn_variable(var_name)
            if result["success"]:
                db_response = f"🗑️ Variable **{result['deleted']}** eliminada."
            else:
                db_response = f"❌ Error: {result['error']}"
        
        elif action == "add_venn_proxy":
            proxy_data = decision.get("proxy_data", {})
            result = add_venn_proxy(var_name, proxy_data)
            if result["success"]:
                db_response = f"✅ Proxy **{result['created']}** añadido a **{result['variable']}**."
            elif result.get("suggestions"):
                db_response = f"🔍 No encontré la variable '{var_name}'. Similares:\n"
                for s in result["suggestions"][:3]:
                    db_response += f"• {s['name']}\n"
            else:
                db_response = f"❌ Error: {result['error']}"
        
        elif action == "delete_venn_proxy":
            proxy_name = decision.get("proxy_name", "")
            result = delete_venn_proxy(var_name, proxy_name)
            if result["success"]:
                db_response = f"🗑️ Proxy eliminado de **{result['variable']}**."
            else:
                db_response = f"❌ Error: {result['error']}"
        
        # ==================== VENN INTERSECTIONS ====================
        
        elif action == "list_venn_intersections":
            result = list_venn_intersections()
            if result["success"] and result["intersections"]:
                db_response = f"🔷 **{result['total']} intersecciones:**\n\n"
                for inter in result["intersections"]:
                    db_response += f"**{inter['name']}** (ID: {inter['id']})\n"
                    if inter.get('use_logic_expression'):
                        db_response += f"  🧮 Expresión: `{inter.get('expression_display', 'N/A')}`\n"
                    elif inter.get('include_proxies'):
                        op = inter.get('operation', 'intersection')
                        db_response += f"  📝 {len(inter['include_proxies'])} proxies ({op})\n"
                    db_response += "\n"
            else:
                db_response = "📭 No hay intersecciones configuradas."
        
        elif action == "create_venn_intersection":
            inter_name = inter_name or decision.get("intersection_name", f"Intersección {__import__('datetime').datetime.now().strftime('%H%M')}")
            inter_op = decision.get("intersection_operation", "intersection")
            include_proxies = decision.get("include_proxies", [])
            logic_expr_text = decision.get("logic_expression_text", "")
            
            # Check for parentheses in user input as fallback
            if not logic_expr_text and '(' in user_input:
                import re
                # Extract expression from user input
                patterns = [
                    r':\s*(.+)',
                    r'expresi[oó]n[^:]*:\s*(.+)',
                ]
                for pattern in patterns:
                    match = re.search(pattern, user_input, re.IGNORECASE)
                    if match:
                        logic_expr_text = match.group(1).strip()
                        break
            
            # Parse logic expression if provided
            parsed_expr = None
            if logic_expr_text:
                session = get_sync_db_session()
                try:
                    parsed_expr = parse_logic_expression_text(logic_expr_text, session)
                    matched = parsed_expr.pop('matched_proxies', [])
                    
                    # Check for unknown proxies
                    def find_unknown(node):
                        unknowns = []
                        if node.get('type') == 'unknown':
                            unknowns.append(node.get('text', '?'))
                        for child in node.get('children', []):
                            unknowns.extend(find_unknown(child))
                        return unknowns
                    
                    unknowns = find_unknown(parsed_expr)
                    if unknowns:
                        db_response = f"❌ Proxies no encontrados: {', '.join(unknowns[:3])}"
                        parsed_expr = None
                finally:
                    session.close()
            
            if parsed_expr or include_proxies:
                result = create_venn_intersection(
                    name=inter_name,
                    operation=inter_op,
                    include_proxies=include_proxies if include_proxies else None,
                    logic_expression=parsed_expr
                )
                if result["success"]:
                    db_response = f"✅ Intersección **{result['created']}** creada.\n"
                    db_response += f"- Modo: {result['mode']}\n"
                    if result.get('expression_display'):
                        db_response += f"- Expresión: `{result['expression_display']}`\n"
                else:
                    db_response = f"❌ Error: {result['error']}"
            elif not db_response:
                db_response = "❌ Se requiere expresión lógica o lista de proxies."
        
        elif action == "delete_venn_intersection":
            result = delete_venn_intersection(name=inter_name)
            if result["success"]:
                db_response = f"🗑️ Intersección **{result['deleted']}** eliminada."
            else:
                db_response = f"❌ Error: {result['error']}"
        
        elif action == "update_venn_intersection":
            new_op = decision.get("new_operation")
            include_proxies = decision.get("include_proxies")
            result = update_venn_intersection(
                name=inter_name,
                new_operation=new_op,
                include_proxies=include_proxies
            )
            if result["success"]:
                db_response = f"✅ Intersección **{result['updated']}** actualizada."
            else:
                db_response = f"❌ Error: {result['error']}"
        
        # ==================== OTHER ====================
        
        elif action == "trigger_scrape":
            result = get_organization_by_name(org_name or search_term)
            if result["found"]:
                org = result["organization"]
                return {
                    **state,
                    "current_agent": "scraper",
                    "task_description": f"Buscar info sobre {org['name']}",
                    "db_response": f"🔍 Iniciando scraping para **{org['name']}**...",
                }
            else:
                db_response = f"❌ No encontré la organización para scraping."
        
        elif action == "no_db_action":
            db_response = None
        
        else:
            db_response = f"⚠️ Acción no reconocida: {action}"
        
        return {
            **state,
            "current_agent": "finalizer",
            "db_response": db_response,
            "iterations": state.get("iterations", 0) + 1,
        }
    
    except Exception as e:
        import traceback
        return {
            **state,
            "current_agent": "finalizer",
            "db_response": f"❌ Error en consulta de BD: {str(e)}",
            "iterations": state.get("iterations", 0) + 1,
        }
