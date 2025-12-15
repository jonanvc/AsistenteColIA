"""
LangGraph State and Graph Definition for Multi-Agent System

Asistente de Recopilación y Análisis de Datos de Organizaciones de la Sociedad Civil
Lideradas por Mujeres en Colombia

Graph Flow:
    User Input -> Guardrails -> Orchestrator -> [Scraper/Classifier/Evaluator/Venn] -> Finalizer -> Response

Agents:
    - Orchestrator (GPT-4o): Routes tasks to appropriate agents
    - Scraper (GPT-4o-mini): Searches web for organization information
    - Classifier (GPT-4o): Classifies and structures scraped data
    - Evaluator (GPT-4o): Validates data quality and correctness
    - Venn (GPT-4o-mini): Manages Venn variables, proxies, and results from chat
    - Finalizer (GPT-4o-mini): Formats final response for user
"""
import os
from typing import TypedDict, Annotated, Literal, List, Optional, Any
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langsmith import traceable

from .guardrails import validate_user_input, GuardrailResult
from .orchestrator import orchestrator_node
from .scraper import scraper_node
from .classifier import classifier_node
from .evaluator import evaluator_node
from .finalizer import finalizer_node
from .venn_agent import venn_agent_node
from .db_agent import db_agent_node


class AgentState(TypedDict):
    """State shared across all agents in the graph."""
    # User input
    user_input: str
    conversation_history: List[dict]
    
    # Guardrails
    guardrail_passed: bool
    guardrail_message: Optional[str]
    
    # Orchestrator decisions
    current_agent: str
    task_description: str
    orchestrator_reasoning: str
    iteration_count: int
    max_iterations: int
    
    # Scraper output
    scraped_data: List[dict]
    scraper_status: str
    urls_visited: List[str]
    suggested_sources: List[dict]  # New sources suggested by the agent
    
    # Classifier output
    classified_data: List[dict]
    classification_summary: str
    db_operations: List[dict]
    
    # Evaluator output
    evaluation_passed: bool
    evaluation_score: float
    evaluation_feedback: str
    corrections_needed: List[str]
    
    # Pending validations (for user approval)
    pending_organizations: List[dict]  # Organizations pending user validation
    pending_sources: List[dict]  # Sources pending user validation
    requires_user_validation: bool  # Whether the response needs user action
    
    # Venn agent output
    venn_response: Optional[str]  # Response from Venn agent
    venn_action_result: Optional[dict]  # Result of Venn action
    
    # DB agent output
    db_response: Optional[str]  # Response from DB agent
    
    # Final output
    final_response: str
    response_ready: bool
    
    # Metadata
    session_id: str
    started_at: str
    errors: List[str]


def create_initial_state(user_input: str, session_id: str, conversation_history: List[dict] = None) -> AgentState:
    """Create initial state for a new agent run."""
    return AgentState(
        user_input=user_input,
        conversation_history=conversation_history or [],
        guardrail_passed=False,
        guardrail_message=None,
        current_agent="guardrails",
        task_description="",
        orchestrator_reasoning="",
        iteration_count=0,
        max_iterations=10,
        scraped_data=[],
        scraper_status="pending",
        urls_visited=[],
        suggested_sources=[],
        classified_data=[],
        classification_summary="",
        db_operations=[],
        evaluation_passed=False,
        evaluation_score=0.0,
        evaluation_feedback="",
        corrections_needed=[],
        pending_organizations=[],
        pending_sources=[],
        requires_user_validation=False,
        venn_response=None,
        venn_action_result=None,
        final_response="",
        response_ready=False,
        session_id=session_id,
        started_at=datetime.utcnow().isoformat(),
        errors=[],
    )


def guardrails_node(state: AgentState) -> AgentState:
    """
    First node: Validate user input against guardrails.
    Ensures the request is related to organizations/Venn diagrams.
    """
    result: GuardrailResult = validate_user_input(state["user_input"])
    
    return {
        **state,
        "guardrail_passed": result.passed,
        "guardrail_message": result.message,
        "current_agent": "orchestrator" if result.passed else "blocked",
    }


def should_continue_after_guardrails(state: AgentState) -> Literal["orchestrator", "blocked"]:
    """Route after guardrails check."""
    if state["guardrail_passed"]:
        return "orchestrator"
    return "blocked"


def blocked_node(state: AgentState) -> AgentState:
    """Handle blocked requests that failed guardrails."""
    return {
        **state,
        "final_response": state["guardrail_message"] or "Lo siento, tu solicitud no está relacionada con organizaciones de la sociedad civil o diagramas Venn. Por favor, reformula tu pregunta.",
        "response_ready": True,
    }


def route_from_orchestrator(state: AgentState) -> Literal["scraper", "classifier", "evaluator", "venn", "db_query", "finalizer"]:
    """Route to the agent decided by orchestrator."""
    next_agent = state.get("current_agent", "finalizer")
    
    # Safety: max iterations
    if state["iteration_count"] >= state["max_iterations"]:
        return "finalizer"
    
    if next_agent in ["scraper", "classifier", "evaluator", "venn", "db_query", "finalizer"]:
        return next_agent
    
    return "finalizer"


def route_from_evaluator(state: AgentState) -> Literal["orchestrator", "finalizer"]:
    """Route after evaluation: back to orchestrator if corrections needed, or to finalizer."""
    if state["evaluation_passed"]:
        return "finalizer"
    
    # If we have corrections and haven't exceeded iterations, go back to orchestrator
    if state["corrections_needed"] and state["iteration_count"] < state["max_iterations"]:
        return "orchestrator"
    
    return "finalizer"


def create_agent_graph() -> StateGraph:
    """
    Create the LangGraph for the multi-agent system.
    
    Graph Structure:
    
        ┌─────────────┐
        │   START     │
        └──────┬──────┘
               │
               ▼
        ┌─────────────┐
        │ Guardrails  │
        └──────┬──────┘
               │
        ┌──────┴──────┐
        │             │
        ▼             ▼
    ┌───────┐   ┌─────────┐
    │Blocked│   │Orchestr.│◄─────────────┐
    └───┬───┘   └────┬────┘              │
        │            │                   │
        │     ┌──────┼──────┬────────┐   │
        │     ▼      ▼      ▼        ▼   │
        │  ┌─────┐┌─────┐┌─────┐┌─────┐  │
        │  │Scrap││Class││Eval.││Final│  │
        │  └──┬──┘└──┬──┘└──┬──┘└──┬──┘  │
        │     │      │      │      │     │
        │     └──────┴──────┘      │     │
        │            │             │     │
        │            └─────────────┘     │
        │                  │             │
        │            (if not passed)─────┘
        │                  │
        │            (if passed)
        │                  │
        ▼                  ▼
        └────────►   ┌─────────┐
                     │   END   │
                     └─────────┘
    """
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("guardrails", guardrails_node)
    workflow.add_node("blocked", blocked_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("scraper", scraper_node)
    workflow.add_node("classifier", classifier_node)
    workflow.add_node("evaluator", evaluator_node)
    workflow.add_node("venn", venn_agent_node)
    workflow.add_node("db_query", db_agent_node)
    workflow.add_node("finalizer", finalizer_node)
    
    # Set entry point
    workflow.set_entry_point("guardrails")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "guardrails",
        should_continue_after_guardrails,
        {
            "orchestrator": "orchestrator",
            "blocked": "blocked",
        }
    )
    
    # Blocked goes to END
    workflow.add_edge("blocked", END)
    
    # Orchestrator routes to different agents
    workflow.add_conditional_edges(
        "orchestrator",
        route_from_orchestrator,
        {
            "scraper": "scraper",
            "classifier": "classifier",
            "evaluator": "evaluator",
            "venn": "venn",
            "db_query": "db_query",
            "finalizer": "finalizer",
        }
    )
    
    # Scraper and Classifier go to Evaluator
    workflow.add_edge("scraper", "evaluator")
    workflow.add_edge("classifier", "evaluator")
    
    # Venn goes directly to finalizer
    workflow.add_edge("venn", "finalizer")
    
    # db_query goes directly to finalizer
    workflow.add_edge("db_query", "finalizer")
    
    # Evaluator routes back to orchestrator or to finalizer
    workflow.add_conditional_edges(
        "evaluator",
        route_from_evaluator,
        {
            "orchestrator": "orchestrator",
            "finalizer": "finalizer",
        }
    )
    
    # Finalizer goes to END
    workflow.add_edge("finalizer", END)
    
    return workflow


def compile_graph_with_memory():
    """Compile the graph with memory checkpointing."""
    workflow = create_agent_graph()
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


def get_graph_image():
    """Generate a Mermaid diagram of the graph."""
    try:
        workflow = create_agent_graph()
        # Compile the graph first, then get the visualization
        compiled = workflow.compile()
        return compiled.get_graph().draw_mermaid()
    except Exception as e:
        # Fallback: return a static Mermaid diagram if dynamic fails
        return """graph TD
    START((Start)) --> guardrails[🛡️ Guardrails]
    guardrails --> orchestrator[🎯 Orchestrator]
    orchestrator --> |scraper| scraper[🔍 Scraper]
    orchestrator --> |classifier| classifier[📊 Classifier]  
    orchestrator --> |evaluator| evaluator[✅ Evaluator]
    orchestrator --> |venn| venn[🔵 Venn Agent]
    orchestrator --> |db_query| db_query[🗃️ DB Query]
    orchestrator --> |finalizer| finalizer[📝 Finalizer]
    scraper --> evaluator
    classifier --> evaluator
    evaluator --> orchestrator
    venn --> finalizer
    db_query --> finalizer
    finalizer --> END((End))"""


@traceable(name="agent_pipeline")
async def run_agent_pipeline(user_input: str, session_id: str, conversation_history: List[dict] = None) -> dict:
    """
    Run the complete agent pipeline for a user query.
    
    Args:
        user_input: The user's query or instruction
        session_id: Unique session identifier
        conversation_history: Previous messages in the conversation for context
        
    Returns:
        Final response and metadata
    """
    app = compile_graph_with_memory()
    initial_state = create_initial_state(user_input, session_id, conversation_history)
    
    config = {"configurable": {"thread_id": session_id}}
    
    # Run the graph
    final_state = await app.ainvoke(initial_state, config)
    
    return {
        "response": final_state.get("final_response", ""),
        "success": final_state.get("response_ready", False),
        "iterations": final_state.get("iteration_count", 0),
        "errors": final_state.get("errors", []),
        "session_id": session_id,
    }
