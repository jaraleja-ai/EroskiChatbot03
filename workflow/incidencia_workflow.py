# =====================================================
# workflows/incidencia_workflow.py - Workflow principal
# =====================================================
from nodes.identificar_usuario import identificar_usuario_node
from nodes.recopilar_input_usuario import recopilar_input_usuario, procesar_input_recibido
from nodes.procesar_incidencia import procesar_incidencia_node
from nodes.escalar_supervisor import escalar_supervisor_node
from nodes.finalizar_ticket import finalizar_ticket_node
from langgraph.graph import StateGraph, START, END
from workflow import BaseWorkflow
from models import GraphState
from typing import Dict, Any

class IncidenciaWorkflow(BaseWorkflow):
    """
    Workflow principal para el manejo completo de incidencias.
    
    Flujo:
    1. Identificar usuario → Validar datos
    2. Procesar incidencia → Categorizar y crear ticket  
    3. Finalizar o escalar según sea necesario
    """
    
    def __init__(self):
        super().__init__("IncidenciaWorkflow")
    
    def _route_conversation(self, state: Dict[str, Any]) -> str:
        """
        Router siguiendo patrón de actor puro.
        
        El ACTOR decide → El ROUTER solo interpreta las decisiones del actor.
        """
        
        # ✅ 1. DECISIÓN EXPLÍCITA DEL ACTOR (máxima prioridad)
        next_actor = state.get("_next_actor")
        if next_actor:
            self.logger.info(f"🎯 Actor decidió explícitamente → {next_actor}")
            return next_actor
        
        # ✅ 2. ESTADO FINAL DEL ACTOR (segunda prioridad)
        # El actor marcó su trabajo como completo
        if state.get("datos_usuario_completos", False):
            self.logger.info("✅ Actor completó su trabajo → procesar_incidencia")
            return "procesar_incidencia"
        
        # ✅ 3. ACTOR NECESITA INFORMACIÓN (tercera prioridad)
        # El actor está esperando input del usuario
        if state.get("awaiting_input", False):
            self.logger.info("⏸️ Actor necesita información → recopilar_input_usuario")
            return "recopilar_input_usuario"
        
        # ✅ 4. SEÑALES DE CONTROL DEL SISTEMA (última prioridad)
        if state.get("escalar_a_supervisor", False):
            self.logger.info("🔼 Sistema escalando → escalar_supervisor")
            return "escalar_supervisor"
        
        if state.get("flujo_completado", False):
            self.logger.info("🏁 Sistema completado → finalizar_ticket")
            return "finalizar_ticket"
        
        # ✅ 5. FALLBACK: usar estado de completitud
        self.logger.info("🔄 Fallback → routing por completitud")
        return self._route_by_completion_state(state)
    

    def _route_by_completion_state(self, state: Dict[str, Any]) -> str:
        """
        Routing escalable basado en estado de completitud.
        
        Esta función es independiente del dominio y fácilmente escalable.
        """
        
        # Verificar datos de usuario
        if not state.get("datos_usuario_completos", False):
            self.logger.info("👤 Routing: Datos de usuario incompletos")
            return "identificar_usuario"
        
        # Verificar estado de incidencia
        if not state.get("incidencia_resuelta", False):
            self.logger.info("🔧 Routing: Procesando incidencia")
            return "procesar_incidencia"
        
        # Estado completado por defecto
        self.logger.info("✅ Routing: Completando flujo")
        return "finalizar_ticket"

    def get_entry_point(self) -> str:
        return "identificar_usuario"
    
    def get_workflow_description(self) -> str:
        return (
            "Workflow completo para manejo de incidencias: identificación de usuario, "
            "procesamiento de incidencia, escalación automática y finalización"
        )
    
    def build_graph(self) -> StateGraph:
        """Construir el grafo principal de incidencias con routing mejorado"""
        
        self.logger.info("🔧 Construyendo grafo de incidencias...")
        
        # Crear grafo con el estado
        graph = StateGraph(GraphState)
        
        # Agregar nodos principales
        graph.add_node("identificar_usuario", identificar_usuario_node)
        graph.add_node("procesar_incidencia", procesar_incidencia_node) 
        graph.add_node("escalar_supervisor", escalar_supervisor_node)
        graph.add_node("finalizar_ticket", finalizar_ticket_node)
        graph.add_node("recopilar_input_usuario", recopilar_input_usuario)
        graph.add_node("procesar_input_recibido", procesar_input_recibido)
        
        # Punto de entrada
        graph.add_edge(START, "identificar_usuario")
        
        # ===== ROUTING MEJORADO =====
        # Definir todos los posibles destinos de routing
        routing_destinations = {
            "identificar_usuario": "identificar_usuario",
            "procesar_incidencia": "procesar_incidencia",
            "escalar_supervisor": "escalar_supervisor", 
            "finalizar_ticket": "finalizar_ticket",
            "recopilar_input_usuario": "recopilar_input_usuario",
            END: END
        }
        
        # Aplicar routing universal a nodos que toman decisiones
        decision_nodes = ["identificar_usuario", "procesar_incidencia"]
        
        for node_name in decision_nodes:
            self.add_conditional_edges(
                graph,
                node_name,
                self._route_conversation,
                routing_destinations
            )
            self.logger.debug(f"🔀 Routing configurado para {node_name}")
        
        # ===== EDGES FINALES (sin decisiones) =====
        graph.add_edge("escalar_supervisor", END)
        graph.add_edge("finalizar_ticket", END)
        
        # Validar estructura
        if not self.validate_graph_structure(graph):
            raise ValueError(f"Estructura del grafo {self.name} inválida")
        
        self.logger.info("✅ Grafo de incidencias construido con routing mejorado")
        return graph