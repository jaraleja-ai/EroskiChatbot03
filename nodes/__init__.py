
# =====================================================
# nodes/__init__.py - Exportaciones del módulo ACTUALIZADO
# =====================================================
from .base_node import BaseNode 
from .nodes_utils import (node_wrapper, 
                          validate_email_format, 
                          validate_name_format, 
                          names_are_similar)

# Nodos específicos de Eroski (ahora en nodes/ directamente)
from .authenticate import authenticate_employee_node
from .classify import classify_query_node
from .collect_incident import collect_incident_details_node
from .search_solution import search_solution_node
from .search_knowledge import search_knowledge_node
from .escalate import escalate_supervisor_node
from .verify import verify_resolution_node
from .finalize import finalize_conversation_node

__all__ = [
    "BaseWorkflow",
    "node_wrapper",
    "validate_email_format",
    "validate_name_format",
    "names_are_similar",
    "authenticate_employee_node",
    "classify_query_node",
    "collect_incident_details_node",
    "search_solution_node",
    "search_knowledge_node",
    "escalate_supervisor_node",
    "verify_resolution_node",
    "finalize_conversation_node"
]