"""
Agent Chat API Routes

Provides endpoints for interacting with the multi-agent system.
"""
import uuid
from typing import Optional, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.base import get_db
from ..agents.graph import run_agent_pipeline, create_initial_state, get_graph_image
from ..agents.guardrails import validate_user_input, GuardrailResult
from ..agents.langsmith_config import configure_langsmith, log_feedback
from ..models.db_models import PendingValidation, PendingItemType

# Configure LangSmith on import
configure_langsmith()

router = APIRouter(prefix="/chat", tags=["Agent Chat"])


async def _create_pending_validations(
    session_id: str,
    pending_organizations: list,
    pending_sources: list,
    db: AsyncSession
):
    """Create pending validation records in database."""
    from datetime import timedelta
    
    expires_at = datetime.utcnow() + timedelta(hours=24)
    
    # Create pending validations for organizations
    for org in pending_organizations:
        validation = PendingValidation(
            item_type=PendingItemType.ORGANIZATION,
            session_id=session_id,
            pending_data=org,
            agent_reasoning=org.get("approach_reasoning", ""),
            confidence_score=org.get("confianza", org.get("confidence", 0.5)),
            source_urls=[org.get("fuente_url")] if org.get("fuente_url") else None,
            status="pending",
            expires_at=expires_at,
        )
        db.add(validation)
    
    # Create pending validations for sources
    for source in pending_sources:
        validation = PendingValidation(
            item_type=PendingItemType.INFO_SOURCE,
            session_id=session_id,
            pending_data=source,
            agent_reasoning=source.get("description", ""),
            confidence_score=source.get("reliability_score", 0.5),
            source_urls=[source.get("url")] if source.get("url") else None,
            status="pending",
            expires_at=expires_at,
        )
        db.add(validation)
    
    try:
        await db.commit()
    except Exception as e:
        await db.rollback()
        print(f"Error creating pending validations: {e}")


# Request/Response Models
class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    message: str = Field(..., min_length=1, max_length=5000, description="User message/query")
    session_id: Optional[str] = Field(None, description="Session ID for conversation continuity")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Busca organizaciones de mujeres constructoras de paz en Cauca",
                "session_id": None
            }
        }


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    response: str = Field(..., description="Agent response")
    session_id: str = Field(..., description="Session ID for future requests")
    success: bool = Field(..., description="Whether the request was successful")
    iterations: int = Field(0, description="Number of agent iterations")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    requires_validation: bool = Field(False, description="Whether user validation is required")
    pending_organizations: list = Field(default_factory=list, description="Organizations pending validation")
    pending_sources: list = Field(default_factory=list, description="Info sources pending validation")


class GuardrailCheckRequest(BaseModel):
    """Request for guardrail validation."""
    message: str = Field(..., min_length=1, max_length=5000)


class GuardrailCheckResponse(BaseModel):
    """Response for guardrail validation."""
    passed: bool
    message: str
    confidence: float
    topics: List[str]


class FeedbackRequest(BaseModel):
    """Request for providing feedback."""
    session_id: str
    run_id: Optional[str] = None
    score: float = Field(..., ge=0, le=1, description="Score from 0 to 1")
    comment: Optional[str] = None


class GraphVisualizationResponse(BaseModel):
    """Response with graph visualization."""
    mermaid: str
    description: str


# Session storage (in production, use Redis or database)
_sessions: dict = {}


def get_or_create_session(session_id: Optional[str]) -> str:
    """Get existing session or create new one."""
    if session_id and session_id in _sessions:
        return session_id
    
    new_id = str(uuid.uuid4())
    _sessions[new_id] = {
        "created_at": datetime.utcnow().isoformat(),
        "history": [],
    }
    return new_id


def add_to_history(session_id: str, role: str, content: str):
    """Add message to session history."""
    if session_id in _sessions:
        _sessions[session_id]["history"].append({
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
        })
        # Keep only last 20 messages
        _sessions[session_id]["history"] = _sessions[session_id]["history"][-20:]


@router.post("/send", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """
    Send a message to the multi-agent system.
    
    The system will:
    1. Validate the message against guardrails
    2. Route to the appropriate agents
    3. Search for organization information if needed
    4. Classify and validate the data
    5. Return a formatted response
    
    **Example queries:**
    - "Busca organizaciones de mujeres constructoras de paz en Cauca"
    - "¿Qué organizaciones de derechos humanos hay en Nariño?"
    - "Información sobre colectivos de mujeres víctimas en Meta"
    """
    session_id = get_or_create_session(request.session_id)
    
    try:
        # Get existing conversation history for context
        conversation_history = _sessions[session_id].get("history", [])
        
        # Add user message to history
        add_to_history(session_id, "user", request.message)
        
        # Run the agent pipeline with conversation history
        result = await run_agent_pipeline(request.message, session_id, conversation_history)
        
        response_text = result.get("response", "Lo siento, no pude procesar tu solicitud.")
        success = result.get("success", False)
        iterations = result.get("iterations", 0)
        errors = result.get("errors", [])
        requires_validation = result.get("requires_user_validation", False)
        pending_organizations = result.get("pending_organizations", [])
        pending_sources = result.get("pending_sources", [])
        
        # Create pending validations in database if needed
        if requires_validation:
            await _create_pending_validations(
                session_id, pending_organizations, pending_sources, db
            )
        
        # Add response to history
        add_to_history(session_id, "assistant", response_text)
        
        return ChatResponse(
            response=response_text,
            session_id=session_id,
            success=success,
            iterations=iterations,
            metadata={
                "errors": errors,
                "timestamp": datetime.utcnow().isoformat(),
            },
            requires_validation=requires_validation,
            pending_organizations=pending_organizations,
            pending_sources=pending_sources,
        )
        
    except Exception as e:
        error_msg = f"Error procesando la solicitud: {str(e)}"
        return ChatResponse(
            response=f"Lo siento, ocurrió un error al procesar tu solicitud. Por favor, intenta de nuevo.",
            session_id=session_id,
            success=False,
            iterations=0,
            metadata={"error": error_msg},
            requires_validation=False,
            pending_organizations=[],
            pending_sources=[],
        )


@router.post("/validate", response_model=GuardrailCheckResponse)
async def validate_message(request: GuardrailCheckRequest) -> GuardrailCheckResponse:
    """
    Validate a message against guardrails without processing.
    
    Use this to check if a message will be accepted before sending.
    """
    result: GuardrailResult = validate_user_input(request.message)
    
    return GuardrailCheckResponse(
        passed=result.passed,
        message=result.message,
        confidence=result.confidence,
        topics=result.detected_topics,
    )


@router.get("/history/{session_id}")
async def get_session_history(session_id: str) -> dict:
    """
    Get conversation history for a session.
    """
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = _sessions[session_id]
    return {
        "session_id": session_id,
        "created_at": session["created_at"],
        "messages": session["history"],
        "message_count": len(session["history"]),
    }


@router.delete("/history/{session_id}")
async def clear_session_history(session_id: str) -> dict:
    """
    Clear conversation history for a session.
    """
    if session_id in _sessions:
        _sessions[session_id]["history"] = []
        return {"message": "History cleared", "session_id": session_id}
    
    raise HTTPException(status_code=404, detail="Session not found")


@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest) -> dict:
    """
    Submit feedback for a chat response.
    
    This helps improve the system over time.
    """
    try:
        if request.run_id:
            await log_feedback(
                run_id=request.run_id,
                score=request.score,
                comment=request.comment,
            )
        
        # Store feedback locally as well
        if request.session_id in _sessions:
            if "feedback" not in _sessions[request.session_id]:
                _sessions[request.session_id]["feedback"] = []
            
            _sessions[request.session_id]["feedback"].append({
                "score": request.score,
                "comment": request.comment,
                "timestamp": datetime.utcnow().isoformat(),
            })
        
        return {"message": "Feedback received", "success": True}
        
    except Exception as e:
        return {"message": f"Error saving feedback: {str(e)}", "success": False}


@router.get("/graph", response_model=GraphVisualizationResponse)
async def get_graph_visualization() -> GraphVisualizationResponse:
    """
    Get the Mermaid diagram of the agent graph.
    
    Use this to visualize the multi-agent workflow.
    """
    try:
        mermaid = get_graph_image()
        return GraphVisualizationResponse(
            mermaid=mermaid,
            description="""
# Agent Graph Visualization

El sistema multi-agente sigue el siguiente flujo:

1. **Guardrails**: Valida que la consulta esté relacionada con organizaciones de la sociedad civil
2. **Orchestrator**: Decide qué agente debe procesar la solicitud
3. **Scraper**: Busca información en la web
4. **Classifier**: Clasifica y estructura los datos
5. **Evaluator**: Valida la calidad de los datos
6. **Finalizer**: Genera la respuesta final

Cada agente usa diferentes modelos de OpenAI según la complejidad:
- GPT-4o: Orquestador, Clasificador, Evaluador (tareas complejas)
- GPT-4o-mini: Guardrails, Scraper, Finalizer (tareas rápidas)
"""
        )
    except Exception as e:
        return GraphVisualizationResponse(
            mermaid="graph TD\n    Error[Error generating graph]",
            description=f"Error: {str(e)}"
        )


@router.get("/status")
async def get_system_status() -> dict:
    """
    Get the current status of the agent system.
    """
    import os
    
    return {
        "status": "operational",
        "agents": {
            "guardrails": "active",
            "orchestrator": "active",
            "scraper": "active",
            "classifier": "active",
            "evaluator": "active",
            "venn_agent": "active",
            "db_agent": "active",
            "validator": "active",
            "synthesizer": "active",
            "finalizer": "active",
        },
        "langsmith_enabled": os.getenv("LANGSMITH_TRACING", "false").lower() == "true",
        "active_sessions": len(_sessions),
        "timestamp": datetime.utcnow().isoformat(),
    }


# Example queries for documentation
EXAMPLE_QUERIES = [
    # Búsqueda de organizaciones
    {
        "query": "Busca organizaciones de mujeres constructoras de paz en Chocó",
        "description": "Búsqueda de organizaciones en un departamento específico",
        "category": "búsqueda"
    },
    {
        "query": "¿Cuántas organizaciones de mujeres hay registradas en Antioquia?",
        "description": "Consulta de conteo por departamento",
        "category": "búsqueda"
    },
    {
        "query": "Información sobre colectivos de mujeres líderes en Meta",
        "description": "Búsqueda de una organización específica",
        "category": "búsqueda"
    },
    {
        "query": "Lista de organizaciones de mujeres en la región Pacífica",
        "description": "Búsqueda regional por tipo de organización",
        "category": "búsqueda"
    },
    {
        "query": "Organizaciones de mujeres víctimas del conflicto en Nariño",
        "description": "Búsqueda por temática y región geográfica",
        "category": "búsqueda"
    },
    # Gestión de Variables Venn
    {
        "query": "Crea una variable llamada Liderazgo Femenino",
        "description": "Crear nueva variable Venn para análisis",
        "category": "venn"
    },
    {
        "query": "Agrega el proxy 'mujeres líderes' a Liderazgo Femenino",
        "description": "Agregar término de búsqueda a una variable",
        "category": "venn"
    },
    {
        "query": "Agrega los proxies 'reconciliación', 'víctimas', 'proceso de paz' a Construcción de Paz",
        "description": "Agregar múltiples proxies a una variable",
        "category": "venn"
    },
    {
        "query": "¿Qué variables Venn tenemos?",
        "description": "Listar todas las variables con sus proxies",
        "category": "venn"
    },
    {
        "query": "Elimina el proxy 'ejemplo' de la variable Prueba",
        "description": "Eliminar un proxy específico de una variable",
        "category": "venn"
    },
    {
        "query": "Elimina la variable Prueba",
        "description": "Eliminar una variable Venn completa",
        "category": "venn"
    },
]


@router.get("/examples")
async def get_example_queries() -> dict:
    """
    Get example queries that work well with the system.
    Includes examples for search and Venn variable management.
    """
    return {
        "examples": EXAMPLE_QUERIES,
        "categories": {
            "búsqueda": "Buscar información sobre organizaciones de mujeres",
            "venn": "Gestionar variables Venn, proxies y análisis"
        },
        "tips": [
            "Incluye el departamento o municipio para resultados más precisos",
            "Especifica el tipo de organización (mujeres constructoras de paz, líderes comunitarias, etc.)",
            "Puedes preguntar sobre una organización específica por nombre",
            "Las consultas en español funcionan mejor",
            "Usa 'Crea una variable llamada X' para crear variables Venn",
            "Usa 'Agrega el proxy Y a X' para agregar términos de búsqueda",
            "Usa '¿Qué variables tenemos?' para ver todas las variables Venn",
        ]
    }
