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
from nodes import get_best_authenticate_node, get_best_classify_node

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
        Construir el grafo con nodos mejorados.
        """
        self.logger.info("🏗️ Construyendo grafo con nodos mejorados")
        
        # Crear grafo
        graph = StateGraph(EroskiState)
        
        # ========== AGREGAR NODOS CON FALLBACK AUTOMÁTICO ==========
        
        # Obtener mejores nodos disponibles
        authenticate_node = get_best_authenticate_node()
        classify_node = get_best_classify_node()
        
        # Nodo de autenticación (mejorado o básico)
        graph.add_node("authenticate", authenticate_node)
        
        # Nodo de clasificación (mejorado o básico)
        graph.add_node("classify", classify_node)
        
        # Nodos adicionales (pueden ser mock por ahora)
        graph.add_node("collect_incident", self._mock_collect_incident)
        graph.add_node("search_knowledge", self._mock_search_knowledge)
        graph.add_node("escalate", self._mock_escalate)
        graph.add_node("finalize", self._mock_finalize)
        
        # ========== DEFINIR FLUJO CON ROUTING MEJORADO ==========
        
        # Punto de entrada
        graph.add_edge(START, "authenticate")
        
        # AUTHENTICATE: Routing mejorado
        graph.add_conditional_edges(
            "authenticate",
            self.route_authenticate_enhanced,
            {
                "continue": "classify",           # ✅ Información completa
                "need_input": END,                # 🔄 Esperando respuesta del usuario
                "cancelled": END,                 # 🚫 Usuario canceló
                "escalate": "escalate"            # ⚠️ Error o máximo intentos
            }
        )
        
        # CLASSIFY: Routing mejorado
        graph.add_conditional_edges(
            "classify",
            self.route_classify_enhanced,
            {
                "collect_details": "collect_incident",  # 📋 Incidencia detectada
                "need_clarification": END,              # ❓ Necesita más info
                "cancelled": END,                       # 🚫 Usuario canceló
                "escalate": "escalate"                  # ⚠️ No se pudo clasificar
            }
        )
        
        # COLLECT_INCIDENT: Flujo básico por ahora
        graph.add_conditional_edges(
            "collect_incident",
            self.route_collect_incident,
            {
                "search_solution": "search_knowledge",
                "need_details": END,
                "escalate": "escalate"
            }
        )
        
        # SEARCH_KNOWLEDGE: Flujo básico
        graph.add_conditional_edges(
            "search_knowledge",
            self.route_search_knowledge,
            {
                "resolved": "finalize",
                "escalate": "escalate",
                "need_clarification": END
            }
        )
        
        # ESCALATE y FINALIZE van a END
        graph.add_edge("escalate", "finalize")
        graph.add_edge("finalize", END)
        
        self.logger.info("✅ Grafo construido con nodos mejorados")
        
        return graph
    
    # ========== ROUTING FUNCTIONS MEJORADAS ==========
    
    def route_authenticate_enhanced(self, state: EroskiState) -> Literal["continue", "need_input", "cancelled", "escalate"]:
        """
        Routing mejorado para nodo de autenticación.
        """
        self.logger.info("🔄 Routing authenticate enhanced")
        
        # Verificar cancelación
        if state.get("cancelled"):
            self.logger.info("🚫 Usuario canceló en autenticación")
            return "cancelled"
        
        # Verificar escalación
        if state.get("escalation_needed"):
            self.logger.info("⚠️ Escalación necesaria en autenticación")
            return "escalate"
        
        # Verificar si está listo para continuar
        if state.get("ready_for_classification"):
            self.logger.info("✅ Autenticación completa - continuando a clasificación")
            return "continue"
        
        # Por defecto, necesita más input del usuario
        self.logger.info("🔄 Esperando más información del usuario")
        return "need_input"
    
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
            "messages": state.get("messages", []) + [AIMessage(content=message)],
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
            "messages": state.get("messages", []) + [AIMessage(content=message)],
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
            "messages": state.get("messages", []) + [AIMessage(content=message)],
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
            "messages": state.get("messages", []) + [AIMessage(content=message)],
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