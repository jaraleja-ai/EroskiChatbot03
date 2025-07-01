# interfaces/chainlit_app.py
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional

import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage

from config.settings import get_settings
from config.logging_config import setup_logging
from graph import build_graph
from utils.crear_estado_inicial import crear_estado_inicial
from utils.database import init_database, close_database

class ChatbotManager:
    """
    Gestor del chatbot refactorizado con la nueva arquitectura.
    
    Responsabilidades:
    - Gestionar el ciclo de vida del grafo
    - Manejar el estado de la conversación  
    - Procesar mensajes del usuario
    - Manejar debug y logging
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.graph = None
        self.graph_state = None
        self.logger = None
        self.waiting_for_user = False
        self._debug_mode = self.settings.app.debug_mode
    
    async def initialize(self):
        """Inicializar el manager con todas las dependencias"""
        try:
            # Configurar logging si no está configurado
            if not self.logger:
                setup_logging()
                self.logger = self._get_logger()
            
            self.logger.info("🚀 Inicializando ChatbotManager...")
            
            # Inicializar base de datos
            self.logger.info("🗄️ Inicializando conexión a base de datos...")
            await init_database()
            
            # Construir grafo
            self.logger.info("🔧 Construyendo grafo de conversación...")
            self.graph = build_graph()
            
            # Crear estado inicial
            self.logger.info("📋 Creando estado inicial...")
            self.graph_state = crear_estado_inicial()
            
            # Reset flags
            self.waiting_for_user = False
            
            self.logger.info("✅ ChatbotManager inicializado correctamente")
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"❌ Error en inicialización: {e}")
            raise
    
    def _get_logger(self):
        """Obtener logger para el manager"""
        import logging
        return logging.getLogger("ChatbotManager")
    
    async def process_message(self, user_message: str) -> Optional[str]:
        """
        Procesar mensaje del usuario con la nueva arquitectura.
        
        Args:
            user_message: Mensaje del usuario
            
        Returns:
            Mensaje de finalización o None si el flujo continúa
        """
        try:
            self.logger.info(f"📩 Procesando mensaje: {user_message[:50]}...")
            
            # Agregar mensaje del usuario al estado
            current_messages = self._get_current_messages()
            new_messages = current_messages + [HumanMessage(content=user_message)]
            
            # Actualizar estado
            self._update_state_messages(new_messages)
            
            # Debug info si está habilitado
            if self._debug_mode:
                await self._send_debug_info("Procesando Mensaje", {
                    "user_message": user_message,
                    "total_messages": len(new_messages),
                    "current_state": self._get_state_summary()
                })
            
            # Procesar con el grafo usando streaming
            mensaje_enviado = False
            
            async for event in self.graph.astream(self.graph_state):
                self.logger.debug(f"🔄 Evento del grafo: {list(event.keys())}")
                
                for node_name, node_output in event.items():
                    # Manejar eventos especiales
                    if node_name == "__end__":
                        self.logger.info("🏁 Flujo completado")
                        self.waiting_for_user = False
                        return None
                    
                    if node_name == "__interrupt__":
                        self.logger.info("⏸️ Grafo interrumpido - esperando input del usuario")
                        self.waiting_for_user = True
                        return None
                    
                    # Procesar salida del nodo
                    await self._process_node_output(node_name, node_output)
                    mensaje_enviado = True
            
            # Determinar estado final
            if self._is_conversation_complete():
                self.logger.info("✅ Conversación completada")
                self.waiting_for_user = False
            else:
                self.logger.info("⏸️ Esperando más input del usuario")
                self.waiting_for_user = True
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error en procesamiento: {e}", exc_info=True)
            
            if self._debug_mode:
                await self._send_debug_info("Error", {
                    "error": str(e), 
                    "type": type(e).__name__
                })
            
            return f"Error interno: {str(e)}. Por favor, intenta de nuevo."
    
    async def _process_node_output(self, node_name: str, node_output: Dict[str, Any]):
        """Procesar la salida de un nodo específico"""
        self.logger.info(f"📦 Procesando nodo: {node_name}")
        
        if not isinstance(node_output, dict):
            self.logger.warning(f"⚠️ Salida de nodo no es dict: {type(node_output)}")
            return
        
        # Actualizar estado con la salida del nodo
        self._update_state_from_node_output(node_output)
        
        # Enviar mensajes AI si los hay
        await self._send_ai_messages_from_output(node_output)
        
        # Verificar escalación
        if node_output.get("escalar_a_supervisor", False):
            self.logger.warning("🔼 Escalando a supervisor")
            self.waiting_for_user = False
        
        # Debug info del nodo si está habilitado
        if self._debug_mode:
            await self._send_debug_info(f"Nodo {node_name}", {
                "output_keys": list(node_output.keys()),
                "escalation": node_output.get("escalar_a_supervisor", False),
                "user_data_complete": node_output.get("datos_usuario_completos", False)
            })
    
    async def _send_ai_messages_from_output(self, node_output: Dict[str, Any]):
        """Enviar mensajes AI desde la salida del nodo"""
        if "messages" not in node_output:
            return
        
        messages = node_output["messages"]
        
        # Buscar el último mensaje AI
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                self.logger.info(f"💬 Enviando mensaje AI: {msg.content[:50]}...")
                await cl.Message(
                    content=msg.content,
                    author="Asistente"
                ).send()
                break
    
    def _get_current_messages(self):
        """Obtener mensajes actuales del estado"""
        return self._safe_get_attribute("messages", [])
    
    def _update_state_messages(self, new_messages):
        """Actualizar mensajes en el estado"""
        if isinstance(self.graph_state, dict):
            self.graph_state["messages"] = new_messages
        else:
            self.graph_state.messages = new_messages
    
    def _update_state_from_node_output(self, node_output: Dict[str, Any]):
        """Actualizar estado desde la salida del nodo"""
        if isinstance(self.graph_state, dict):
            self.graph_state.update(node_output)
        else:
            for key, value in node_output.items():
                setattr(self.graph_state, key, value)
    
    def _safe_get_attribute(self, attr: str, default=None):
        """Obtener atributo de forma segura del estado"""
        if isinstance(self.graph_state, dict):
            return self.graph_state.get(attr, default)
        else:
            return getattr(self.graph_state, attr, default)
    
    def _is_conversation_complete(self) -> bool:
        """Verificar si la conversación ha terminado"""
        escalation = self._safe_get_attribute("escalar_a_supervisor", False)
        if escalation:
            return True
        
        nombre_confirmado = self._safe_get_attribute("nombre_confirmado", False)
        email_confirmado = self._safe_get_attribute("email_confirmado", False)
        datos_completos = self._safe_get_attribute("datos_usuario_completos", False)
        tipo_incidencia = self._safe_get_attribute("tipo_incidencia", None)
        
        return (nombre_confirmado and email_confirmado and 
                datos_completos and tipo_incidencia)
    
    def _get_state_summary(self) -> Dict[str, Any]:
        """Obtener resumen del estado para debug"""
        return {
            "messages_count": len(self._safe_get_attribute("messages", [])),
            "intentos": self._safe_get_attribute("intentos", 0),
            "nombre": self._safe_get_attribute("nombre"),
            "email": self._safe_get_attribute("email"),
            "nombre_confirmado": self._safe_get_attribute("nombre_confirmado", False),
            "email_confirmado": self._safe_get_attribute("email_confirmado", False),
            "datos_completos": self._safe_get_attribute("datos_usuario_completos", False),
            "escalar": self._safe_get_attribute("escalar_a_supervisor", False)
        }
    
    async def _send_debug_info(self, info_type: str, data: Any):
        """Enviar información de debug al chat"""
        if not self._debug_mode:
            return
        
        try:
            if isinstance(data, dict):
                formatted_data = json.dumps(data, indent=2, default=str)
            else:
                formatted_data = str(data)
            
            debug_message = f"🐛 **DEBUG - {info_type}:**\n```json\n{formatted_data}\n```"
            
            await cl.Message(
                content=debug_message,
                author="Debug"
            ).send()
        except Exception as e:
            await cl.Message(
                content=f"🐛 **DEBUG ERROR:** {str(e)}",
                author="Debug"
            ).send()

# Instancia global del manager
chatbot_manager = ChatbotManager()

# ===========================================
# EVENTOS DE CHAINLIT
# ===========================================

@cl.on_chat_start
async def start():
    """Inicializar cuando se inicia el chat"""
    try:
        await chatbot_manager.initialize()
        
        settings = get_settings()
        
        welcome_message = (
            "¡Hola! Soy tu **Asistente de Incidencias** 🛠️\n\n"
            "Estoy aquí para ayudarte con cualquier problema técnico que tengas. "
            "¿En qué puedo asistirte hoy?"
        )
        
        if settings.app.debug_mode:
            welcome_message += (
                "\n\n🐛 **Modo Debug Activado**\n"
                "Comandos disponibles:\n"
                "- `/debug state` - Ver estado actual\n"
                "- `/debug off` - Desactivar debug\n"
                "- `/debug reset` - Reiniciar estado"
            )
        
        await cl.Message(
            content=welcome_message,
            author="Asistente"
        ).send()
        
        chatbot_manager.logger.info("✅ Sesión iniciada correctamente")
        
    except Exception as e:
        error_msg = "❌ Error al inicializar el asistente. Por favor, recarga la página."
        await cl.Message(content=error_msg, author="Sistema").send()
        
        if chatbot_manager.logger:
            chatbot_manager.logger.error(f"❌ Error en inicio: {e}")

@cl.on_message
async def main(message: cl.Message):
    """Manejar mensajes del usuario"""
    user_input = message.content
    
    try:
        chatbot_manager.logger.info(f"📨 Mensaje recibido: {user_input[:50]}...")
        
        # Comandos de debug especiales
        if user_input.startswith("/debug"):
            await _handle_debug_command(user_input)
            return
        
        # Mostrar indicador de carga
        loading_message = cl.Message(content="🤔 Procesando tu mensaje...", author="Asistente")
        await loading_message.send()
        
        # Procesar mensaje
        result = await chatbot_manager.process_message(user_input)
        
        # Eliminar indicador de carga
        await loading_message.remove()
        
        # Mostrar resultado final si es necesario
        if result:
            await cl.Message(content=result, author="Sistema").send()
        
        chatbot_manager.logger.info("✅ Mensaje procesado correctamente")
        
    except Exception as e:
        # Eliminar indicador de carga si existe
        try:
            await loading_message.remove()
        except:
            pass
        
        error_message = (
            f"❌ Error: {str(e)}\n\n"
            "Por favor, intenta de nuevo o usa `/debug state` para ver el estado actual."
        )
        await cl.Message(content=error_message, author="Sistema").send()
        
        if chatbot_manager.logger:
            chatbot_manager.logger.error(f"❌ Error en main handler: {e}", exc_info=True)

async def _handle_debug_command(command: str):
    """Manejar comandos especiales de debug"""
    settings = get_settings()
    
    if command == "/debug on":
        chatbot_manager._debug_mode = True
        await cl.Message(content="🐛 Debug mode activado", author="Sistema").send()
    
    elif command == "/debug off":
        chatbot_manager._debug_mode = False
        await cl.Message(content="🐛 Debug mode desactivado", author="Sistema").send()
    
    elif command == "/debug state":
        await chatbot_manager._send_debug_info("Estado Actual", {
            "graph_state": chatbot_manager._get_state_summary(),
            "waiting_for_user": chatbot_manager.waiting_for_user,
            "debug_mode": chatbot_manager._debug_mode
        })
    
    elif command == "/debug reset":
        await chatbot_manager.initialize()
        await cl.Message(content="🔄 Estado reiniciado", author="Sistema").send()

@cl.on_stop
async def stop():
    """Cleanup cuando se detiene el chat"""
    try:
        if chatbot_manager.logger:
            chatbot_manager.logger.info("🛑 Sesión de chat terminada")
        
        # Cerrar conexión a base de datos
        await close_database()
        
        if chatbot_manager.logger:
            chatbot_manager.logger.info("🗄️ Conexión a base de datos cerrada")
            
    except Exception as e:
        if chatbot_manager.logger:
            chatbot_manager.logger.error(f"❌ Error en cleanup: {e}")

# Función para ejecutar la aplicación
async def run_chainlit_app():
    """Ejecutar la aplicación de Chainlit"""
    settings = get_settings()
    
    # Configurar e inicializar
    setup_logging()
    
    # Chainlit se ejecuta automáticamente cuando se importa
    # Esta función es para compatibilidad con el entry point principal