# =====================================================
# workflows/eroski_main_workflow.py - Workflow Principal con Nodos Mejorados
# =====================================================
"""
Workflow principal actualizado para usar los nodos mejorados con LLM.

CAMBIOS PRINCIPALES:
- Usa authenticate_enhanced para autenticación completa
- Usa classify_enhanced para clasificación con LLM
- Elimina nodos mock
- Routing actualizado para nuevos estados
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from typing import Literal, Dict, Any
import logging

from models.eroski_state import EroskiState, ConsultaType
from .base_workflow import BaseWorkflow

# Importar nodos usando el sistema de fallback
from nodes.authenticate_llm_driven import llm_driven_authenticate_node
from nodes.classify_enhanced import classify_query_node
from nodes.finalize import finalize_conversation_node
from nodes.verify import verify_resolution_node
from nodes.escalate import escalate_supervisor_node
from nodes.search_knowledge import search_knowledge_node
from nodes.search_solution import search_solution_node
from nodes.collect_incident import collect_incident_details_node


class EroskiFinalWorkflow(BaseWorkflow):
    """
    Workflow principal actualizado con nodos mejorados.
    """
    
    def __init__(self):
        super().__init__("EroskiMainWorkflow")
        self.memory = MemorySaver()
        
    def get_entry_point(self) -> str:
        return "authenticate"
    
    def get_workflow_description(self) -> str:
        return """
        Workflow Principal de Eroski - Con Nodos Mejorados
        
        Funcionalidades:
        1. Autenticación completa con LLM (usuario BD + no BD)
        2. Clasificación inteligente de incidencias
        3. Detección de cancelación en cualquier momento
        4. Recopilación iterativa de información
        
        Nodos mejorados:
        - AuthenticateNodeEnhanced: Recopila toda la información necesaria
        - ClassifyQueryNodeEnhanced: Análisis LLM de incidencias
        """
   


    def build_graph(self) -> StateGraph:
        """
        Construir el grafo principal con nodo LLM-driven integrado.
        
        Returns:
            Grafo compilado con checkpointer y persistencia
        """
        self.logger.info("🔨 Construyendo grafo principal de Eroski con LLM-driven...")
        
        # Crear grafo con el estado
        graph = StateGraph(EroskiState)
        
        # ========== CREAR INSTANCIAS DE NODOS ==========
        try:
            # NUEVO: Importar nodo LLM-driven
            
            # NUEVO: Usar instancia única para el nodo de autenticación
            graph.add_node("authenticate", llm_driven_authenticate_node)
            
            # Nodos existentes usando funciones wrapper
            graph.add_node("classify", classify_query_node)
            graph.add_node("collect_incident", collect_incident_details_node)
            graph.add_node("search_solution", search_solution_node)
            graph.add_node("search_knowledge", search_knowledge_node)
            graph.add_node("escalate", escalate_supervisor_node)
            graph.add_node("verify", verify_resolution_node)
            graph.add_node("finalize", finalize_conversation_node)
            
            self.logger.info("✅ Todos los nodos agregados correctamente (LLM-driven integrado)")
            
        except ImportError as e:
            self.logger.error(f"❌ Error importando nodos: {e}")
            # Fallback: usar nodos mock para desarrollo
            self._add_mock_nodes(graph)
        
        # ========== DEFINIR FLUJO CON NODO LLM-DRIVEN ==========
        
        # Punto de entrada
        graph.add_edge(START, "authenticate")
        
        # NUEVO: AUTHENTICATE con router LLM-driven
        graph.add_conditional_edges(
            "authenticate",
            self.route_authenticate_llm_driven_with_validation,  # Router mejorado
            {
                "continue": "classify",      # Autenticación completa → Clasificar consulta
                "need_input": END,           # Esperando input del usuario → Terminar y esperar
                "escalate": "escalate",      # Error/límite → Escalar a supervisor
                "cancelled": END             # Usuario canceló → Terminar conversación
            }
        )
        
        # CLASSIFY: Puede solicitar clarificación y terminar, o continuar
        graph.add_conditional_edges(
            "classify",
            self.route_classify,
            {
                "incident": "collect_incident",  # Es incidencia
                "query": "search_knowledge",     # Es consulta
                "urgent": "escalate",            # Es urgente
                "need_clarification": END,       # 🎯 RAMA A END: Necesita clarificación
                "escalate": "escalate"           # No se pudo clasificar
            }
        )
        
        # COLLECT_INCIDENT: Puede solicitar más detalles y terminar, o continuar
        graph.add_conditional_edges(
            "collect_incident",
            self.route_collect_incident,
            {
                "search_solution": "search_solution",  # Buscar solución
                "escalate": "escalate",                # Muy complejo
                "need_details": END                    # 🎯 RAMA A END: Necesita más detalles
            }
        )
        
        # SEARCH_SOLUTION: Buscar solución en base de conocimiento
        graph.add_conditional_edges(
            "search_solution",
            self.route_search_solution,
            {
                "solution_found": "verify",    # Solución encontrada
                "escalate": "escalate",        # No hay solución
                "need_clarification": END      # 🎯 RAMA A END: Necesita clarificación
            }
        )
        
        # SEARCH_KNOWLEDGE: Para consultas generales
        graph.add_conditional_edges(
            "search_knowledge",
            self.route_search_knowledge,
            {
                "information_provided": "finalize",  # Información proporcionada
                "escalate": "escalate",               # No se encontró información
                "need_clarification": END             # 🎯 RAMA A END: Necesita clarificación
            }
        )
        
        # VERIFY: Verificar si la solución funcionó
        graph.add_conditional_edges(
            "verify",
            self.route_verify,
            {
                "resolved": "finalize",        # Problema resuelto
                "not_resolved": "escalate",    # No funcionó la solución
                "need_feedback": END           # 🎯 RAMA A END: Esperando feedback
            }
        )
        
        # ESCALATE y FINALIZE terminan en END
        graph.add_edge("escalate", END)
        graph.add_edge("finalize", END)
        
        self.logger.info("✅ Grafo construido exitosamente con nodo LLM-driven")
        
        return graph

    # ========== ROUTING FUNCTIONS MEJORADAS ==========
    def route_authenticate_llm_driven(self, state: EroskiState) -> Literal["continue", "need_input", "escalate", "cancelled"]:
        """
        Router mejorado para el nodo de autenticación LLM-driven.
        
        Args:
            state: Estado actual del workflow
            
        Returns:
            Siguiente nodo o acción a ejecutar
        """
        
        # Log del estado actual para debugging
        self.logger.debug(f"🔍 Routing authenticate - Estado: {state.get('authentication_stage', 'no_stage')}")
        
        # 1. Verificar cancelación confirmada
        if (state.get("user_cancelled") or 
            state.get("conversation_cancelled") or
            state.get("awaiting_cancellation_confirmation")):
            self.logger.info("🚫 Usuario canceló la conversación")
            return "cancelled"
        
        # 2. Verificar si necesita input del usuario
        if state.get("awaiting_user_input"):
            self.logger.debug("⏳ Esperando input del usuario")
            return "need_input"
        
        # 3. Verificar escalación por errores o límite de intentos
        escalation_conditions = [
            state.get("escalation_needed"),
            state.get("attempts", 0) >= 5,
            state.get("fallback_mode") and state.get("attempts", 0) >= 3,
            state.get("error_count", 0) >= 3
        ]
        
        if any(escalation_conditions):
            escalation_reason = "Límite de intentos o errores críticos en autenticación"
            self.logger.warning(f"🔼 Escalando: {escalation_reason}")
            
            # Actualizar estado con información de escalación
            state.update({
                "escalation_needed": True,
                "escalation_reason": escalation_reason,
                "escalation_level": "supervisor"
            })
            return "escalate"
        
        # 4. Verificar si la autenticación está completa
        authentication_complete = (
            state.get("authentication_stage") == "completed" and
            state.get("datos_usuario_completos") and
            state.get("ready_for_classification") and
            state.get("employee_name") and
            state.get("incident_store_name") and
            state.get("incident_section")
        )
        
        if authentication_complete:
            self.logger.info("✅ Autenticación completada, continuando a clasificación")
            
            # Registrar métricas de autenticación
            self._log_authentication_metrics(state)
            
            return "continue"
        
        # 5. Por defecto, necesita más input del usuario
        self.logger.debug("📝 Autenticación en proceso, necesita más input")
        return "need_input"

    def route_authenticate_llm_driven_with_validation(self, state: EroskiState) -> Literal["continue", "need_input", "escalate", "cancelled"]:
        """
        Router con validación previa del estado.
        Este es el router principal que se usa en el workflow.
        """
        
        # 1. Validar estado antes de routing
        if not self.validate_auth_state_before_routing(state):
            self.logger.error("❌ Estado inválido, escalando")
            return "escalate"
        
        # 2. Logging de debugging si está habilitado
        if self.logger.isEnabledFor(logging.DEBUG):
            debug_info = self.debug_authentication_state(state)
            self.logger.debug(f"🔍 Debug autenticación: {debug_info}")
        
        # 3. Ejecutar routing principal
        return self.route_authenticate_llm_driven(state)


    def _log_authentication_metrics(self, state: EroskiState):
        """Registrar métricas del proceso de autenticación"""
        
        try:
            metrics = {
                "session_id": state.get("session_id"),
                "employee_name": state.get("employee_name"),
                "total_attempts": state.get("attempts", 0),
                "found_in_database": state.get("found_in_database", False),
                "fallback_used": state.get("fallback_mode", False),
                "completion_method": "llm_driven",
                "authentication_efficiency": self._calculate_auth_efficiency(state)
            }
            
            self.logger.info(f"📊 Métricas de autenticación LLM: {metrics}")
            
            # Guardar métricas en el estado para análisis posterior
            state["authentication_metrics"] = metrics
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error registrando métricas: {e}")

    def _calculate_auth_efficiency(self, state: EroskiState) -> str:
        """Calcular eficiencia del proceso de autenticación"""
        
        attempts = state.get("attempts", 0)
        
        if attempts == 1:
            return "excellent"  # Todo en un intercambio
        elif attempts <= 2:
            return "good"      # 2 intercambios
        elif attempts <= 3:
            return "fair"      # 3 intercambios
        else:
            return "poor"      # Más de 3 intercambios

    # =============================================================================
    # FUNCIÓN AUXILIAR PARA DEBUGGING
    # =============================================================================

    def debug_authentication_state(self, state: EroskiState) -> Dict[str, Any]:
        """
        Función de debugging para inspeccionar el estado de autenticación.
        
        Args:
            state: Estado actual
            
        Returns:
            Resumen del estado de autenticación
        """
        
        return {
            "authentication_stage": state.get("authentication_stage"),
            "datos_usuario_completos": state.get("datos_usuario_completos"),
            "awaiting_user_input": state.get("awaiting_user_input"),
            "attempts": state.get("attempts"),
            "fallback_mode": state.get("fallback_mode"),
            "escalation_needed": state.get("escalation_needed"),
            "auth_data_collected": state.get("auth_data_collected", {}),
            "employee_name": state.get("employee_name"),
            "incident_store_name": state.get("incident_store_name"),
            "incident_section": state.get("incident_section"),
            "found_in_database": state.get("found_in_database"),
            "ready_for_classification": state.get("ready_for_classification")
        }

    # =============================================================================
    # VALIDADOR DE ESTADO PRE-ROUTING
    # =============================================================================

    def validate_auth_state_before_routing(self, state: EroskiState) -> bool:
        """
        Validar que el estado sea consistente antes del routing.
        
        Args:
            state: Estado a validar
            
        Returns:
            True si el estado es válido
        """
        
        try:
            # Verificar campos críticos
            required_fields = ["messages", "session_id"]
            for field in required_fields:
                if field not in state:
                    self.logger.error(f"❌ Campo crítico faltante: {field}")
                    return False
            
            # Verificar consistencia de autenticación
            if state.get("authentication_stage") == "completed":
                if not state.get("datos_usuario_completos"):
                    self.logger.warning("⚠️ Inconsistencia: authentication_stage=completed pero datos_usuario_completos=False")
                    # Intentar corregir
                    state["datos_usuario_completos"] = True
            
            # Verificar que los attempts no sean negativos
            if state.get("attempts", 0) < 0:
                self.logger.warning("⚠️ Corrigiendo attempts negativo")
                state["attempts"] = 0
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error validando estado de autenticación: {e}")
            return False


    # =============================================================================
    # ROUTER MEJORADO CON VALIDACIÓN
    # =============================================================================

    def route_classify_enhanced(self, state: EroskiState) -> Literal["collect_details", "need_clarification", "cancelled", "escalate"]:
        """
        Routing mejorado para nodo de clasificación.
        """
        self.logger.info("🔄 Routing classify enhanced")
        
        # Verificar cancelación
        if state.get("cancelled"):
            self.logger.info("🚫 Usuario canceló en clasificación")
            return "cancelled"
        
        # Verificar escalación
        if state.get("escalation_needed"):
            self.logger.info("⚠️ Escalación necesaria en clasificación")
            return "escalate"
        
        # Verificar si se detectó incidencia
        query_type = state.get("query_type")
        confidence = state.get("confidence_score", 0)
        
        if query_type == ConsultaType.INCIDENCIA and confidence > 0.6:
            self.logger.info("🔧 Incidencia detectada - recopilando detalles")
            return "collect_details"
        
        # Verificar si hay clasificación de consulta
        if query_type == ConsultaType.CONSULTA and confidence > 0.6:
            self.logger.info("❓ Consulta general detectada - buscando conocimiento")
            return "collect_details"  # Por ahora mismo flujo
        
        # Por defecto, necesita clarificación
        self.logger.info("❓ Necesita clarificación del usuario")
        return "need_clarification"
    
    def route_collect_incident(self, state: EroskiState) -> Literal["search_solution", "need_details", "escalate"]:
        """
        Routing para recopilar detalles de incidencia.
        """
        # Lógica básica por ahora
        if state.get("escalation_needed"):
            return "escalate"
        
        incident_details = state.get("incident_details")
        if incident_details and len(incident_details) > 2:  # Suficientes detalles
            return "search_solution"
        else:
            return "need_details"
    
    def route_search_knowledge(self, state: EroskiState) -> Literal["resolved", "escalate", "need_clarification"]:
        """
        Routing para búsqueda de conocimiento.
        """
        # Lógica básica por ahora
        if state.get("escalation_needed"):
            return "escalate"
        elif state.get("solution_found"):
            return "resolved"
        else:
            return "need_clarification"
    
    # ========== NODOS MOCK TEMPORALES ==========
    
    async def _mock_collect_incident(self, state: EroskiState):
        """Nodo temporal para recopilar detalles de incidencia"""
        from langgraph.types import Command
        from langchain_core.messages import AIMessage
        from datetime import datetime
        
        self.logger.info("📋 Mock: Recopilando detalles de incidencia")
        
        incident_type = state.get("incident_type", "problema técnico")
        
        message = f"""📋 **Recopilando detalles de la incidencia**

He identificado que tienes un problema de tipo: **{incident_type}**

Para ayudarte mejor, necesito algunos detalles adicionales:

🔧 **¿Qué equipo específico está afectado?** (ej: TPV Caja 3, Impresora etiquetas)
⏰ **¿Cuándo comenzó el problema?** (ej: esta mañana, después de reiniciar)
❌ **¿Qué mensaje de error aparece?** (si aplica)
🔄 **¿Has intentado alguna solución?** (ej: reiniciar, cambiar papel)

*(En desarrollo - nodo temporal)*"""
        
        return Command(update={
            "current_node": "collect_incident",
            "messages": [AIMessage(content=message)],
            "awaiting_user_input": True,
            "last_activity": datetime.now(),
            "incident_details": {"stage": "collecting"}
        })
    
    async def _mock_search_knowledge(self, state: EroskiState):
        """Nodo temporal para búsqueda de conocimiento"""
        from langgraph.types import Command
        from langchain_core.messages import AIMessage
        from datetime import datetime
        
        self.logger.info("🔍 Mock: Buscando soluciones")
        
        message = """🔍 **Buscando soluciones**

Estoy consultando la base de conocimiento para encontrar soluciones a tu problema...

📚 **Consultando:**
• Base de datos de soluciones técnicas
• Procedimientos de Eroski
• Casos similares resueltos

*(En desarrollo - nodo temporal)*

Por ahora te derivaré a soporte técnico:
📞 **+34 946 211 000 (ext. 123)**"""
        
        return Command(update={
            "current_node": "search_knowledge",
            "messages": [AIMessage(content=message)],
            "escalation_needed": True,
            "escalation_reason": "Nodo search_knowledge en desarrollo",
            "last_activity": datetime.now()
        })
    
    async def _mock_escalate(self, state: EroskiState):
        """Nodo temporal para escalación"""
        from langgraph.types import Command
        from langchain_core.messages import AIMessage
        from datetime import datetime
        
        self.logger.info("⚠️ Mock: Escalando a supervisor")
        
        escalation_reason = state.get("escalation_reason", "Escalación solicitada")
        
        message = f"""🔼 **Escalando a supervisor**

**Motivo:** {escalation_reason}

📞 **Te he conectado con soporte técnico:**
• **Teléfono:** +34 946 211 000 (ext. 123)
• **Email:** soporte.tecnico@eroski.es

**Información de tu caso:**
🆔 **Sesión:** {state.get('session_id', 'N/A')}
👤 **Empleado:** {state.get('employee_name', 'N/A')}
🏪 **Tienda:** {state.get('incident_store_name', 'N/A')}
📍 **Sección:** {state.get('incident_section', 'N/A')}

Un especialista te atenderá pronto. ¡Gracias por tu paciencia! 🙏"""
        
        return Command(update={
            "current_node": "escalate",
            "messages": [AIMessage(content=message)],
            "escalated": True,
            "awaiting_user_input": False,
            "last_activity": datetime.now()
        })
    
    async def _mock_finalize(self, state: EroskiState):
        """Nodo temporal para finalización"""
        from langgraph.types import Command
        from langchain_core.messages import AIMessage
        from datetime import datetime
        
        self.logger.info("✅ Mock: Finalizando conversación")
        
        message = """✅ **Conversación finalizada**

Gracias por usar el asistente de incidencias de Eroski.

**Resumen de la sesión:**
👤 **Empleado:** {employee_name}
🏪 **Tienda:** {store_name}
📍 **Sección:** {section}
⏰ **Duración:** {duration}

Si necesitas más ayuda, no dudes en contactarnos nuevamente.

¡Que tengas un buen día! 😊""".format(
            employee_name=state.get('employee_name', 'N/A'),
            store_name=state.get('incident_store_name', 'N/A'),
            section=state.get('incident_section', 'N/A'),
            duration="N/A"  # Calcular duración real si es necesario
        )
        
        return Command(update={
            "current_node": "finalize",
            "messages": [AIMessage(content=message)],
            "conversation_ended": True,
            "awaiting_user_input": False,
            "last_activity": datetime.now()
        })
    
    def compile_with_checkpointer(self, checkpointer=None) -> StateGraph:
        """
        Compilar el workflow con checkpointer.
        """
        if checkpointer is None:
            checkpointer = self.memory
            
        graph = self.build_graph()
        
        self.logger.info("🔗 Compilando grafo con checkpointer")
        
        return graph.compile(
            checkpointer=checkpointer,
            interrupt_before=[]  # Sin interrupciones automáticas
        )
    
    def get_workflow_metrics(self, state: EroskiState) -> Dict[str, Any]:
        """
        Obtener métricas del workflow.
        """
        from datetime import datetime
        
        start_time = state.get("start_time")
        current_time = datetime.now()
        
        execution_path = state.get("execution_path", [])
        
        return {
            "session_id": state.get("session_id"),
            "employee_id": state.get("employee_id"),
            "store_id": state.get("incident_store_code"),
            "store_name": state.get("incident_store_name"),
            "section": state.get("incident_section"),
            "current_node": state.get("current_node"),
            "execution_path": execution_path,
            "total_nodes_visited": len(execution_path),
            "total_time_minutes": (current_time - start_time).total_seconds() / 60 if start_time else 0,
            "authenticated": state.get("authenticated", False),
            "ready_for_classification": state.get("ready_for_classification", False),
            "escalated": state.get("escalation_needed", False),
            "cancelled": state.get("cancelled", False),
            "query_type": state.get("query_type"),
            "incident_type": state.get("incident_type"),
            "workflow_name": self.name,
            "using_enhanced_nodes": True
        }

# ========== FUNCIONES DE CONVENIENCIA ==========

def create_eroski_workflow() -> EroskiFinalWorkflow:
    """
    Crear y configurar el workflow principal de Eroski con nodos mejorados.
    """
    return EroskiFinalWorkflow()

def get_compiled_eroski_graph():
    """
    Obtener grafo compilado listo para usar con nodos mejorados.
    """
    workflow = create_eroski_workflow()
    return workflow.compile_with_checkpointer()

def get_workflow_description() -> str:
    """
    Obtener descripción del workflow mejorado.
    """
    workflow = create_eroski_workflow()
    return workflow.get_workflow_description()