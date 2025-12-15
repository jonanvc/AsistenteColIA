"""
Scraper Agent

Responsible for searching the web and extracting information about
civil society organizations led by women for peace-building in Colombia.

Uses GPT-4o-mini for query formulation and result parsing.
"""
import os
import json
import asyncio
from typing import TYPE_CHECKING, List, Dict, Any, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable

if TYPE_CHECKING:
    from .graph import AgentState

# Initialize ChatOpenAI client (integrates with LangSmith automatically)
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
    max_tokens=400,
)

# Tavily API for web search
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")


SCRAPER_SYSTEM_PROMPT = """Eres un agente especializado en buscar información sobre organizaciones de la sociedad civil lideradas por mujeres en Colombia, especialmente aquellas enfocadas en construcción de paz.

Tu tarea es:
1. Formular consultas de búsqueda efectivas
2. Identificar fuentes confiables (gobierno, ONGs, organizaciones internacionales, registros oficiales)
3. Extraer información estructurada sobre organizaciones de mujeres constructoras de paz

INFORMACIÓN OBLIGATORIA A EXTRAER:
- Nombre de la organización
- Localización (departamento, municipio, región)
- Alcance territorial (municipal, departamental, regional, nacional)
- Años activa (desde cuándo existe o cuántos años lleva funcionando)
- Número de mujeres miembros
- Si el líder es una mujer (sí/no) - IMPORTANTE: buscamos organizaciones lideradas por mujeres
- Nombre del líder/representante
- Enfoque/origen: "bottom_up" (desde abajo, iniciativa comunitaria/popular) o "top_down" (desde arriba, iniciativa gubernamental/institucional)
- Enfoque en construcción de paz (sí/no)

INFORMACIÓN ADICIONAL (si está disponible):
- NIT
- Tipo de organización (derechos humanos, construcción de paz, empoderamiento, justicia transicional, etc.)
- Actividad principal
- Número total de miembros
- Contacto (teléfono, email, dirección, web)
- Estado legal (activa, inactiva)
- URL de la fuente

FUENTES PRIORITARIAS:
1. ONU Mujeres Colombia
2. Alta Consejería para los Derechos de la Mujer
3. Consejería Presidencial para la Equidad de la Mujer
4. Unidad para las Víctimas
5. JEP (Jurisdicción Especial para la Paz)
6. Comisión de la Verdad
7. Defensoría del Pueblo
8. RUES (Registro Único Empresarial y Social)
9. Gobernaciones y Alcaldías - Secretarías de la Mujer
10. Fundaciones y ONGs de paz y género (Ruta Pacífica, LIMPAL, etc.)
11. Cooperación Internacional (USAID, UE, PNUD)

Responde con un JSON:
{{
    "search_queries": ["lista de consultas de búsqueda"],
    "reasoning": "por qué estas consultas"
}}"""


RESULT_PARSER_PROMPT = """Analiza los siguientes resultados de búsqueda web y extrae información estructurada sobre organizaciones de la sociedad civil lideradas por mujeres, especialmente aquellas enfocadas en construcción de paz.

RESULTADOS DE BÚSQUEDA:
{search_results}

Extrae la información en el siguiente formato JSON:
{{
    "organizations_found": [
        {{
            "nombre": "Nombre de la organización",
            "nit": "NIT o null",
            "departamento": "Departamento",
            "municipio": "Municipio o null",
            "alcance_territorial": "municipal|departamental|regional|nacional",
            "tipo": "derechos_humanos|construccion_paz|empoderamiento|justicia_transicional|victimas|genero|comunitaria|otro",
            "actividad_principal": "Descripción breve",
            "years_active": número de años activa o null,
            "year_founded": año de fundación si se conoce o null,
            "women_count": número de mujeres miembros o null,
            "total_members": número total de miembros o null,
            "leader_is_woman": true/false/null,
            "leader_name": "nombre del líder o representante o null",
            "approach": "bottom_up|top_down|mixed|unknown",
            "approach_reasoning": "explicación de por qué clasificas así el enfoque",
            "is_peace_building": true/false (si la organización trabaja en construcción de paz),
            "peace_building_activities": ["lista de actividades de paz si aplica"],
            "telefono": "teléfono o null",
            "email": "email o null",
            "direccion": "dirección o null",
            "url": "sitio web de la organización o null",
            "estado": "activa|inactiva|desconocido",
            "fuente_url": "URL de donde se extrajo",
            "confianza": 0.0-1.0,
            "missing_fields": ["lista de campos importantes que no se pudieron encontrar"]
        }}
    ],
    "new_sources_suggested": [
        {{
            "name": "Nombre de la fuente sugerida",
            "url": "URL completa",
            "description": "Por qué es útil esta fuente",
            "source_type": "government|registry|ngo|academic|news|peace_org|international|women_org|other",
            "reliability_score": 0.0-1.0
        }}
    ],
    "summary": "Resumen de lo encontrado",
    "needs_more_search": true/false,
    "suggested_queries": ["consultas adicionales si se necesitan para completar información faltante"],
    "data_quality_notes": "Notas sobre la calidad de los datos encontrados"
}}

REGLAS:
- Solo incluye organizaciones con información verificable
- PRIORIZA organizaciones lideradas por mujeres y/o enfocadas en construcción de paz
- Asigna confianza basada en la calidad de la fuente
- El campo "approach" es MUY IMPORTANTE:
  * "bottom_up": Iniciativa comunitaria, surgió del pueblo, liderazgo local, mujeres organizadas desde la base
  * "top_down": Iniciativa gubernamental, programa estatal, proyecto institucional
  * "mixed": Combinación de ambos enfoques
  * "unknown": No hay información suficiente
- El campo "is_peace_building" debe ser true si la organización trabaja en: reconciliación, víctimas, justicia transicional, memoria histórica, prevención de violencia, construcción de paz
- Sugiere nuevas fuentes de información que encuentres en los resultados
- Indica qué campos faltan para que se puedan buscar después"""


async def search_with_tavily(query: str, num_results: int = 5) -> List[Dict[str, Any]]:
    """
    Search the web using Tavily API.
    
    Args:
        query: Search query
        num_results: Number of results to retrieve
        
    Returns:
        List of search results
    """
    import httpx
    
    if not TAVILY_API_KEY:
        return []
    
    try:
        async with httpx.AsyncClient() as http_client:
            response = await http_client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": TAVILY_API_KEY,
                    "query": query,
                    "search_depth": "advanced",
                    "include_domains": [
                        "rfrfrues.org.co",
                        "camaras.org.co",
                        "minagricultura.gov.co",
                        "agronet.gov.co",
                        "dane.gov.co",
                        "finagro.com.co",
                        ".gov.co",
                    ],
                    "max_results": num_results,
                    "include_raw_content": True,
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            else:
                return []
                
    except Exception as e:
        print(f"Tavily search error: {e}")
        return []


def generate_search_queries(user_input: str, task_description: str) -> List[str]:
    """
    Generate effective search queries based on user input.
    
    Uses GPT-4o-mini for fast query generation.
    """
    try:
        messages = [
            SystemMessage(content=SCRAPER_SYSTEM_PROMPT),
            HumanMessage(content=f"Consulta del usuario: {user_input}\n\nTarea: {task_description}\n\nGenera las consultas de búsqueda óptimas. Responde SOLO con JSON válido.")
        ]
        
        llm_json = llm.bind(response_format={"type": "json_object"})
        response = llm_json.invoke(messages)
        result = json.loads(response.content)
        return result.get("search_queries", [f"organizaciones mujeres constructoras paz Colombia {user_input}"])
        
    except Exception as e:
        # Fallback queries
        return [
            f"organizaciones mujeres {user_input} Colombia",
            f"colectivos mujeres paz {user_input}",
            f"organizaciones sociedad civil mujeres {user_input}",
        ]


def parse_search_results(results: List[Dict[str, Any]], user_input: str) -> Dict[str, Any]:
    """
    Parse search results and extract structured organization data.
    
    Uses GPT-4o-mini for parsing.
    """
    if not results:
        return {
            "organizations_found": [],
            "summary": "No se encontraron resultados",
            "needs_more_search": True,
            "suggested_queries": [],
        }
    
    # Format results for the parser
    formatted_results = []
    for r in results:
        formatted_results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", "")[:2000],  # Limit content
            "raw_content": r.get("raw_content", "")[:3000] if r.get("raw_content") else "",
        })
    
    try:
        messages = [
            SystemMessage(content=RESULT_PARSER_PROMPT.format(
                search_results=json.dumps(formatted_results, ensure_ascii=False, indent=2)
            )),
            HumanMessage(content=f"Extrae información de organizaciones relacionada con: {user_input}. Responde SOLO con JSON válido.")
        ]
        
        llm_parser = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, max_tokens=2000)
        llm_json = llm_parser.bind(response_format={"type": "json_object"})
        response = llm_json.invoke(messages)
        return json.loads(response.content)
        
    except Exception as e:
        return {
            "organizations_found": [],
            "summary": f"Error al parsear resultados: {str(e)}",
            "needs_more_search": False,
            "suggested_queries": [],
        }


@traceable(name="scraper_agent")
def scraper_node(state: "AgentState") -> "AgentState":
    """
    Scraper node that searches for organization information.
    
    Uses Tavily for web search and GPT-4o-mini for parsing.
    """
    user_input = state["user_input"]
    task_description = state.get("task_description", "Buscar organizaciones de mujeres")
    
    # Generate search queries
    queries = generate_search_queries(user_input, task_description)
    
    # Perform searches
    all_results = []
    urls_visited = state.get("urls_visited", [])
    
    # Run searches synchronously (will be called from async context)
    import asyncio
    
    async def run_searches():
        all_search_results = []
        for query in queries[:3]:  # Limit to 3 queries
            results = await search_with_tavily(query)
            all_search_results.extend(results)
        return all_search_results
    
    try:
        # Try to get existing event loop or create new one
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're in an async context, use nest_asyncio or schedule
                import nest_asyncio
                nest_asyncio.apply()
                all_results = loop.run_until_complete(run_searches())
            else:
                all_results = loop.run_until_complete(run_searches())
        except RuntimeError:
            # No event loop exists
            all_results = asyncio.run(run_searches())
    except Exception as e:
        all_results = []
        errors = state.get("errors", []) + [f"Error en búsqueda: {str(e)}"]
        return {
            **state,
            "scraper_status": "error",
            "errors": errors,
        }
    
    # Update URLs visited
    for r in all_results:
        url = r.get("url", "")
        if url and url not in urls_visited:
            urls_visited.append(url)
    
    # Parse results
    parsed = parse_search_results(all_results, user_input)
    
    # Merge with existing scraped data
    existing_data = state.get("scraped_data", [])
    new_organizations = parsed.get("organizations_found", [])
    
    # Deduplicate by name (simple approach)
    existing_names = {o.get("nombre", "").lower() for o in existing_data}
    for org in new_organizations:
        name = org.get("nombre", "").lower()
        if name and name not in existing_names:
            existing_data.append(org)
            existing_names.add(name)
    
    return {
        **state,
        "scraped_data": existing_data,
        "scraper_status": "completed",
        "urls_visited": urls_visited,
        "current_agent": "evaluator",  # Next: evaluate the scraped data
    }


class ScraperAgent:
    """
    Scraper Agent class for use outside of LangGraph.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.tavily_key = TAVILY_API_KEY
    
    @traceable(name="scraper_search")
    async def search(self, query: str, context: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for organizations based on query.
        
        Args:
            query: Search query from user
            context: Additional context
            
        Returns:
            Dictionary with found organizations and metadata
        """
        # Generate search queries
        queries = generate_search_queries(query, context or "Buscar organizaciones de mujeres")
        
        # Perform searches
        all_results = []
        for q in queries[:3]:
            results = await search_with_tavily(q)
            all_results.extend(results)
        
        # Parse and return
        return parse_search_results(all_results, query)
    
    @traceable(name="scraper_targeted")
    async def search_specific_organization(self, name: str, location: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for a specific organization by name.
        
        Args:
            name: Organization name
            location: Optional location filter
            
        Returns:
            Organization data if found
        """
        query = f'"{name}" organización mujeres paz'
        if location:
            query += f" {location} Colombia"
        else:
            query += " Colombia"
        
        results = await search_with_tavily(query, num_results=10)
        parsed = parse_search_results(results, name)
        
        # Filter results to match name closely
        matching = [
            o for o in parsed.get("organizations_found", [])
            if name.lower() in o.get("nombre", "").lower()
        ]
        
        if matching:
            parsed["organizations_found"] = matching
        
        return parsed
