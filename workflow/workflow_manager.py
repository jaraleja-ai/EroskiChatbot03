# =====================================================
# workflow/workflow_manager.py - CON DEBUG MEJORADO PARA DIAGNOSTICAR
# =====================================================
from typing import Dict, Type, Union, List, Any, Optional, TYPE_CHECKING
from enum import Enum
from workflow import BaseWorkflow
from langgraph.graph.state import CompiledStateGraph
import logging
import traceback

# ✅ SOLUCIÓN: Imports corregidos
from config.settings import get_settings
if TYPE_CHECKING:
    from .base_workflow import BaseWorkflow

class WorkflowType(str, Enum):
    """Tipos de workflow disponibles"""
    INCIDENCIA = "incidencia"
    ESCALACION = "escalacion"
    CONSULTA = "consulta"

class WorkflowManager:
    """
    Gestor centralizado de workflows con debug mejorado.
    
    Responsabilidades:
    - Registrar y mantener workflows disponibles
    - Diagnosticar problemas de carga
    - Proporcionar fallbacks seguros
    - Manejar caché de workflows compilados
    """
    
    def __init__(self):
        self.workflows: Dict[str, BaseWorkflow] = {}
        self.logger = logging.getLogger("WorkflowManager")
        self.settings = get_settings()
        self.load_errors: Dict[str, str] = {}  # Guardar errores de carga para debug
        self._register_workflows()
    
    def _register_workflows(self):
        """Registrar todos los workflows disponibles con debug detallado"""
        try:
            self.logger.info("📋 === INICIANDO REGISTRO DE WORKFLOWS ===")
            
            # ✅ WORKFLOW 1: IncidenciaWorkflow (CRÍTICO)
            self._try_register_incidencia_workflow()
            
            # ✅ WORKFLOW 2: ConsultaWorkflow (opcional)
            self._try_register_consulta_workflow()
            
            # ✅ WORKFLOW 3: EscalacionWorkflow (opcional)
            self._try_register_escalacion_workflow()
            
            # ✅ VERIFICACIÓN FINAL
            self._verify_registration_results()
            
        except Exception as e:
            self.logger.error(f"❌ Error crítico registrando workflows: {e}")
            self.logger.error(f"📍 Traceback completo: {traceback.format_exc()}")
            raise
    
    def _try_register_incidencia_workflow(self):
        """Intentar registrar IncidenciaWorkflow con debug detallado"""
        
        workflow_name = "IncidenciaWorkflow"
        self.logger.info(f"🔍 === CARGANDO {workflow_name} ===")
        
        try:
            # Step 1: Verificar import del módulo
            self.logger.info("📦 Step 1: Importando módulo incidencia_workflow...")
            from .incidencia_workflow import IncidenciaWorkflow
            self.logger.info("✅ Step 1: Módulo importado exitosamente")
            
            # Step 2: Crear instancia
            self.logger.info("🏗️ Step 2: Creando instancia de IncidenciaWorkflow...")
            workflow_instance = IncidenciaWorkflow()
            self.logger.info(f"✅ Step 2: Instancia creada - Nombre: {workflow_instance.name}")
            
            # Step 3: Verificar métodos requeridos
            self.logger.info("🔍 Step 3: Verificando métodos requeridos...")
            required_methods = ["build_graph", "get_entry_point", "get_workflow_description"]
            for method in required_methods:
                if hasattr(workflow_instance, method):
                    self.logger.debug(f"✓ Método {method} disponible")
                else:
                    raise AttributeError(f"Método requerido {method} no encontrado")
            self.logger.info("✅ Step 3: Todos los métodos requeridos disponibles")
            
            # Step 4: Intentar construir grafo (test)
            self.logger.info("🔧 Step 4: Probando construcción de grafo...")
            try:
                test_graph = workflow_instance.build_graph()
                self.logger.info(f"✅ Step 4: Grafo construido exitosamente con {len(test_graph.nodes)} nodos")
            except Exception as e:
                self.logger.warning(f"⚠️ Step 4: Error construyendo grafo (continuando): {e}")
            
            # Step 5: Registrar workflow
            self.logger.info("📝 Step 5: Registrando workflow...")
            self.workflows[WorkflowType.INCIDENCIA] = workflow_instance
            self.logger.info("✅ IncidenciaWorkflow registrado exitosamente ✅")
            
        except ImportError as e:
            error_msg = f"ImportError: {e}"
            self.logger.error(f"❌ {workflow_name} - {error_msg}")
            self.load_errors[workflow_name] = error_msg
            
        except AttributeError as e:
            error_msg = f"AttributeError: {e}"
            self.logger.error(f"❌ {workflow_name} - {error_msg}")
            self.load_errors[workflow_name] = error_msg
            
        except Exception as e:
            error_msg = f"Error general: {type(e).__name__}: {e}"
            self.logger.error(f"❌ {workflow_name} - {error_msg}")
            self.logger.error(f"📍 Traceback: {traceback.format_exc()}")
            self.load_errors[workflow_name] = error_msg
    
    def _try_register_consulta_workflow(self):
        """Intentar registrar ConsultaWorkflow"""
        
        try:
            self.logger.info("🔍 Cargando ConsultaWorkflow...")
            from .consulta_workflow import ConsultaWorkflow
            workflow_instance = ConsultaWorkflow()
            self.workflows[WorkflowType.CONSULTA] = workflow_instance
            self.logger.info("✅ ConsultaWorkflow registrado")
            
        except ImportError as e:
            self.logger.warning(f"⚠️ ConsultaWorkflow no disponible: {e}")
            self.load_errors["ConsultaWorkflow"] = f"ImportError: {e}"
            
        except Exception as e:
            self.logger.error(f"❌ Error cargando ConsultaWorkflow: {e}")
            self.load_errors["ConsultaWorkflow"] = f"Error: {e}"
    
    def _try_register_escalacion_workflow(self):
        """Intentar registrar EscalacionWorkflow"""
        
        try:
            self.logger.info("🔍 Cargando EscalacionWorkflow...")
            from .escalacion_workflow import EscalacionWorkflow
            workflow_instance = EscalacionWorkflow()
            self.workflows[WorkflowType.ESCALACION] = workflow_instance
            self.logger.info("✅ EscalacionWorkflow registrado")
            
        except ImportError as e:
            self.logger.warning(f"⚠️ EscalacionWorkflow no disponible: {e}")
            self.load_errors["EscalacionWorkflow"] = f"ImportError: {e}"
            
        except Exception as e:
            self.logger.error(f"❌ Error cargando EscalacionWorkflow: {e}")
            self.load_errors["EscalacionWorkflow"] = f"Error: {e}"
    
    def _verify_registration_results(self):
        """Verificar resultados del registro"""
        
        workflows_count = len(self.workflows)
        errors_count = len(self.load_errors)
        
        self.logger.info("📊 === RESUMEN DE REGISTRO ===")
        self.logger.info(f"✅ Workflows cargados: {workflows_count}")
        self.logger.info(f"❌ Errores de carga: {errors_count}")
        
        if self.workflows:
            self.logger.info(f"📋 Workflows disponibles: {list(self.workflows.keys())}")
        
        if self.load_errors:
            self.logger.warning("🚨 Errores encontrados:")
            for workflow, error in self.load_errors.items():
                self.logger.warning(f"   • {workflow}: {error}")
        
        # ✅ VERIFICACIÓN CRÍTICA: Al menos un workflow debe estar disponible
        if not self.workflows:
            self.logger.error("❌ CRÍTICO: No se pudo cargar ningún workflow")
            self.logger.error("📋 Errores detallados:")
            for workflow, error in self.load_errors.items():
                self.logger.error(f"   🔴 {workflow}: {error}")
            
            raise RuntimeError(
                f"❌ No se pudo cargar ningún workflow. "
                f"Errores: {dict(self.load_errors)}"
            )
        
        # ⚠️ ADVERTENCIA: Si no está IncidenciaWorkflow (el principal)
        if WorkflowType.INCIDENCIA not in self.workflows:
            self.logger.warning("⚠️ ADVERTENCIA: IncidenciaWorkflow no disponible")
            self.logger.warning("🔄 Se usarán workflows alternativos")
        
        self.logger.info("✅ === REGISTRO COMPLETADO ===")

    def get_workflow(self, workflow_name: str) -> BaseWorkflow:
        """
        Obtener workflow por nombre con mejor manejo de errores.
        
        Args:
            workflow_name: Nombre del workflow
            
        Returns:
            Instancia del workflow
            
        Raises:
            ValueError: Si el workflow no existe
        """
        if workflow_name not in self.workflows:
            available = list(self.workflows.keys())
            error_details = self.load_errors.get(workflow_name, "No se intentó cargar")
            
            raise ValueError(
                f"Workflow '{workflow_name}' no encontrado. "
                f"Disponibles: {available}. "
                f"Error de carga: {error_details}"
            )
        
        return self.workflows[workflow_name]
    
    def get_compiled_workflow(self, workflow_name: str) -> CompiledStateGraph:
        """Obtener workflow compilado listo para ejecución."""
        workflow = self.get_workflow(workflow_name)
        return workflow.compile()
    
    def list_workflows(self) -> List[str]:
        """Listar workflows disponibles."""
        return list(self.workflows.keys())
    
    def get_default_workflow(self) -> BaseWorkflow:
        """
        Obtener workflow por defecto con fallback inteligente.
        
        Returns:
            Workflow por defecto (preferiblemente IncidenciaWorkflow)
        """
        # Preferir IncidenciaWorkflow
        if WorkflowType.INCIDENCIA in self.workflows:
            return self.get_workflow(WorkflowType.INCIDENCIA)
        
        # Fallback al primer workflow disponible
        if self.workflows:
            fallback_name = list(self.workflows.keys())[0]
            self.logger.warning(f"🔄 Usando fallback workflow: {fallback_name}")
            return self.workflows[fallback_name]
        
        raise RuntimeError("❌ No hay workflows disponibles")
    
    def select_workflow_for_context(self, context: Dict[str, Any]) -> str:
        """
        Seleccionar workflow apropiado según el contexto con fallback.
        """
        # Si hay escalación marcada y EscalacionWorkflow disponible
        if (context.get("escalar_a_supervisor", False) and 
            WorkflowType.ESCALACION in self.workflows):
            return WorkflowType.ESCALACION
        
        # Si parece ser una consulta simple y ConsultaWorkflow disponible
        ultimo_mensaje = ""
        if "messages" in context and context["messages"]:
            ultimo_mensaje = context["messages"][-1].content.lower()
        
        palabras_consulta = ["consulta", "pregunta", "estado", "información", "cómo", "dónde", "cuándo"]
        if (any(palabra in ultimo_mensaje for palabra in palabras_consulta) and
            WorkflowType.CONSULTA in self.workflows):
            return WorkflowType.CONSULTA
        
        # Preferir IncidenciaWorkflow si está disponible
        if WorkflowType.INCIDENCIA in self.workflows:
            return WorkflowType.INCIDENCIA
        
        # Fallback al primer workflow disponible
        if self.workflows:
            fallback = list(self.workflows.keys())[0]
            self.logger.warning(f"🔄 Fallback a: {fallback}")
            return fallback
        
        raise RuntimeError("❌ No hay workflows disponibles para contexto")
    
    def get_debug_info(self) -> Dict[str, Any]:
        """Obtener información de debug del WorkflowManager"""
        return {
            "workflows_loaded": list(self.workflows.keys()),
            "load_errors": dict(self.load_errors),
            "workflows_count": len(self.workflows),
            "errors_count": len(self.load_errors),
            "default_available": WorkflowType.INCIDENCIA in self.workflows
        }

# ✅ Singleton pattern para WorkflowManager
_workflow_manager = None

def get_workflow_manager() -> WorkflowManager:
    """Obtener instancia singleton del WorkflowManager"""
    global _workflow_manager
    if _workflow_manager is None:
        _workflow_manager = WorkflowManager()
    return _workflow_manager

def reset_workflow_manager():
    """Resetear WorkflowManager (útil para testing)"""
    global _workflow_manager
    _workflow_manager = None