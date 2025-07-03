# =====================================================
# nodes/escalar_supervisor.py - Nodo de escalación
# =====================================================
from datetime import datetime
from typing import Any, Dict, List
from langgraph.types import Command
from nodes import BaseNode


class EscalarSupervisorNode(BaseNode):
    """
    Nodo para manejar escalaciones a supervisor.
    
    Funcionalidades:
    - Crear resumen de la conversación
    - Notificar al supervisor
    - Proporcionar información de contacto
    - Cerrar el flujo apropiadamente
    """
    
    def __init__(self):
        super().__init__("escalar_supervisor", timeout_seconds=30)
    
    def get_required_fields(self) -> List[str]:
        return ["messages", "escalar_a_supervisor"]
    
    def get_node_description(self) -> str:
        return "Maneja escalaciones a supervisor con resumen contextual y notificación"
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """Ejecutar escalación a supervisor"""
        
        # Crear resumen de la conversación
        resumen = self._create_conversation_summary(state)
        
        # Generar ID de escalación único
        escalation_id = f"ESC-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        
        # Mensaje para el usuario
        mensaje_usuario = self._generate_escalation_message(escalation_id, state)
        
        # TODO: Notificar al supervisor (email, Slack, etc.)
        await self._notify_supervisor(escalation_id, resumen, state)
        
        return Command(update=self.create_message_update(mensaje_usuario, {
            "escalation_id": escalation_id,
            "escalation_summary": resumen,
            "flujo_completado": True,
            "timestamp_escalacion": datetime.now().isoformat()
        }))
    
    def _create_conversation_summary(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Crear resumen estructurado de la conversación"""
        messages = state.get("messages", [])
        
        return {
            "usuario": {
                "nombre": state.get("nombre"),
                "email": state.get("email"),
                "numero_empleado": state.get("numero_empleado"),
                "datos_confirmados": state.get("datos_usuario_completos", False)
            },
            "incidencia": {
                "tipo": state.get("tipo_incidencia"),
                "descripcion": state.get("descripcion_incidencia"),
                "prioridad": state.get("prioridad_incidencia")
            },
            "conversacion": {
                "total_mensajes": len(messages),
                "intentos_identificacion": state.get("intentos", 0),
                "intentos_incidencia": state.get("intentos_incidencia", 0),
                "razon_escalacion": state.get("razon_escalacion"),
                "contexto_adicional": state.get("contexto_adicional")
            },
            "metadata": {
                "sesion_id": state.get("sesion_id"),
                "timestamp": datetime.now().isoformat(),
                "ultimo_nodo": state.get("contexto_escalacion", {}).get("node_origin")
            }
        }
    
    def _generate_escalation_message(self, escalation_id: str, state: Dict[str, Any]) -> str:
        """Generar mensaje de escalación para el usuario"""
        nombre = state.get("nombre", "")
        saludo = f"Hola {nombre}!" if nombre else "Hola!"
        
        return f"""
{saludo} 

He derivado tu consulta a un supervisor especializado que podrá ayudarte de manera más efectiva.

📋 **Número de escalación:** {escalation_id}
⏰ **Tiempo estimado de respuesta:** 2-4 horas laborales
📧 **Notificación:** Recibirás un email cuando tengamos una respuesta

Mientras tanto, si tienes alguna urgencia, puedes contactar directamente a:
📞 **Soporte urgente:** +34 900 123 456
✉️ **Email directo:** soporte.urgente@empresa.com

¡Gracias por tu paciencia! 😊
"""
    
    async def _notify_supervisor(self, escalation_id: str, resumen: Dict[str, Any], state: Dict[str, Any]):
        """Notificar al supervisor (placeholder)"""
        # TODO: Implementar notificación real
        self.logger.info(f"📧 Notificación de escalación enviada: {escalation_id}")

async def escalar_supervisor_node(state: Dict[str, Any]) -> Command:
    """Wrapper para nodo de escalación"""
    node = EscalarSupervisorNode()
    return await node.execute_with_monitoring(state)

