# =====================================================
# workflows/base_workflow.py - Clase base para workflows
# =====================================================
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Callable, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph
from langgraph.checkpoint.memory import MemorySaver
import logging
from nodes import escalate_supervisor_node

from models.eroski_state import EroskiState
from config.settings import get_settings

class BaseWorkflow(ABC):
    """
    Clase base para todos los workflows de LangGraph.
    
    Proporciona:
    - Estructura común para workflows
    - Métodos de construcción estandarizados  
    - Logging y monitoreo
    - Patrones de routing reutilizables
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Workflow.{name}")
        self.settings = get_settings()
        self._graph: Optional[CompiledStateGraph] = None
        
        self.logger.debug(f"🔧 Workflow {name} inicializado")
    
    @abstractmethod
    def build_graph(self) -> StateGraph:
        """
        Construir el grafo específico del workflow.
        
        Returns:
            StateGraph configurado pero no compilado
        """
        pass
    
    @abstractmethod
    def get_entry_point(self) -> str:
        """
        Obtener el punto de entrada del workflow.
        
        Returns:
            Nombre del nodo inicial
        """
        pass
    
    @abstractmethod
    def get_workflow_description(self) -> str:
        """
        Descripción del propósito del workflow.
        
        Returns:
            Descripción human-readable
        """
        pass
    
    # ✅ NUEVO MÉTODO - Compilar con checkpointer
    def compile_with_checkpointer(self, checkpointer=None) -> CompiledStateGraph:
        """
        Compilar el workflow con checkpointer para persistencia de estado.
        
        Args:
            checkpointer: Checkpointer a usar (MemorySaver por defecto)
            
        Returns:
            Grafo compilado con checkpointer
        """
        try:
            self.logger.info(f"🔨 Compilando workflow {self.name} con checkpointer...")
            
            # Usar checkpointer por defecto si no se proporciona
            if checkpointer is None:
                checkpointer = MemorySaver()
            
            # Construir grafo
            graph = self.build_graph()
            
            # ✅ CONFIGURAR INTERRUPCIONES PARA RECOPILAR INPUT
            interrupt_after = ["interrupcion_identificar_usuario"]  # Nodo donde interrumpir
            
            # ✅ COMPILAR CON CHECKPOINTER E INTERRUPCIONES
            self._graph = graph.compile(
                checkpointer=checkpointer,
                interrupt_after=interrupt_after
            )
            
            self.logger.info(f"✅ Workflow {self.name} compilado con checkpointer")
            self.logger.debug(f"📋 Interrupciones en: {interrupt_after}")
            
            return self._graph
            
        except Exception as e:
            self.logger.error(f"❌ Error compilando workflow {self.name} con checkpointer: {e}")
            raise


    def compile(self) -> CompiledStateGraph:
        """
        Compilar el workflow para ejecución.
        
        Returns:
            Grafo compilado listo para ejecutar
        """
        if self._graph is None:
            try:
                self.logger.info(f"🔨 Compilando workflow {self.name}...")
                
                # Construir grafo
                graph = self.build_graph()
                
                # Configurar interrupciones si está habilitado
                interrupt_after = self._get_interrupt_nodes()
                if interrupt_after:
                    self._graph = graph.compile(interrupt_after=interrupt_after)
                else:
                    self._graph = graph.compile()
                
                self.logger.info(f"✅ Workflow {self.name} compilado correctamente")
                self.logger.debug(f"📋 Descripción: {self.get_workflow_description()}")
                
            except Exception as e:
                self.logger.error(f"❌ Error compilando workflow {self.name}: {e}")
                raise
        
        return self._graph
    
    def _get_interrupt_nodes(self) -> List[str]:
        """
        Obtener nodos donde interrumpir para input del usuario.
        Puede ser sobrescrito por workflows específicos.
        
        Returns:
            Lista de nombres de nodos donde interrumpir
        """
        return ["interrupcion_identificar_usuario"]
    
    def add_conditional_edges(
        self, 
        graph: StateGraph, 
        from_node: str,
        condition_func: Callable,
        condition_map: Dict[str, str]
    ):
        """
        Helper para agregar edges condicionales con logging.
        
        Args:
            graph: Grafo al que agregar edges
            from_node: Nodo origen
            condition_func: Función de condición
            condition_map: Mapeo de condiciones a nodos destino
        """
        try:
            graph.add_conditional_edges(from_node, condition_func, condition_map)
            self.logger.debug(
                f"🔀 Edge condicional agregado desde {from_node}: {list(condition_map.keys())}"
            )
        except Exception as e:
            self.logger.error(f"❌ Error agregando edge condicional: {e}")
            raise
    
    def validate_graph_structure(self, graph: StateGraph) -> bool:
        """
        Validar que la estructura del grafo sea correcta.
        
        Args:
            graph: Grafo a validar
            
        Returns:
            True si es válido
        """
        try:
            # Verificar que hay nodos
            if not hasattr(graph, 'nodes') or len(graph.nodes) == 0:
                self.logger.error("❌ Grafo sin nodos")
                return False
            
            # Verificar que el punto de entrada existe
            entry_point = self.get_entry_point()
            if entry_point not in graph.nodes:
                self.logger.error(f"❌ Punto de entrada {entry_point} no existe en el grafo")
                return False
            
            self.logger.debug("✅ Estructura del grafo válida")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error validando grafo: {e}")
            return False
    
    async def execute(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ejecutar el workflow con un estado inicial.
        
        Args:
            initial_state: Estado inicial del workflow
            
        Returns:
            Estado final después de la ejecución
        """
        try:
            self.logger.info(f"🚀 Ejecutando workflow {self.name}")
            
            # Compilar si no está compilado
            graph = self.compile()
            
            # Agregar metadatos al estado inicial
            enriched_state = self._enrich_initial_state(initial_state)
            
            # Ejecutar
            result = await graph.ainvoke(enriched_state)
            
            self.logger.info(f"✅ Workflow {self.name} completado")
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error ejecutando workflow {self.name}: {e}")
            raise
    
    def _enrich_initial_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Enriquecer estado inicial con metadatos del workflow"""
        from datetime import datetime
        import uuid
        
        enriched = dict(state)
        
        # Agregar metadatos si no existen
        if "sesion_id" not in enriched:
            enriched["sesion_id"] = str(uuid.uuid4())
        
        if "timestamp_inicio" not in enriched:
            enriched["timestamp_inicio"] = datetime.now().isoformat()
        
        # Inicializar campos requeridos si no existen
        default_fields = {
            "intentos": 0,
            "intentos_incidencia": 0,
            "escalar_a_supervisor": False,
            "flujo_completado": False,
            "datos_usuario_completos": False,
            "nombre_confirmado": False,
            "email_confirmado": False,
            "usuario_encontrado_bd": False,
            "incidencia_resuelta": False
        }
        
        for field, default_value in default_fields.items():
            if field not in enriched:
                enriched[field] = default_value
        
        return enriched






