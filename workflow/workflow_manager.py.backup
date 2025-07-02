
# =====================================================
# workflow/workflow_manager.py - Gestor de workflows CORREGIDO
# =====================================================
from typing import Dict, Type, Union, List, Any, Optional, TYPE_CHECKING
from enum import Enum
from workflow import BaseWorkflow
from langgraph.graph.state import CompiledStateGraph
import logging

# 🔥 SOLUCIÓN: Imports corregidos
from config.settings import get_settings  # ✅ Correcto
if TYPE_CHECKING:
    from .base_workflow import BaseWorkflow

class WorkflowType(str, Enum):
    """Tipos de workflow disponibles"""
    INCIDENCIA = "incidencia"
    ESCALACION = "escalacion"
    CONSULTA = "consulta"

class WorkflowManager:
    """
    Gestor centralizado de workflows.
    
    Responsabilidades:
    - Registrar y mantener workflows disponibles
    - Seleccionar workflow apropiado según contexto
    - Proporcionar acceso unificado a workflows
    - Manejar caché de workflows compilados
    """
    
    def __init__(self):
        self.workflows: Dict[str, BaseWorkflow] = {}
        self.logger = logging.getLogger("WorkflowManager")
        self.settings = get_settings()
        self._register_workflows()
    
    def _register_workflows(self):
        """Registrar todos los workflows disponibles"""
        try:
            self.logger.info("📋 Registrando workflows...")
            
            # 🔥 SOLUCIÓN: Registrar workflows con imports seguros
            
            # Workflow 1: IncidenciaWorkflow
            try:
                from .incidencia_workflow import IncidenciaWorkflow
                self.workflows[WorkflowType.INCIDENCIA] = IncidenciaWorkflow()
                self.logger.info("✅ IncidenciaWorkflow registrado")
            except ImportError as e:
                self.logger.warning(f"⚠️ IncidenciaWorkflow no disponible: {e}")
            except Exception as e:
                self.logger.error(f"❌ Error cargando IncidenciaWorkflow: {e}")
            
            # Workflow 2: ConsultaWorkflow (opcional)
            try:
                from .consulta_workflow import ConsultaWorkflow
                self.workflows[WorkflowType.CONSULTA] = ConsultaWorkflow()
                self.logger.info("✅ ConsultaWorkflow registrado")
            except ImportError as e:
                self.logger.warning(f"⚠️ ConsultaWorkflow no disponible: {e}")
            except Exception as e:
                self.logger.error(f"❌ Error cargando ConsultaWorkflow: {e}")
            
            # Workflow 3: EscalacionWorkflow (opcional)
            try:
                from .escalacion_workflow import EscalacionWorkflow
                self.workflows[WorkflowType.ESCALACION] = EscalacionWorkflow()
                self.logger.info("✅ EscalacionWorkflow registrado")
            except ImportError as e:
                self.logger.warning(f"⚠️ EscalacionWorkflow no disponible: {e}")
            except Exception as e:
                self.logger.error(f"❌ Error cargando EscalacionWorkflow: {e}")
            
            # Verificar que al menos un workflow esté disponible
            if not self.workflows:
                raise RuntimeError("❌ No se pudo cargar ningún workflow")
            
            self.logger.info(f"✅ {len(self.workflows)} workflows registrados: {list(self.workflows.keys())}")
            
        except Exception as e:
            self.logger.error(f"❌ Error registrando workflows: {e}")
            raise

    def get_workflow(self, workflow_name: str) -> BaseWorkflow:
        """
        Obtener workflow por nombre.
        
        Args:
            workflow_name: Nombre del workflow
            
        Returns:
            Instancia del workflow
            
        Raises:
            ValueError: Si el workflow no existe
        """
        if workflow_name not in self.workflows:
            available = list(self.workflows.keys())
            raise ValueError(f"Workflow '{workflow_name}' no encontrado. Disponibles: {available}")
        
        return self.workflows[workflow_name]
    
    def get_compiled_workflow(self, workflow_name: str) -> CompiledStateGraph:
        """
        Obtener workflow compilado listo para ejecución.
        
        Args:
            workflow_name: Nombre del workflow
            
        Returns:
            Grafo compilado
        """
        workflow = self.get_workflow(workflow_name)
        return workflow.compile()
    
    def list_workflows(self) -> List[str]:
        """
        Listar workflows disponibles.
        
        Returns:
            Lista de nombres de workflows
        """
        return list(self.workflows.keys())
    
    def get_default_workflow(self) -> BaseWorkflow:
        """
        Obtener workflow por defecto.
        
        Returns:
            Workflow de incidencias (por defecto)
        """
        return self.get_workflow(WorkflowType.INCIDENCIA)
    
    def select_workflow_for_context(self, context: Dict[str, Any]) -> str:
        """
        Seleccionar workflow apropiado según el contexto.
        
        Args:
            context: Contexto de la conversación
            
        Returns:
            Nombre del workflow más apropiado
        """
        # Por ahora, lógica simple
        # TODO: Implementar selección inteligente basada en análisis del contexto
        
        # Si ya hay escalación marcada
        if context.get("escalar_a_supervisor", False):
            return WorkflowType.ESCALACION
        
        # Si parece ser una consulta simple (palabras clave)
        ultimo_mensaje = ""
        if "messages" in context and context["messages"]:
            ultimo_mensaje = context["messages"][-1].content.lower()
        
        palabras_consulta = ["consulta", "pregunta", "estado", "información", "cómo", "dónde", "cuándo"]
        if any(palabra in ultimo_mensaje for palabra in palabras_consulta):
            return WorkflowType.CONSULTA
        
        # Por defecto, workflow de incidencias
        return WorkflowType.INCIDENCIA
    
    def get_workflow_metrics(self) -> Dict[str, Any]:
        """
        Obtener métricas de todos los workflows.
        
        Returns:
            Diccionario con métricas por workflow
        """
        metrics = {}
        
        for name, workflow in self.workflows.items():
            try:
                # Información básica del workflow
                metrics[name] = {
                    "description": workflow.get_workflow_description(),
                    "entry_point": workflow.get_entry_point(),
                    "compiled": workflow._graph is not None
                }
                
                # Si está compilado, agregar info del grafo
                if workflow._graph:
                    metrics[name]["nodes_count"] = len(workflow._graph.nodes)
                
            except Exception as e:
                metrics[name] = {"error": str(e)}
        
        return metrics

# Singleton global
_workflow_manager: Optional[WorkflowManager] = None

def get_workflow_manager() -> WorkflowManager:
    """
    Obtener instancia singleton del workflow manager.
    
    Returns:
        Instancia de WorkflowManager
    """
    global _workflow_manager
    if _workflow_manager is None:
        _workflow_manager = WorkflowManager()
    return _workflow_manager

def reset_workflow_manager():
    """Reset workflow manager (útil para tests)"""
    global _workflow_manager
    _workflow_manager = None