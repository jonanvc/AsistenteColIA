"""
Multi-Agent System for Civil Society Organization Data Collection
Uses LangGraph for orchestration and LangSmith for tracing
"""
"""
Multi-Agent System for Organization Management

This module provides a LangGraph-based multi-agent system for:
- Searching and scraping organization information (women-led peace-building organizations)
- Classifying and structuring data
- Validating data quality
- Generating user-friendly responses
- Managing Venn diagrams and variables

Agents:
    - OrchestratorAgent: Routes tasks to appropriate agents
    - ScraperAgent: Web search using Tavily
    - ClassifierAgent: Data classification and structuring
    - EvaluatorAgent: Data quality validation
    - FinalizerAgent: Response formatting
    - VennAgent: Venn diagram management

Usage:
    from app.agents import run_agent_pipeline
    result = await run_agent_pipeline("buscar organizaciones de mujeres constructoras de paz", session_id)
"""

from .graph import (
    create_agent_graph,
    AgentState,
    run_agent_pipeline,
    get_graph_image,
    compile_graph_with_memory,
)
from .orchestrator import OrchestratorAgent, orchestrator_node
from .scraper import ScraperAgent, scraper_node
from .classifier import ClassifierAgent, classifier_node
from .evaluator import EvaluatorAgent, evaluator_node
from .finalizer import FinalizerAgent, finalizer_node
from .guardrails import validate_user_input, is_on_topic, GuardrailResult
from .langsmith_config import configure_langsmith, get_langsmith_client


__all__ = [
    # Graph
    "create_agent_graph",
    "AgentState",
    "run_agent_pipeline",
    "get_graph_image",
    "compile_graph_with_memory",
    # Agents
    "OrchestratorAgent",
    "ScraperAgent",
    "ClassifierAgent",
    "EvaluatorAgent",
    "FinalizerAgent",
    # Node functions
    "orchestrator_node",
    "scraper_node",
    "classifier_node",
    "evaluator_node",
    "finalizer_node",
    # Guardrails
    "validate_user_input",
    "is_on_topic",
    "GuardrailResult",
    # Config
    "configure_langsmith",
    "get_langsmith_client",
]

__all__ = [
    "create_agent_graph",
    "AgentState",
    "OrchestratorAgent",
    "ScraperAgent",
    "ClassifierAgent",
    "EvaluatorAgent",
    "FinalizerAgent",
    "validate_user_input",
    "is_on_topic",
]
