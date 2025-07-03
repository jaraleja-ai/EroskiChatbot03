# =====================================================
# workflow/incidencia_workflow.py - CORREGIDO PARA EVITAR ERRORES DE IMPORT
# =====================================================
from langgraph.graph import StateGraph, START, END
from typing import Dict, Any
import logging
from nodes.identificar_usuario import identificar_usuario_node
from nodes.procesar_incidencia import procesar_incidencia_node
from nodes.escalar_supervisor import escalar_supervisor_node
from nodes.finalizar_ticket import finalizar_ticket_node
from nodes.interrupcion_procesar_incidencia import interrupcion_identificar_usuario
from utils.interruption_trip import create_return_trip, get_trip_destination, get_trip_origin


# ✅ Import relativo corregido
from .base_workflow import BaseWorkflow
from models.state import GraphState

class IncidenciaWorkflow(BaseWorkflow):
    
    def __init__(self):
        super().__init__("IncidenciaWorkflow")
        self.logger = logging.getLogger("IncidenciaWorkflow")
        self.logger.info("🎭 Inicializando IncidenciaWorkflow")
    
    def get_entry_point(self) -> str:
        return "identificar_usuario"
    
    def get_workflow_description(self) -> str:
        return "Workflow principal para manejo de incidencias técnicas con Actor Pattern"
# En incidencia_workflow.py - Método build_graph()

    def build_graph(self) -> StateGraph:
        """Construir grafo híbrido con routing completo de interrupciones"""
        
        self.logger.info("🔧 Construyendo grafo híbrido...")
        
        # Crear grafo con el estado
        graph = StateGraph(GraphState)
        
        # ✅ AGREGAR TODOS LOS NODOS/ACTORES
        graph.add_node("identificar_usuario", identificar_usuario_node)
        graph.add_node("procesar_incidencia", procesar_incidencia_node) 
        graph.add_node("escalar_supervisor", escalar_supervisor_node)
        graph.add_node("finalizar_ticket", finalizar_ticket_node)
        graph.add_node("interrupcion_identificar_usuario", interrupcion_identificar_usuario)
        
        # Punto de entrada
        graph.add_edge(START, "identificar_usuario")
        
        # ✅ EDGES DIRECTOS PARA NODOS TERMINALES
        graph.add_edge("escalar_supervisor", END)
        graph.add_edge("finalizar_ticket", END)
        
        self.logger.info("✅ Grafo híbrido construido exitosamente")
        return graph


        

    def _import_nodes_safely(self) -> Dict[str, Any]:
        """Importar nodos de forma segura, con fallbacks si fallan"""
        
        nodes = {}
        
        # Importar cada nodo de forma segura
        try:
            from nodes.identificar_usuario import identificar_usuario_node
            nodes["identificar_usuario"] = identificar_usuario_node
            self.logger.info("✅ identificar_usuario_node cargado")
        except Exception as e:
            self.logger.warning(f"⚠️ identificar_usuario_node no disponible: {e}")
            nodes["identificar_usuario"] = self._create_fallback_node("identificar_usuario")
        
        try:
            from nodes.procesar_incidencia import procesar_incidencia_node
            nodes["procesar_incidencia"] = procesar_incidencia_node
            self.logger.info("✅ procesar_incidencia_node cargado")
        except Exception as e:
            self.logger.warning(f"⚠️ procesar_incidencia_node no disponible: {e}")
            nodes["procesar_incidencia"] = self._create_fallback_node("procesar_incidencia")
        
        try:
            from nodes.escalar_supervisor import escalar_supervisor_node
            nodes["escalar_supervisor"] = escalar_supervisor_node
            self.logger.info("✅ escalar_supervisor_node cargado")
        except Exception as e:
            self.logger.warning(f"⚠️ escalar_supervisor_node no disponible: {e}")
            nodes["escalar_supervisor"] = self._create_fallback_node("escalar_supervisor")
        
        try:
            from nodes.finalizar_ticket import finalizar_ticket_node
            nodes["finalizar_ticket"] = finalizar_ticket_node
            self.logger.info("✅ finalizar_ticket_node cargado")
        except Exception as e:
            self.logger.warning(f"⚠️ finalizar_ticket_node no disponible: {e}")
            nodes["finalizar_ticket"] = self._create_fallback_node("finalizar_ticket")
        
        try:
            from nodes.interrupcion_procesar_incidencia import interrupcion_identificar_usuario
            nodes["interrupcion_identificar_usuario"] = interrupcion_identificar_usuario
            self.logger.info("✅ interrupcion_identificar_usuario cargado")
        except Exception as e:
            self.logger.warning(f"⚠️ interrupcion_identificar_usuario no disponible: {e}")
            nodes["interrupcion_identificar_usuario"] = self._create_fallback_node("interrupcion_identificar_usuario")
        
        return nodes
    
    def _create_fallback_node(self, node_name: str):
        """Crear nodo fallback funcional"""
        
        async def fallback_node(state: Dict[str, Any]):
            from langgraph.types import Command
            from langchain_core.messages import AIMessage
            
            mensaje = f"El nodo {node_name} está en modo fallback. Funcionalidad limitada."
            
            # Comportamiento básico según el tipo de nodo
            if node_name == "identificar_usuario":
                return Command(update={
                    "messages": [AIMessage(content="Hola, necesito tu nombre y email para continuar.")],
                    "requires_user_input": True
                })
            elif node_name == "procesar_incidencia":
                return Command(update={
                    "messages": [AIMessage(content="Tu incidencia está siendo procesada.")],
                    "flujo_completado": True
                })
            elif node_name == "escalar_supervisor":
                return Command(update={
                    "messages": [AIMessage(content="Escalando a supervisor...")],
                    "flujo_completado": True
                })
            elif node_name == "finalizar_ticket":
                return Command(update={
                    "messages": [AIMessage(content="Ticket finalizado.")],
                    "flujo_completado": True
                })
            elif node_name == "interrupcion_identificar_usuario":
                return Command(update={
                    "messages": [AIMessage(content="¿Puedes proporcionar más información?")],
                    "requires_user_input": True
                })
            else:
                return Command(update={
                    "messages": [AIMessage(content=mensaje)],
                    "flujo_completado": True
                })
        
        return fallback_node
    
    def _build_minimal_graph(self) -> StateGraph:
        """Construir grafo mínimo en caso de error"""
        
        self.logger.warning("🔄 Construyendo grafo mínimo como fallback")
        
        graph = StateGraph(GraphState)
        
        async def minimal_node(state: Dict[str, Any]):
            from langgraph.types import Command
            from langchain_core.messages import AIMessage
            
            return Command(update={
                "messages": [AIMessage(content="Sistema en modo mínimo. Contacta al administrador.")],
                "flujo_completado": True
            })
        
        graph.add_node("minimal_node", minimal_node)
        graph.add_edge(START, "minimal_node")
        graph.add_edge("minimal_node", END)
        
        return graph

    def _route_conversation(self, state: Dict[str, Any]) -> str:
        print("🎛️"*50)
        print("entra al router")
        print("🎛️"*50)
        return "interrupcion_identificar_usuario"

    def _route_conversation2(self, state: Dict[str, Any]) -> str:
        """
        🧠 ROUTER HÍBRIDO ACTUALIZADO - Maneja input_received de interrupcion_identificar_usuario
        
        ORDEN DE PRIORIDADES:
        1. Input recibido (vuelta desde interrupcion_identificar_usuario)
        2. Señales explícitas de actores
        3. Estado awaiting_input (interrupciones)
        4. Estado de datos del usuario
        5. Escalación y finalización
        6. Fallback inteligente
        """
        
        # 🔍 DEBUG COMPLETO DEL ESTADO
        self.logger.info("🔍 === ROUTER - ANÁLISIS DE ESTADO CORREGIDO ===")
        self.logger.info(f"⏸️ awaiting_input: {state.get('awaiting_input', False)}")
        self.logger.info(f"⏸️ _next_actor: {state.get('_next_actor')}")
        self.logger.info(f"🔄 _in_recopilar: {state.get('_recopilar_execution') == 'second_run'}")
        self.logger.info(f"📍 _resume_node: {state.get('_resume_context', {}).get('resume_node')}")
        self.logger.info(f"👤 datos_usuario_completos: {state.get('datos_usuario_completos', False)}")
        self.logger.info(f"🔄 Execution count: {state.get('_execution_count', 0)}")
        self.logger.info(f"🔄 Interruption trip: {state.get('interruption_trip', 0)}")
        
        next_actor = state.get("_next_actor")
        if next_actor == "interrupcion_identificar_usuario":
            print("🛑"*50)
            print(f"next actor: {next_actor}")
            trip = state["interruption_trip"]
            state["interruption_trip"] = create_return_trip(trip)
            print(f"interruption_trip: {state['interruption_trip']}")
            print("🛑"*50)
            
            # ⭐ PRIORIDAD 3: INTERRUPCIONES - Vuelta desde interrupcion_identificar_usuario
            if state.get("_recopilar_execution") == "second_run":
                print("🌟"*50)
                print(f"interrupcion_identificar_usuario: {state.get('interrupcion_identificar_usuario', False)}")
                print("🌟"*50)
            print(f"next_actor: {next_actor}")
            return next_actor
        elif state["interruption_trip"]:
            print("🏅"*50)
            print(f"get_trip_destination: {get_trip_destination}")
            return get_trip_destination
        
        # ⭐ PRIORIDAD 1: INPUT RECIBIDO - Vuelta desde interrupcion_identificar_usuario
        actor_decision = state.get("_actor_decision")
        # PRIORIDAD 1: INPUT RECIBIDO
        if actor_decision == "input_received":
            next_actor = state.get("_next_actor")
            if next_actor:
                self.logger.info(f"📥 INPUT RECIBIDO → {next_actor}")
                return next_actor
        
            
        # ⭐ PRIORIDAD 2: SEÑALES EXPLÍCITAS DE ACTORES (need_input, etc.)
        next_actor = state.get("_next_actor")
        if actor_decision == "need_input" and next_actor:
            self.logger.info(f"📥 NUEVA SOLICITUD DE INPUT → {next_actor}")
            return next_actor
        
        if next_actor and actor_decision in ["complete", "continue", "delegate"]:
            self.logger.info(f"🎭 ACTOR DECIDIÓ '{actor_decision}' → {next_actor}")
            return next_actor
        
        # ⏸️ PRIORIDAD 3: ESTADO AWAITING_INPUT (solo para nuevas interrupciones)
        if state.get("awaiting_input", False) and actor_decision != "input_received":
            execution_type = state.get("_recopilar_execution")
            if execution_type != "second_run":  # No interrumpir en segunda ejecución
                self.logger.info("⏸️ ESPERANDO INPUT DEL USUARIO → __interrupt__")
                return "interrupcion_identificar_usuario"
        
        # 🔼 PRIORIDAD 4: ESCALACIÓN SOLICITADA
        if state.get("escalar_a_supervisor", False):
            self.logger.info("🔼 ESCALACIÓN → escalar_supervisor")
            return "escalar_supervisor"
        
        # 🏁 PRIORIDAD 5: FLUJO COMPLETADO
        if state.get("flujo_completado", False):
            self.logger.info("🏁 FLUJO COMPLETADO → finalizar_ticket")
            return "finalizar_ticket"
        
        # ✅ PRIORIDAD 6: DATOS COMPLETOS
        if state.get("datos_usuario_completos", False):
            incidencia_info = state.get("descripcion_incidencia")
            if incidencia_info:
                self.logger.info("✅ DATOS E INCIDENCIA COMPLETOS → procesar_incidencia")
                return "procesar_incidencia"
            else:
                self.logger.info("✅ DATOS COMPLETOS, PROCESAR INCIDENCIA → procesar_incidencia")
                return "procesar_incidencia"
        
        # 🛑 PRIORIDAD 7: PROTECCIÓN ANTI-BUCLE
        execution_count = state.get("_execution_count", 0)
        if execution_count > 15:  # Aumentar límite para permitir flujo de interrupciones
            self.logger.warning(f"🛑 BUCLE DETECTADO ({execution_count} ejecuciones) → escalar_supervisor")
            return "escalar_supervisor"
        
        # 🔄 PRIORIDAD 8: ANÁLISIS DE DATOS DE USUARIO
        nombre = state.get("nombre")
        email = state.get("email")
        
        # Si no tenemos datos de usuario básicos
        if not nombre or not email:
            intentos_usuario = state.get("intentos", 0)
            if intentos_usuario < 5:  # Límite de intentos para identificación
                self.logger.info(f"👤 FALTAN DATOS DE USUARIO (intento {intentos_usuario}) → identificar_usuario")
                # Incrementar execution_count para tracking
                state["_execution_count"] = execution_count + 1
                return "identificar_usuario"
            else:
                self.logger.warning(f"🛑 DEMASIADOS INTENTOS IDENTIFICANDO USUARIO → escalar_supervisor")
                return "escalar_supervisor"
        
        # Si tenemos datos básicos pero no están marcados como completos
        if nombre and email and not state.get("datos_usuario_completos", False):
            self.logger.info("🔄 DATOS PRESENTES PERO NO VALIDADOS → identificar_usuario")
            return "identificar_usuario"
        
        # 🎯 DEFAULT FINAL: Procesar incidencia
        self.logger.info("🎯 DEFAULT → procesar_incidencia")
        return "procesar_incidencia"


    def _route_interruption(self, state: Dict[str, Any]) -> str:
        """
        🧠 ROUTER para devolver la interrupción.
        Es necesario porque el state no se sincroniza hasta que 
        se ejecuta el siguiente nodo a la interrupción
        """
        
        # 🔍 DEBUG COMPLETO DEL ESTADO
        self.logger.info("🔍 === ROUTER INTERRUPTION- ANÁLISIS DE ESTADO CORREGIDO ===")
        self.logger.info(f"⏸️ awaiting_input: {state.get('awaiting_input', False)}")
        self.logger.info(f"⏸️ _next_actor: {state.get('_next_actor')}")
        self.logger.info(f"🔄 _in_recopilar: {state.get('_recopilar_execution') == 'second_run'}")
        self.logger.info(f"📍 _resume_node: {state.get('_resume_context', {}).get('resume_node')}")
        self.logger.info(f"👤 datos_usuario_completos: {state.get('datos_usuario_completos', False)}")
        self.logger.info(f"🔄 Execution count: {state.get('_execution_count', 0)}")
        self.logger.info(f"🔄 Interruption trip: {state.get('interruption_trip', 0)}")
        
        trip = state["interruption_trip"]
        origen = get_trip_origin(trip)
        print(f"Trip origen: {origen}")
        self.logger.info(f"📍 Trip destino: {get_trip_destination(trip)}")
        return origen




    def add_conditional_edges(self, graph: StateGraph, source: str, condition_func, path_map: Dict[str, str]):
        """Helper para agregar edges condicionales de forma consistente"""
        try:
            graph.add_conditional_edges(
                source,
                condition_func,
                path_map
            )
            self.logger.debug(f"✅ Conditional edges agregados para {source}")
            
        except Exception as e:
            self.logger.error(f"❌ Error agregando conditional edges para {source}: {e}")
            # En lugar de fallar, agregar edge directo a END
            graph.add_edge(source, END)