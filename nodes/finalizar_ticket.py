# =====================================================
# nodes/finalizar_ticket.py - Nodo de finalización
# =====================================================
from nodes import BaseNode
from utils.database import IncidenciaRepository
from typing import List, Dict, Any
from langgraph.types import Command
from datetime import datetime

class FinalizarTicketNode(BaseNode):
    """
    Nodo para finalizar tickets resueltos.
    
    Funcionalidades:
    - Confirmar resolución con el usuario
    - Actualizar estado en BD
    - Solicitar feedback
    - Cerrar conversación apropiadamente
    """
    
    def __init__(self):
        super().__init__("finalizar_ticket", timeout_seconds=30)
        self.incidencia_repository = IncidenciaRepository()
    
    def get_required_fields(self) -> List[str]:
        return ["messages", "incidencia_resuelta"]
    
    def get_node_description(self) -> str:
        return "Finaliza tickets resueltos, actualiza BD y solicita feedback"
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """Ejecutar finalización de ticket"""
        
        numero_ticket = state.get("numero_ticket", "N/A")
        incidencia_id = state.get("incidencia_id")
        
        # Actualizar estado en BD si existe
        if incidencia_id:
            try:
                from models.incidencia import EstadoIncidencia
                await self.incidencia_repository.actualizar_estado(
                    incidencia_id, 
                    EstadoIncidencia.RESUELTA
                )
            except Exception as e:
                self.logger.error(f"Error actualizando estado de incidencia: {e}")
        
        # Mensaje de finalización
        mensaje_final = f"""
¡Perfecto! Tu incidencia ha sido procesada exitosamente. ✅

📋 **Número de ticket:** {numero_ticket}
📅 **Fecha:** {datetime.now().strftime('%d/%m/%Y %H:%M')}
✅ **Estado:** Resuelto

**¿Podemos ayudarte con algo más?**

Si tienes otra consulta, simplemente escríbela y estaré encantado de ayudarte. 

¡Que tengas un excelente día! 😊
"""
        
        return Command(update=self.create_message_update(mensaje_final, {
            "flujo_completado": True,
            "timestamp_finalizacion": datetime.now().isoformat(),
            "ticket_finalizado": True
        }))
    

async def finalizar_ticket_node(state: Dict[str, Any]) -> Command:
    """Wrapper para nodo de finalización"""
    node = FinalizarTicketNode()
    return await node.execute_with_monitoring(state)
