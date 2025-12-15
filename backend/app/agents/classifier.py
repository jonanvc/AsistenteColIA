"""
Classifier Agent

Responsible for classifying scraped data and inserting it into the database.
Structures raw data into proper database models.

Uses GPT-4o for accurate classification and data structuring.
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
    max_tokens=3000,
)


# Colombia departments and their codes (DANE)
COLOMBIA_DEPARTMENTS = {
    "amazonas": "91", "antioquia": "05", "arauca": "81", "atlantico": "08",
    "bolivar": "13", "boyaca": "15", "caldas": "17", "caqueta": "18",
    "casanare": "85", "cauca": "19", "cesar": "20", "choco": "27",
    "cordoba": "23", "cundinamarca": "25", "guainia": "94", "guaviare": "95",
    "huila": "41", "la guajira": "44", "magdalena": "47", "meta": "50",
    "narino": "52", "norte de santander": "54", "putumayo": "86",
    "quindio": "63", "risaralda": "66", "san andres": "88", "santander": "68",
    "sucre": "70", "tolima": "73", "valle del cauca": "76", "vaupes": "97",
    "vichada": "99", "bogota": "11",
}

# Organization types - Civil society organizations led by women for peace-building
ORGANIZATION_TYPES = [
    "construcción_paz", "derechos_humanos", "víctimas_conflicto",
    "liderazgo_femenino", "participación_política", "desarrollo_comunitario",
    "empoderamiento_económico", "memoria_histórica", "reconciliación",
    "justicia_transicional", "educación_paz", "salud_mental",
    "reintegración", "medio_ambiente", "cultura_paz", "otro"
]


CLASSIFIER_SYSTEM_PROMPT = """Eres un agente clasificador que EXTRAE y ESTRUCTURA información de organizaciones de mujeres constructoras de paz en Colombia.

TAREA PRINCIPAL: Analiza el texto y EXTRAE cada campo por separado. NO pongas todo el texto en la descripción.

CÓMO EXTRAER CAMPOS DEL TEXTO DEL USUARIO:
- "Crea Asmubuli" → name: "Asmubuli"
- "en Bogotá" o "localización Bogotá" → department_code: "11", municipality_code: "11001", latitude: 4.6097, longitude: -74.0817
- "alcance nacional" → territorial_scope: "nacional"
- "alcance departamental" → territorial_scope: "departamental"
- "líder es una mujer" o "la líder es mujer" → leader_is_woman: true
- "líder: María García" o "la líder es María" → leader_name: "María García", leader_is_woman: true
- "enfoque desde abajo" o "grassroots" → approach: "bottom_up"
- "enfoque desde arriba" o "gubernamental" → approach: "top_down"
- "enfocada en paz" o "construcción de paz" → is_peace_building: true

CÓDIGOS DANE:
- Bogotá: department_code="11", municipality_code="11001", lat=4.6097, lon=-74.0817
- Medellín: department_code="05", municipality_code="05001", lat=6.2442, lon=-75.5812
- Cali: department_code="76", municipality_code="76001", lat=3.4516, lon=-76.5320
- Barranquilla: department_code="08", municipality_code="08001", lat=10.9685, lon=-74.7813

DATOS A PROCESAR:
{scraped_data}

Responde SOLO con JSON:
{{
    "classified_organizations": [
        {{
            "name": "SOLO el nombre de la organización (ej: Asmubuli)",
            "description": "Breve descripción de actividades SI SE PROPORCIONA, o null",
            "approach": "bottom_up|top_down|mixed|unknown",
            "women_count": número o null,
            "leader_is_woman": true|false|null,
            "leader_name": "nombre completo o null",
            "territorial_scope": "municipal|departamental|regional|nacional|internacional",
            "department_code": "código 2 dígitos",
            "department_name": "nombre departamento",
            "municipality_code": "código 5 dígitos o null",
            "municipality_name": "nombre municipio o null",
            "latitude": número decimal,
            "longitude": número decimal,
            "is_peace_building": true|false,
            "is_international": true|false,
            "status": "active",
            "confidence": 0.8,
            "source_url": null
        }}
    ],
    "summary": "Organización extraída del input del usuario",
    "total_processed": 1,
    "valid_records": 1,
    "issues_found": []
}}

EJEMPLO - Input: "Crea Asmubuli en Bogotá, alcance nacional, líder Fidelia Suárez, enfoque desde abajo"
Resultado esperado:
- name: "Asmubuli" (NO "Crea Asmubuli en Bogotá...")
- territorial_scope: "nacional"
- department_code: "11"
- municipality_code: "11001"
- latitude: 4.6097
- longitude: -74.0817
- leader_name: "Fidelia Suárez"
- leader_is_woman: true
- approach: "bottom_up"
- description: null (no se proporcionó descripción específica)"""


def normalize_department(dept_name: str) -> tuple[Optional[str], Optional[str]]:
    """
    Normalize department name to DANE code.
    
    Args:
        dept_name: Department name (possibly with typos)
        
    Returns:
        Tuple of (code, normalized_name)
    """
    if not dept_name:
        return None, None
    
    dept_lower = dept_name.lower().strip()
    
    # Direct match
    if dept_lower in COLOMBIA_DEPARTMENTS:
        return COLOMBIA_DEPARTMENTS[dept_lower], dept_lower.title()
    
    # Partial match
    for name, code in COLOMBIA_DEPARTMENTS.items():
        if name in dept_lower or dept_lower in name:
            return code, name.title()
    
    # Common variations
    variations = {
        "bogotá": ("11", "Bogotá D.C."),
        "bogota d.c.": ("11", "Bogotá D.C."),
        "norte santander": ("54", "Norte de Santander"),
        "valle": ("76", "Valle del Cauca"),
        "san andrés": ("88", "San Andrés"),
        "guajira": ("44", "La Guajira"),
        "nariño": ("52", "Nariño"),
    }
    
    for var, (code, name) in variations.items():
        if var in dept_lower:
            return code, name
    
    return None, dept_name


def classify_organization_type(description: str, activities: str = "") -> str:
    """
    Classify organization type based on description and activities.
    Focused on women-led peace-building organizations.
    """
    text = f"{description} {activities}".lower()
    
    type_keywords = {
        "construcción_paz": ["paz", "pacificación", "no violencia", "convivencia"],
        "derechos_humanos": ["derechos humanos", "ddhh", "defensa derechos"],
        "víctimas_conflicto": ["víctimas", "desplazados", "conflicto armado"],
        "liderazgo_femenino": ["liderazgo", "mujeres líderes", "empoderamiento"],
        "participación_política": ["participación", "incidencia política", "ciudadanía"],
        "desarrollo_comunitario": ["comunidad", "desarrollo local", "territorio"],
        "empoderamiento_económico": ["económico", "emprendimiento", "productivo"],
        "memoria_histórica": ["memoria", "historia", "verdad", "recuerdo"],
        "reconciliación": ["reconciliación", "perdón", "sanación"],
        "justicia_transicional": ["justicia", "reparación", "transición"],
        "educación_paz": ["educación", "formación", "capacitación", "pedagogía"],
        "salud_mental": ["salud mental", "psicosocial", "trauma", "bienestar"],
        "reintegración": ["reintegración", "reincorporación", "excombatientes"],
        "medio_ambiente": ["ambiente", "ecología", "sostenibilidad"],
        "cultura_paz": ["cultura", "arte", "expresión", "tradición"],
    }
    
    for org_type, keywords in type_keywords.items():
        if any(kw in text for kw in keywords):
            return org_type
    
    return "otro"


@traceable(name="classifier_agent")
def classifier_node(state: "AgentState") -> "AgentState":
    """
    Classifier node that structures data for database insertion.
    Can process scraped data OR extract data directly from user input.
    
    Uses GPT-4o for accurate classification.
    """
    scraped_data = state.get("scraped_data", [])
    user_input = state.get("user_input", "")
    
    # If no scraped data, try to extract organization info directly from user input
    if not scraped_data:
        # Create a synthetic data entry from user input
        scraped_data = [{
            "source": "user_input",
            "raw_text": user_input,
            "name": "",  # Will be extracted by classifier
            "description": user_input,
        }]
    
    try:
        messages = [
            SystemMessage(content=CLASSIFIER_SYSTEM_PROMPT.format(
                scraped_data=json.dumps(scraped_data, ensure_ascii=False, indent=2)
            )),
            HumanMessage(content=f"Clasifica los {len(scraped_data)} registros de organizaciones de mujeres constructoras de paz y prepáralos para la base de datos. Responde SOLO con JSON válido.")
        ]
        
        llm_json = llm.bind(response_format={"type": "json_object"})
        response = llm_json.invoke(messages)
        result = json.loads(response.content)
        
        classified = result.get("classified_organizations", [])
        summary = result.get("summary", "Clasificación completada")
        issues = result.get("issues_found", [])
        
        # Post-process: normalize department codes
        for org in classified:
            if org.get("department_name") and not org.get("department_code"):
                code, name = normalize_department(org["department_name"])
                org["department_code"] = code
                org["department_name"] = name
            
            # Ensure organization type is valid
            if org.get("type") not in ORGANIZATION_TYPES:
                org["type"] = classify_organization_type(
                    org.get("description", ""),
                    org.get("name", "")
                )
        
        # Prepare DB operations
        db_operations = []
        for org in classified:
            if org.get("confidence", 0) >= 0.5:  # Only high-confidence records
                db_operations.append({
                    "operation": "insert_or_update",
                    "table": "organizations",
                    "data": {
                        "name": org["name"],
                        "description": org.get("description"),
                        "territorial_scope": org.get("territorial_scope", "municipal"),
                        "department_code": org.get("department_code"),
                        "municipality_code": org.get("municipality_code"),
                        "latitude": org.get("latitude"),
                        "longitude": org.get("longitude"),
                        "approach": org.get("approach", "unknown"),
                        "women_count": org.get("women_count"),
                        "leader_is_woman": org.get("leader_is_woman"),
                        "leader_name": org.get("leader_name"),
                        "is_peace_building": org.get("is_peace_building", True),
                        "is_international": org.get("is_international", False),
                        "url": org.get("source_url"),
                    },
                    "confidence": org.get("confidence", 0.5),
                })
        
        return {
            **state,
            "classified_data": classified,
            "classification_summary": summary,
            "db_operations": db_operations,
            "current_agent": "evaluator",
        }
        
    except Exception as e:
        error_msg = f"Error en clasificación: {str(e)}"
        errors = state.get("errors", []) + [error_msg]
        
        return {
            **state,
            "classified_data": [],
            "classification_summary": f"Error: {error_msg}",
            "db_operations": [],
            "errors": errors,
            "current_agent": "finalizer",  # Skip to finalizer on error
        }


class ClassifierAgent:
    """
    Classifier Agent class for use outside of LangGraph.
    """
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.2,
            max_tokens=3000,
        )
    
    @traceable(name="classifier_process")
    def classify_organizations(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Classify a list of raw organization data.
        
        Args:
            raw_data: List of raw organization dictionaries
            
        Returns:
            Classified and structured data
        """
        if not raw_data:
            return {
                "classified_organizations": [],
                "summary": "No data to classify",
                "valid_records": 0,
            }
        
        messages = [
            SystemMessage(content=CLASSIFIER_SYSTEM_PROMPT.format(
                scraped_data=json.dumps(raw_data, ensure_ascii=False, indent=2)
            )),
            HumanMessage(content=f"Clasifica los {len(raw_data)} registros. Responde SOLO con JSON válido.")
        ]
        
        llm_json = self.llm.bind(response_format={"type": "json_object"})
        response = llm_json.invoke(messages)
        return json.loads(response.content)
    
    @traceable(name="classifier_single")
    def classify_single(self, organization_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Classify a single organization record.
        
        Args:
            organization_data: Raw organization dictionary
            
        Returns:
            Classified organization
        """
        result = self.classify_organizations([organization_data])
        classified = result.get("classified_organizations", [])
        return classified[0] if classified else {}
    
    def prepare_db_record(self, classified_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare a classified record for database insertion.
        
        Args:
            classified_data: Classified organization data
            
        Returns:
            Database-ready record
        """
        return {
            "name": classified_data.get("name", ""),
            "description": classified_data.get("description"),
            "territorial_scope": classified_data.get("territorial_scope", "municipal"),
            "department": classified_data.get("department_code"),
            "municipality_code": classified_data.get("municipality_code"),
            "latitude": classified_data.get("latitude"),
            "longitude": classified_data.get("longitude"),
            "status": classified_data.get("status", "active"),
        }
