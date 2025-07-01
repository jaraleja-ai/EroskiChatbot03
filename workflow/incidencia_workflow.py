# =====================================================
# workflow/incidencia_workflow.py - ROUTER HÍBRIDO INTELIGENTE
# =====================================================
from nodes.identificar_usuario import identificar_usuario_node
from nodes.procesar_incidencia import procesar_incidencia_node
from nodes.escalar_supervisor import escalar_supervisor_node
from nodes.finalizar_ticket import finalizar_ticket_node
from langgraph.graph import StateGraph, START, END
from workflow import BaseWorkflow
from models import GraphState
from typing import Dict, Any

class IncidenciaWorkflow(BaseWorkflow):
    """
    🎭 WORKFLOW HÍBRIDO: LangGraph + Actor Pattern
    
    PRINCIPIOS HÍBRIDOS:
    - ✅ Estructura LangGraph para el framework
    - ✅ Decisiones autónomas de actores
    - ✅ Router que RESPETA las señales de actores
    - ✅ Sin bucles infinitos
    
    ROUTER INTELIGENTE:
    - Los actores DECIDEN, el router solo EJECUTA
    - Prioriza señales explícitas de actores
    - Fallback inteligente sin bucles
    """
    
    def __init__(self):
        super().__init__("IncidenciaWorkflow")
    
    def _route_conversation(self, state: Dict[str, Any]) -> str:
        """
        🧠 ROUTER HÍBRIDO INTELIGENTE
        
        PRIORIDADES (en orden estricto):
        1. 🎯 Decisión EXPLÍCITA del actor (máxima autoridad)
        2. 🔼 Escalación solicitada
        3. 🏁 Flujo marcado como completado  
        4. ✅ Datos completos → continuar flujo
        5. 📥 Actor necesita input → manejar
        6. 🔄 Fallback inteligente
        
        CLAVE: El router NO toma decisiones de negocio,
               solo INTERPRETA las señales de los actores.
        """
        
        # 🎯 1. MÁXIMA PRIORIDAD: Decisión EXPLÍCITA del actor
        next_actor = state.get("_next_actor")
        if next_actor:
            self.logger.info(f"🎯 ACTOR DECIDIÓ → {next_actor}")
            # Limpiar señal para evitar loops
            return next_actor
        
        # 🔼 2. ESCALACIÓN solicitada por actor
        if state.get("escalar_a_supervisor", False):
            self.logger.info("🔼 ESCALACIÓN SOLICITADA → escalar_supervisor")
            return "escalar_supervisor"
        
        # 🏁 3. FLUJO COMPLETADO por actor
        if state.get("flujo_completado", False):
            self.logger.info("🏁 FLUJO COMPLETADO → finalizar_ticket")
            return "finalizar_ticket"
        
        # ✅ 4. DATOS COMPLETOS → continuar flujo natural
        datos_completos = state.get("datos_usuario_completos", False)
        if datos_completos and not state.get("incidencia_resuelta", False):
            self.logger.info("✅ DATOS COMPLETOS → procesar_incidencia")
            return "procesar_incidencia"
        
        # 📥 5. ACTOR NECESITA INPUT → verificar contexto
        actor_decision = state.get("_actor_decision")
        if actor_decision == "need_input":
            self.logger.info("📥 ACTOR SOLICITA INPUT → mantener en actor actual")
            # El actor maneja su propio input, no interrumpir
            return self._get_current_actor_from_state(state)
        
        # 🔄 6. FALLBACK INTELIGENTE (sin bucles)
        return self._intelligent_fallback_routing(state)
    
    def _intelligent_fallback_routing(self, state: Dict[str, Any]) -> str:
        """
        🧠 Fallback inteligente que evita bucles infinitos
        
        Analiza el estado y determina el próximo paso lógico
        sin crear bucles.
        """
        
        nombre = state.get("nombre")
        email = state.get("email")
        datos_completos = state.get("datos_usuario_completos", False)
        incidencia_resuelta = state.get("incidencia_resuelta", False)
        
        # 👤 Si faltan datos básicos de usuario
        if not datos_completos and (not nombre or not email):
            self.logger.info(f"👤 FALLBACK: Datos incompletos (N:{bool(nombre)} E:{bool(email)}) → identificar_usuario")
            return "identificar_usuario"
        
        # 🔧 Si tenemos usuario pero no incidencia procesada
        if datos_completos and not incidencia_resuelta:
            self.logger.info("🔧 FALLBACK: Usuario OK, procesar incidencia → procesar_incidencia")
            return "procesar_incidencia"
        
        # ✅ Si todo está procesado
        if datos_completos and incidencia_resuelta:
            self.logger.info("✅ FALLBACK: Todo completo → finalizar_ticket")
            return "finalizar_ticket"
        
        # 🆘 Último recurso: volver al inicio
        self.logger.warning("🆘 FALLBACK: Estado indeterminado → identificar_usuario")
        return "identificar_usuario"
    
    def _get_current_actor_from_state(self, state: Dict[str, Any]) -> str:
        """
        Determinar qué actor debe manejar el input actual
        basado en el contexto del estado.
        """
        
        # Si hay contexto de input, mantener el actor apropiado
        input_context = state.get("_input_context", {})
        waiting_for = input_context.get("waiting_for", [])
        
        if "nombre" in waiting_for or "email" in waiting_for:
            return "identificar_usuario"
        
        if "descripcion" in waiting_for or "problema" in waiting_for:
            return "procesar_incidencia"
        
        # Default: identificar usuario
        return "identificar_usuario"
    
    def get_entry_point(self) -> str:
        return "identificar_usuario"
    
    def get_workflow_description(self) -> str:
        return (
            "Workflow híbrido LangGraph+Actor que evita bucles infinitos "
            "mediante señalización clara entre actores autónomos"
        )
    
    def build_graph(self) -> StateGraph:
        """Construir grafo híbrido con routing inteligente"""
        
        self.logger.info("🔧 Construyendo grafo híbrido...")
        
        # Crear grafo con el estado
        graph = StateGraph(GraphState)
        
        # Agregar nodos/actores
        graph.add_node("identificar_usuario", identificar_usuario_node)
        graph.add_node("procesar_incidencia", procesar_incidencia_node) 
        graph.add_node("escalar_supervisor", escalar_supervisor_node)
        graph.add_node("finalizar_ticket", finalizar_ticket_node)
        
        # Punto de entrada
        graph.add_edge(START, "identificar_usuario")
        
        # ===== ROUTING HÍBRIDO =====
        # Router inteligente que respeta decisiones de actores
        routing_destinations = {
            "identificar_usuario": "identificar_usuario",
            "procesar_incidencia": "procesar_incidencia",
            "escalar_supervisor": "escalar_supervisor", 
            "finalizar_ticket": "finalizar_ticket",
            END: END
        }
        
        # Aplicar routing inteligente a actores principales
        decision_actors = ["identificar_usuario", "procesar_incidencia"]
        
        for actor_name in decision_actors:
            self.add_conditional_edges(
                graph,
                actor_name,
                self._route_conversation,
                routing_destinations
            )
            self.logger.debug(f"🔀 Routing híbrido configurado para {actor_name}")
        
        # ===== EDGES DIRECTOS (sin decisiones) =====
        graph.add_edge("escalar_supervisor", END)
        graph.add_edge("finalizar_ticket", END)
        
        self.logger.info("✅ Grafo híbrido construido exitosamente")
        return graph
    
    def _cleanup_actor_signals(self, state: Dict[str, Any]):
        """
        Limpiar señales de actores después de procesar.
        
        Previene que las señales se acumulen y causen comportamientos
        inesperados en futuras ejecuciones.
        """
        signals_to_clean = [
            "_next_actor",
            "_actor_decision", 
            "_completion_message",
            "_request_message",
            "_input_context",
            "_delegation_reason"
        ]
        
        for signal in signals_to_clean:
            if signal in state:
                del state[signal]