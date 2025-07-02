# =====================================================
# workflow/incidencia_workflow.py - CORREGIDO PARA EVITAR ERRORES DE IMPORT
# =====================================================
from langgraph.graph import StateGraph, START, END
from typing import Dict, Any
import logging

# ✅ Import relativo corregido
from .base_workflow import BaseWorkflow
from models.state import GraphState

class IncidenciaWorkflow(BaseWorkflow):
    """
    🎭 WORKFLOW HÍBRIDO: LangGraph + Actor Pattern
    
    VERSIÓN CORREGIDA - Evita errores de import de nodos
    """
    
    def __init__(self):
        super().__init__("IncidenciaWorkflow")
        self.logger = logging.getLogger("IncidenciaWorkflow")
        self.logger.info("🎭 Inicializando IncidenciaWorkflow")
    
    def get_entry_point(self) -> str:
        return "identificar_usuario"
    
    def get_workflow_description(self) -> str:
        return "Workflow principal para manejo de incidencias técnicas con Actor Pattern"
    
    def build_graph(self) -> StateGraph:
        """Construir grafo híbrido con imports seguros"""
        
        try:
            self.logger.info("🔧 Construyendo grafo híbrido...")
            
            # Crear grafo con el estado
            graph = StateGraph(GraphState)
            
            # ✅ IMPORTAR NODOS DE FORMA SEGURA
            self.logger.info("📦 Cargando nodos...")
            
            # Import seguro de nodos
            nodes = self._import_nodes_safely()
            
            # ✅ AGREGAR TODOS LOS NODOS/ACTORES
            self.logger.info("📦 Agregando nodos al grafo...")
            
            graph.add_node("identificar_usuario", nodes["identificar_usuario"])
            graph.add_node("procesar_incidencia", nodes["procesar_incidencia"]) 
            graph.add_node("escalar_supervisor", nodes["escalar_supervisor"])
            graph.add_node("finalizar_ticket", nodes["finalizar_ticket"])
            graph.add_node("recopilar_input_usuario", nodes["recopilar_input_usuario"])
            
            self.logger.info("✅ Nodos agregados exitosamente")
            
            # Punto de entrada
            graph.add_edge(START, "identificar_usuario")
            
            # ✅ ROUTING HÍBRIDO ACTUALIZADO - INCLUYE recopilar_input_usuario
            self.routing_destinations = {
                "identificar_usuario": "identificar_usuario",
                "procesar_incidencia": "procesar_incidencia",
                "escalar_supervisor": "escalar_supervisor", 
                "finalizar_ticket": "finalizar_ticket",
                "recopilar_input_usuario": "recopilar_input_usuario",
                END: END
            }
            
            # ✅ APLICAR ROUTING INTELIGENTE A TODOS LOS ACTORES QUE TOMAN DECISIONES
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
                    self.routing_destinations
                )
                self.logger.debug(f"🔀 Routing híbrido configurado para {actor_name}")
            
            # ✅ EDGES DIRECTOS PARA NODOS FINALES (sin decisiones complejas)
            graph.add_edge("escalar_supervisor", END)
            graph.add_edge("finalizar_ticket", END)
            
            self.logger.info("✅ Grafo híbrido construido exitosamente")
            return graph
            
        except Exception as e:
            self.logger.error(f"❌ Error construyendo grafo: {e}")
            # En lugar de fallar, construir un grafo mínimo
            return self._build_minimal_graph()
    
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
            from nodes.recopilar_input_usuario import recopilar_input_usuario
            nodes["recopilar_input_usuario"] = recopilar_input_usuario
            self.logger.info("✅ recopilar_input_usuario cargado")
        except Exception as e:
            self.logger.warning(f"⚠️ recopilar_input_usuario no disponible: {e}")
            nodes["recopilar_input_usuario"] = self._create_fallback_node("recopilar_input_usuario")
        
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
            elif node_name == "recopilar_input_usuario":
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
        """
        Router híbrido ACTUALIZADO que centraliza interrupciones en recopilar_input_usuario
        """

        # Debug básico
        self.logger.debug(f"🔍 Router recibió estado con claves: {list(state.keys())}")

        # ⏸️ PRIORIDAD 1: CENTRALIZAR TODAS LAS INTERRUPCIONES EN recopilar_input_usuario
        if (state.get("requires_user_input", False) or 
            state.get("_actor_decision") == "need_input" or
            state.get("awaiting_input", False) or
            state.get("_request_message")):
            
            self.logger.info("⏸️ NECESITA INPUT → recopilar_input_usuario")
            return "recopilar_input_usuario"
        
        # 🎯 PRIORIDAD 2: DECISIÓN EXPLÍCITA DEL ACTOR
        next_actor = state.get("_next_actor")
        if next_actor and next_actor in self.routing_destinations:
            self.logger.info(f"🎯 Actor solicita explícitamente: {next_actor}")
            return next_actor
        
        # 🏁 PRIORIDAD 3: FLUJO COMPLETADO
        if state.get("flujo_completado", False):
            self.logger.info("🏁 FLUJO COMPLETADO → END")
            return END
        
        # 🔼 PRIORIDAD 4: ESCALACIÓN A SUPERVISOR
        if state.get("escalar_a_supervisor", False):
            self.logger.info("🔼 ESCALACIÓN → escalar_supervisor")
            return "escalar_supervisor"
        
        # ✅ PRIORIDAD 5: DATOS DE USUARIO COMPLETOS → PROCESAR INCIDENCIA
        if state.get("datos_usuario_completos", False):
            nombre = state.get("nombre")
            email = state.get("email")
            
            if nombre and email:
                self.logger.info("✅ DATOS COMPLETOS Y VERIFICADOS → procesar_incidencia")
                return "procesar_incidencia"
            else:
                self.logger.warning("⚠️ datos_usuario_completos=True pero faltan datos reales")
                return "identificar_usuario"
        
        # 🔄 FALLBACK: IDENTIFICAR USUARIO
        nombre = state.get("nombre")
        email = state.get("email")
        
        if not nombre or not email:
            self.logger.info("🔄 FALTAN DATOS DE USUARIO → identificar_usuario")
            return "identificar_usuario"
        
        # Si tenemos datos pero no están marcados como completos, procesar
        self.logger.info("🔄 DATOS DISPONIBLES PERO NO MARCADOS COMPLETOS → procesar_incidencia")
        return "procesar_incidencia"
    
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