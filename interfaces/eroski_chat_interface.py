# =====================================================
# interfaces/eroski_chat_interface.py - Interfaz de Chat Optimizada
# =====================================================
"""
Interfaz de chat optimizada para Eroski.

RESPONSABILIDADES:
- Gestionar interacción entre usuario y workflow
- Mantener sesiones y estado persistente
- Formatear respuestas para el usuario
- Manejar errores y recuperación
- Integrar con diferentes frontends (Chainlit, FastAPI, etc.)

PRINCIPIOS:
- Un mensaje = un ciclo completo del grafo
- Estado persistente entre mensajes
- Respuestas inmediatas al usuario
- Manejo robusto de errores
"""

from typing import Dict, Any, Optional, List
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from datetime import datetime
import logging
import uuid
import traceback

from workflows.eroski_main_workflow import EroskiFinalWorkflow
from models.eroski_state import EroskiState, create_initial_eroski_state

class EroskiChatInterface:
    """
    Interfaz de chat principal para el sistema Eroski.
    
    Maneja la comunicación entre el frontend (Chainlit, FastAPI, etc.)
    y el workflow de LangGraph, proporcionando una API simple y robusta.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("EroskiChatInterface")
        self.workflow = EroskiFinalWorkflow()
        self.graph = self.workflow.compile_with_checkpointer()
        self.active_sessions: Dict[str, Dict] = {}  # Cache de sesiones activas
        
        self.logger.info("🤖 EroskiChatInterface inicializada correctamente")
    
    async def process_message(
        self, 
        user_message: str, 
        session_id: Optional[str] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Procesar mensaje del usuario ejecutando el workflow completo.
        
        Args:
            user_message: Mensaje del usuario
            session_id: ID de la sesión (se genera si no se proporciona)
            user_context: Contexto adicional del usuario
            
        Returns:
            Diccionario con respuesta y metadatos
        """
        try:
            # Generar session_id si no se proporciona
            if not session_id:
                session_id = f"eroski_{uuid.uuid4().hex[:8]}"
            
            self.logger.info(f"📨 Procesando mensaje para sesión {session_id}")
            self.logger.debug(f"📝 Mensaje: {user_message[:100]}...")
            
            # Configuración para persistencia del grafo
            config = {
                "configurable": {"thread_id": session_id},
                "recursion_limit": 20
            }
            
            # Preparar input para el grafo
            input_data = {
                "messages": [HumanMessage(content=user_message)],
                "session_id": session_id,
                "last_activity": datetime.now()
            }
            
            # Agregar contexto del usuario si se proporciona
            if user_context:
                input_data.update(user_context)
            
            # Ejecutar grafo
            self.logger.debug("🔄 Ejecutando workflow...")
            result = await self.graph.ainvoke(input_data, config)
            
            # Procesar resultado
            response_data = self._process_workflow_result(result, session_id)
            
            # Actualizar cache de sesión
            self._update_session_cache(session_id, result)
            
            self.logger.info(f"✅ Mensaje procesado exitosamente para {session_id}")
            return response_data
            
        except Exception as e:
            self.logger.error(f"❌ Error procesando mensaje: {e}")
            self.logger.error(f"📍 Traceback: {traceback.format_exc()}")
            
            return self._create_error_response(str(e), session_id)
    
    def _process_workflow_result(self, result: EroskiState, session_id: str) -> Dict[str, Any]:
        """
        Procesar resultado del workflow y extraer información relevante.
        
        Args:
            result: Estado resultante del workflow
            session_id: ID de la sesión
            
        Returns:
            Diccionario con respuesta formateada
        """
        try:
            # Extraer respuesta del asistente
            assistant_response = self._extract_assistant_response(result)
            
            # Extraer metadatos
            metadata = self._extract_metadata(result)
            
            # Determinar estado de la conversación
            conversation_status = self._determine_conversation_status(result)
            
            return {
                "success": True,
                "response": assistant_response,
                "session_id": session_id,
                "status": conversation_status,
                "metadata": metadata,
                "awaiting_input": result.get("awaiting_user_input", False),
                "current_node": result.get("current_node"),
                "resolved": result.get("resolved", False),
                "escalated": result.get("escalation_needed", False),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error procesando resultado: {e}")
            return self._create_error_response(str(e), session_id)
    
    def _extract_assistant_response(self, state: EroskiState) -> str:
        """
        Extraer la última respuesta del asistente de los mensajes.
        
        Args:
            state: Estado del workflow
            
        Returns:
            Último mensaje del asistente
        """
        messages = state.get("messages", [])
        
        # Buscar último mensaje del asistente
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content.strip():
                return message.content
        
        # Fallback si no hay respuesta del asistente
        if state.get("escalation_needed"):
            return """Lo siento, he tenido que derivar tu consulta a un supervisor. 

📧 Recibirás una respuesta por email en las próximas horas.
📞 Para urgencias, contacta: +34 900 123 456

¡Gracias por tu paciencia! 😊"""
        
        return "Estoy procesando tu solicitud. ¿En qué más puedo ayudarte?"
    
    def _extract_metadata(self, state: EroskiState) -> Dict[str, Any]:
        """
        Extraer metadatos relevantes del estado.
        
        Args:
            state: Estado del workflow
            
        Returns:
            Diccionario con metadatos
        """
        return {
            "employee_id": state.get("employee_id"),
            "employee_name": state.get("employee_name"),
            "store_id": state.get("store_id"),
            "store_name": state.get("store_name"),
            "query_type": state.get("query_type"),
            "incident_type": state.get("incident_type"),
            "urgency_level": state.get("urgency_level"),
            "attempts": state.get("attempts", 0),
            "execution_path": state.get("execution_path", []),
            "total_messages": len(state.get("messages", [])),
            "start_time": state.get("start_time"),
            "resolution_time": self._calculate_resolution_time(state)
        }
    
    def _determine_conversation_status(self, state: EroskiState) -> str:
        """
        Determinar el estado actual de la conversación.
        
        Args:
            state: Estado del workflow
            
        Returns:
            Estado de la conversación
        """
        if state.get("escalation_needed"):
            return "escalated"
        elif state.get("resolved"):
            return "resolved"
        elif state.get("awaiting_user_input"):
            return "awaiting_input"
        elif state.get("flow_completed"):
            return "completed"
        else:
            return "in_progress"
    
    def _calculate_resolution_time(self, state: EroskiState) -> Optional[float]:
        """
        Calcular tiempo de resolución en minutos.
        
        Args:
            state: Estado del workflow
            
        Returns:
            Tiempo en minutos o None si no ha terminado
        """
        start_time = state.get("start_time")
        end_time = state.get("end_time")
        
        if start_time and end_time:
            return (end_time - start_time).total_seconds() / 60.0
        elif start_time and (state.get("resolved") or state.get("escalation_needed")):
            return (datetime.now() - start_time).total_seconds() / 60.0
        
        return None
    
    def _update_session_cache(self, session_id: str, state: EroskiState):
        """
        Actualizar cache de sesión para estadísticas.
        
        Args:
            session_id: ID de la sesión
            state: Estado actual
        """
        try:
            self.active_sessions[session_id] = {
                "last_activity": datetime.now(),
                "status": self._determine_conversation_status(state),
                "employee_id": state.get("employee_id"),
                "store_id": state.get("store_id"),
                "total_messages": len(state.get("messages", [])),
                "current_node": state.get("current_node")
            }
            
            # Limpiar sesiones antiguas (más de 24 horas)
            self._cleanup_old_sessions()
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error actualizando cache de sesión: {e}")
    
    def _cleanup_old_sessions(self):
        """Limpiar sesiones antiguas del cache"""
        try:
            cutoff_time = datetime.now().timestamp() - (24 * 3600)  # 24 horas
            
            old_sessions = [
                session_id for session_id, data in self.active_sessions.items()
                if data["last_activity"].timestamp() < cutoff_time
            ]
            
            for session_id in old_sessions:
                del self.active_sessions[session_id]
            
            if old_sessions:
                self.logger.info(f"🧹 Limpiadas {len(old_sessions)} sesiones antiguas")
                
        except Exception as e:
            self.logger.warning(f"⚠️ Error limpiando cache: {e}")
    
    def _create_error_response(self, error_message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Crear respuesta de error amigable para el usuario.
        
        Args:
            error_message: Mensaje de error técnico
            session_id: ID de la sesión
            
        Returns:
            Respuesta de error formateada
        """
        return {
            "success": False,
            "response": """Lo siento, ha ocurrido un error técnico. 😔

Por favor:
1. Intenta enviar tu mensaje nuevamente
2. Si el problema persiste, contacta con soporte técnico

📞 **Soporte técnico:** +34 900 123 456
📧 **Email:** soporte.tecnico@eroski.es

¡Gracias por tu paciencia!""",
            "session_id": session_id,
            "status": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat(),
            "awaiting_input": False,
            "resolved": False,
            "escalated": True
        }
    
    # ========== MÉTODOS PÚBLICOS ADICIONALES ==========
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtener información de una sesión activa.
        
        Args:
            session_id: ID de la sesión
            
        Returns:
            Información de la sesión o None si no existe
        """
        return self.active_sessions.get(session_id)
    
    def get_active_sessions_count(self) -> int:
        """
        Obtener número de sesiones activas.
        
        Returns:
            Número de sesiones activas
        """
        return len(self.active_sessions)
    
    def get_sessions_by_store(self, store_id: str) -> List[Dict[str, Any]]:
        """
        Obtener sesiones activas por tienda.
        
        Args:
            store_id: ID de la tienda
            
        Returns:
            Lista de sesiones de la tienda
        """
        return [
            {"session_id": sid, **data}
            for sid, data in self.active_sessions.items()
            if data.get("store_id") == store_id
        ]
    
    async def reset_session(self, session_id: str) -> bool:
        """
        Resetear una sesión específica.
        
        Args:
            session_id: ID de la sesión a resetear
            
        Returns:
            True si se reseteo correctamente
        """
        try:
            # Limpiar del cache
            if session_id in self.active_sessions:
                del self.active_sessions[session_id]
            
            # Crear nuevo estado inicial para la sesión
            config = {"configurable": {"thread_id": session_id}}
            initial_state = create_initial_eroski_state(session_id)
            
            # Guardar estado inicial en el checkpointer
            await self.graph.aupdate_state(config, initial_state)
            
            self.logger.info(f"🔄 Sesión {session_id} reseteada correctamente")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error reseteando sesión {session_id}: {e}")
            return False
    
    def get_interface_stats(self) -> Dict[str, Any]:
        """
        Obtener estadísticas de la interfaz.
        
        Returns:
            Diccionario con estadísticas
        """
        total_sessions = len(self.active_sessions)
        
        status_counts = {}
        store_counts = {}
        
        for session_data in self.active_sessions.values():
            # Contar por estado
            status = session_data.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Contar por tienda
            store = session_data.get("store_id", "unknown")
            store_counts[store] = store_counts.get(store, 0) + 1
        
        return {
            "total_active_sessions": total_sessions,
            "sessions_by_status": status_counts,
            "sessions_by_store": store_counts,
            "interface_uptime": datetime.now().isoformat(),
            "workflow_name": self.workflow.name
        }

# ========== FUNCIONES DE CONVENIENCIA ==========

def create_eroski_chat_interface() -> EroskiChatInterface:
    """
    Crear y configurar la interfaz de chat de Eroski.
    
    Returns:
        Instancia configurada de la interfaz
    """
    return EroskiChatInterface()

# Instancia global para uso en aplicaciones
_global_interface: Optional[EroskiChatInterface] = None

def get_global_chat_interface() -> EroskiChatInterface:
    """
    Obtener instancia global de la interfaz de chat.
    
    Returns:
        Instancia global de la interfaz
    """
    global _global_interface
    
    if _global_interface is None:
        _global_interface = create_eroski_chat_interface()
    
    return _global_interface

async def process_user_message(
    message: str, 
    session_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Función de conveniencia para procesar mensajes del usuario.
    
    Args:
        message: Mensaje del usuario
        session_id: ID de la sesión
        context: Contexto adicional
        
    Returns:
        Respuesta procesada
    """
    interface = get_global_chat_interface()
    return await interface.process_message(message, session_id, context)