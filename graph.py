# =====================================================
# graph.py - Constructor principal del grafo
# =====================================================
"""
Archivo principal para construir y configurar el grafo de LangGraph.

Este módulo:
- Integra todos los workflows
- Proporciona interfaz unificada para el grafo
- Maneja configuración y inicialización
- Facilita el uso desde la aplicación principal
"""

import logging
from typing import Dict, Any, Optional
from langgraph.graph.state import CompiledStateGraph

from models.state import GraphState
from config.settings import get_settings
from datetime import datetime
from workflow import get_workflow_manager, WorkflowType, ConversationSteps
from langgraph.checkpoint.memory import MemorySaver
logger = logging.getLogger("Graph")

# =====================================================
# graph.py - MODIFICACIONES NECESARIAS
# =====================================================

# ✅ AGREGAR IMPORT al inicio del archivo


def build_adaptive_graph(context: Optional[Dict[str, Any]] = None) -> CompiledStateGraph:
    """
    Construir grafo adaptativo basado en contexto.
    """
    try:
        logger.info("🧠 Construyendo grafo adaptativo")
        
        workflow_manager = get_workflow_manager()
        
        # Seleccionar workflow según contexto
        if context:
            workflow_type = workflow_manager.select_workflow_for_context(context)
            logger.info(f"🎯 Workflow seleccionado por contexto: {workflow_type}")
        else:
            workflow_type = WorkflowType.INCIDENCIA
            logger.info("📋 Usando workflow por defecto (sin contexto)")
        
        # ✅ MODIFICACIÓN CRÍTICA: Usar build_graph_with_checkpointer
        return build_graph_with_checkpointer(workflow_type)
        
    except Exception as e:
        logger.error(f"❌ Error en grafo adaptativo: {e}")
        # Fallback al grafo por defecto
        logger.info("🔄 Fallback a grafo por defecto")
        return build_graph_with_checkpointer(WorkflowType.INCIDENCIA)

# ✅ NUEVA FUNCIÓN - Construir grafo con checkpointer
def build_graph_with_checkpointer(workflow_type: str = WorkflowType.INCIDENCIA) -> CompiledStateGraph:
    """
    Construir grafo con checkpointer para mantener estado entre interrupciones.
    
    Args:
        workflow_type: Tipo de workflow a construir
        
    Returns:
        Grafo compilado con checkpointer configurado
    """
    try:
        logger.info(f"🔨 Construyendo grafo con checkpointer (tipo: {workflow_type})")
        
        # Obtener manager de workflows
        workflow_manager = get_workflow_manager()
        
        # Obtener workflow específico
        workflow = workflow_manager.get_workflow(workflow_type)
        
        # ✅ CREAR CHECKPOINTER PARA PERSISTENCIA
        memory = MemorySaver()
        
        # ✅ COMPILAR CON CHECKPOINTER E INTERRUPCIONES
        compiled_graph = workflow.compile_with_checkpointer(memory)
        
        logger.info(f"✅ Grafo con checkpointer construido exitosamente")
        
        return compiled_graph
        
    except Exception as e:
        logger.error(f"❌ Error construyendo grafo con checkpointer: {e}")
        raise RuntimeError(f"No se pudo construir el grafo: {e}")

def build_graph(workflow_type: str = WorkflowType.INCIDENCIA) -> CompiledStateGraph:
    """
    Construir y compilar el grafo principal de la aplicación.
    
    Args:
        workflow_type: Tipo de workflow a construir (por defecto: incidencia)
        
    Returns:
        Grafo compilado listo para ejecutar
        
    Raises:
        ValueError: Si el tipo de workflow no es válido
        RuntimeError: Si hay errores en la construcción
    """
    try:
        logger.info(f"🔨 Construyendo grafo principal (tipo: {workflow_type})")
        
        # Obtener manager de workflows
        workflow_manager = get_workflow_manager()
        
        # Obtener workflow específico
        workflow = workflow_manager.get_workflow(workflow_type)
        
        # Compilar workflow
        compiled_graph = workflow.compile()
        
        logger.info(f"✅ Grafo principal construido exitosamente")
        logger.debug(f"📋 Descripción: {workflow.get_workflow_description()}")
        
        return compiled_graph
        
    except Exception as e:
        logger.error(f"❌ Error construyendo grafo: {e}")
        raise RuntimeError(f"No se pudo construir el grafo: {e}")

def build_default_graph() -> CompiledStateGraph:
    """
    Construir el grafo por defecto de la aplicación.
    
    Returns:
        Grafo por defecto (incidencias) compilado
    """
    return build_graph(WorkflowType.INCIDENCIA)

class GraphBuilder:
    """
    Constructor avanzado de grafos con configuración y caché.
    
    Proporciona interfaz más avanzada para casos de uso complejos.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger("GraphBuilder")
        self._cached_graphs: Dict[str, CompiledStateGraph] = {}
        self._workflow_manager = get_workflow_manager()
    
    def build_with_config(
        self, 
        workflow_type: str,
        enable_cache: bool = True,
        custom_config: Optional[Dict[str, Any]] = None
    ) -> CompiledStateGraph:
        """
        Construir grafo con configuración avanzada.
        
        Args:
            workflow_type: Tipo de workflow
            enable_cache: Si habilitar caché de grafos compilados
            custom_config: Configuración personalizada
            
        Returns:
            Grafo compilado
        """
        try:
            cache_key = f"{workflow_type}_{hash(str(custom_config))}"
            
            # Verificar caché
            if enable_cache and cache_key in self._cached_graphs:
                self.logger.debug(f"📦 Usando grafo desde caché: {cache_key}")
                return self._cached_graphs[cache_key]
            
            self.logger.info(f"🔨 Construyendo grafo con config: {workflow_type}")
            
            # Aplicar configuración personalizada si existe
            if custom_config:
                self._apply_custom_config(custom_config)
            
            # Construir workflow
            workflow = self._workflow_manager.get_workflow(workflow_type)
            compiled_graph = workflow.compile()
            
            # Guardar en caché si está habilitado
            if enable_cache:
                self._cached_graphs[cache_key] = compiled_graph
                self.logger.debug(f"💾 Grafo guardado en caché: {cache_key}")
            
            self.logger.info(f"✅ Grafo construido con configuración personalizada")
            return compiled_graph
            
        except Exception as e:
            self.logger.error(f"❌ Error construyendo grafo con config: {e}")
            raise
    
    def _apply_custom_config(self, config: Dict[str, Any]):
        """Aplicar configuración personalizada"""
        # TODO: Implementar aplicación de configuración personalizada
        self.logger.debug(f"⚙️ Aplicando configuración: {list(config.keys())}")
    
    def clear_cache(self):
        """Limpiar caché de grafos"""
        self._cached_graphs.clear()
        self.logger.info("🧹 Caché de grafos limpiado")
    
    def get_graph_info(self, workflow_type: str) -> Dict[str, Any]:
        """
        Obtener información sobre un grafo específico.
        
        Args:
            workflow_type: Tipo de workflow
            
        Returns:
            Información del grafo
        """
        try:
            workflow = self._workflow_manager.get_workflow(workflow_type)
            
            info = {
                "name": workflow.name,
                "description": workflow.get_workflow_description(),
                "entry_point": workflow.get_entry_point(),
                "compiled": workflow._graph is not None
            }
            
            # Si está compilado, agregar información del grafo
            if workflow._graph:
                info.update({
                    "nodes": list(workflow._graph.nodes.keys()),
                    "nodes_count": len(workflow._graph.nodes)
                })
            
            return info
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo info del grafo: {e}")
            return {"error": str(e)}
    
    def list_available_workflows(self) -> Dict[str, Dict[str, Any]]:
        """
        Listar todos los workflows disponibles con su información.
        
        Returns:
            Diccionario con información de workflows
        """
        workflows_info = {}
        
        for workflow_name in self._workflow_manager.list_workflows():
            workflows_info[workflow_name] = self.get_graph_info(workflow_name)
        
        return workflows_info

# =====================================================
# Funciones de conveniencia para retrocompatibilidad
# =====================================================

def crear_estado_inicial() -> GraphState:
    """
    Crear estado inicial para el grafo.
    Función de conveniencia para retrocompatibilidad.
    
    Returns:
        Estado inicial del grafo
    """
    from datetime import datetime
    import uuid
    
    return GraphState(
        messages=[],
        intentos=0,
        intentos_incidencia=0,
        nombre=None,
        email=None,
        numero_empleado=None,
        nombre_confirmado=False,
        email_confirmado=False,
        datos_usuario_completos=False,
        usuario_encontrado_bd=False,
        escalar_a_supervisor=False,
        razon_escalacion=None,
        flujo_completado=False,
        tipo_incidencia=None,
        descripcion_incidencia=None,
        prioridad_incidencia=None,
        categoria_incidencia=None,
        preguntas_contestadas=None,
        incidencia_resuelta=False,
        contexto_adicional=None,
        sesion_id=str(uuid.uuid4()),
        timestamp_inicio=datetime.now().isoformat(),
        error_info=None
    )

def get_graph_metrics() -> Dict[str, Any]:
    """
    Obtener métricas de todos los grafos/workflows.
    
    Returns:
        Métricas agregadas del sistema
    """
    try:
        workflow_manager = get_workflow_manager()
        
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "total_workflows": len(workflow_manager.list_workflows()),
            "available_workflows": workflow_manager.list_workflows(),
            "workflow_details": workflow_manager.get_workflow_metrics()
        }
        
        # Agregar configuración del sistema
        settings = get_settings()
        metrics["system_config"] = {
            "debug_mode": settings.app.debug_mode,
            "max_intentos_identificacion": settings.app.max_intentos_identificacion,
            "max_intentos_incidencia": settings.app.max_intentos_incidencia,
            "database_lookup_enabled": settings.workflow.enable_database_lookup
        }
        
        return metrics
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo métricas: {e}")
        return {"error": str(e)}

# =====================================================
# Instancia global del builder (opcional)
# =====================================================
_graph_builder: Optional[GraphBuilder] = None

def get_graph_builder() -> GraphBuilder:
    """
    Obtener instancia singleton del GraphBuilder.
    
    Returns:
        Instancia de GraphBuilder
    """
    global _graph_builder
    if _graph_builder is None:
        _graph_builder = GraphBuilder()
    return _graph_builder




# =====================================================
# Funciones principales exportadas
# =====================================================

# Para uso simple y directo
__all__ = [
    # Funciones principales
    "build_graph",
    "build_default_graph", 
    "build_adaptive_graph",
    
    # Builder avanzado
    "GraphBuilder",
    "get_graph_builder",
    
    # Utilidades
    "crear_estado_inicial",
    "get_graph_metrics",
    
    # Tipos
    "GraphState"
]

# =====================================================
# Ejemplo de uso del módulo
# =====================================================
if __name__ == "__main__":
    """
    Ejemplo de uso del sistema de grafos.
    Útil para testing y desarrollo.
    """
    import asyncio
    from langchain_core.messages import HumanMessage
    
    async def example_usage():
        """Ejemplo de uso completo"""
        try:
            print("🚀 Ejemplo de uso del sistema de grafos")
            
            # 1. Construir grafo por defecto
            graph = build_default_graph()
            print("✅ Grafo construido")
            
            # 2. Crear estado inicial
            initial_state = crear_estado_inicial()
            initial_state["messages"] = [
                HumanMessage(content="Hola, soy Juan Pérez y tengo un problema con mi computadora")
            ]
            
            # 3. Obtener métricas
            metrics = get_graph_metrics()
            print(f"📊 Métricas: {metrics['total_workflows']} workflows disponibles")
            
            # 4. Información del builder
            builder = get_graph_builder()
            workflows_info = builder.list_available_workflows()
            print(f"📋 Workflows: {list(workflows_info.keys())}")
            
            print("✅ Ejemplo completado exitosamente")
            
        except Exception as e:
            print(f"❌ Error en ejemplo: {e}")
    
    # Ejecutar ejemplo
    asyncio.run(example_usage())