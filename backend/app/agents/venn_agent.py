"""
Venn Agent

Responsible for managing Venn variables, proxies, and results from the chat interface.
Allows users to create, update, and delete Venn diagram components through natural language.

Uses GPT-4o-mini for intent parsing and response generation.

Enhanced with match evidence tracking for full traceability.
"""
import os
import json
import re
from typing import TYPE_CHECKING, List, Dict, Any, Optional, Tuple
from datetime import datetime

from openai import OpenAI
from langsmith import traceable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, and_

if TYPE_CHECKING:
    from .graph import AgentState

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


VENN_AGENT_SYSTEM_PROMPT = """Eres un agente especializado en gestionar variables Venn, proxies y resultados para un sistema de análisis de organizaciones de la sociedad civil lideradas por mujeres en Colombia.

Tu tarea es interpretar las solicitudes del usuario relacionadas con:
1. **Variables Venn**: Dimensiones de análisis (ej: "Liderazgo Femenino", "Construcción de Paz", "Alcance Regional")
2. **Proxies**: Términos de búsqueda asociados a cada variable (ej: para "Construcción de Paz": "reconciliación", "víctimas", "proceso de paz")
3. **Resultados Venn**: Valor 0 o 1 que indica si una organización cumple con una variable. Puede ser manual o calculado automáticamente.
4. **Validación Territorial**: El sistema valida que los proxies sean compatibles con el alcance territorial de cada organización.

ACCIONES DISPONIBLES:
- create_variable: Crear nueva variable Venn
- update_variable: Actualizar variable existente
- delete_variable: Eliminar variable
- add_proxy: Agregar proxy a una variable (puede incluir restricciones territoriales)
- remove_proxy: Eliminar proxy de una variable
- set_result: Establecer resultado (0 o 1) para una organización en una variable
- search_proxies: Buscar coincidencias de proxies CON VALIDACIÓN TERRITORIAL
- apply_search: Ejecutar búsqueda de proxies en organizaciones CON VALIDACIÓN TERRITORIAL
- evaluate_organization: Pipeline completo: scrapear → normalizar → evaluar → guardar resultados
- decision_table: Generar tabla de decisión territorial (org × variable × proxies válidos)
- list_variables: Listar variables existentes
- list_results: Listar resultados de una organización o variable
- explain: Explicar al usuario cómo funcionan las variables Venn

VALIDACIÓN TERRITORIAL:
- MUNICIPAL: Solo puede activar proxies MUNICIPALES o universales
- DEPARTAMENTAL: Puede activar MUNICIPALES, DEPARTAMENTALES o universales
- REGIONAL: Puede activar MUNICIPALES, DEPARTAMENTALES, REGIONALES o universales
- NACIONAL/INTERNACIONAL: Puede activar TODOS los tipos de proxies
- Los proxies sin restricción (applicable_scopes=null) son UNIVERSALES y aplican a todos

EJEMPLOS DE SOLICITUDES:
- "Crea una variable llamada 'Liderazgo Femenino'" → create_variable
- "Agrega el proxy 'mujeres líderes' a Liderazgo Femenino" → add_proxy
- "Agrega el proxy 'programa municipal X' con scope municipal a Paz" → add_proxy (con applicable_scopes)
- "Marca la organización 5 como 1 en Construcción de Paz" → set_result (value: true)
- "La organización 3 no cumple con Liderazgo Femenino" → set_result (value: false)
- "Busca proxies de Paz en la organización 7" → search_proxies
- "Evalúa la organización 5" → evaluate_organization (pipeline completo)
- "Aplica la búsqueda de proxies a todas las organizaciones" → apply_search (all: true)
- "Muestra la tabla de decisión territorial" → decision_table
- "¿Qué resultados tiene la organización 5?" → list_results
- "¿Qué variables tenemos?" → list_variables

Responde con un JSON:
{{
    "action": "create_variable|update_variable|delete_variable|add_proxy|remove_proxy|set_result|search_proxies|apply_search|evaluate_organization|decision_table|list_variables|list_results|explain",
    "params": {{
        "variable_name": "nombre de la variable (si aplica)",
        "description": "descripción (si aplica)",
        "proxy_term": "término del proxy (si aplica)",
        "is_regex": false,
        "weight": 1.0,
        "applicable_scopes": null,
        "organization_id": null,
        "value": true,
        "all_organizations": false,
        "force_rescrape": false,
        "include_rejected": false,
        "data_type": "list|count|boolean"
    }},
    "reasoning": "Tu razonamiento",
    "user_message": "Mensaje amigable para el usuario explicando lo que vas a hacer"
}}

NOTAS SOBRE RESULTADOS:
- Un resultado de 1 (true) indica que la organización CUMPLE con la variable
- Un resultado de 0 (false) indica que NO CUMPLE
- Los resultados pueden ser manuales (el usuario los marca) o automáticos (calculados por búsqueda de proxies)
- La búsqueda de proxies analiza el contenido scrapeado Y valida compatibilidad territorial
- Los proxies rechazados por scope NO se consideran para el resultado final

Si no entiendes la solicitud, usa action: "explain" para guiar al usuario."""


@traceable(name="venn_agent_node")
async def venn_agent_node(state: "AgentState") -> Dict[str, Any]:
    """
    Venn agent node for LangGraph.
    
    Handles Venn variable, proxy, and result management from chat.
    """
    from app.models.db_models import VennVariable, VennProxy
    from app.db.base import async_session_maker
    
    user_input = state.get("user_input", "")
    
    try:
        # Parse user intent
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": VENN_AGENT_SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_input
                }
            ],
            temperature=0.1,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        result = json.loads(response.choices[0].message.content)
        action = result.get("action", "explain")
        params = result.get("params", {})
        user_message = result.get("user_message", "")
        
        # Execute action with database session
        async with async_session_maker() as db:
            action_result = await execute_venn_action(db, action, params)
        
        # Combine user message with action result
        final_message = f"{user_message}\n\n{action_result['message']}"
        
        return {
            "venn_response": final_message,
            "venn_action_result": action_result,
            "next_agent": "finalizer"
        }
        
    except Exception as e:
        return {
            "venn_response": f"❌ Error al procesar la solicitud de Venn: {str(e)}",
            "errors": [str(e)],
            "next_agent": "finalizer"
        }


# ============================================================================
# MATCH EVIDENCE HELPERS
# ============================================================================

def find_matches_with_context(
    text: str, 
    term: str, 
    is_regex: bool = False,
    context_chars: int = 150
) -> List[Dict[str, Any]]:
    """
    Find all matches of a term in text and extract surrounding context.
    
    Returns list of matches with:
    - matched_text: The exact matched portion
    - text_fragment: Surrounding context (context_chars before and after)
    - position: Character position in text
    - paragraph_number: Estimated paragraph based on double newlines
    """
    matches = []
    text_lower = text.lower()
    term_lower = term.lower()
    
    if is_regex:
        try:
            pattern = re.compile(term, re.IGNORECASE)
            for match in pattern.finditer(text):
                start = max(0, match.start() - context_chars)
                end = min(len(text), match.end() + context_chars)
                
                # Estimate paragraph number
                paragraphs_before = text[:match.start()].count('\n\n')
                
                matches.append({
                    "matched_text": match.group(),
                    "text_fragment": text[start:end].strip(),
                    "position": match.start(),
                    "paragraph_number": paragraphs_before + 1,
                    "is_exact_match": True
                })
        except re.error:
            pass
    else:
        # Simple substring search
        start_pos = 0
        while True:
            pos = text_lower.find(term_lower, start_pos)
            if pos == -1:
                break
            
            # Extract context
            ctx_start = max(0, pos - context_chars)
            ctx_end = min(len(text), pos + len(term) + context_chars)
            
            # Estimate paragraph number
            paragraphs_before = text[:pos].count('\n\n')
            
            matches.append({
                "matched_text": text[pos:pos + len(term)],
                "text_fragment": text[ctx_start:ctx_end].strip(),
                "position": pos,
                "paragraph_number": paragraphs_before + 1,
                "is_exact_match": True
            })
            
            start_pos = pos + 1
    
    return matches


def determine_source_type(url: str) -> str:
    """Determine the type of source based on URL patterns."""
    url_lower = url.lower()
    
    if '.pdf' in url_lower:
        return 'pdf'
    elif any(gov in url_lower for gov in ['.gov.co', 'gobierno', 'mininterior', 'dane']):
        return 'government'
    elif any(social in url_lower for social in ['facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com']):
        return 'social_media'
    elif any(news in url_lower for news in ['eltiempo', 'elespectador', 'semana', 'noticias']):
        return 'news'
    elif 'camara' in url_lower or 'registro' in url_lower or 'confecamaras' in url_lower:
        return 'registry'
    elif '/about' in url_lower or '/nosotros' in url_lower or '/quienes-somos' in url_lower:
        return 'subpage'
    elif '/servicios' in url_lower or '/programas' in url_lower or '/proyectos' in url_lower:
        return 'subpage'
    else:
        return 'main_page'


async def create_match_evidence(
    db: AsyncSession,
    venn_result_id: int,
    proxy_id: int,
    source_url: str,
    match_info: Dict[str, Any],
    page_title: Optional[str] = None,
    scraping_session_id: Optional[int] = None
) -> None:
    """
    Create a VennMatchEvidence record for a proxy match.
    """
    from app.models.db_models import VennMatchEvidence, SourceType
    
    source_type_str = determine_source_type(source_url)
    try:
        source_type = SourceType(source_type_str)
    except ValueError:
        source_type = SourceType.OTHER
    
    evidence = VennMatchEvidence(
        venn_result_id=venn_result_id,
        venn_proxy_id=proxy_id,
        source_url=source_url,
        source_type=source_type,
        matched_text=match_info.get("matched_text"),
        text_fragment=match_info.get("text_fragment"),
        paragraph_number=match_info.get("paragraph_number"),
        is_exact_match=match_info.get("is_exact_match", True),
        match_score=match_info.get("match_score", 1.0),
        page_title=page_title,
        scraping_session_id=scraping_session_id,
        scraped_at=datetime.utcnow()
    )
    
    db.add(evidence)


async def execute_venn_action(db: AsyncSession, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the Venn action based on parsed intent."""
    from app.models.db_models import VennVariable, VennProxy
    
    try:
        if action == "create_variable":
            return await create_venn_variable(db, params)
        elif action == "update_variable":
            return await update_venn_variable(db, params)
        elif action == "delete_variable":
            return await delete_venn_variable(db, params)
        elif action == "add_proxy":
            return await add_venn_proxy(db, params)
        elif action == "remove_proxy":
            return await remove_venn_proxy(db, params)
        elif action == "add_result":
            return await add_venn_result(db, params)
        elif action == "set_result":
            return await set_venn_result(db, params)
        elif action == "search_proxies":
            return await search_venn_proxies(db, params)
        elif action == "apply_search":
            return await apply_search_results(db, params)
        elif action == "list_variables":
            return await list_venn_variables(db)
        elif action == "list_results":
            return await list_venn_results(db, params)
        elif action == "evaluate_organization":
            return await scrape_and_evaluate_organization(db, params)
        elif action == "decision_table":
            return await get_territorial_decision_table(db, params)
        elif action == "explain":
            return {
                "success": True,
                "message": get_venn_explanation()
            }
        else:
            return {
                "success": False,
                "message": f"❓ Acción no reconocida: {action}"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Error ejecutando acción: {str(e)}"
        }


async def create_venn_variable(db: AsyncSession, params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a new Venn variable."""
    from app.models.db_models import VennVariable
    
    name = params.get("variable_name", "").strip()
    if not name:
        return {"success": False, "message": "❌ Se requiere un nombre para la variable."}
    
    # Check if exists
    existing = await db.execute(
        select(VennVariable).where(VennVariable.name == name)
    )
    if existing.scalar_one_or_none():
        return {"success": False, "message": f"⚠️ Ya existe una variable con el nombre '{name}'."}
    
    variable = VennVariable(
        name=name,
        description=params.get("description", ""),
        data_type=params.get("data_type", "list")
    )
    
    db.add(variable)
    await db.commit()
    await db.refresh(variable)
    
    return {
        "success": True,
        "message": f"✅ Variable **{name}** creada exitosamente (ID: {variable.id})",
        "variable_id": variable.id
    }


async def update_venn_variable(db: AsyncSession, params: Dict[str, Any]) -> Dict[str, Any]:
    """Update an existing Venn variable."""
    from app.models.db_models import VennVariable
    
    name = params.get("variable_name", "").strip()
    if not name:
        return {"success": False, "message": "❌ Se requiere el nombre de la variable a actualizar."}
    
    result = await db.execute(
        select(VennVariable).where(VennVariable.name == name)
    )
    variable = result.scalar_one_or_none()
    
    if not variable:
        return {"success": False, "message": f"❌ No se encontró la variable '{name}'."}
    
    if params.get("description"):
        variable.description = params["description"]
    if params.get("data_type"):
        variable.data_type = params["data_type"]
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"✅ Variable **{name}** actualizada exitosamente."
    }


async def delete_venn_variable(db: AsyncSession, params: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a Venn variable."""
    from app.models.db_models import VennVariable
    
    name = params.get("variable_name", "").strip()
    if not name:
        return {"success": False, "message": "❌ Se requiere el nombre de la variable a eliminar."}
    
    result = await db.execute(
        select(VennVariable).where(VennVariable.name == name)
    )
    variable = result.scalar_one_or_none()
    
    if not variable:
        return {"success": False, "message": f"❌ No se encontró la variable '{name}'."}
    
    await db.delete(variable)
    await db.commit()
    
    return {
        "success": True,
        "message": f"✅ Variable **{name}** eliminada exitosamente (incluyendo sus proxies)."
    }


async def add_venn_proxy(db: AsyncSession, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Add a proxy to a Venn variable.
    
    Supports territorial scope restrictions:
    - applicable_scopes: List of scopes where this proxy can be activated
      Valid values: ["MUNICIPAL", "DEPARTAMENTAL", "REGIONAL", "NACIONAL", "INTERNACIONAL"]
      If null/empty: Proxy applies to ALL scopes (universal proxy)
    
    - location_restriction: Dict with department/municipality codes
      Example: {"department_code": "05", "municipality_code": "05001"}
      If null: No location restriction
    """
    from app.models.db_models import VennVariable, VennProxy, TerritorialScope
    
    var_name = params.get("variable_name", "").strip()
    proxy_term = params.get("proxy_term", "").strip()
    
    if not var_name or not proxy_term:
        return {"success": False, "message": "❌ Se requiere el nombre de la variable y el término del proxy."}
    
    result = await db.execute(
        select(VennVariable).where(VennVariable.name == var_name)
    )
    variable = result.scalar_one_or_none()
    
    if not variable:
        return {"success": False, "message": f"❌ No se encontró la variable '{var_name}'."}
    
    # Check if proxy already exists
    existing = await db.execute(
        select(VennProxy).where(
            VennProxy.venn_variable_id == variable.id,
            VennProxy.term == proxy_term
        )
    )
    if existing.scalar_one_or_none():
        return {"success": False, "message": f"⚠️ El proxy '{proxy_term}' ya existe en la variable '{var_name}'."}
    
    # Process applicable_scopes
    applicable_scopes = params.get("applicable_scopes")
    if applicable_scopes:
        # Validate scope values
        valid_scopes = [s.value for s in TerritorialScope]
        if isinstance(applicable_scopes, str):
            applicable_scopes = [applicable_scopes.upper()]
        else:
            applicable_scopes = [s.upper() for s in applicable_scopes]
        
        invalid_scopes = [s for s in applicable_scopes if s not in valid_scopes]
        if invalid_scopes:
            return {
                "success": False,
                "message": f"❌ Scopes inválidos: {invalid_scopes}. Válidos: {valid_scopes}"
            }
    
    # Process location_restriction
    location_restriction = params.get("location_restriction")
    
    proxy = VennProxy(
        venn_variable_id=variable.id,
        term=proxy_term,
        is_regex=params.get("is_regex", False),
        weight=params.get("weight", 1.0),
        applicable_scopes=applicable_scopes,
        location_restriction=location_restriction
    )
    
    db.add(proxy)
    await db.commit()
    
    # Build confirmation message
    scope_info = ""
    if applicable_scopes:
        scope_info = f"\n   📍 Scopes válidos: {', '.join(applicable_scopes)}"
    else:
        scope_info = "\n   📍 Scope: Universal (aplica a todos los alcances)"
    
    if location_restriction:
        scope_info += f"\n   📌 Restricción de ubicación: {location_restriction}"
    
    return {
        "success": True,
        "message": f"✅ Proxy **'{proxy_term}'** agregado a la variable **{var_name}**.{scope_info}"
    }


async def remove_venn_proxy(db: AsyncSession, params: Dict[str, Any]) -> Dict[str, Any]:
    """Remove a proxy from a Venn variable."""
    from app.models.db_models import VennVariable, VennProxy
    
    var_name = params.get("variable_name", "").strip()
    proxy_term = params.get("proxy_term", "").strip()
    
    if not var_name or not proxy_term:
        return {"success": False, "message": "❌ Se requiere el nombre de la variable y el término del proxy."}
    
    result = await db.execute(
        select(VennVariable).where(VennVariable.name == var_name)
    )
    variable = result.scalar_one_or_none()
    
    if not variable:
        return {"success": False, "message": f"❌ No se encontró la variable '{var_name}'."}
    
    proxy_result = await db.execute(
        select(VennProxy).where(
            VennProxy.venn_variable_id == variable.id,
            VennProxy.term == proxy_term
        )
    )
    proxy = proxy_result.scalar_one_or_none()
    
    if not proxy:
        return {"success": False, "message": f"❌ No se encontró el proxy '{proxy_term}' en la variable '{var_name}'."}
    
    await db.delete(proxy)
    await db.commit()
    
    return {
        "success": True,
        "message": f"✅ Proxy **'{proxy_term}'** eliminado de la variable **{var_name}**."
    }


async def add_venn_result(db: AsyncSession, params: Dict[str, Any]) -> Dict[str, Any]:
    """Add a manual result to a Venn variable (stores in description for now)."""
    from app.models.db_models import VennVariable
    
    var_name = params.get("variable_name", "").strip()
    result_value = params.get("result_value", "")
    
    if not var_name:
        return {"success": False, "message": "❌ Se requiere el nombre de la variable."}
    
    result = await db.execute(
        select(VennVariable).where(VennVariable.name == var_name)
    )
    variable = result.scalar_one_or_none()
    
    if not variable:
        return {"success": False, "message": f"❌ No se encontró la variable '{var_name}'."}
    
    # Append result to description (simple approach)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    result_note = f"\n[{timestamp}] Resultado manual: {result_value}"
    variable.description = (variable.description or "") + result_note
    
    await db.commit()
    
    return {
        "success": True,
        "message": f"✅ Resultado **'{result_value}'** registrado para la variable **{var_name}**."
    }


async def list_venn_variables(db: AsyncSession) -> Dict[str, Any]:
    """List all Venn variables with their proxies."""
    from app.models.db_models import VennVariable, VennProxy
    
    result = await db.execute(select(VennVariable))
    variables = result.scalars().all()
    
    if not variables:
        return {
            "success": True,
            "message": "📋 No hay variables Venn definidas todavía.\n\nPuedes crear una con: *'Crea una variable llamada [nombre]'*"
        }
    
    lines = ["📊 **Variables Venn existentes:**\n"]
    
    for var in variables:
        proxies_result = await db.execute(
            select(VennProxy).where(VennProxy.venn_variable_id == var.id)
        )
        proxies = proxies_result.scalars().all()
        
        lines.append(f"### {var.name}")
        if var.description:
            lines.append(f"   *{var.description[:100]}{'...' if len(var.description) > 100 else ''}*")
        lines.append(f"   Tipo: {var.data_type}")
        
        if proxies:
            proxy_terms = [p.term for p in proxies]
            lines.append(f"   Proxies: {', '.join(proxy_terms[:5])}")
            if len(proxy_terms) > 5:
                lines.append(f"   ... y {len(proxy_terms) - 5} más")
        else:
            lines.append("   Proxies: ninguno")
        
        lines.append("")
    
    return {
        "success": True,
        "message": "\n".join(lines)
    }


async def set_venn_result(db: AsyncSession, params: Dict[str, Any]) -> Dict[str, Any]:
    """Set a Venn result (0 or 1) for an organization-variable pair."""
    from app.models.db_models import VennVariable, VennResult, VennResultSource, Organization
    from sqlalchemy import and_
    
    var_name = params.get("variable_name", "").strip()
    org_id = params.get("organization_id")
    value = params.get("value", True)  # True = 1, False = 0
    
    if not var_name or not org_id:
        return {"success": False, "message": "❌ Se requiere el nombre de la variable y el ID de la organización."}
    
    # Get variable
    var_result = await db.execute(
        select(VennVariable).where(VennVariable.name == var_name)
    )
    variable = var_result.scalar_one_or_none()
    if not variable:
        return {"success": False, "message": f"❌ No se encontró la variable '{var_name}'."}
    
    # Get organization
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    organization = org_result.scalar_one_or_none()
    if not organization:
        return {"success": False, "message": f"❌ No se encontró la organización con ID {org_id}."}
    
    # Check if result exists
    existing_result = await db.execute(
        select(VennResult).where(
            and_(
                VennResult.organization_id == org_id,
                VennResult.venn_variable_id == variable.id
            )
        )
    )
    existing = existing_result.scalar_one_or_none()
    
    if existing:
        existing.value = value
        if existing.source == VennResultSource.AUTOMATIC:
            existing.source = VennResultSource.MIXED
        else:
            existing.source = VennResultSource.MANUAL
        await db.commit()
        return {
            "success": True,
            "message": f"✅ Resultado actualizado: **{organization.name}** = {'1 (cumple)' if value else '0 (no cumple)'} en **{var_name}**"
        }
    else:
        new_result = VennResult(
            organization_id=org_id,
            venn_variable_id=variable.id,
            value=value,
            source=VennResultSource.MANUAL
        )
        db.add(new_result)
        await db.commit()
        return {
            "success": True,
            "message": f"✅ Resultado creado: **{organization.name}** = {'1 (cumple)' if value else '0 (no cumple)'} en **{var_name}**"
        }


async def search_venn_proxies(db: AsyncSession, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for proxy matches in an organization's data.
    
    Includes TERRITORIAL VALIDATION:
    - Proxies are filtered by applicable_scopes based on organization's territorial_scope
    - Location-specific proxies are validated against organization's department/municipality codes
    """
    from app.models.db_models import VennVariable, VennProxy, Organization, ScrapedData, TerritorialScope
    from app.services.territorial_validation import (
        validate_proxy_for_organization,
        explain_scope_compatibility
    )
    import re
    
    org_id = params.get("organization_id")
    var_name = params.get("variable_name", "").strip()
    include_rejected = params.get("include_rejected", False)  # Show rejected proxies
    
    if not org_id:
        return {"success": False, "message": "❌ Se requiere el ID de la organización."}
    
    # Get organization
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    organization = org_result.scalar_one_or_none()
    if not organization:
        return {"success": False, "message": f"❌ No se encontró la organización con ID {org_id}."}
    
    # Get organization's scope for validation
    org_scope = organization.territorial_scope or TerritorialScope.MUNICIPAL
    
    # Get scraped data
    scraped_result = await db.execute(
        select(ScrapedData).where(ScrapedData.organization_id == org_id)
    )
    scraped_data = scraped_result.scalars().all()
    
    # Combine all text from scraped data
    all_text = ""
    source_urls = []
    for sd in scraped_data:
        # variable_value is the JSON field with scraped content
        if sd.variable_value:
            if isinstance(sd.variable_value, dict):
                # Extract text from various possible structures
                content_text = sd.variable_value.get("text", sd.variable_value.get("data", str(sd.variable_value)))
            else:
                content_text = str(sd.variable_value)
            all_text += " " + content_text.lower()
        if sd.source_url and sd.source_url not in source_urls:
            source_urls.append(sd.source_url)
    
    # Also check organization description and URL
    if organization.description:
        all_text += " " + organization.description.lower()
    if organization.url:
        all_text += " " + organization.url.lower()
    
    # Get variables to search
    if var_name:
        vars_result = await db.execute(
            select(VennVariable).where(VennVariable.name == var_name)
        )
    else:
        vars_result = await db.execute(select(VennVariable))
    
    variables = vars_result.scalars().all()
    
    if not variables:
        return {"success": False, "message": "❌ No hay variables Venn definidas."}
    
    # Build report header
    lines = [
        f"🔍 **Resultados de búsqueda para '{organization.name}'**",
        f"📍 Alcance territorial: **{org_scope.value}**",
        f"ℹ️ {explain_scope_compatibility(org_scope)}",
        ""
    ]
    
    total_proxies_checked = 0
    total_proxies_rejected_scope = 0
    total_matches = 0
    
    for variable in variables:
        proxies_result = await db.execute(
            select(VennProxy).where(VennProxy.venn_variable_id == variable.id)
        )
        proxies = proxies_result.scalars().all()
        
        matched = []
        rejected_proxies = []
        
        for proxy in proxies:
            total_proxies_checked += 1
            
            # TERRITORIAL VALIDATION
            validation = validate_proxy_for_organization(organization, proxy)
            
            if not validation["is_valid"]:
                # Proxy rejected due to territorial incompatibility
                total_proxies_rejected_scope += 1
                rejected_proxies.append({
                    "term": proxy.term,
                    "reason": validation["reason"]
                })
                continue  # Skip this proxy
            
            # Proxy passed territorial validation - check for text match
            term = proxy.term.lower()
            if proxy.is_regex:
                try:
                    if re.search(term, all_text, re.IGNORECASE):
                        matched.append({
                            "term": proxy.term,
                            "weight": proxy.weight,
                            "scopes": proxy.applicable_scopes
                        })
                except re.error:
                    pass
            else:
                if term in all_text:
                    matched.append({
                        "term": proxy.term,
                        "weight": proxy.weight,
                        "scopes": proxy.applicable_scopes
                    })
        
        status = "✅" if matched else "❌"
        lines.append(f"{status} **{variable.name}**: ")
        
        if matched:
            total_matches += len(matched)
            match_terms = [m["term"] for m in matched]
            lines.append(f"   Coincidencias: {', '.join(match_terms)}")
        else:
            lines.append("   Sin coincidencias válidas")
        
        # Show rejected proxies if requested
        if include_rejected and rejected_proxies:
            lines.append(f"   ⚠️ Proxies rechazados por scope ({len(rejected_proxies)}):")
            for rp in rejected_proxies[:3]:  # Limit to 3
                lines.append(f"      - '{rp['term']}': {rp['reason']}")
            if len(rejected_proxies) > 3:
                lines.append(f"      ... y {len(rejected_proxies) - 3} más")
        
        lines.append("")
    
    # Summary
    lines.append("---")
    lines.append(f"📊 **Resumen:**")
    lines.append(f"   - Proxies evaluados: {total_proxies_checked}")
    lines.append(f"   - Proxies válidos (coinciden scope): {total_proxies_checked - total_proxies_rejected_scope}")
    lines.append(f"   - Proxies rechazados (scope incompatible): {total_proxies_rejected_scope}")
    lines.append(f"   - Coincidencias de texto: {total_matches}")
    
    return {
        "success": True,
        "message": "\n".join(lines),
        "stats": {
            "total_proxies": total_proxies_checked,
            "valid_proxies": total_proxies_checked - total_proxies_rejected_scope,
            "rejected_by_scope": total_proxies_rejected_scope,
            "text_matches": total_matches
        }
    }


async def apply_search_results(db: AsyncSession, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply proxy search and save results automatically.
    
    Includes TERRITORIAL VALIDATION:
    - Only proxies with compatible territorial scopes are considered
    - Results track which proxies were rejected due to scope mismatch
    """
    from app.models.db_models import (
        VennVariable, VennProxy, VennResult, VennResultSource, 
        VennResultStatus, Organization, ScrapedData, TerritorialScope
    )
    from app.services.territorial_validation import validate_proxy_for_organization
    from sqlalchemy import and_
    import re
    
    org_id = params.get("organization_id")
    all_orgs = params.get("all_organizations", False)
    var_name = params.get("variable_name", "").strip()
    
    # Get organizations
    if all_orgs:
        orgs_result = await db.execute(select(Organization))
        organizations = orgs_result.scalars().all()
    elif org_id:
        org_result = await db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        org = org_result.scalar_one_or_none()
        if not org:
            return {"success": False, "message": f"❌ No se encontró la organización con ID {org_id}."}
        organizations = [org]
    else:
        return {"success": False, "message": "❌ Se requiere organization_id o all_organizations=true."}
    
    # Get variables
    if var_name:
        vars_result = await db.execute(
            select(VennVariable).where(VennVariable.name == var_name)
        )
    else:
        vars_result = await db.execute(select(VennVariable))
    
    variables = vars_result.scalars().all()
    if not variables:
        return {"success": False, "message": "❌ No hay variables Venn definidas."}
    
    # Statistics tracking
    total_results = 0
    total_matched = 0
    total_proxies_evaluated = 0
    total_proxies_rejected_scope = 0
    orgs_by_scope = {}  # Track orgs by territorial scope
    
    for organization in organizations:
        # Track by scope
        org_scope = organization.territorial_scope or TerritorialScope.MUNICIPAL
        scope_name = org_scope.value
        if scope_name not in orgs_by_scope:
            orgs_by_scope[scope_name] = 0
        orgs_by_scope[scope_name] += 1
        
        # Get scraped data
        scraped_result = await db.execute(
            select(ScrapedData).where(ScrapedData.organization_id == organization.id)
        )
        scraped_data = scraped_result.scalars().all()
        
        # Combine text from scraped data
        all_text = ""
        source_urls = []
        for sd in scraped_data:
            # variable_value is the JSON field with scraped content
            if sd.variable_value:
                if isinstance(sd.variable_value, dict):
                    content_text = sd.variable_value.get("text", sd.variable_value.get("data", str(sd.variable_value)))
                else:
                    content_text = str(sd.variable_value)
                all_text += " " + content_text.lower()
            if sd.source_url and sd.source_url not in source_urls:
                source_urls.append(sd.source_url)
        if organization.description:
            all_text += " " + organization.description.lower()
        if organization.url:
            all_text += " " + organization.url.lower()
        
        for variable in variables:
            proxies_result = await db.execute(
                select(VennProxy).where(VennProxy.venn_variable_id == variable.id)
            )
            proxies = proxies_result.scalars().all()
            
            matched_proxies = []
            matched_proxy_details = []  # Store detailed match info for evidence
            rejected_proxies = []  # Track rejected by scope
            score = 0.0
            
            for proxy in proxies:
                total_proxies_evaluated += 1
                
                # TERRITORIAL VALIDATION
                validation = validate_proxy_for_organization(organization, proxy)
                
                if not validation["is_valid"]:
                    # Proxy rejected due to territorial incompatibility
                    total_proxies_rejected_scope += 1
                    rejected_proxies.append({
                        "term": proxy.term,
                        "reason": validation["reason"],
                        "proxy_scopes": proxy.applicable_scopes
                    })
                    continue  # Skip this proxy
                
                # Proxy passed territorial validation - check for text match with context
                matches_found = find_matches_with_context(all_text, proxy.term, proxy.is_regex)
                
                if matches_found:
                    matched_proxies.append(proxy.term)
                    score += proxy.weight
                    
                    # Store match details for evidence creation
                    matched_proxy_details.append({
                        "proxy_id": proxy.id,
                        "proxy_term": proxy.term,
                        "matches": matches_found[:3],  # Limit to 3 matches per proxy
                        "weight": proxy.weight
                    })
            
            value = len(matched_proxies) > 0
            
            # Build notes with territorial validation info
            validation_notes = f"Org scope: {scope_name}. "
            if rejected_proxies:
                validation_notes += f"Rejected {len(rejected_proxies)} proxies by scope. "
            validation_notes += f"Evaluated {len(proxies)} proxies total."
            
            # Check if result exists
            existing_result = await db.execute(
                select(VennResult).where(
                    and_(
                        VennResult.organization_id == organization.id,
                        VennResult.venn_variable_id == variable.id
                    )
                )
            )
            existing = existing_result.scalar_one_or_none()
            
            result_id = None
            if existing:
                existing.value = value
                existing.source = VennResultSource.AUTOMATIC
                existing.search_score = score
                existing.matched_proxies = matched_proxies
                existing.source_urls = source_urls[:5]  # Limit URLs
                existing.notes = validation_notes
                existing.verification_status = VennResultStatus.PENDING
                result_id = existing.id
            else:
                new_result = VennResult(
                    organization_id=organization.id,
                    venn_variable_id=variable.id,
                    value=value,
                    source=VennResultSource.AUTOMATIC,
                    search_score=score,
                    matched_proxies=matched_proxies,
                    source_urls=source_urls[:5],
                    notes=validation_notes,
                    verification_status=VennResultStatus.PENDING
                )
                db.add(new_result)
                await db.flush()  # Get the ID before commit
                result_id = new_result.id
            
            # Create match evidence for each matched proxy
            if result_id and matched_proxy_details:
                for proxy_detail in matched_proxy_details:
                    for match in proxy_detail["matches"]:
                        # Use first available source URL or organization URL
                        evidence_url = source_urls[0] if source_urls else (organization.url or "unknown")
                        await create_match_evidence(
                            db=db,
                            venn_result_id=result_id,
                            proxy_id=proxy_detail["proxy_id"],
                            source_url=evidence_url,
                            match_info={
                                "matched_text": match.get("matched_text"),
                                "text_fragment": match.get("text_fragment"),
                                "paragraph_number": match.get("paragraph_number"),
                                "is_exact_match": match.get("is_exact_match", True),
                                "match_score": proxy_detail["weight"]
                            },
                            page_title=organization.name
                        )
            
            total_results += 1
            if value:
                total_matched += 1
    
    await db.commit()
    
    # Build detailed summary
    scope_breakdown = ", ".join([f"{k}: {v}" for k, v in orgs_by_scope.items()])
    
    return {
        "success": True,
        "message": (
            f"✅ **Búsqueda con validación territorial completada**\n\n"
            f"📊 **Organizaciones:**\n"
            f"   - Procesadas: {len(organizations)}\n"
            f"   - Por alcance: {scope_breakdown}\n\n"
            f"📋 **Resultados:**\n"
            f"   - Total evaluaciones: {total_results}\n"
            f"   - Coincidencias (valor=1): {total_matched}\n"
            f"   - No coincidencias (valor=0): {total_results - total_matched}\n\n"
            f"🔍 **Proxies:**\n"
            f"   - Evaluados: {total_proxies_evaluated}\n"
            f"   - Rechazados por scope: {total_proxies_rejected_scope}\n"
            f"   - Tasa de filtrado: {(total_proxies_rejected_scope/total_proxies_evaluated*100):.1f}%" if total_proxies_evaluated > 0 else ""
        ),
        "stats": {
            "organizations": len(organizations),
            "orgs_by_scope": orgs_by_scope,
            "total_results": total_results,
            "matches": total_matched,
            "proxies_evaluated": total_proxies_evaluated,
            "proxies_rejected_scope": total_proxies_rejected_scope
        }
    }


async def list_venn_results(db: AsyncSession, params: Dict[str, Any]) -> Dict[str, Any]:
    """List Venn results for an organization or variable."""
    from app.models.db_models import VennVariable, VennResult, Organization
    
    org_id = params.get("organization_id")
    var_name = params.get("variable_name", "").strip()
    
    query = select(VennResult)
    
    if org_id:
        query = query.where(VennResult.organization_id == org_id)
    if var_name:
        var_result = await db.execute(
            select(VennVariable).where(VennVariable.name == var_name)
        )
        variable = var_result.scalar_one_or_none()
        if variable:
            query = query.where(VennResult.venn_variable_id == variable.id)
    
    results_result = await db.execute(query)
    results = results_result.scalars().all()
    
    if not results:
        return {
            "success": True,
            "message": "📋 No hay resultados Venn registrados para los criterios especificados."
        }
    
    lines = ["📊 **Resultados Venn:**\n"]
    
    for r in results:
        # Get names
        org_result = await db.execute(
            select(Organization.name).where(Organization.id == r.organization_id)
        )
        org_name = org_result.scalar_one_or_none() or f"Org #{r.organization_id}"
        
        var_result = await db.execute(
            select(VennVariable.name).where(VennVariable.id == r.venn_variable_id)
        )
        var_name = var_result.scalar_one_or_none() or f"Var #{r.venn_variable_id}"
        
        value_str = "✅ 1 (cumple)" if r.value else "❌ 0 (no cumple)"
        source_str = f"({r.source.value if r.source else 'manual'})"
        
        lines.append(f"• **{org_name}** → {var_name}: {value_str} {source_str}")
        
        if r.matched_proxies:
            lines.append(f"  Proxies: {', '.join(r.matched_proxies[:3])}")
    
    return {
        "success": True,
        "message": "\n".join(lines)
    }


def get_venn_explanation() -> str:
    """Get explanation of Venn variables system."""
    return """
📊 **Sistema de Variables Venn**

Las variables Venn te permiten analizar y visualizar datos de organizaciones desde múltiples dimensiones.

**Componentes:**
1. **Variable**: Una dimensión de análisis (ej: "Liderazgo Femenino", "Construcción de Paz")
2. **Proxies**: Términos de búsqueda asociados que identifican la variable en los datos
3. **Resultados**: Valor 0 o 1 que indica si una organización cumple con la variable

**Comandos disponibles:**
- *"Crea una variable llamada [nombre]"* - Nueva variable
- *"Agrega el proxy '[término]' a [variable]"* - Nuevo proxy
- *"Elimina el proxy '[término]' de [variable]"* - Borrar proxy
- *"Elimina la variable [nombre]"* - Borrar variable
- *"Marca la organización [ID] como 1 en [variable]"* - Marcar como cumple
- *"La organización [ID] no cumple con [variable]"* - Marcar como no cumple
- *"Busca proxies en la organización [ID]"* - Ver coincidencias
- *"Aplica búsqueda a todas las organizaciones"* - Calcular resultados automáticos
- *"¿Qué resultados tiene la organización [ID]?"* - Ver resultados
- *"¿Qué variables tenemos?"* - Listar todas

**Validación Territorial:**
- Los proxies pueden tener restricciones de alcance territorial
- Una organización MUNICIPAL solo puede activar proxies MUNICIPALES o universales
- Una organización NACIONAL puede activar TODOS los tipos de proxies
- Usa *"Evalúa la organización [ID]"* para ver resultados con validación territorial

**Ejemplo de flujo:**
1. Crea variable "Construcción de Paz"
2. Agrega proxies: "reconciliación", "víctimas", "proceso de paz"
3. Ejecuta búsqueda automática en todas las organizaciones
4. Revisa y ajusta resultados manualmente si es necesario
"""


# ============================================================================
# COMPLETE PIPELINE FUNCTIONS
# ============================================================================

async def scrape_and_evaluate_organization(
    db: AsyncSession, 
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Complete pipeline: Scrape → Normalize → Venn Match → Territorial Validation → Save Results
    
    This function orchestrates the entire flow:
    1. Trigger scraping for the organization (if needed)
    2. Normalize/extract text from scraped content
    3. Search for Venn proxy matches with territorial validation
    4. Save results with full audit trail
    
    Args (in params):
        organization_id: ID of organization to process
        force_rescrape: If True, re-scrape even if data exists (default: False)
        variable_name: Optional - only evaluate specific variable
    
    Returns:
        Detailed report of the pipeline execution
    """
    from app.models.db_models import (
        Organization, ScrapedData, VennVariable, VennProxy,
        VennResult, VennResultSource, VennResultStatus, TerritorialScope
    )
    from app.services.territorial_validation import (
        validate_proxy_for_organization, explain_scope_compatibility
    )
    from app.services.scraper import scrape_organization
    from sqlalchemy import and_
    import re
    
    org_id = params.get("organization_id")
    force_rescrape = params.get("force_rescrape", False)
    var_name = params.get("variable_name", "").strip()
    
    if not org_id:
        return {"success": False, "message": "❌ Se requiere organization_id"}
    
    # Step 1: Get organization
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id)
    )
    organization = org_result.scalar_one_or_none()
    if not organization:
        return {"success": False, "message": f"❌ Organización {org_id} no encontrada"}
    
    org_scope = organization.territorial_scope or TerritorialScope.MUNICIPAL
    
    report = {
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "scope": org_scope.value,
            "url": organization.url
        },
        "steps": [],
        "results": [],
        "summary": {}
    }
    
    # Step 2: Check existing scraped data
    scraped_result = await db.execute(
        select(ScrapedData).where(ScrapedData.organization_id == org_id)
    )
    existing_data = scraped_result.scalars().all()
    
    if not existing_data or force_rescrape:
        # Need to scrape
        report["steps"].append({
            "step": "scraping",
            "action": "Iniciando scraping...",
            "status": "pending"
        })
        
        try:
            # Call the scraper service
            scrape_result = await scrape_organization(org_id)
            report["steps"][-1]["status"] = scrape_result.get("status", "unknown")
            report["steps"][-1]["variables_found"] = scrape_result.get("variables_found", 0)
            
            # Refresh scraped data
            scraped_result = await db.execute(
                select(ScrapedData).where(ScrapedData.organization_id == org_id)
            )
            existing_data = scraped_result.scalars().all()
        except Exception as e:
            report["steps"][-1]["status"] = "error"
            report["steps"][-1]["error"] = str(e)
    else:
        report["steps"].append({
            "step": "scraping",
            "action": "Usando datos existentes",
            "status": "skipped",
            "existing_records": len(existing_data)
        })
    
    # Step 3: Normalize text from all scraped data
    all_text = ""
    source_urls = []
    
    for sd in existing_data:
        if sd.variable_value:
            if isinstance(sd.variable_value, dict):
                content = sd.variable_value.get("text", sd.variable_value.get("data", str(sd.variable_value)))
            else:
                content = str(sd.variable_value)
            all_text += " " + content.lower()
        if sd.source_url and sd.source_url not in source_urls:
            source_urls.append(sd.source_url)
    
    if organization.description:
        all_text += " " + organization.description.lower()
    if organization.url:
        all_text += " " + organization.url.lower()
    
    report["steps"].append({
        "step": "normalization",
        "text_length": len(all_text),
        "source_urls": len(source_urls),
        "status": "completed"
    })
    
    # Step 4: Get variables and proxies
    if var_name:
        vars_result = await db.execute(
            select(VennVariable).where(VennVariable.name == var_name)
        )
    else:
        vars_result = await db.execute(select(VennVariable))
    
    variables = vars_result.scalars().all()
    
    if not variables:
        return {
            "success": False,
            "message": "❌ No hay variables Venn definidas. Crea variables primero.",
            "report": report
        }
    
    # Step 5: Evaluate each variable with territorial validation
    total_matches = 0
    total_rejected_scope = 0
    
    for variable in variables:
        proxies_result = await db.execute(
            select(VennProxy).where(VennProxy.venn_variable_id == variable.id)
        )
        proxies = proxies_result.scalars().all()
        
        var_result = {
            "variable": variable.name,
            "variable_id": variable.id,
            "proxies_total": len(proxies),
            "proxies_valid": 0,
            "proxies_rejected_scope": 0,
            "matches": [],
            "rejected": [],
            "final_value": False,
            "score": 0.0
        }
        
        for proxy in proxies:
            # Territorial validation
            validation = validate_proxy_for_organization(organization, proxy)
            
            if not validation["is_valid"]:
                var_result["proxies_rejected_scope"] += 1
                total_rejected_scope += 1
                var_result["rejected"].append({
                    "term": proxy.term,
                    "reason": validation["reason"]
                })
                continue
            
            var_result["proxies_valid"] += 1
            
            # Text matching
            term = proxy.term.lower()
            matched = False
            if proxy.is_regex:
                try:
                    matched = bool(re.search(term, all_text, re.IGNORECASE))
                except re.error:
                    pass
            else:
                matched = term in all_text
            
            if matched:
                var_result["matches"].append(proxy.term)
                var_result["score"] += proxy.weight
                total_matches += 1
        
        var_result["final_value"] = len(var_result["matches"]) > 0
        
        # Save result to database
        existing_vr = await db.execute(
            select(VennResult).where(
                and_(
                    VennResult.organization_id == org_id,
                    VennResult.venn_variable_id == variable.id
                )
            )
        )
        existing = existing_vr.scalar_one_or_none()
        
        notes = (
            f"Pipeline evaluation. Scope: {org_scope.value}. "
            f"Valid proxies: {var_result['proxies_valid']}/{var_result['proxies_total']}. "
            f"Rejected by scope: {var_result['proxies_rejected_scope']}."
        )
        
        if existing:
            existing.value = var_result["final_value"]
            existing.source = VennResultSource.AUTOMATIC
            existing.search_score = var_result["score"]
            existing.matched_proxies = var_result["matches"]
            existing.source_urls = source_urls[:5]
            existing.notes = notes
            existing.verification_status = VennResultStatus.PENDING
        else:
            new_result = VennResult(
                organization_id=org_id,
                venn_variable_id=variable.id,
                value=var_result["final_value"],
                source=VennResultSource.AUTOMATIC,
                search_score=var_result["score"],
                matched_proxies=var_result["matches"],
                source_urls=source_urls[:5],
                notes=notes,
                verification_status=VennResultStatus.PENDING
            )
            db.add(new_result)
        
        report["results"].append(var_result)
    
    await db.commit()
    
    # Build summary
    report["summary"] = {
        "organization_scope": org_scope.value,
        "variables_evaluated": len(variables),
        "total_matches": total_matches,
        "total_rejected_by_scope": total_rejected_scope,
        "scope_explanation": explain_scope_compatibility(org_scope)
    }
    
    # Build user-friendly message
    results_summary = []
    for r in report["results"]:
        status = "✅" if r["final_value"] else "❌"
        matches_str = f"({', '.join(r['matches'][:3])})" if r["matches"] else "(sin coincidencias)"
        rejected_str = f" ⚠️{r['proxies_rejected_scope']} rechazados" if r["proxies_rejected_scope"] > 0 else ""
        results_summary.append(f"{status} **{r['variable']}**: {matches_str}{rejected_str}")
    
    message = (
        f"🔄 **Pipeline completado para '{organization.name}'**\n\n"
        f"📍 Alcance territorial: **{org_scope.value}**\n"
        f"ℹ️ {report['summary']['scope_explanation']}\n\n"
        f"📊 **Resultados:**\n" + "\n".join(results_summary) + "\n\n"
        f"📋 **Resumen:**\n"
        f"   - Variables evaluadas: {len(variables)}\n"
        f"   - Coincidencias totales: {total_matches}\n"
        f"   - Proxies rechazados por scope: {total_rejected_scope}"
    )
    
    return {
        "success": True,
        "message": message,
        "report": report
    }


async def get_territorial_decision_table(
    db: AsyncSession,
    params: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Generate a decision table showing organization × variable × territorial validation.
    
    This provides a matrix view of which proxies are valid for which organizations
    based on territorial scope rules.
    """
    from app.models.db_models import Organization, VennVariable, VennProxy, TerritorialScope
    from app.services.territorial_validation import validate_proxy_scope, SCOPE_CAN_MATCH
    
    # Get all organizations
    orgs_result = await db.execute(select(Organization))
    organizations = orgs_result.scalars().all()
    
    # Get all variables with their proxies
    vars_result = await db.execute(select(VennVariable))
    variables = vars_result.scalars().all()
    
    # Build the decision table
    table = {
        "title": "Tabla de Decisión Territorial",
        "description": "Muestra qué proxies pueden ser activados por cada organización según su alcance territorial",
        "organizations": [],
        "variables": [],
        "matrix": []
    }
    
    # Populate organizations info
    for org in organizations:
        scope = org.territorial_scope or TerritorialScope.MUNICIPAL
        table["organizations"].append({
            "id": org.id,
            "name": org.name,
            "scope": scope.value,
            "matchable_scopes": [s.value for s in SCOPE_CAN_MATCH.get(scope, [])]
        })
    
    # Populate variables info
    for var in variables:
        proxies_result = await db.execute(
            select(VennProxy).where(VennProxy.venn_variable_id == var.id)
        )
        proxies = proxies_result.scalars().all()
        
        var_info = {
            "id": var.id,
            "name": var.name,
            "total_proxies": len(proxies),
            "proxies_by_scope": {}
        }
        
        # Categorize proxies by scope
        for proxy in proxies:
            scopes_str = str(proxy.applicable_scopes) if proxy.applicable_scopes else "universal"
            if scopes_str not in var_info["proxies_by_scope"]:
                var_info["proxies_by_scope"][scopes_str] = 0
            var_info["proxies_by_scope"][scopes_str] += 1
        
        table["variables"].append(var_info)
    
    # Build matrix: for each org × variable, how many proxies are valid?
    for org in organizations:
        org_scope = org.territorial_scope or TerritorialScope.MUNICIPAL
        org_row = {
            "org_id": org.id,
            "org_name": org.name,
            "org_scope": org_scope.value,
            "variable_results": []
        }
        
        for var in variables:
            proxies_result = await db.execute(
                select(VennProxy).where(VennProxy.venn_variable_id == var.id)
            )
            proxies = proxies_result.scalars().all()
            
            valid_count = 0
            invalid_count = 0
            
            for proxy in proxies:
                if validate_proxy_scope(org_scope, proxy.applicable_scopes):
                    valid_count += 1
                else:
                    invalid_count += 1
            
            org_row["variable_results"].append({
                "var_id": var.id,
                "var_name": var.name,
                "valid_proxies": valid_count,
                "invalid_proxies": invalid_count,
                "total_proxies": len(proxies),
                "can_potentially_activate": valid_count > 0
            })
        
        table["matrix"].append(org_row)
    
    # Generate readable message
    lines = [
        "📋 **Tabla de Decisión Territorial**\n",
        "Esta tabla muestra qué proxies puede activar cada organización según su alcance territorial.\n",
    ]
    
    for org_row in table["matrix"]:
        lines.append(f"\n🏢 **{org_row['org_name']}** (Alcance: {org_row['org_scope']})")
        for vr in org_row["variable_results"]:
            status = "✅" if vr["can_potentially_activate"] else "⚠️"
            lines.append(f"   {status} {vr['var_name']}: {vr['valid_proxies']}/{vr['total_proxies']} proxies válidos")
    
    return {
        "success": True,
        "message": "\n".join(lines),
        "table": table
    }
