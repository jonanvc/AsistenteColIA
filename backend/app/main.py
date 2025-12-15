"""
Main FastAPI application entry point.

Asistente de Recopilación y Análisis de Datos de Organizaciones 
de la Sociedad Civil Lideradas por Mujeres en Colombia

Features:
- AI-powered chat interface
- Automated web scraping
- Data classification and validation
- LangSmith tracing
- Scheduled updates
- Venn diagram management from chat
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import os

from app.api.routes import router as api_router
from app.api.venndiagram import router as venn_router
from app.api.organizations import router as organizations_router
from app.api.venn_variables import router as venn_variables_router
from app.api.venn_results import router as venn_results_router
from app.api.match_evidence import router as match_evidence_router
from app.api.scraping import router as scraping_router
from app.api.geography import router as geography_router
from app.api.agent_chat import router as agent_chat_router
from app.api.scheduler_routes import router as scheduler_router
from app.api.info_sources import router as info_sources_router
from app.api.validations import router as validations_router
from app.db.base import init_db
from app.agents.langsmith_config import configure_langsmith
from app.agents.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup/shutdown events.
    """
    # Startup: Initialize database tables
    await init_db()
    
    # Configure LangSmith tracing
    configure_langsmith()
    
    # Start scheduler for automated jobs (only if enabled)
    if os.getenv("ENABLE_SCHEDULER", "true").lower() == "true":
        start_scheduler()
    
    yield
    
    # Shutdown: Stop scheduler
    stop_scheduler()


# Create FastAPI app
app = FastAPI(
    title="Asistente OSC Mujeres Colombia",
    description="""
## Asistente de Recopilación y Análisis de Datos de Organizaciones de la Sociedad Civil Lideradas por Mujeres en Colombia

API con sistema multi-agente basado en LangGraph para:
- 🤖 Chat inteligente con IA para búsqueda de organizaciones
- 🔍 Scraping automatizado de información web
- 📊 Clasificación y validación de datos
- 🗺️ Visualización geográfica
- 📈 Diagramas Venn para análisis (gestionados desde chat)
- ⏰ Actualizaciones automáticas semanales

### Enfoque:
Organizaciones sociales lideradas por mujeres que trabajen en construcción de paz.

### Agentes Disponibles:
- **Orquestador**: Coordina las tareas entre agentes
- **Scraper**: Búsqueda web de organizaciones
- **Clasificador**: Estructuración de datos
- **Evaluador**: Validación de calidad
- **Finalizador**: Formateo de respuestas
- **Venn**: Gestión de variables y proxies Venn
    """,
    version="3.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers - Order matters! More specific routes first
# Agent Chat - Main interface for multi-agent system
app.include_router(agent_chat_router, prefix="/api", tags=["Agent Chat"])
# Scheduler for automated jobs
app.include_router(scheduler_router, prefix="/api", tags=["Scheduler"])
# Information Sources management
app.include_router(info_sources_router, prefix="/api", tags=["Information Sources"])
# Pending Validations from chat
app.include_router(validations_router, prefix="/api", tags=["Validations"])
# Geography and data routes
app.include_router(geography_router, tags=["Colombia Geography"])
app.include_router(organizations_router, prefix="/api/organizations", tags=["Organizations Management"])
app.include_router(venn_router, prefix="/api/venn", tags=["Venn Diagram"])
app.include_router(venn_variables_router, prefix="/api/venn-variables", tags=["Venn Variables"])
app.include_router(venn_results_router, prefix="/api/venn-results", tags=["Venn Results"])
app.include_router(match_evidence_router, prefix="/api/match-evidence", tags=["Match Evidence"])
app.include_router(scraping_router, prefix="/api/scraping", tags=["Scraping"])
app.include_router(api_router, prefix="/api", tags=["API"])


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {"status": "ok", "message": "Asistente OSC Mujeres Colombia API is running"}


@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
