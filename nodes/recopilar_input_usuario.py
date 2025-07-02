# =====================================================
# nodes/recopilar_input_usuario.py - RECOPILAR INPUT CORREGIDO
# =====================================================
from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from .base_node import BaseNode

class RecopilarInputUsuarioNode(BaseNode):
    """
    🎭 Nodo especializado para manejar recopilación de input del usuario.
    
    Este nodo:
    - Maneja interrupciones del flujo cuando se necesita input del usuario
    - Establece flags correctos para el sistema de interrupciones  
    - Genera mensajes apropiados según el contexto
    - Mantiene el contexto para continuar después de recibir el input
    """
    
    def __init__(self):
        super().__init__("RecopilarInputUsuario", timeout_seconds=30)
    
    def get_required_fields(self) -> List[str]:
        """✅ IMPLEMENTACIÓN REQUERIDA"""
        return ["messages"]
    
    def get_actor_description(self) -> str:
        """✅ IMPLEMENTACIÓN REQUERIDA - CORREGIDA"""
        return (
            "Maneja la recopilación de input del usuario estableciendo flags "
            "de interrupción y generando mensajes apropiados según el contexto"
        )
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """
        🎭 Ejecutar lógica principal de recopilación de input.
        
        Este nodo maneja el proceso de solicitar input del usuario y
        configurar las interrupciones apropiadas.
        """
        try:
            # Obtener contexto de la solicitud
            request_message = state.get("_request_message", "")
            input_context = state.get("_input_context", {})
            
            self.logger.info("🔄 === RECOPILANDO INPUT DEL USUARIO ===")
            self.logger.info(f"📨 Mensaje a mostrar: {request_message[:100]}...")
            self.logger.info(f"📋 Contexto: {input_context}")
            
            # Si no hay mensaje específico, generar uno genérico
            if not request_message:
                request_message = "Necesito más información para continuar. ¿Puedes ayudarme?"
                self.logger.warning("⚠️ No hay mensaje específico, usando genérico")
            
            # Configurar estado para interrumpir el flujo
            update_data = {
                **state,
                "messages": [AIMessage(content=request_message)],
                "awaiting_input": True,
                "requires_user_input": True,
                "_waiting_for_input": True,
                "_input_context": input_context,
                "_current_request": request_message
            }
            
            self.logger.info("⏸️ Configurando interrupción para esperar input del usuario")
            self.logger.info("✅ RecopilarInputUsuario completado - Esperando input")
            
            return Command(update=update_data)
            
        except Exception as e:
            self.logger.error(f"❌ Error en recopilar_input_usuario: {e}")
            
            # En caso de error, mostrar mensaje genérico
            return Command(update={
                **state,
                "messages": [AIMessage(content="Disculpa, necesito que me proporciones más información.")],
                "awaiting_input": True,
                "requires_user_input": True,
                "error_info": {
                    "node": "RecopilarInputUsuario",
                    "error": str(e)
                }
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
async def recopilar_input_usuario(state: Dict[str, Any]) -> Command:
    """
    Wrapper function para el nodo de recopilación de input del usuario.
    
    Args:
        state: Estado actual del grafo
        
    Returns:
        Command con las actualizaciones del estado para interrumpir el flujo
    """
    node = RecopilarInputUsuarioNode()
    
    try:
        node.logger.info(f"🔵 ESTADO ANTES DE RECOPILAR: awaiting_input={state.get('awaiting_input')}")
        
        result = await node.execute_with_monitoring(state)
        
        node.logger.info(f"🔴 RECOPILAR COMPLETADO: type={type(result)}")
        if hasattr(result, 'update'):
            node.logger.info(f"🔴 AWAITING_INPUT: {result.update.get('awaiting_input')}")
        
        return result
        
    except Exception as e:
        node.logger.error(f"❌ Error en recopilar_input_usuario wrapper: {e}")
        
        # Comando de recuperación
        return Command(update={
            **state,
            "messages": [AIMessage(content="Disculpa, hubo un problema. ¿Puedes intentar de nuevo?")],
            "awaiting_input": True,
            "error_info": {
                "node": "recopilar_input_usuario",
                "error": str(e)
            }
        })