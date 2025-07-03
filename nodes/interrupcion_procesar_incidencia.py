# =====================================================
# nodes/interrupcion_identificar_usuario.py - RECOPILAR INPUT CORREGIDO
# =====================================================
from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
from utils.interruption_trip import get_trip_origin

from .base_node import BaseNode

class InterrupcionIdentificarUsuarioNode(BaseNode):
    """
    🎭 Nodo especializado para manejar recopilación de input del usuario.
    
    Este nodo:
    - Maneja interrupciones del flujo cuando se necesita input del usuario
    - Establece flags correctos para el sistema de interrupciones  
    - Genera mensajes apropiados según el contexto
    - Mantiene el contexto para continuar después de recibir el input
    """
    
    def __init__(self):
        super().__init__("interrupcion_identificar_usuario", timeout_seconds=30)
    
    def get_required_fields(self) -> List[str]:
        """✅ IMPLEMENTACIÓN REQUERIDA"""
        return ["messages"]
    
    def get_actor_description(self) -> str:
        """✅ IMPLEMENTACIÓN REQUERIDA - CORREGIDA"""
        return (
            "Maneja la recopilación de input del usuario cuando se está identificando"
            "generando mensajes apropiados según el contexto"
        )

# 8. EN interrupcion_identificar_usuario.py - IMPLEMENTAR LÓGICA DE STACK:

    async def execute(self, state: Dict[str, Any]) -> Command:
        #state['interruption_trip'] = None
        
        # Obtener el último mensaje del usuario y el último mensaje procesado
        try:
            request_message = state.get("_request_message", "")
            last_processed = state.get("_last_processed_message", "")
            
            self.logger.info("🔄 === INTERRUPCION IDENTIFICAR USUARIO ===")
            
            current_message = self.get_last_user_message(state)
            self.logger.info(f"📥 Mensaje usuario: '{current_message[:50] if current_message else 'None'}...'")
            
            if current_message and current_message != last_processed and current_message.strip():
                # ✅ HAY INPUT
                
                return Command(
                    goto="identificar_usuario",
                    update={
                    "intentos": state.get("intentos", 0) + 1
                })
            
            else:
                # ❌ NO HAY INPUT → Mantener interrupción
                self.logger.info("⏸️ Esperando input del usuario")
                
                return Command(
                    goto="identificar_usuario",
                    update={
                    **state,
                    "messages": [AIMessage(content=request_message or "Necesito más información")],
                })
                
        except Exception as e:
            self.logger.error(f"❌ Error: {e}")
            
            return Command(
                goto="escalar_supervisor",
                update={
                "razon_escalacion": f"Error en interrupcion_identificar_usuario: {e}",
            })



    def create_message_update(
        self, 
        message: str, 
        additional_updates: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Crear actualización con mensaje para el usuario.
        """
        update_data = {
            "messages": [AIMessage(content=message)],
            "awaiting_input": True,
            "requires_user_input": True
        }
        
        if additional_updates:
            update_data.update(additional_updates)
        
        return update_data
    
    def should_continue_after_input(self, state: Dict[str, Any]) -> bool:
        """
        Determinar si el flujo debe continuar después de recibir input.
        """
        return not state.get("awaiting_input", False)
    
    def get_resume_node(self, state: Dict[str, Any]) -> str:
        """
        Obtener el nodo donde debe continuar el flujo después del input.
        """
        input_context = state.get("_input_context", {})
        return input_context.get("resume_node", "identificar_usuario")


# =====================================================
# WRAPPER PARA LANGGRAPH  
# =====================================================
async def interrupcion_identificar_usuario(state: Dict[str, Any]) -> Command:
    """
    Wrapper function para el nodo de recopilación de input del usuario.
    
    Args:
        state: Estado actual del grafo
        
    Returns:
        Command con las actualizaciones del estado para interrumpir el flujo
    """
    node = InterrupcionIdentificarUsuarioNode()
    
    try:
        node.logger.info(f"🔵 ESTADO ANTES DE RECOPILAR: awaiting_input={state.get('awaiting_input')}")
        
        result = await node.execute_with_monitoring(state)
        
        node.logger.info(f"🔴 RECOPILAR COMPLETADO: type={type(result)}")
        if hasattr(result, 'update'):
            node.logger.info(f"🔴 AWAITING_INPUT: {result.update.get('awaiting_input')}")
        
        return result
        
    except Exception as e:
        node.logger.error(f"❌ Error en interrupcion_identificar_usuario wrapper: {e}")
        
        # Comando de recuperación
        return Command(update={
            **state,
            "messages": [AIMessage(content="Disculpa, hubo un problema. ¿Puedes intentar de nuevo?")],
            "awaiting_input": True,
            "error_info": {
                "node": "interrupcion_identificar_usuario",
                "error": str(e)
            }
        })