"""
Evaluator Agent

Responsible for validating the quality and correctness of data
processed by other agents. Acts as quality control.

Uses GPT-4o for thorough evaluation.
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

# Initialize ChatOpenAI client (integrates with LangSmith automatically)
llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.2,
    max_tokens=2000,
)


EVALUATOR_SYSTEM_PROMPT = """Eres un agente evaluador de calidad de datos para un sistema de gestión de organizaciones de la sociedad civil lideradas por mujeres constructoras de paz en Colombia.

Tu rol es:
1. Validar la precisión de los datos clasificados
2. Verificar la consistencia de la información
3. Detectar posibles errores o datos duplicados
4. Evaluar la completitud de los registros
5. Proporcionar feedback para mejoras

CRITERIOS DE EVALUACIÓN:

1. **Completitud** (0-25 puntos):
   - Nombre de la organización presente y válido
   - Ubicación geográfica identificada
   - Tipo de organización clasificado
   - Datos de contacto disponibles

2. **Precisión** (0-25 puntos):
   - Códigos DANE válidos
   - Formato correcto de datos
   - Información coherente y sin contradicciones

3. **Confiabilidad** (0-25 puntos):
   - Fuentes verificables
   - Datos corroborados por múltiples fuentes
   - Información actualizada

4. **Utilidad** (0-25 puntos):
   - Datos suficientes para el propósito del sistema
   - Información procesable y estructurada
   - Valor agregado para el usuario

DATOS A EVALUAR:
{data_to_evaluate}

CONTEXTO DE LA SOLICITUD:
{user_context}

Responde con un JSON:
{{
    "overall_score": 0-100,
    "evaluation_passed": true/false (score >= 60),
    "criteria_scores": {{
        "completitud": 0-25,
        "precision": 0-25,
        "confiabilidad": 0-25,
        "utilidad": 0-25
    }},
    "individual_evaluations": [
        {{
            "name": "nombre de la organización",
            "score": 0-100,
            "passed": true/false,
            "issues": ["lista de problemas"],
            "suggestions": ["sugerencias de mejora"]
        }}
    ],
    "corrections_needed": ["acciones correctivas si score < 60"],
    "feedback": "Resumen de la evaluación",
    "recommendation": "proceed|retry_scraping|retry_classification|manual_review"
}}

UMBRAL DE APROBACIÓN: 60 puntos
- Si score >= 60: Datos aprobados para uso
- Si score < 60: Requiere correcciones"""


def calculate_data_completeness(data: Dict[str, Any]) -> float:
    """
    Calculate completeness score for a data record.
    
    Args:
        data: Organization data dictionary
        
    Returns:
        Completeness score 0-1
    """
    required_fields = ["name", "department_code", "type", "status"]
    optional_fields = ["description", "municipality_code", "contact", "members_count", "founded_date"]
    
    required_score = sum(1 for f in required_fields if data.get(f)) / len(required_fields)
    optional_score = sum(1 for f in optional_fields if data.get(f)) / len(optional_fields)
    
    return (required_score * 0.7) + (optional_score * 0.3)


def validate_dane_code(code: str, is_department: bool = True) -> bool:
    """
    Validate DANE geographic code.
    
    Args:
        code: DANE code to validate
        is_department: True for department (2 digits), False for municipality (5 digits)
        
    Returns:
        True if valid
    """
    if not code:
        return False
    
    if is_department:
        return len(code) == 2 and code.isdigit()
    else:
        return len(code) == 5 and code.isdigit()


def quick_validation(classified_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Perform quick validation without LLM.
    
    Args:
        classified_data: List of classified organizations
        
    Returns:
        Quick validation results
    """
    results = []
    total_score = 0
    
    for data in classified_data:
        issues = []
        score = 0
        
        # Name check
        if data.get("name"):
            score += 25
        else:
            issues.append("Nombre faltante")
        
        # Location check
        if validate_dane_code(data.get("department_code", ""), True):
            score += 15
        else:
            issues.append("Código de departamento inválido")
        
        if data.get("municipality_code"):
            if validate_dane_code(data.get("municipality_code", ""), False):
                score += 10
            else:
                issues.append("Código de municipio inválido")
        
        # Type check
        if data.get("type"):
            score += 15
        else:
            issues.append("Tipo de organización no clasificado")
        
        # Confidence check
        confidence = data.get("confidence", 0)
        score += int(confidence * 20)
        
        # Source check
        if data.get("source_url"):
            score += 15
        else:
            issues.append("Sin URL fuente")
        
        results.append({
            "name": data.get("name", "Sin nombre"),
            "score": score,
            "passed": score >= 60,
            "issues": issues,
        })
        total_score += score
    
    avg_score = total_score / len(classified_data) if classified_data else 0
    
    return {
        "overall_score": avg_score,
        "evaluation_passed": avg_score >= 60,
        "individual_evaluations": results,
        "total_records": len(classified_data),
        "passed_records": sum(1 for r in results if r["passed"]),
    }


@traceable(name="evaluator_agent")
def evaluator_node(state: "AgentState") -> "AgentState":
    """
    Evaluator node that validates data quality.
    
    Uses GPT-4o for thorough evaluation.
    """
    classified_data = state.get("classified_data", [])
    scraped_data = state.get("scraped_data", [])
    user_input = state["user_input"]
    
    # If no data to evaluate, pass through
    if not classified_data and not scraped_data:
        return {
            **state,
            "evaluation_passed": True,
            "evaluation_score": 0.0,
            "evaluation_feedback": "No hay datos para evaluar",
            "corrections_needed": [],
            "current_agent": "finalizer",
        }
    
    # Data to evaluate (prioritize classified, fallback to scraped)
    data_to_evaluate = classified_data if classified_data else scraped_data
    
    # Quick validation first
    quick_result = quick_validation(data_to_evaluate)
    
    # If quick validation passes with high score, skip LLM
    if quick_result["overall_score"] >= 80:
        return {
            **state,
            "evaluation_passed": True,
            "evaluation_score": quick_result["overall_score"] / 100,
            "evaluation_feedback": f"Validación rápida: {quick_result['passed_records']}/{quick_result['total_records']} registros aprobados",
            "corrections_needed": [],
            "current_agent": "finalizer",
        }
    
    # Use LLM for detailed evaluation
    try:
        messages = [
            SystemMessage(content=EVALUATOR_SYSTEM_PROMPT.format(
                data_to_evaluate=json.dumps(data_to_evaluate[:10], ensure_ascii=False, indent=2),
                user_context=user_input
            )),
            HumanMessage(content=f"Evalúa la calidad de estos {len(data_to_evaluate)} registros de organizaciones. Responde SOLO con JSON válido.")
        ]
        
        llm_json = llm.bind(response_format={"type": "json_object"})
        response = llm_json.invoke(messages)
        result = json.loads(response.content)
        
        overall_score = result.get("overall_score", 50) / 100
        passed = result.get("evaluation_passed", overall_score >= 0.6)
        feedback = result.get("feedback", "Evaluación completada")
        corrections = result.get("corrections_needed", [])
        recommendation = result.get("recommendation", "proceed")
        
        # Determine next agent based on recommendation
        if passed or recommendation == "proceed":
            next_agent = "finalizer"
        elif recommendation == "retry_scraping":
            next_agent = "orchestrator"
            corrections = corrections or ["Buscar más información en otras fuentes"]
        elif recommendation == "retry_classification":
            next_agent = "orchestrator"
            corrections = corrections or ["Re-clasificar datos con más contexto"]
        else:
            next_agent = "finalizer"
        
        return {
            **state,
            "evaluation_passed": passed,
            "evaluation_score": overall_score,
            "evaluation_feedback": feedback,
            "corrections_needed": corrections,
            "current_agent": next_agent,
        }
        
    except Exception as e:
        error_msg = f"Error en evaluación: {str(e)}"
        errors = state.get("errors", []) + [error_msg]
        
        # On error, use quick validation results
        return {
            **state,
            "evaluation_passed": quick_result["overall_score"] >= 60,
            "evaluation_score": quick_result["overall_score"] / 100,
            "evaluation_feedback": f"Validación básica: {error_msg}",
            "corrections_needed": [],
            "errors": errors,
            "current_agent": "finalizer",
        }


class EvaluatorAgent:
    """
    Evaluator Agent class for use outside of LangGraph.
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.2,
            max_tokens=2000,
        )
    
    @traceable(name="evaluator_validate")
    def validate(self, data: List[Dict[str, Any]], context: str = "") -> Dict[str, Any]:
        """
        Validate a list of data records.
        
        Args:
            data: List of data dictionaries to validate
            context: Additional context about the data
            
        Returns:
            Validation results
        """
        if not data:
            return {
                "overall_score": 0,
                "evaluation_passed": False,
                "feedback": "No data to validate",
            }
        
        messages = [
            SystemMessage(content=EVALUATOR_SYSTEM_PROMPT.format(
                data_to_evaluate=json.dumps(data[:10], ensure_ascii=False, indent=2),
                user_context=context
            )),
            HumanMessage(content=f"Evalúa estos {len(data)} registros. Responde SOLO con JSON válido.")
        ]
        
        llm_json = self.llm.bind(response_format={"type": "json_object"})
        response = llm_json.invoke(messages)
        return json.loads(response.content)
    
    @traceable(name="evaluator_quick")
    def quick_validate(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Perform quick validation without LLM.
        
        Args:
            data: List of data dictionaries
            
        Returns:
            Quick validation results
        """
        return quick_validation(data)
    
    def validate_single(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a single record.
        
        Args:
            record: Data dictionary
            
        Returns:
            Validation result for the record
        """
        result = self.validate([record])
        evals = result.get("individual_evaluations", [])
        return evals[0] if evals else {"passed": False, "score": 0}
