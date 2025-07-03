# =====================================================
# nodes/finalize.py - Nodo de Finalización de Conversación
# =====================================================
"""
Nodo para finalizar conversaciones y cerrar tickets.

RESPONSABILIDADES:
- Registrar resolución en BD
- Recopilar feedback final
- Actualizar métricas
- Cerrar tickets apropiadamente
- Proporcionar resumen final
"""

from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging

from models.eroski_state import EroskiState
from nodes.base_node import BaseNode

class FinalizeConversationNode(BaseNode):
    """
    Nodo para finalizar conversaciones del chatbot.
    
    CARACTERÍSTICAS:
    - Cierre apropiado de tickets
    - Recopilación de feedback
    - Actualización de métricas
    - Registro en base de datos
    - Mensaje de despedida personalizado
    """
    
    def __init__(self):
        super().__init__("FinalizeConversation")
        
        # Tipos de finalización
        self.finalization_types = {
            "resolved": "Problema resuelto satisfactoriamente",
            "information_provided": "Información proporcionada",
            "escalated": "Escalado a soporte especializado",
            "user_satisfied": "Usuario satisfecho con la atención",
            "timeout": "Finalización por timeout",
            "error": "Finalización por error técnico"
        }
    
    def get_required_fields(self) -> List[str]:
        return ["messages", "authenticated"]
    
    def get_actor_description(self) -> str:
        return "Finalizo conversaciones, cierro tickets y registro métricas de atención"
    
    async def execute(self, state: EroskiState) -> Command:
        """
        Ejecutar finalización de conversación.
        
        Args:
            state: Estado actual del workflow
            
        Returns:
            Command con la finalización completada
        """
        try:
            # Determinar tipo de finalización
            finalization_type = self._determine_finalization_type(state)
            
            # Registrar en base de datos (si es necesario)
            registration_result = await self._register_completion(state, finalization_type)
            
            # Calcular métricas finales
            metrics = self._calculate_final_metrics(state)
            
            # Recopilar feedback implícito
            feedback = self._collect_implicit_feedback(state)
            
            # Proporcionar mensaje de finalización
            return self._provide_finalization_message(state, finalization_type, metrics, feedback)
            
        except Exception as e:
            self.logger.error(f"❌ Error en finalización: {e}")
            return self._provide_error_finalization(state)
    
    def _determine_finalization_type(self, state: EroskiState) -> str:
        """Determinar tipo de finalización basado en el estado"""
        
        # Verificar si fue resuelto
        if state.get("resolved"):
            return "resolved"
        
        # Verificar si fue escalado
        if state.get("escalation_processed"):
            return "escalated"
        
        # Verificar si se proporcionó información
        if state.get("information_provided"):
            return "information_provided"
        
        # Verificar si hay errores
        if state.get("error_count", 0) > 0:
            return "error"
        
        # Por defecto
        return "user_satisfied"
    
    async def _register_completion(self, state: EroskiState, finalization_type: str) -> bool:
        """
        Registrar finalización en base de datos.
        
        TODO: Implementar integración con base de datos
        - Actualizar estado de ticket
        - Registrar métricas
        - Guardar feedback
        """
        try:
            # Preparar datos para BD
            completion_data = {
                "session_id": state.get("session_id"),
                "employee_id": state.get("employee_id"),
                "ticket_number": state.get("ticket_number"),
                "finalization_type": finalization_type,
                "resolved": state.get("resolved", False),
                "escalated": state.get("escalation_processed", False),
                "resolution_time": self._calculate_resolution_time(state),
                "completed_at": datetime.now()
            }
            
            self.logger.info(f"📝 Registrando finalización: {completion_data}")
            
            # TODO: Implementar inserción en BD
            # await self.db_service.register_completion(completion_data)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error registrando finalización: {e}")
            return False
    
    def _calculate_final_metrics(self, state: EroskiState) -> Dict[str, Any]:
        """Calcular métricas finales de la conversación"""
        start_time = state.get("start_time")
        current_time = datetime.now()
        
        total_time = (current_time - start_time).total_seconds() / 60 if start_time else 0
        
        execution_path = state.get("execution_path", [])
        
        return {
            "total_time_minutes": round(total_time, 2),
            "nodes_visited": len(execution_path),
            "execution_path": execution_path,
            "messages_exchanged": len(state.get("messages", [])),
            "attempts": state.get("attempts", 0),
            "errors": state.get("error_count", 0),
            "resolved": state.get("resolved", False),
            "escalated": state.get("escalation_processed", False),
            "automated_resolution": state.get("automated_resolution", False)
        }
    
    def _collect_implicit_feedback(self, state: EroskiState) -> Dict[str, Any]:
        """Recopilar feedback implícito de la conversación"""
        feedback = {
            "user_satisfaction": "unknown",
            "solution_effectiveness": "unknown",
            "process_efficiency": "unknown"
        }
        
        # Analizar satisfacción basada en resolución
        if state.get("resolved"):
            feedback["user_satisfaction"] = "satisfied"
            feedback["solution_effectiveness"] = "effective"
        elif state.get("escalation_processed"):
            feedback["user_satisfaction"] = "needs_attention"
            feedback["solution_effectiveness"] = "escalated"
        
        # Analizar eficiencia del proceso
        total_time = self._calculate_resolution_time_minutes(state)
        if total_time <= 5:
            feedback["process_efficiency"] = "excellent"
        elif total_time <= 15:
            feedback["process_efficiency"] = "good"
        elif total_time <= 30:
            feedback["process_efficiency"] = "acceptable"
        else:
            feedback["process_efficiency"] = "slow"
        
        return feedback
    
    def _provide_finalization_message(self, state: EroskiState, finalization_type: str, 
                                    metrics: Dict[str, Any], feedback: Dict[str, Any]) -> Command:
        """Proporcionar mensaje de finalización apropiado"""
        
        # Construir mensaje según tipo de finalización
        if finalization_type == "resolved":
            message = self._build_resolved_message(state, metrics)
        elif finalization_type == "escalated":
            message = self._build_escalated_message(state, metrics)
        elif finalization_type == "information_provided":
            message = self._build_information_message(state, metrics)
        else:
            message = self._build_general_message(state, metrics)
        
        return Command(update={
            "flow_completed": True,
            "finalization_type": finalization_type,
            "final_metrics": metrics,
            "implicit_feedback": feedback,
            "conversation_closed": True,
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "current_node": "finalize",
            "last_activity": datetime.now(),
            "awaiting_user_input": False
        })
    
    def _build_resolved_message(self, state: EroskiState, metrics: Dict[str, Any]) -> str:
        """Construir mensaje para problemas resueltos"""
        
        ticket_number = state.get("ticket_number", "N/A")
        total_time = metrics.get("total_time_minutes", 0)
        
        return f"""🎉 **¡CONVERSACIÓN FINALIZADA EXITOSAMENTE!**

**✅ Resumen de la atención:**
• **Problema:** Resuelto satisfactoriamente
• **Tiempo total:** {total_time:.1f} minutos
• **Ticket:** {ticket_number} - **CERRADO**

**🌟 ¡Excelente trabajo!**
Tu problema ha sido resuelto exitosamente y toda la información ha sido registrada.

**📋 Lo que hemos logrado:**
• Identificación correcta del problema
• Aplicación de solución efectiva
• Verificación de funcionamiento
• Cierre satisfactorio del ticket

**🔄 Para futuras consultas:**
• Guarda el número de ticket: `{ticket_number}`
• Puedes contactarme nuevamente cuando necesites ayuda
• Recuerda que estoy disponible 24/7

**📞 Contactos de referencia:**
• Soporte técnico: +34 946 211 000
• Mi asistente virtual: Siempre disponible

¡Gracias por tu colaboración y que tengas un excelente día! 😊

---
*Conversación finalizada el {datetime.now().strftime("%d/%m/%Y a las %H:%M")}*"""
    
    def _build_escalated_message(self, state: EroskiState, metrics: Dict[str, Any]) -> str:
        """Construir mensaje para casos escalados"""
        
        ticket_number = state.get("ticket_number", "N/A")
        escalation_type = state.get("escalation_type", "supervisor")
        
        return f"""🔼 **CONVERSACIÓN ESCALADA EXITOSAMENTE**

**📋 Resumen de la escalación:**
• **Ticket:** {ticket_number} - **ESCALADO**
• **Derivado a:** {escalation_type.title()}
• **Estado:** En proceso con especialista

**✅ Lo que hemos logrado:**
• Identificación del problema
• Recopilación de información completa
• Escalación al equipo apropiado
• Creación de ticket prioritario

**⏰ Próximos pasos:**
• El equipo especializado te contactará pronto
• Mantén a mano el ticket: `{ticket_number}`
• Tiempo de respuesta estimado: 15-30 minutos

**📞 Para seguimiento:**
• Soporte técnico: +34 946 211 000
• Menciona el ticket: {ticket_number}

¡Gracias por tu paciencia! El equipo especializado se pondrá en contacto contigo pronto. 🤝

---
*Escalación procesada el {datetime.now().strftime("%d/%m/%Y a las %H:%M")}*"""
    
    def _build_information_message(self, state: EroskiState, metrics: Dict[str, Any]) -> str:
        """Construir mensaje para información proporcionada"""
        
        information_topics = state.get("information_provided", [])
        total_time = metrics.get("total_time_minutes", 0)
        
        return f"""ℹ️ **INFORMACIÓN PROPORCIONADA EXITOSAMENTE**

**📚 Resumen de la consulta:**
• **Información sobre:** {', '.join(information_topics[:3])}
• **Tiempo total:** {total_time:.1f} minutos
• **Estado:** Consulta completada

**✅ Lo que hemos cubierto:**
• Respuesta a tu consulta específica
• Información detallada y actualizada
• Recursos adicionales disponibles

**🔄 Para más información:**
• Puedes consultarme sobre otros temas
• Tengo información sobre: horarios, procedimientos, políticas
• Disponible 24/7 para tus consultas

**📞 Contactos útiles:**
• Supervisor de tienda: Ext. 100
• Soporte técnico: +34 946 211 000

¡Espero que la información haya sido útil! 😊

---
*Consulta completada el {datetime.now().strftime("%d/%m/%Y a las %H:%M")}*"""
    
    def _build_general_message(self, state: EroskiState, metrics: Dict[str, Any]) -> str:
        """Construir mensaje general de finalización"""
        
        return f"""✅ **CONVERSACIÓN FINALIZADA**

**📋 Resumen de la atención:**
• **Tiempo total:** {metrics.get('total_time_minutes', 0):.1f} minutos
• **Estado:** Atención completada

**🤝 Gracias por contactar conmigo**
Espero haber podido ayudarte con tu consulta.

**🔄 Para futuras consultas:**
• Estoy disponible 24/7
• Puedo ayudarte con problemas técnicos e información general
• No dudes en contactarme cuando necesites ayuda

**📞 Contactos útiles:**
• Soporte técnico: +34 946 211 000
• Supervisor de tienda: Ext. 100

¡Que tengas un excelente día! 😊

---
*Conversación finalizada el {datetime.now().strftime("%d/%m/%Y a las %H:%M")}*"""
    
    def _provide_error_finalization(self, state: EroskiState) -> Command:
        """Proporcionar finalización por error"""
        
        error_message = """⚠️ **FINALIZACIÓN POR ERROR TÉCNICO**

Ha ocurrido un error técnico durante la finalización de la conversación.

**📞 Contactos inmediatos:**
• Soporte técnico: +34 946 211 000
• Supervisor de tienda: Ext. 100

**📋 Información a proporcionar:**
• Menciona que hubo un error en el chatbot
• Proporciona detalles de tu consulta original

¡Disculpa las molestias técnicas! 🙏

---
*Error registrado el {datetime.now().strftime("%d/%m/%Y a las %H:%M")}*"""
        
        return Command(update={
            "flow_completed": True,
            "finalization_type": "error",
            "error_in_finalization": True,
            "messages": state.get("messages", []) + [AIMessage(content=error_message)],
            "current_node": "finalize",
            "last_activity": datetime.now(),
            "awaiting_user_input": False
        })
    
    def _calculate_resolution_time(self, state: EroskiState) -> str:
        """Calcular tiempo de resolución como string"""
        start_time = state.get("start_time")
        if not start_time:
            return "N/A"
        
        resolution_time = datetime.now() - start_time
        minutes = int(resolution_time.total_seconds() / 60)
        
        if minutes < 1:
            return "menos de 1 minuto"
        elif minutes < 60:
            return f"{minutes} minutos"
        else:
            hours = minutes // 60
            remaining_minutes = minutes % 60
            return f"{hours}h {remaining_minutes}m"
    
    def _calculate_resolution_time_minutes(self, state: EroskiState) -> float:
        """Calcular tiempo de resolución en minutos"""
        start_time = state.get("start_time")
        if not start_time:
            return 0.0
        
        resolution_time = datetime.now() - start_time
        return resolution_time.total_seconds() / 60

# ========== WRAPPER PARA LANGGRAPH ==========

async def finalize_conversation_node(state: EroskiState) -> Command:
    """
    Wrapper function para el nodo de finalización.
    
    Args:
        state: Estado actual del workflow
        
    Returns:
        Command con la actualización de estado
    """
    node = FinalizeConversationNode()
    return await node.execute(state)