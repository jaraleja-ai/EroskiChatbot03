# =====================================================
# workflow/incidencia_workflow.py - ROUTER HÍBRIDO INTELIGENTE CORREGIDO
# =====================================================
from langgraph.graph import StateGraph, START, END
from workflow.base_workflow import BaseWorkflow
from models.state import GraphState
from typing import Dict, Any

# ✅ IMPORTS LIMPIOS - SIN DUPLICACIONES
from nodes.identificar_usuario import identificar_usuario_node
from nodes.procesar_incidencia import procesar_incidencia_node
from nodes.escalar_supervisor import escalar_supervisor_node
from nodes.finalizar_ticket import finalizar_ticket_node
from nodes.recopilar_input_usuario import recopilar_input_usuario

class IncidenciaWorkflow(BaseWorkflow):
    """
    🎭 WORKFLOW HÍBRIDO: LangGraph + Actor Pattern
    
    PRINCIPIOS HÍBRIDOS:
    - ✅ Estructura LangGraph para el framework
    - ✅ Decisiones autónomas de actores
    - ✅ Router que RESPETA las señales de actores
    - ✅ Sin bucles infinitos
    - ✅ Manejo de interrupciones para input del usuario
    
    ROUTER INTELIGENTE:
    - Los actores DECIDEN, el router solo EJECUTA
    - Prioriza señales explícitas de actores
    - Fallback inteligente sin bucles
    """
    
    def __init__(self):
        super().__init__("IncidenciaWorkflow")
    
    def build_graph(self) -> StateGraph:
        """Construir grafo híbrido con routing inteligente"""
        
        self.logger.info("🔧 Construyendo grafo híbrido...")
        
        # Crear grafo con el estado
        graph = StateGraph(GraphState)
        
        # ✅ AGREGAR TODOS LOS NODOS/ACTORES
        graph.add_node("identificar_usuario", identificar_usuario_node)
        graph.add_node("procesar_incidencia", procesar_incidencia_node) 
        graph.add_node("escalar_supervisor", escalar_supervisor_node)
        graph.add_node("finalizar_ticket", finalizar_ticket_node)
        graph.add_node("recopilar_input_usuario", recopilar_input_usuario)
        
        # Punto de entrada
        graph.add_edge(START, "identificar_usuario")
        
        # ✅ ROUTING HÍBRIDO ACTUALIZADO
        routing_destinations = {
            "identificar_usuario": "identificar_usuario",
            "procesar_incidencia": "procesar_incidencia",
            "escalar_supervisor": "escalar_supervisor", 
            "finalizar_ticket": "finalizar_ticket",
            "recopilar_input_usuario": "recopilar_input_usuario",
            END: END
        }
        
        # ✅ APLICAR ROUTING INTELIGENTE A ACTORES PRINCIPALES
        decision_actors = [
            "identificar_usuario", 
            "procesar_incidencia", 
            "recopilar_input_usuario"
        ]
        
        for actor_name in decision_actors:
            self.add_conditional_edges(
                graph,
                actor_name,
                self._route_conversation,
                routing_destinations
            )
            self.logger.debug(f"🔀 Routing híbrido configurado para {actor_name}")
        
        # ✅ EDGES DIRECTOS PARA NODOS FINALES
        graph.add_edge("escalar_supervisor", END)
        graph.add_edge("finalizar_ticket", END)
        
        self.logger.info("✅ Grafo híbrido construido exitosamente")
        return graph
    
    def _route_conversation(self, state: Dict[str, Any]) -> str:
        """
        🧠 ROUTER HÍBRIDO INTELIGENTE
        
        PRIORIDADES (en orden estricto):
        1. 🎯 Decisión EXPLÍCITA del actor (máxima autoridad)
        2. ⏸️ Interrupción para recopilar input del usuario
        3. 🔄 Continuar después de recopilar input
        4. 🔼 Escalación solicitada
        5. 🏁 Flujo marcado como completado  
        6. 📥 Actor necesita input → verificar contexto
        7. ✅ Datos completos → continuar flujo
        8. 🔄 Fallback inteligente
        
        CLAVE: El router NO toma decisiones de negocio,
               solo INTERPRETA las señales de los actores.
        """
        
        # 🎯 1. MÁXIMA PRIORIDAD: Decisión EXPLÍCITA del actor
        next_actor = state.get("_next_actor")
        if next_actor:
            self.logger.info(f"🎯 ACTOR DECIDIÓ → {next_actor}")
            # ✅ IMPORTANTE: Limpiar la señal para evitar loops
            state["_next_actor"] = None
            return next_actor
        
        # ⏸️ 2. INTERRUPCIÓN PARA RECOPILAR INPUT DEL USUARIO
        if state.get("requires_user_input", False):
            self.logger.info("⏸️ INPUT REQUERIDO → recopilar_input_usuario")
            return "recopilar_input_usuario"
        
        # 🔄 3. CONTINUAR DESPUÉS DE RECOPILAR INPUT
        workflow_state = state.get("workflow_state", {})
        if workflow_state.get("input_processed", False):
            resume_node = workflow_state.get("resume_node", "identificar_usuario")
            self.logger.info(f"🔄 CONTINUAR DESPUÉS DE INPUT → {resume_node}")
            return resume_node
        
        # 🔼 4. ESCALACIÓN solicitada por actor
        if state.get("escalar_a_supervisor", False):
            self.logger.info("🔼 ESCALACIÓN SOLICITADA → escalar_supervisor")
            return "escalar_supervisor"
        
        # 🏁 5. FLUJO COMPLETADO por actor
        if state.get("flujo_completado", False):
            self.logger.info("🏁 FLUJO COMPLETADO → finalizar_ticket")
            return "finalizar_ticket"
        
        # 📥 6. ACTOR NECESITA INPUT → verificar contexto
        actor_decision = state.get("_actor_decision")
        if actor_decision == "need_input":
            self.logger.info("📥 ACTOR SOLICITA INPUT → mantener en actor actual")
            # El actor maneja su propio input, no interrumpir
            return self._get_current_actor_from_state(state)
        
        # ✅ 7. DATOS COMPLETOS → continuar flujo natural
        datos_completos = state.get("datos_usuario_completos", False)
        if datos_completos and not state.get("incidencia_resuelta", False):
            self.logger.info("✅ DATOS COMPLETOS → procesar_incidencia")
            return "procesar_incidencia"
        
        # 🔄 8. FALLBACK INTELIGENTE (sin bucles)
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
        
        # ✅ MANEJAR CONTEXTO DE INPUT
        input_context = state.get("_input_context", {})
        waiting_for = input_context.get("waiting_for", [])
        
        if "nombre" in waiting_for or "email" in waiting_for:
            self.logger.info("👤 FALLBACK: Esperando datos de usuario → identificar_usuario")
            return "identificar_usuario"
        
        if "descripcion" in waiting_for or "problema" in waiting_for:
            self.logger.info("🔧 FALLBACK: Esperando detalles de incidencia → procesar_incidencia")
            return "procesar_incidencia"
        
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
        
        LÓGICA:
        - Si el actor solicitó input, debe seguir manejándolo
        - Analizar el contexto para determinar el actor apropiado
        - Fallback inteligente si no hay contexto claro
        """
        
        # 🎭 1. VERIFICAR SI HAY UN ACTOR ACTUAL EXPLÍCITO
        current_actor = state.get("_current_actor")
        if current_actor:
            self.logger.info(f"🎭 ACTOR ACTUAL DEFINIDO → {current_actor}")
            return current_actor
        
        # 📋 2. ANALIZAR CONTEXTO DE INPUT
        input_context = state.get("_input_context", {})
        waiting_for = input_context.get("waiting_for", [])
        context_actor = input_context.get("actor", "")
        
        if context_actor:
            self.logger.info(f"📋 CONTEXTO INDICA ACTOR → {context_actor}")
            return context_actor
        
        # 👤 3. DETERMINAR POR TIPO DE INPUT ESPERADO
        if any(field in waiting_for for field in ["nombre", "email", "identificacion"]):
            self.logger.info("👤 INPUT DE USUARIO → identificar_usuario")
            return "identificar_usuario"
        
        if any(field in waiting_for for field in ["descripcion", "problema", "detalles", "categoria"]):
            self.logger.info("🔧 INPUT DE INCIDENCIA → procesar_incidencia")
            return "procesar_incidencia"
        
        # 🔄 4. FALLBACK BASADO EN ESTADO ACTUAL
        if not state.get("datos_usuario_completos", False):
            self.logger.info("🔄 DATOS INCOMPLETOS → identificar_usuario")
            return "identificar_usuario"
        
        if state.get("datos_usuario_completos", False) and not state.get("incidencia_resuelta", False):
            self.logger.info("🔄 USUARIO OK, PROCESAR INCIDENCIA → procesar_incidencia")
            return "procesar_incidencia"
        
        # 🆘 ÚLTIMO RECURSO
        self.logger.warning("🆘 NO SE PUEDE DETERMINAR ACTOR → identificar_usuario")
        return "identificar_usuario"
    
    def get_entry_point(self) -> str:
        return "identificar_usuario"
    
    def get_workflow_description(self) -> str:
        return (
            "Workflow híbrido LangGraph+Actor que evita bucles infinitos "
            "mediante señalización clara entre actores autónomos y maneja "
            "interrupciones para recopilar input del usuario"
        )
    
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
    
    # ✅ SOBRESCRIBIR MÉTODO DE INTERRUPCIONES
    def _get_interrupt_nodes(self) -> list[str]:
        """
        Nodos donde interrumpir para recopilar input del usuario.
        """
        return ["recopilar_input_usuario"]