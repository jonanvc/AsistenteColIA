"""
Finalizer Agent

Responsible for formatting the final response for the user.
Compiles all processed data into a clear, helpful response.
Also executes database operations to persist organizations.

Uses GPT-4o-mini for fast response generation.
"""
import os
import json
from typing import TYPE_CHECKING, List, Dict, Any, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable

if TYPE_CHECKING:
    from .graph import AgentState

# Initialize ChatOpenAI client (automatically integrates with LangSmith)
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.4,
    max_tokens=2000,
)


def save_organizations_to_db(db_operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Execute database operations to save organizations (synchronous version).
    
    Args:
        db_operations: List of database operations from classifier
        
    Returns:
        Summary of operations performed
    """
    from ..db.base import get_sync_db_session
    from ..models.db_models import Organization, TerritorialScope, OrganizationApproach
    
    saved = []
    errors = []
    
    # Helper to convert string to TerritorialScope enum
    def get_territorial_scope(value):
        if value is None:
            return TerritorialScope.MUNICIPAL
        if isinstance(value, TerritorialScope):
            return value
        scope_map = {
            "municipal": TerritorialScope.MUNICIPAL,
            "departamental": TerritorialScope.DEPARTAMENTAL,
            "regional": TerritorialScope.REGIONAL,
            "nacional": TerritorialScope.NACIONAL,
            "internacional": TerritorialScope.INTERNACIONAL,
        }
        return scope_map.get(str(value).lower(), TerritorialScope.MUNICIPAL)
    
    # Helper to convert string to OrganizationApproach enum
    def get_approach(value):
        if value is None:
            return OrganizationApproach.UNKNOWN
        if isinstance(value, OrganizationApproach):
            return value
        approach_map = {
            "bottom_up": OrganizationApproach.BOTTOM_UP,
            "top_down": OrganizationApproach.TOP_DOWN,
            "mixed": OrganizationApproach.MIXED,
            "unknown": OrganizationApproach.UNKNOWN,
        }
        return approach_map.get(str(value).lower(), OrganizationApproach.UNKNOWN)
    
    session = get_sync_db_session()
    try:
        for op in db_operations:
            if op.get("operation") == "insert_or_update" and op.get("table") == "organizations":
                data = op.get("data", {})
                
                try:
                    # Check if organization already exists by name
                    existing = session.query(Organization).filter(
                        Organization.name == data.get("name")
                    ).first()
                    
                    if existing:
                        # Update existing
                        for key, value in data.items():
                            if value is not None and hasattr(existing, key):
                                if key == "territorial_scope":
                                    value = get_territorial_scope(value)
                                elif key == "approach":
                                    value = get_approach(value)
                                setattr(existing, key, value)
                        saved.append({"name": data.get("name"), "action": "updated"})
                    else:
                        # Create new organization
                        org = Organization(
                            name=data.get("name"),
                            description=data.get("description"),
                            territorial_scope=get_territorial_scope(data.get("territorial_scope")),
                            latitude=data.get("latitude"),
                            longitude=data.get("longitude"),
                            department_code=data.get("department_code"),
                            municipality_code=data.get("municipality_code"),
                            women_count=data.get("women_count"),
                            leader_is_woman=data.get("leader_is_woman", True),
                            leader_name=data.get("leader_name"),
                            approach=get_approach(data.get("approach")),
                            is_peace_building=data.get("is_peace_building", True),
                            is_international=data.get("is_international", False),
                            url=data.get("url"),
                        )
                        session.add(org)
                        saved.append({"name": data.get("name"), "action": "created"})
                    
                    session.commit()
                    
                except Exception as e:
                    errors.append(f"Error saving {data.get('name')}: {str(e)}")
                    session.rollback()
    finally:
        session.close()
    
    return {
        "saved_count": len(saved),
        "saved": saved,
        "errors": errors
    }


def save_organizations_sync(db_operations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Wrapper function that calls the synchronous save function."""
    return save_organizations_to_db(db_operations)


FINALIZER_SYSTEM_PROMPT = """Eres el agente finalizador de un sistema multi-agente para gestión de organizaciones de la sociedad civil lideradas por mujeres en Colombia, enfocado en construcción de paz.

Tu tarea es generar una respuesta clara, completa y útil para el usuario basándote en los datos procesados.

INFORMACIÓN DISPONIBLE:
- Consulta original del usuario: {user_input}
- Datos scrapeados: {scraped_summary}
- Datos clasificados: {classified_summary}
- Evaluación: {evaluation_summary}
- Errores (si los hay): {errors}

FORMATO DE RESPUESTA:
1. Comienza con un resumen ejecutivo
2. Presenta los hallazgos principales de forma estructurada
3. Incluye detalles relevantes de las organizaciones encontradas
4. Destaca aspectos de liderazgo femenino y construcción de paz
5. Menciona limitaciones o datos faltantes
6. Ofrece sugerencias para obtener más información si es necesario

ESTILO:
- Profesional pero accesible
- En español
- Usa formato Markdown para mejor legibilidad
- Incluye emojis relevantes para mejor UX (👩‍💼, ☮️, 🕊️, 💪, 📍, etc.)
- Sé conciso pero completo

Si no se encontró información útil, explica por qué y sugiere alternativas.
Si hubo errores, explícalos de forma amigable sin tecnicismos innecesarios."""


def summarize_scraped_data(data: List[Dict[str, Any]]) -> str:
    """Create a summary of scraped data for the finalizer."""
    if not data:
        return "No se encontraron datos en la búsqueda web."
    
    summary_parts = [f"Se encontraron {len(data)} posibles organizaciones:"]
    for i, item in enumerate(data[:5], 1):  # First 5
        name = item.get("nombre", item.get("name", "Sin nombre"))
        location = item.get("departamento", item.get("ubicacion", "Ubicación desconocida"))
        leader_woman = "👩‍💼" if item.get("leader_is_woman") else ""
        peace = "🕊️" if item.get("is_peace_building") else ""
        summary_parts.append(f"  {i}. {name} - {location} {leader_woman}{peace}")
    
    if len(data) > 5:
        summary_parts.append(f"  ... y {len(data) - 5} más")
    
    return "\n".join(summary_parts)


def summarize_classified_data(data: List[Dict[str, Any]]) -> str:
    """Create a summary of classified data for the finalizer."""
    if not data:
        return "No se clasificaron datos."
    
    # Group by type
    by_type = {}
    for item in data:
        t = item.get("type", "otro")
        if t not in by_type:
            by_type[t] = []
        by_type[t].append(item)
    
    summary_parts = [f"Se clasificaron {len(data)} organizaciones:"]
    for t, items in by_type.items():
        summary_parts.append(f"  - {t.title()}: {len(items)}")
    
    # High confidence count
    high_conf = sum(1 for d in data if d.get("confidence", 0) >= 0.7)
    summary_parts.append(f"  - Alta confianza: {high_conf}/{len(data)}")
    
    # Women-led count
    women_led = sum(1 for d in data if d.get("leader_is_woman"))
    summary_parts.append(f"  - Lideradas por mujeres: {women_led}/{len(data)}")
    
    return "\n".join(summary_parts)


def summarize_evaluation(passed: bool, score: float, feedback: str) -> str:
    """Create evaluation summary for the finalizer."""
    status = "✅ Aprobada" if passed else "⚠️ Con observaciones"
    return f"{status} (Score: {score:.0%})\n{feedback}"


def format_organization_details(organizations: List[Dict[str, Any]], max_display: int = 5) -> str:
    """Format organization details for display."""
    if not organizations:
        return ""
    
    details = []
    for i, org in enumerate(organizations[:max_display], 1):
        name = org.get("name", org.get("nombre", "Sin nombre"))
        dept = org.get("department_name", org.get("departamento", ""))
        muni = org.get("municipality_name", org.get("municipio", ""))
        org_type = org.get("type", org.get("tipo", ""))
        status = org.get("status", org.get("estado", ""))
        confidence = org.get("confidence", org.get("confianza", 0))
        
        location = f"{muni}, {dept}" if muni else dept
        
        # New fields
        years_active = org.get("years_active")
        women_count = org.get("women_count")
        leader_is_woman = org.get("leader_is_woman")
        leader_name = org.get("leader_name")
        approach = org.get("approach", "unknown")
        territorial_scope = org.get("alcance_territorial", org.get("territorial_scope", ""))
        
        # Format approach
        approach_labels = {
            "bottom_up": "🌱 Desde abajo (comunitaria)",
            "top_down": "🏛️ Desde arriba (gubernamental)",
            "mixed": "🔄 Mixto",
            "unknown": "❓ Desconocido"
        }
        approach_text = approach_labels.get(approach, approach)
        
        detail = f"""
### {i}. {name}
- 📍 **Ubicación:** {location or 'No especificada'}
- 🌎 **Alcance:** {territorial_scope.title() if territorial_scope else 'No especificado'}
- 🏷️ **Tipo:** {org_type.title() if org_type else 'No clasificado'}
- 📊 **Estado:** {status.title() if status else 'Desconocido'}
- 🎯 **Confianza:** {confidence:.0%}
- 🔄 **Enfoque:** {approach_text}"""
        
        # Add new fields if available
        if years_active:
            detail += f"\n- 📅 **Años activa:** {years_active}"
        if women_count:
            detail += f"\n- 👩 **Mujeres miembros:** {women_count}"
        if leader_name:
            leader_icon = "👩‍💼" if leader_is_woman else "👤"
            detail += f"\n- {leader_icon} **Líder:** {leader_name}"
            if leader_is_woman is not None:
                detail += f" ({'mujer' if leader_is_woman else 'hombre'})"
        
        # Add contact if available
        contact = org.get("contact", {})
        if isinstance(contact, dict):
            if contact.get("phone"):
                detail += f"\n- 📞 **Teléfono:** {contact['phone']}"
            if contact.get("email"):
                detail += f"\n- 📧 **Email:** {contact['email']}"
        
        # Show missing fields
        missing = org.get("missing_fields", [])
        if missing:
            detail += f"\n- ⚠️ **Datos faltantes:** {', '.join(missing[:3])}"
        
        details.append(detail)
    
    if len(organizations) > max_display:
        details.append(f"\n*... y {len(organizations) - max_display} organizaciones más*")
    
    return "\n".join(details)


def format_pending_validation_message(pending_organizations: List[Dict], pending_sources: List[Dict]) -> str:
    """Format message for pending validations."""
    parts = []
    
    if pending_organizations:
        parts.append("\n## ⏳ Organizaciones Pendientes de Validación\n")
        parts.append("He encontrado las siguientes organizaciones que necesitan tu aprobación antes de guardarlas:\n")
        for i, org in enumerate(pending_organizations, 1):
            name = org.get("nombre", org.get("name", "Sin nombre"))
            confidence = org.get("confianza", org.get("confidence", 0))
            missing = org.get("missing_fields", [])
            
            parts.append(f"**{i}. {name}** (Confianza: {confidence:.0%})")
            if missing:
                parts.append(f"   - ⚠️ Datos faltantes: {', '.join(missing)}")
        
        parts.append("\n*Usa los botones de validación para aprobar, rechazar o modificar cada organización.*\n")
    
    if pending_sources:
        parts.append("\n## 📚 Nuevas Fuentes de Información Sugeridas\n")
        parts.append("He encontrado estas fuentes de información útiles:\n")
        for i, source in enumerate(pending_sources, 1):
            name = source.get("name", "Sin nombre")
            url = source.get("url", "")
            source_type = source.get("source_type", "other")
            score = source.get("reliability_score", 0.5)
            
            type_icons = {
                "government": "🏛️", "registry": "📋", "ngo": "🌱",
                "academic": "🎓", "news": "📰", "cooperative": "🤝",
                "international": "🌍", "other": "📎"
            }
            icon = type_icons.get(source_type, "📎")
            
            parts.append(f"**{i}. {icon} {name}**")
            parts.append(f"   - 🔗 {url}")
            parts.append(f"   - Confiabilidad: {score:.0%}")
        
        parts.append("\n*¿Deseas agregar estas fuentes para futuras búsquedas?*\n")
    
    return "\n".join(parts)


@traceable(name="finalizer_agent")
def finalizer_node(state: "AgentState") -> "AgentState":
    """
    Finalizer node that generates the final response.
    
    Uses GPT-4o-mini for fast response generation.
    Now also handles pending validations for organizations and sources.
    """
    user_input = state["user_input"]
    scraped_data = state.get("scraped_data", [])
    classified_data = state.get("classified_data", [])
    evaluation_passed = state.get("evaluation_passed", False)
    evaluation_score = state.get("evaluation_score", 0)
    evaluation_feedback = state.get("evaluation_feedback", "")
    errors = state.get("errors", [])
    iteration_count = state.get("iteration_count", 0)
    
    # Check for Venn agent response first - if present, use it directly
    venn_response = state.get("venn_response")
    if venn_response:
        return {
            **state,
            "final_response": venn_response,
            "response_ready": True,
            "requires_user_validation": False,
        }
    
    # Check for DB Query agent response - if present, use it directly
    db_response = state.get("db_response")
    if db_response:
        return {
            **state,
            "final_response": db_response,
            "response_ready": True,
            "requires_user_validation": False,
        }
    
    # Get pending items
    pending_organizations = state.get("pending_organizations", [])
    pending_sources = state.get("pending_sources", [])
    suggested_sources = state.get("suggested_sources", [])
    
    # If no pending organizations but we have scraped data, make them pending for validation
    if not pending_organizations and scraped_data:
        pending_organizations = scraped_data
    
    # If no pending sources but we have suggested sources, make them pending
    if not pending_sources and suggested_sources:
        pending_sources = suggested_sources
    
    # Prepare summaries
    scraped_summary = summarize_scraped_data(scraped_data)
    classified_summary = summarize_classified_data(classified_data)
    evaluation_summary = summarize_evaluation(evaluation_passed, evaluation_score, evaluation_feedback)
    errors_summary = "; ".join(errors[-3:]) if errors else "Ninguno"
    
    requires_validation = bool(pending_organizations or pending_sources)
    
    # Execute database operations if evaluation passed
    db_operations = state.get("db_operations", [])
    saved_count = 0
    save_errors = []
    
    if db_operations and evaluation_passed:
        db_save_result = save_organizations_sync(db_operations)
        saved_count = db_save_result.get("saved_count", 0)
        save_errors = db_save_result.get("errors", [])
        if saved_count > 0:
            # Add saved info to state
            saved_orgs = db_save_result.get("saved", [])
            save_summary = f"✅ Se guardaron {len(saved_orgs)} organizaciones en el sistema"
        else:
            save_summary = ""
    else:
        save_summary = ""
    
    # If we have good data, format it directly
    if classified_data and evaluation_passed:
        # Generate response with LLM for natural language
        try:
            messages = [
                SystemMessage(content=FINALIZER_SYSTEM_PROMPT.format(
                    user_input=user_input,
                    scraped_summary=scraped_summary,
                    classified_summary=classified_summary,
                    evaluation_summary=evaluation_summary,
                    errors=errors_summary
                )),
                HumanMessage(content=f"""Genera la respuesta final para el usuario.

DATOS CLASIFICADOS DETALLADOS:
{json.dumps(classified_data[:10], ensure_ascii=False, indent=2)}

Incluye los detalles de las organizaciones encontradas de forma clara y estructurada.""")
            ]
            
            response = llm.invoke(messages)
            final_response = response.content
            
        except Exception as e:
            # Fallback: format manually
            final_response = generate_fallback_response(
                user_input, classified_data, evaluation_score, errors
            )
    
    elif scraped_data and not classified_data:
        # Data was scraped but not classified
        final_response = f"""## 🔍 Resultados de Búsqueda

Encontré información que podría ser relevante para tu consulta: "{user_input}"

{scraped_summary}

⚠️ **Nota:** Los datos aún no han sido completamente procesados. La información mostrada es preliminar.

### Próximos pasos sugeridos:
1. Refina tu búsqueda con términos más específicos
2. Incluye el departamento o municipio si buscas organizaciones locales
3. Menciona el tipo de organización (mujeres por la paz, líderes comunitarias, etc.)"""
    
    elif errors:
        # There were errors
        final_response = f"""## ⚠️ Búsqueda Parcial

Hubo algunos inconvenientes al procesar tu solicitud: "{user_input}"

### Problemas encontrados:
{chr(10).join(f'- {e}' for e in errors[-3:])}

### Sugerencias:
- Intenta reformular tu consulta
- Verifica que estés preguntando sobre organizaciones de mujeres en Colombia
- Si el problema persiste, intenta de nuevo en unos minutos"""
    
    else:
        # No data found
        final_response = f"""## 📭 Sin Resultados

No encontré información sobre organizaciones relacionada con: "{user_input}"

### Posibles razones:
- La consulta puede ser muy específica
- Los datos pueden no estar disponibles en línea
- La organización puede no estar registrada formalmente

### Sugerencias:
1. 🔍 Intenta con términos más generales
2. 📍 Especifica una región geográfica (departamento o municipio)
3. 🏷️ Incluye el tipo de organización (mujeres por la paz, colectivo de mujeres, etc.)

### Ejemplo de consulta:
> "Organizaciones de mujeres constructoras de paz en Chocó"
> "Colectivos de mujeres líderes en Antioquia"
> "Organizaciones de mujeres en Meta" """
    
    # Add pending validations section if any
    if requires_validation:
        validation_message = format_pending_validation_message(pending_organizations, pending_sources)
        final_response += "\n" + validation_message
    
    # Add save summary if organizations were saved
    if saved_count > 0:
        final_response += f"\n\n✅ **{saved_count} organización(es) guardada(s) en el sistema.**"
    elif save_errors:
        final_response += f"\n\n⚠️ **No se pudieron guardar las organizaciones:** {'; '.join(save_errors)}"
    
    # Add metadata
    final_response += f"\n\n---\n*Procesado en {iteration_count} iteraciones | Score de calidad: {evaluation_score:.0%}*"
    
    return {
        **state,
        "final_response": final_response,
        "response_ready": True,
        "requires_user_validation": requires_validation,
        "pending_organizations": pending_organizations,
        "pending_sources": pending_sources,
        "saved_count": saved_count,
    }


def generate_fallback_response(
    user_input: str,
    classified_data: List[Dict[str, Any]],
    score: float,
    errors: List[str]
) -> str:
    """Generate fallback response without LLM."""
    response_parts = [
        f"## 🌾 Resultados para: {user_input}",
        "",
        f"Se encontraron **{len(classified_data)}** organizaciones.",
        "",
        format_organization_details(classified_data),
    ]
    
    if errors:
        response_parts.extend([
            "",
            "### ⚠️ Notas:",
            *[f"- {e}" for e in errors[-2:]],
        ])
    
    return "\n".join(response_parts)


class FinalizerAgent:
    """
    Finalizer Agent class for use outside of LangGraph.
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.4,
            max_tokens=2000,
        )
    
    @traceable(name="finalizer_generate")
    def generate_response(
        self,
        user_input: str,
        data: List[Dict[str, Any]],
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Generate final response for user.
        
        Args:
            user_input: Original user query
            data: Processed data to present
            context: Additional context (evaluation, errors, etc.)
            
        Returns:
            Formatted response string
        """
        context = context or {}
        
        messages = [
            SystemMessage(content=FINALIZER_SYSTEM_PROMPT.format(
                user_input=user_input,
                scraped_summary=context.get("scraped_summary", "N/A"),
                classified_summary=context.get("classified_summary", "N/A"),
                evaluation_summary=context.get("evaluation_summary", "N/A"),
                errors=context.get("errors", "Ninguno")
            )),
            HumanMessage(content=f"Datos: {json.dumps(data[:10], ensure_ascii=False)}")
        ]
        
        response = self.llm.invoke(messages)
        return response.content
    
    def format_simple(self, data: List[Dict[str, Any]]) -> str:
        """Simple formatting without LLM."""
        return format_organization_details(data)
