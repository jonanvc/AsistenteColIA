"""
Orchestrator Agent

The central coordinator that receives validated user queries and routes them
to the appropriate agents based on the task requirements.

Uses GPT-4o for complex reasoning and task decomposition.
"""
import os
import json
from typing import TYPE_CHECKING

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langsmith import traceable

if TYPE_CHECKING:
    from .graph import AgentState

# Initialize ChatOpenAI client (integrates with LangSmith automatically)
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.2,
    max_tokens=500,
)


ORCHESTRATOR_SYSTEM_PROMPT = """Eres el Agente Orquestador de un sistema multi-agente para gestionar información sobre organizaciones de la sociedad civil lideradas por mujeres en Colombia, especialmente aquellas enfocadas en construcción de paz.

Tu rol es analizar las consultas del usuario y decidir qué agente debe ejecutar la siguiente acción.

AGENTES DISPONIBLES:
1. **db_query**: Gestiona operaciones CRUD directas en la base de datos. 
   ✅ PRIORIZA ESTE AGENTE para:
   - Consultar si una organización YA EXISTE en el sistema
   - Buscar organizaciones registradas por nombre, ubicación, etc.
   - "¿Tenemos registrada X?", "¿Existe la organización Y?"
   - "Listar organizaciones", "¿Qué organizaciones tenemos?"
   - CREAR organizaciones con datos proporcionados directamente por el usuario
   - EDITAR o ELIMINAR organizaciones existentes
   - Operaciones con MÚLTIPLES organizaciones a la vez
   - Operaciones con variables Venn (crear, editar, eliminar variables y proxies)
   - Operaciones con INTERSECCIONES Venn (crear, listar, eliminar intersecciones)
   
   ✅ USA db_query cuando el usuario dice:
   - "Crea estas organizaciones: X, Y, Z"
   - "Registra la organización X con estos datos..."
   - "Elimina las organizaciones X e Y"
   - "Actualiza X, Y y Z con..."
   - "Crea las variables Venn: A, B, C"
   - "Lista las intersecciones Venn"
   - "Crea intersección: A AND (B OR C)"
   
   Palabras clave: "tenemos", "registrada", "existe", "crea", "registra", "elimina", "actualiza", "añade", "en el sistema", "en la base de datos", "variable venn", "proxy", "intersección", "intersecciones"

2. **scraper**: Busca información en la web sobre organizaciones. 
   ⚠️ SOLO úsalo cuando el usuario EXPLÍCITAMENTE pide buscar en internet/web/red:
   - "busca en la red", "busca en internet", "busca en la web"
   - "buscar información online", "buscar datos en internet"
   - "investiga en la web", "encuentra información online"
   
   ❌ NO uses scraper si:
   - El usuario pregunta si tenemos una organización registrada
   - El usuario da los datos directamente (nombre, ubicación, líder, etc.)
   - El usuario solo quiere crear/registrar una organización con datos que ya tiene
   - No hay mención explícita de buscar en internet

3. **classifier**: Clasifica y estructura datos SCRAPEADOS para la base de datos. Úsalo cuando:
   - Hay datos scraped de internet que necesitan ser procesados y estructurados
   - Se necesita normalizar información obtenida de fuentes externas
   
   ⚠️ NO uses classifier si:
   - El usuario proporciona datos directamente → usa db_query
   - No hay datos de scraping → usa db_query para CRUD directo

4. **evaluator**: Valida la calidad y corrección de los datos. Úsalo cuando:
   - Hay datos clasificados que necesitan validación
   - Se debe verificar la precisión de la información
   - Se necesita control de calidad antes de finalizar

5. **finalizer**: Genera la respuesta final para el usuario. Úsalo cuando:
   - La tarea está completa
   - Se tienen todos los datos necesarios
   - Se necesita presentar resultados al usuario

6. **venn**: SOLO para VISUALIZACIÓN de diagramas Venn. Úsalo ÚNICAMENTE cuando:
   - El usuario quiere GENERAR o VISUALIZAR un diagrama Venn gráficamente
   - Se quieren ingresar resultados de análisis Venn manualmente
   
   ⚠️ NUNCA uses "venn" para:
   - Listar intersecciones Venn → usa db_query
   - Crear/editar/eliminar intersecciones → usa db_query  
   - Listar/crear/editar variables Venn → usa db_query
   - Cualquier operación CRUD sobre variables, proxies o intersecciones → usa db_query

CONTEXTO DEL ESTADO ACTUAL:
{state_context}

HISTORIAL DE ITERACIONES: {iteration_count}/{max_iterations}

Responde SOLO con un JSON:
{{
    "next_agent": "db_query|scraper|classifier|evaluator|finalizer|venn",
    "task_description": "Descripción clara de lo que debe hacer el siguiente agente",
    "reasoning": "Tu razonamiento para esta decisión",
    "estimated_remaining_steps": 1-5
}}

REGLAS IMPORTANTES:
- ⚠️ Si el usuario pregunta si TENEMOS/EXISTE una organización → usa "db_query"
- ⚠️ Si el usuario quiere CREAR/EDITAR/ELIMINAR organizaciones con datos que proporciona → usa "db_query"
- ⚠️ Si el usuario quiere operar con MÚLTIPLES organizaciones o variables Venn → usa "db_query"
- ⚠️ SOLO usa "scraper" si el usuario EXPLÍCITAMENTE pide buscar en internet/web/red
- ⚠️ SOLO usa "classifier" si hay datos de scraping que procesar
- Si ya se tienen todos los datos necesarios, envía a "finalizer"
- Si se alcanzó el máximo de iteraciones, envía a "finalizer"
- Evita ciclos infinitos entre agentes
- Prioriza eficiencia: minimiza el número de pasos necesarios
- Si el usuario quiere generar/visualizar diagramas Venn, envía a "venn"

EJEMPLOS:
- "¿Tenemos registrada la asociación Asmubuli?" → db_query
- "¿Existe la organización Asomujer en el sistema?" → db_query
- "Crea Asmubuli en Bogotá con líder Fidelia" → db_query (CRUD directo)
- "Crea estas 3 organizaciones: X, Y, Z" → db_query (múltiples organizaciones)
- "Registra las organizaciones: A en Bogotá, B en Medellín" → db_query (múltiples)
- "Elimina las organizaciones X e Y" → db_query
- "Actualiza X, Y con alcance regional" → db_query
- "Crea las variables Venn: Liderazgo, Paz, Territorio" → db_query
- "Añade proxies a la variable Liderazgo" → db_query
- "Lista las intersecciones Venn" → db_query (CRUD de intersecciones)
- "¿Qué intersecciones Venn tenemos?" → db_query (CRUD de intersecciones)
- "Muestra las intersecciones" → db_query (CRUD de intersecciones)
- "Crea intersección: A AND (B OR C)" → db_query
- "Elimina la intersección X" → db_query
- "Busca en internet información sobre Asmubuli" → scraper (buscar en web)
- "Encuentra organizaciones de mujeres en Chocó en la web" → scraper (buscar en web)
- "Lista todas las organizaciones que tenemos" → db_query
- "Genera el diagrama Venn gráficamente" → venn (SOLO para visualización gráfica)
"""


def build_state_context(state: "AgentState") -> str:
    """Build a context string from the current state for the orchestrator."""
    context_parts = []
    
    # Conversation history for context (last 10 messages)
    conversation_history = state.get("conversation_history", [])
    if conversation_history:
        context_parts.append("HISTORIAL DE CONVERSACIÓN (últimos mensajes):")
        for msg in conversation_history[-10:]:
            # Ensure msg is a dictionary before accessing properties
            if isinstance(msg, dict):
                role = "Usuario" if msg.get("role") == "user" else "Asistente"
                content = msg.get("content", "")[:200]  # Truncate long messages
                context_parts.append(f"  {role}: {content}")
            elif isinstance(msg, str):
                # Handle case where msg is a string instead of dict
                context_parts.append(f"  Mensaje: {msg[:200]}")
        context_parts.append("")  # Empty line separator
    
    # User request
    context_parts.append(f"CONSULTA DEL USUARIO: {state['user_input']}")
    
    # Check for Venn-related keywords
    user_input_lower = state['user_input'].lower()
    if any(kw in user_input_lower for kw in ['venn', 'variable', 'proxy', 'proxies', 'resultado', 'intersección', 'intersecciones', 'interseccion']):
        context_parts.append("NOTA: La consulta parece relacionada con variables Venn, intersecciones o resultados → usar db_query")
    
    # Scraped data status
    if state.get("scraped_data"):
        context_parts.append(f"DATOS SCRAPEADOS: {len(state['scraped_data'])} elementos encontrados")
        context_parts.append(f"URLs visitadas: {', '.join(state.get('urls_visited', []))[:500]}")
    else:
        context_parts.append("DATOS SCRAPEADOS: Ninguno todavía")
    
    # Classified data status
    if state.get("classified_data"):
        context_parts.append(f"DATOS CLASIFICADOS: {len(state['classified_data'])} registros")
        context_parts.append(f"Resumen: {state.get('classification_summary', 'N/A')[:300]}")
    else:
        context_parts.append("DATOS CLASIFICADOS: Ninguno todavía")
    
    # Evaluation status
    if state.get("evaluation_feedback"):
        context_parts.append(f"EVALUACIÓN: Score {state.get('evaluation_score', 0):.2f}")
        context_parts.append(f"Feedback: {state['evaluation_feedback'][:300]}")
        if state.get("corrections_needed"):
            context_parts.append(f"Correcciones pendientes: {', '.join(state['corrections_needed'])}")
    
    # Errors
    if state.get("errors"):
        context_parts.append(f"ERRORES: {'; '.join(state['errors'][-3:])}")  # Last 3 errors
    
    return "\n".join(context_parts)


@traceable(name="orchestrator_agent")
def orchestrator_node(state: "AgentState") -> "AgentState":
    """
    Orchestrator node that decides the next agent to call.
    
    Uses GPT-4o for complex reasoning about task routing.
    """
    # Increment iteration count
    iteration_count = state.get("iteration_count", 0) + 1
    max_iterations = state.get("max_iterations", 10)
    
    # Safety check: if we've exceeded iterations, go to finalizer
    if iteration_count >= max_iterations:
        return {
            **state,
            "iteration_count": iteration_count,
            "current_agent": "finalizer",
            "task_description": "Generar respuesta final debido a límite de iteraciones alcanzado",
            "orchestrator_reasoning": "Se alcanzó el máximo de iteraciones permitidas",
        }
    
    # Build context for the orchestrator
    state_context = build_state_context(state)
    
    try:
        messages = [
            SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT.format(
                state_context=state_context,
                iteration_count=iteration_count,
                max_iterations=max_iterations
            )),
            HumanMessage(content=f"Consulta original: {state['user_input']}\n\nDecide el siguiente paso. Responde SOLO con JSON válido.")
        ]
        
        llm_json = llm.bind(response_format={"type": "json_object"})
        response = llm_json.invoke(messages)
        result = json.loads(response.content)
        
        next_agent = result.get("next_agent", "finalizer")
        task_description = result.get("task_description", "Procesar solicitud")
        reasoning = result.get("reasoning", "")
        
        # Log the orchestrator decision
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Orchestrator decision: next_agent={next_agent}, reasoning={reasoning[:100]}")
        
        # Validate next_agent
        valid_agents = ["scraper", "classifier", "evaluator", "venn", "db_query", "finalizer"]
        if next_agent not in valid_agents:
            logger.warning(f"Invalid next_agent '{next_agent}', defaulting to finalizer")
            next_agent = "finalizer"
        
        return {
            **state,
            "iteration_count": iteration_count,
            "current_agent": next_agent,
            "task_description": task_description,
            "orchestrator_reasoning": reasoning,
        }
        
    except Exception as e:
        # On error, try to continue gracefully
        error_msg = f"Error en orquestador: {str(e)}"
        errors = state.get("errors", []) + [error_msg]
        
        # Decide next step based on current state
        if not state.get("scraped_data"):
            next_agent = "scraper"
            task = "Buscar información sobre organizaciones"
        elif not state.get("classified_data"):
            next_agent = "classifier"
            task = "Clasificar datos scrapeados"
        else:
            next_agent = "finalizer"
            task = "Generar respuesta con datos disponibles"
        
        return {
            **state,
            "iteration_count": iteration_count,
            "current_agent": next_agent,
            "task_description": task,
            "orchestrator_reasoning": f"Fallback debido a error: {error_msg}",
            "errors": errors,
        }


class OrchestratorAgent:
    """
    Orchestrator Agent class for use outside of LangGraph.
    """
    
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o"
    
    @traceable(name="orchestrator_decide")
    def decide_next_step(self, user_input: str, current_state: dict) -> dict:
        """
        Decide the next step based on user input and current state.
        
        Args:
            user_input: The user's query
            current_state: Current state of the pipeline
            
        Returns:
            Dictionary with next_agent, task_description, and reasoning
        """
        # Convert to AgentState-like format
        mock_state = {
            "user_input": user_input,
            **current_state
        }
        state_context = build_state_context(mock_state)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": ORCHESTRATOR_SYSTEM_PROMPT.format(
                        state_context=state_context,
                        iteration_count=current_state.get("iteration_count", 0),
                        max_iterations=current_state.get("max_iterations", 10)
                    )
                },
                {
                    "role": "user",
                    "content": f"Consulta: {user_input}"
                }
            ],
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
