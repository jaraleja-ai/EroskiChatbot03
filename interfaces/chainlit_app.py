# =====================================================
# interfaces/chainlit_app.py - Aplicación Chainlit con interrupciones
# =====================================================
"""
Aplicación Chainlit refactorizada con sistema de interrupciones.

Cambios principales:
- Usa graph.invoke() en lugar de astream()
- Maneja interrupciones automáticas en __interrupt__
- Sistema de continuación de flujos interrumpidos
- Estado persistente entre interrupciones
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

import chainlit as cl
from langchain_core.messages import HumanMessage, AIMessage


# Importaciones de la nueva arquitectura
from config.settings import get_settings
from config.logging_config import setup_logging
from graph import build_adaptive_graph, get_graph_builder, get_graph_metrics
from utils.crear_estado_inicial import (
    crear_estado_inicial, crear_estado_desde_mensaje, 
    obtener_resumen_estado, validar_integridad_estado
)
from utils.database import init_database, close_database
from workflow import get_workflow_manager, WorkflowType

class ChatbotSession:
    """
    Gestiona una sesión individual de chatbot con sistema de interrupciones.
    
    Responsabilidades:
    - Mantener estado de la conversación
    - Ejecutar workflows con interrupciones
    - Manejar continuaciones de flujos interrumpidos
    - Gestionar debugging y métricas
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.thread_id = f"thread_{session_id}"  # ID del hilo para interrupciones
        self.logger = logging.getLogger(f"Session.{session_id[:8]}")
        self.settings = get_settings()
        
        # ✅ CONFIGURACIÓN DE ESTADO PERSISTENTE
        self.config = {
            "configurable": {"thread_id": self.thread_id},
            "recursion_limit": 100  # Límite de recursión
        }
        
        # Estado de la sesión
        self.graph_state = None
        self.current_graph = None
        self.is_processing = False
        self.conversation_complete = False
        self.is_interrupted = False
        self.pending_user_input = False
        
        # ✅ NUEVO: Estado de usuario persistente
        self.user_data = {
            "nombre": None,
            "email": None,
            "numero_empleado": None,
            "nombre_confirmado": False,
            "email_confirmado": False,
            "datos_usuario_completos": False
        }
        
        # Métricas de la sesión
        self.start_time = datetime.now()
        self.message_count = 0
        self.error_count = 0
        self.interruption_count = 0
        
        self.logger.info(f"🆕 Nueva sesión iniciada: {session_id}")
    

    # ✅ NUEVO MÉTODO - Preservar datos de usuario
    def _preserve_user_data_in_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preservar datos de usuario en el estado entre ejecuciones.
        
        Args:
            state: Estado actual
            
        Returns:
            Estado con datos de usuario preservados
        """
        # Preservar datos existentes
        for key, value in self.user_data.items():
            if value is not None:
                state[key] = value
                self.logger.debug(f"🔄 Preservando {key}: {value}")
        
        return state

    # ✅ NUEVO MÉTODO - Extraer y guardar datos de usuario
    def _extract_and_save_user_data(self, state: Dict[str, Any]):
        """
        Extraer y guardar datos de usuario del estado.
        
        Args:
            state: Estado del grafo
        """
        user_fields = ["nombre", "email", "numero_empleado", 
                      "nombre_confirmado", "email_confirmado", "datos_usuario_completos"]
        
        for field in user_fields:
            if field in state and state[field] is not None:
                old_value = self.user_data.get(field)
                new_value = state[field]
                
                if old_value != new_value:
                    self.user_data[field] = new_value
                    self.logger.info(f"💾 Guardando {field}: {old_value} → {new_value}")
    
    # ✅ NUEVO MÉTODO - Extraer mensajes AI nuevos  
    def _extract_new_ai_messages(self, all_messages: List) -> List[AIMessage]:  # ✅ Retorna AIMessage
        """Extraer solo los mensajes AI nuevos desde el último mensaje del usuario"""
        try:
            from langchain_core.messages import HumanMessage, AIMessage
            
            # Encontrar el índice del último mensaje humano
            last_human_idx = -1
            for i in range(len(all_messages) - 1, -1, -1):
                if isinstance(all_messages[i], HumanMessage):
                    last_human_idx = i
                    break
            
            # Obtener mensajes AI después del último mensaje humano
            if last_human_idx >= 0:
                new_messages = all_messages[last_human_idx + 1:]
                return [msg for msg in new_messages if isinstance(msg, AIMessage)]  # ✅ Retorna AIMessage objects
            else:
                # Si no hay mensajes humanos, devolver todos los AI
                return [msg for msg in all_messages if isinstance(msg, AIMessage)]
                
        except Exception as e:
            self.logger.error(f"❌ Error extrayendo mensajes AI nuevos: {e}")
            return []

    async def initialize(self):
        """Inicializar la sesión"""
        try:
            self.logger.info("🔧 Inicializando sesión...")
            
            # Crear estado inicial
            self.graph_state = crear_estado_inicial(sesion_id=self.session_id)
            
            # Validar estado
            errores = validar_integridad_estado(self.graph_state)
            if errores:
                raise ValueError(f"Estado inicial inválido: {errores}")
            
            self.logger.info("✅ Sesión inicializada correctamente")
            
        except Exception as e:
            self.logger.error(f"❌ Error inicializando sesión: {e}")
            raise
    
    async def process_user_message(self, message: str) -> List[str]:
        """
        Procesar mensaje del usuario con sistema de interrupciones.
        
        Args:
            message: Mensaje del usuario
            
        Returns:
            Lista de respuestas del asistente
        """
        if self.is_processing:
            self.logger.warning("⚠️ Mensaje recibido mientras se procesa otro")
            return ["Un momento, estoy procesando tu mensaje anterior..."]
        
        self.is_processing = True
        self.message_count += 1
        
        try:
            self.logger.info(f"📩 Procesando mensaje #{self.message_count}: {message[:50]}...")
            
            # ✅ PRESERVAR DATOS DE USUARIO EN EL ESTADO
            if self.graph_state:
                self.graph_state = self._preserve_user_data_in_state(self.graph_state)
            
            # Agregar mensaje del usuario al estado
            user_message = HumanMessage(content=message)
            current_messages = self.graph_state.get("messages", [])
            self.graph_state["messages"] = current_messages + [user_message]
            
            # Si hay una interrupción pendiente, continuar el flujo
            if self.is_interrupted and self.pending_user_input:
                responses = await self._continue_interrupted_flow()
            else:
                # Iniciar nuevo flujo
                responses = await self._start_new_flow()
            
            self.logger.info(f"✅ Mensaje procesado - {len(responses)} respuestas generadas")
            return responses
            
        except Exception as e:
            self.error_count += 1
            self.logger.error(f"❌ Error procesando mensaje: {e}", exc_info=True)
            return [f"Ha ocurrido un error. Por favor, intenta de nuevo. (Error #{self.error_count})"]
        
        finally:
            self.is_processing = False
    
    async def _start_new_flow(self) -> List[str]:
        """Iniciar un nuevo flujo de conversación"""
        try:
            # Seleccionar y compilar grafo apropiado si no existe
            if not self.current_graph:
                self.current_graph = build_adaptive_graph(self.graph_state)
                self.logger.info("🔧 Grafo adaptativo compilado")
            
            # Reset de estado de interrupción
            self.is_interrupted = False
            self.pending_user_input = False
            
            # Ejecutar grafo con invoke (se detiene automáticamente en interrupciones)
            return await self._execute_graph_invoke()
            
        except Exception as e:
            self.logger.error(f"❌ Error iniciando nuevo flujo: {e}")
            raise
    
    # ✅ MODIFICAR MÉTODO EXISTENTE
    async def _continue_interrupted_flow(self) -> List[str]:
        """Continuar un flujo que fue interrumpido"""
        try:
            self.logger.info("🔄 Continuando flujo interrumpido...")
            
            # ✅ PRESERVAR DATOS ANTES DE CONTINUAR
            if self.graph_state:
                self.graph_state = self._preserve_user_data_in_state(self.graph_state)
            
            # Marcar que ya no estamos esperando input
            self.pending_user_input = False
            
            # ✅ CONTINUAR CON CONFIGURACIÓN PERSISTENTE (SIN ESTADO INICIAL)
            result = await self.current_graph.ainvoke(
                None,  # ✅ NO pasar estado, usar el persistido
                config=self.config
            )
            
            # ✅ EXTRAER Y GUARDAR DATOS
            self._extract_and_save_user_data(result)
            
            # Procesar resultado
            return await self._process_graph_result(result)
            
        except Exception as e:
            self.logger.error(f"❌ Error continuando flujo interrumpido: {e}")
            raise
    # ✅ MODIFICAR MÉTODO EXISTENTE
    async def _execute_graph_invoke(self) -> List[str]:
        """
        Ejecutar grafo usando ainvoke con configuración persistente.
        """
        responses = []
        
        try:
            self.logger.info("🚀 Ejecutando grafo con ainvoke...")
            
            # ✅ PRESERVAR DATOS ANTES DE EJECUTAR
            if self.graph_state:
                self.graph_state = self._preserve_user_data_in_state(self.graph_state)
            
            # ✅ EJECUTAR CON CONFIGURACIÓN PERSISTENTE
            result = await self.current_graph.ainvoke(
                self.graph_state, 
                config=self.config  # ✅ USAR CONFIG CON THREAD_ID
            )
            
            # ✅ EXTRAER Y GUARDAR DATOS DE USUARIO
            self._extract_and_save_user_data(result)
            
            # Verificar si el resultado indica una interrupción
            if self._is_interrupted_result(result):
                self.logger.info("⏸️ Flujo interrumpido - esperando input del usuario")
                self.is_interrupted = True
                self.pending_user_input = True
                self.interruption_count += 1
                
                # Obtener mensajes hasta el punto de interrupción
                responses = await self._extract_messages_before_interruption(result.get("messages", []))
                return responses
            
            # Procesar resultado normal
            responses = await self._process_graph_result(result)
            
            return responses
            
        except Exception as e:
            self.logger.error(f"❌ Error en ejecución del grafo: {e}")
            raise
    
    async def _process_graph_result(self, result: Dict[str, Any]) -> List[str]:
        """Procesar el resultado completo del grafo"""
        responses = []
        
        try:
            self.logger.info("📦 Procesando resultado del grafo")
            
            if not isinstance(result, dict):
                self.logger.warning(f"⚠️ Resultado no es dict: {type(result)}")
                return responses
            
            # Actualizar estado con el resultado
            self.graph_state.update(result)
            
            # Extraer mensajes AI para mostrar al usuario
            if "messages" in result:
                messages = result["messages"]
                # Obtener solo los mensajes nuevos (desde el último mensaje del usuario)
                new_messages = self._extract_new_ai_messages(messages)
                
                for msg in new_messages:
                    if isinstance(msg, AIMessage) and msg.content.strip():
                        responses.append(msg.content)
                        self.logger.debug(f"💬 Respuesta extraída: {msg.content[:50]}...")
            
            # Verificar estado de finalización
            self._check_flow_completion(result)
            
            return responses
            
        except Exception as e:
            self.logger.error(f"❌ Error procesando resultado del grafo: {e}")
            return []
    
    def _is_interrupted_result(self, result: Dict[str, Any]) -> bool:
        """
        Verificar si el resultado indica una interrupción.
        
        En LangGraph, las interrupciones se detectan por:
        1. Estado específico que indica necesidad de input
        2. Flags en el resultado
        3. Estado incompleto del flujo
        """
        try:
            # Verificar flags explícitos de interrupción
            if result.get("_interrupted", False):
                return True
            
            if result.get("requires_user_input", False):
                return True
            
            # Verificar si hay preguntas pendientes para el usuario
            if result.get("pending_questions"):
                return True
            
            # Verificar estado del workflow que indica interrupción
            workflow_state = result.get("workflow_state", {})
            if workflow_state.get("waiting_for_user", False):
                return True
            
            # Verificar si el flujo no está completo y no hay próximo nodo
            if not result.get("flujo_completado", False) and not result.get("next_node"):
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Error verificando interrupción: {e}")
            return False

            
        except Exception as e:
            self.logger.error(f"❌ Error extrayendo mensajes antes de interrupción: {e}")
            return ["Hubo un problema procesando tu solicitud. ¿Puedes proporcionar más detalles?"]
    
    async def _extract_messages_before_interruption(self, all_messages: List) -> List[str]:
        """Extraer mensajes generados antes de la interrupción"""
        responses = []
        
        try:
            # Usar directamente los mensajes pasados como parámetro
            new_messages = self._extract_new_ai_messages(all_messages)
            
            for msg in new_messages:
                if isinstance(msg, AIMessage) and msg.content.strip():
                    responses.append(msg.content)  # ✅ Agregar msg.content (string), no msg (objeto)
            
            # Agregar mensaje indicando que se necesita más información
            if not responses:
                responses.append("Necesito más información para continuar. ¿Puedes proporcionármela?")
            
            return responses  # ✅ Lista de strings
            
        except Exception as e:
            self.logger.error(f"❌ Error extrayendo mensajes antes de interrupción: {e}")
            return ["Hubo un problema procesando tu solicitud. ¿Puedes proporcionar más detalles?"]
    
    def _check_flow_completion(self, result: Dict[str, Any]):
        """Verificar si el flujo ha terminado"""
        self.conversation_complete = (
            result.get("flujo_completado", False) or
            result.get("escalar_a_supervisor", False) or
            result.get("incidencia_resuelta", False)
        )
        
        if self.conversation_complete:
            self.logger.info("🏁 Flujo completado")
            self.is_interrupted = False
            self.pending_user_input = False
    
    def get_session_summary(self) -> Dict[str, Any]:
        """Obtener resumen de la sesión"""
        duration = (datetime.now() - self.start_time).total_seconds()
        
        return {
            "session_id": self.session_id,
            "thread_id": self.thread_id,
            "duration_seconds": duration,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "interruption_count": self.interruption_count,
            "is_interrupted": self.is_interrupted,
            "pending_user_input": self.pending_user_input,
            "conversation_complete": self.conversation_complete,
            "state_summary": obtener_resumen_estado(self.graph_state) if self.graph_state else None
        }

class ChatbotManager:
    """
    Gestor principal del chatbot que coordina sesiones y configuración global.
    
    Responsabilidades:
    - Gestionar ciclo de vida de sesiones
    - Coordinar inicialización de servicios
    - Manejar debugging global
    - Proporcionar métricas agregadas
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.logger = logging.getLogger("ChatbotManager")
        self.sessions: Dict[str, ChatbotSession] = {}
        self.debug_mode = self.settings.app.debug_mode
        
        # Estadísticas globales
        self.total_sessions = 0
        self.total_messages = 0
        self.total_interruptions = 0  # Nuevo: contador global de interrupciones
        
    async def initialize_services(self):
        """Inicializar servicios globales del chatbot"""
        try:
            self.logger.info("🚀 Inicializando servicios del chatbot...")
            
            # Configurar logging
            setup_logging()
            
            # Inicializar base de datos
            self.logger.info("🗄️ Inicializando conexión a base de datos...")
            await init_database()
            
            # Verificar workflows
            workflow_manager = get_workflow_manager()
            workflows = workflow_manager.list_workflows()
            self.logger.info(f"🔧 Workflows disponibles: {workflows}")
            
            # Verificar configuración
            from config.settings import validate_environment
            if not validate_environment():
                raise RuntimeError("Configuración del entorno inválida")
            
            self.logger.info("✅ Servicios inicializados correctamente")
            
        except Exception as e:
            self.logger.error(f"❌ Error inicializando servicios: {e}")
            raise
    
    async def create_session(self, session_id: str) -> ChatbotSession:
        """Crear nueva sesión de chatbot"""
        try:
            self.logger.info(f"🆕 Creando nueva sesión: {session_id}")
            
            session = ChatbotSession(session_id)
            await session.initialize()
            
            self.sessions[session_id] = session
            self.total_sessions += 1
            
            self.logger.info(f"✅ Sesión creada exitosamente: {session_id}")
            return session
            
        except Exception as e:
            self.logger.error(f"❌ Error creando sesión {session_id}: {e}")
            raise
    
    def get_session(self, session_id: str) -> Optional[ChatbotSession]:
        """Obtener sesión existente"""
        return self.sessions.get(session_id)
    
    async def cleanup_session(self, session_id: str):
        """Limpiar sesión terminada"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            summary = session.get_session_summary()
            
            # Actualizar estadísticas globales
            self.total_interruptions += summary.get("interruption_count", 0)
            
            self.logger.info(f"🧹 Limpiando sesión {session_id}")
            self.logger.debug(f"📊 Resumen: {summary}")
            
            del self.sessions[session_id]
    
    async def cleanup_services(self):
        """Cleanup de servicios globales"""
        try:
            self.logger.info("🧹 Limpiando servicios...")
            
            # Limpiar todas las sesiones
            for session_id in list(self.sessions.keys()):
                await self.cleanup_session(session_id)
            
            # Cerrar conexiones de BD
            await close_database()
            
            self.logger.info("✅ Servicios limpiados")
            
        except Exception as e:
            self.logger.error(f"❌ Error en cleanup: {e}")
    
    async def handle_debug_command(self, command: str, session_id: str) -> str:
        """Manejar comandos de debug"""
        if not self.debug_mode:
            return "🐛 Debug mode no está activado"
        
        try:
            parts = command.split()
            cmd = parts[1] if len(parts) > 1 else ""
            
            if cmd == "state":
                session = self.get_session(session_id)
                if session and session.graph_state:
                    resumen = obtener_resumen_estado(session.graph_state)
                    interruption_info = {
                        "is_interrupted": session.is_interrupted,
                        "pending_user_input": session.pending_user_input,
                        "interruption_count": session.interruption_count
                    }
                    resumen["interruption_status"] = interruption_info
                    return f"```json\n{json.dumps(resumen, indent=2, default=str)}\n```"
                return "❌ No hay sesión activa"
            
            elif cmd == "metrics":
                metrics = get_graph_metrics()
                global_metrics = {
                    "total_sessions": self.total_sessions,
                    "total_interruptions": self.total_interruptions,
                    "active_sessions": len(self.sessions)
                }
                metrics["global_stats"] = global_metrics
                return f"```json\n{json.dumps(metrics, indent=2, default=str)}\n```"
            
            elif cmd == "sessions":
                sessions_info = {
                    "total_sessions": self.total_sessions,
                    "active_sessions": len(self.sessions),
                    "total_interruptions": self.total_interruptions,
                    "session_details": {}
                }
                
                for sid, session in self.sessions.items():
                    sessions_info["session_details"][sid] = {
                        "is_interrupted": session.is_interrupted,
                        "pending_user_input": session.pending_user_input,
                        "interruption_count": session.interruption_count,
                        "message_count": session.message_count
                    }
                
                return f"```json\n{json.dumps(sessions_info, indent=2)}\n```"
            
            elif cmd == "continue":
                session = self.get_session(session_id)
                if session and session.is_interrupted:
                    # Forzar continuación del flujo interrumpido
                    session.pending_user_input = False
                    return "🔄 Flujo interrumpido será continuado en el próximo mensaje"
                return "❌ No hay flujo interrumpido para continuar"
            
            elif cmd == "reset":
                session = self.get_session(session_id)
                if session:
                    await session.initialize()
                    return "🔄 Sesión reiniciada"
                return "❌ No hay sesión para reiniciar"
            
            elif cmd == "off":
                self.debug_mode = False
                return "🐛 Debug mode desactivado"
            
            else:
                return """🐛 **Comandos de debug disponibles:**
- `/debug state` - Ver estado actual e info de interrupciones
- `/debug metrics` - Ver métricas del sistema
- `/debug sessions` - Ver información de sesiones
- `/debug continue` - Forzar continuación de flujo interrumpido
- `/debug reset` - Reiniciar sesión actual
- `/debug off` - Desactivar debug mode"""
        
        except Exception as e:
            return f"❌ Error en comando debug: {e}"

# Instancia global del manager
chatbot_manager = ChatbotManager()

# =====================================================
# EVENTOS DE CHAINLIT (sin cambios significativos)
# =====================================================

@cl.on_chat_start
async def start():
    """Inicializar cuando se inicia el chat"""
    session_id = cl.user_session.get("id", f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    try:
        # Inicializar servicios si es necesario
        if not chatbot_manager.sessions:
            await chatbot_manager.initialize_services()
        
        # Crear sesión
        session = await chatbot_manager.create_session(session_id)
        
        # Guardar en sesión de Chainlit
        cl.user_session.set("chatbot_session", session)
        
        # Mensaje de bienvenida
        welcome_message = "¡Hola! Soy tu **Asistente de Incidencias** 🛠️\n\n"
        welcome_message += "Estoy aquí para ayudarte con cualquier problema técnico que tengas. "
        welcome_message += "¿En qué puedo asistirte hoy?"
        
        if chatbot_manager.debug_mode:
            welcome_message += f"\n\n🐛 **Debug Mode Activado** (Sesión: {session_id[:8]})\n"
            welcome_message += "**Sistema de interrupciones habilitado**\n"
            welcome_message += "Comandos: `/debug state`, `/debug metrics`, `/debug continue`, `/debug reset`, `/debug off`"
        
        await cl.Message(
            content=welcome_message,
            author="Asistente"
        ).send()
        
        session.logger.info("✅ Chat iniciado correctamente")
        
    except Exception as e:
        error_msg = f"❌ Error al inicializar el asistente: {str(e)}"
        await cl.Message(content=error_msg, author="Sistema").send()
        
        if hasattr(chatbot_manager, 'logger'):
            chatbot_manager.logger.error(f"❌ Error en inicio de chat: {e}")

@cl.on_message
async def main(message: cl.Message):
    """Manejar mensajes del usuario con soporte para interrupciones"""
    user_input = message.content.strip()
    
    # Obtener sesión
    session: ChatbotSession = cl.user_session.get("chatbot_session")
    if not session:
        await cl.Message(
            content="❌ Error: Sesión no encontrada. Por favor, recarga la página.",
            author="Sistema"
        ).send()
        return
    
    try:
        session.logger.info(f"📨 Mensaje recibido: {user_input[:50]}...")
        
        # Manejar comandos de debug
        if user_input.startswith("/debug"):
            debug_response = await chatbot_manager.handle_debug_command(user_input, session.session_id)
            await cl.Message(content=debug_response, author="Debug").send()
            return
        
        # Mostrar indicador de carga apropiado
        if session.is_interrupted and session.pending_user_input:
            loading_msg = cl.Message(content="🔄 Continuando el proceso...", author="Asistente")
        else:
            loading_msg = cl.Message(content="🤔 Procesando tu mensaje...", author="Asistente")
        
        await loading_msg.send()
        
        try:
            # Procesar mensaje
            responses = await session.process_user_message(user_input)
            
            # Remover indicador de carga
            await loading_msg.remove()
            
            # Enviar respuestas
            for i, response in enumerate(responses):
                if response.strip():  # Solo enviar respuestas no vacías
                    await cl.Message(
                        content=response,
                        author="Asistente"
                    ).send()
                    
                    # Pequeña pausa entre mensajes múltiples
                    if i < len(responses) - 1:
                        await asyncio.sleep(0.5)
            
            # Mostrar estado de interrupción en debug mode
            if chatbot_manager.debug_mode and session.is_interrupted:
                debug_info = f"⏸️ **Flujo interrumpido** - Esperando tu respuesta\n"
                debug_info += f"Interrupciones en esta sesión: {session.interruption_count}"
                
                await cl.Message(
                    content=debug_info,
                    author="Debug"
                ).send()
            
            # Verificar si la conversación ha terminado
            if session.conversation_complete:
                session.logger.info("🏁 Conversación completada")
                
                # Mensaje de finalización
                if not session.graph_state.get("escalar_a_supervisor", False):
                    await asyncio.sleep(1)
                    await cl.Message(
                        content="✨ **¿Hay algo más en lo que pueda ayudarte?**\n\nSi tienes otra consulta, simplemente escríbela.",
                        author="Asistente"
                    ).send()
        
        except Exception as e:
            # Remover indicador de carga en caso de error
            try:
                await loading_msg.remove()
            except:
                pass
            
            session.logger.error(f"❌ Error procesando mensaje: {e}", exc_info=True)
            
            error_message = "❌ Ha ocurrido un error procesando tu mensaje. "
            if chatbot_manager.debug_mode:
                error_message += f"Detalles: {str(e)}"
            else:
                error_message += "Por favor, intenta de nuevo o contacta a soporte si persiste."
            
            await cl.Message(content=error_message, author="Sistema").send()
        
    except Exception as e:
        # Error crítico
        await cl.Message(
            content=f"💥 Error crítico: {str(e)}. Por favor, recarga la página.",
            author="Sistema"
        ).send()
        
        if hasattr(session, 'logger'):
            session.logger.error(f"💥 Error crítico en main: {e}", exc_info=True)

@cl.on_stop
async def stop():
    """Cleanup cuando se detiene el chat"""
    session: ChatbotSession = cl.user_session.get("chatbot_session")
    
    if session:
        session.logger.info("🛑 Chat detenido por el usuario")
        
        # Obtener resumen final
        summary = session.get_session_summary()
        session.logger.info(f"📊 Resumen final: {summary}")
        
        # Cleanup de la sesión
        await chatbot_manager.cleanup_session(session.session_id)
    
    # Si no hay más sesiones activas, cleanup de servicios
    if not chatbot_manager.sessions:
        await chatbot_manager.cleanup_services()

# =====================================================
# CONFIGURACIÓN DE CHAINLIT (sin cambios)
# =====================================================

@cl.set_starters
async def set_starters():
    """Configurar mensajes de inicio sugeridos"""
    settings = get_settings()
    
    starters = [
        cl.Starter(
            label="🖥️ Problema con mi computadora",
            message="Hola, tengo un problema con mi computadora. Se está ejecutando muy lenta.",
            icon="/public/computer.svg",
        ),
        cl.Starter(
            label="📧 Problemas con email",
            message="No puedo acceder a mi correo electrónico corporativo.",
            icon="/public/email.svg",
        ),
        cl.Starter(
            label="🌐 Conexión a internet",
            message="Tengo problemas de conexión a internet en mi área de trabajo.",
            icon="/public/wifi.svg",
        ),
        cl.Starter(
            label="🔒 Olvide mi contraseña",
            message="He olvidado mi contraseña y no puedo acceder al sistema.",
            icon="/public/lock.svg",
        )
    ]
    
    return starters

@cl.set_chat_profiles
async def chat_profile():
    """Configurar perfiles de chat"""
    return [
        cl.ChatProfile(
            name="incidencias",
            markdown_description="Asistente para **incidencias técnicas** completo con escalación automática.",
            icon="🛠️",
        ),
        cl.ChatProfile(
            name="consultas",
            markdown_description="Asistente para **consultas rápidas** e información general.",
            icon="❓",
        ),
    ]

# =====================================================
# FUNCIÓN PARA EJECUTAR LA APLICACIÓN
# =====================================================

async def run_chainlit_app():
    """
    Función para ejecutar la aplicación Chainlit.
    Usada por el entry point principal.
    """
    try:
        chatbot_manager.logger.info("🚀 Aplicación Chainlit con interrupciones lista para ejecutar")
        return True
        
    except Exception as e:
        print(f"❌ Error configurando aplicación Chainlit: {e}")
        return False

# =====================================================
# CONFIGURACIÓN ADICIONAL
# =====================================================

try:
    import chainlit as cl
    
    if hasattr(cl, 'md') and hasattr(cl.md, 'ChatProfile'):
        cl.md.ChatProfile.markdown_description = """
# 🤖 Asistente de Incidencias Técnicas (Sistema de Interrupciones)

Bienvenido al sistema inteligente de soporte técnico con **sistema de interrupciones avanzado**. 

## ✨ Nuevas características:

- **🔄 Interrupciones inteligentes** - El sistema se detiene automáticamente cuando necesita más información
- **💬 Conversaciones contextuales** - Mantiene el contexto entre interrupciones  
- **⚡ Respuestas más precisas** - Hace preguntas específicas para resolver mejor tu problema

## ¿Cómo funciona?

1. **Cuéntame tu problema** - Describe qué está pasando
2. **Conversación interactiva** - Te haré preguntas específicas durante el proceso
3. **Resolución dirigida** - Cada interrupción nos acerca más a la solución
4. **Seguimiento personalizado** - Hasta que tu problema esté completamente resuelto

¡Empecemos! Describe tu problema y experimentarás un flujo más inteligente y dirigido 🚀
"""
    else:
        print("⚠️ API cl.md no disponible, usando configuración básica")
        
except Exception as e:
    print(f"⚠️ Error configurando perfil de chat: {e}")

if __name__ == "__main__":
    print("🚀 Para ejecutar la aplicación Chainlit, usa: chainlit run interfaces/chainlit_app.py")
    print("🔧 O desde el directorio raíz: python main.py")