
# =====================================================
# workflows/__init__.py - Exportaciones
# =====================================================
from .base_workflow import BaseWorkflow
from .incidencia_workflow import IncidenciaWorkflow
from .consulta_workflow import ConsultaWorkflow
from .workflow_manager import (WorkflowManager, 
                               WorkflowType, 
                               get_workflow_manager, 
                               reset_workflow_manager)
from .escalacion_workflow import EscalacionWorkflow
from .conversation_step import ConversationSteps

__all__ = [
    "BaseWorkflow",
    "ConversationSteps",
    "escalacion_workflow",
    "IncidenciaWorkflow",
    "ConsultaWorkflow",
    "WorkflowManager",
    "WorkflowType",
    "get_workflow_manager",
    "reset_workflow_manager"
]