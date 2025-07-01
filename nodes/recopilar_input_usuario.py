# =====================================================
# nodes/recopilar_input_usuario.py - Nodo para recopilar input del usuario
# =====================================================
from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage
from langgraph.types import Command

from .base_node import BaseNode, NodeExecutionResult
from utils import generate_natural_message

class RecopilarInputUsuarioNode(BaseNode):
    """
    Nodo especializado para manejar recopilación de input del usuario.
    
    Este nodo:
    - Maneja interrupciones del flujo cuando se necesita input del usuario
    - Establece flags correctos para el sistema de interrupciones
    - Genera mensajes apropiados según el contexto
    - Mantiene el contexto para continuar después de recibir el input
    - Proporciona una transición limpia desde "__interrupt__" hacia nodos válidos
    
    Funcionalidades:
    - Detección automática del tipo de input requerido
    - Generación de mensajes contextuales
    - Configuración de flags de interrupción
    - Mantenimiento del estado para continuación
    """
    
    def __init__(self):
        super().__init__("RecopilarInputUsuario", timeout_seconds=30)
    
    def get_required_fields(self) -> List[str]:
        """Campos requeridos en el estado"""
        return ["messages"]
    
    def get_node_description(self) -> str:
        """Descripción del nodo"""
        return (
            "Maneja la recopilación de input del usuario estableciendo flags "
            "de interrupción y generando mensajes apropiados según el contexto"
        )
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """
        Ejecutar lógica principal de recopilación de input.
        
        Este nodo siempre establece flags de interrupción y genera
        un mensaje apropiado para solicitar input del usuario.
        """
        
        try:
            self.logger.info("⏸️ Iniciando recopilación de input del usuario")
            
            # Obtener contexto de lo que se necesita
            awaiting_context = self._safe_get_awaiting_context(state)
            current_messages = state.get("messages", [])
            
            # Generar mensaje apropiado basado en el contexto
            user_message = await self._generate_input_request_message(awaiting_context, state)
            
            # Preparar el estado para la interrupción
            update_data = {
                # Mantener mensajes existentes y agregar nuevo
                "messages": [AIMessage(content=user_message)],
                
                # Flags CRÍTICOS para el sistema de interrupciones
                "requires_user_input": True,
                "workflow_state": {
                    "waiting_for_user": True,
                    "awaiting_context": awaiting_context,
                    "last_node": "recopilar_input_usuario",
                    "resume_node": awaiting_context.get("resume_node", "identificar_usuario"),
                    "original_step": state.get("current_step", "unknown")
                },
                
                # Información para debugging y continuación
                "interruption_reason": awaiting_context.get("reason", "input_required"),
                "pending_questions": [user_message],
                
                # Limpiar flag original pero mantener contexto
                "awaiting_input": False,  # Lo manejamos con requires_user_input
                
                # Información de continuación del flujo
                "next_action_after_input": awaiting_context.get("next_action", "process_input"),
                "input_type": awaiting_context.get("type", "general"),
                
                # Incrementar contador de interrupciones
                "interruption_count": state.get("interruption_count", 0) + 1
            }
            
            self.logger.info(f"⏸️ Input solicitado: {user_message[:50]}...")
            self.logger.debug(f"🔧 Contexto de interrupción: {awaiting_context}")
            
            return Command(update=update_data)
            
        except Exception as e:
            self.logger.error(f"❌ Error en recopilar_input_usuario: {e}")
            # Fallback en caso de error
            return await self._create_fallback_response(state)
    
    def _safe_get_awaiting_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Obtener contexto de forma segura, proporcionando defaults apropiados.
        """
        try:
            # Intentar obtener contexto específico
            awaiting_context = state.get("awaiting_context", {})
            
            if awaiting_context:
                self.logger.debug(f"📋 Contexto específico encontrado: {awaiting_context}")
                return awaiting_context
            
            # Si no hay contexto específico, inferir del estado actual
            inferred_context = self._infer_context_from_state(state)
            self.logger.debug(f"🔍 Contexto inferido: {inferred_context}")
            
            return inferred_context
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo contexto: {e}")
            return self._get_default_context()
    
    def _infer_context_from_state(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inferir contexto basado en el estado actual cuando no hay contexto explícito.
        """
        
        # Verificar qué datos faltan para inferir el tipo de input necesario
        nombre = state.get("nombre")
        email = state.get("email")
        current_step = state.get("current_step", "")
        
        # Contexto para identificación de usuario
        if not nombre and not email:
            return {
                "type": "user_identification",
                "reason": "Necesito tu nombre y email para identificarte correctamente",
                "resume_node": "identificar_usuario",
                "fields_needed": ["nombre", "email"]
            }
        
        elif not nombre:
            return {
                "type": "user_name",
                "reason": "Necesito tu nombre completo para continuar",
                "resume_node": "identificar_usuario",
                "fields_needed": ["nombre"]
            }
        
        elif not email:
            return {
                "type": "user_email", 
                "reason": "Necesito tu email para verificar tu identidad",
                "resume_node": "identificar_usuario",
                "fields_needed": ["email"]
            }
        
        # Contexto para descripción de problema
        elif "problema" in current_step.lower() or not state.get("descripcion_problema"):
            return {
                "type": "problem_description",
                "reason": "Necesito que describas el problema con más detalle",
                "resume_node": "analizar_problema",
                "fields_needed": ["descripcion_problema"]
            }
        
        # Contexto para confirmación
        elif "confirma" in current_step.lower():
            return {
                "type": "confirmation",
                "reason": "Necesito que confirmes la información proporcionada",
                "resume_node": "procesar_confirmacion",
                "fields_needed": ["confirmacion"]
            }
        
        # Contexto general por defecto
        else:
            return self._get_default_context()
    
    def _get_default_context(self) -> Dict[str, Any]:
        """Contexto por defecto cuando no se puede inferir"""
        return {
            "type": "general",
            "reason": "Necesito más información para continuar ayudándote",
            "resume_node": "identificar_usuario",
            "fields_needed": ["informacion_adicional"]
        }
    
    async def _generate_input_request_message(
        self, 
        awaiting_context: Dict[str, Any], 
        state: Dict[str, Any]
    ) -> str:
        """
        Generar mensaje apropiado para solicitar input del usuario.
        """
        
        input_type = awaiting_context.get("type", "general")
        reason = awaiting_context.get("reason", "")
        fields_needed = awaiting_context.get("fields_needed", [])
        
        try:
            # Intentar generar mensaje usando plantillas naturales
            if hasattr(generate_natural_message, '__call__'):
                template_data = {
                    "reason": reason,
                    "fields": ", ".join(fields_needed),
                    "context": awaiting_context
                }
                message = await generate_natural_message(f"solicitar_{input_type}", template_data)
                
                if message and message.strip():
                    return message
                    
        except Exception as e:
            self.logger.warning(f"⚠️ Error generando mensaje natural: {e}")
        
        # Fallback a mensajes predefinidos
        return self._get_predefined_message(input_type, awaiting_context, state)
    
    def _get_predefined_message(
        self, 
        input_type: str, 
        awaiting_context: Dict[str, Any], 
        state: Dict[str, Any]
    ) -> str:
        """
        Obtener mensaje predefinido según el tipo de input.
        """
        
        reason = awaiting_context.get("reason", "")
        
        # Mensajes predefinidos por tipo
        message_templates = {
            "user_identification": (
                "Para ayudarte mejor, necesito que me proporciones:\n"
                "• Tu **nombre completo**\n"
                "• Tu **email corporativo**\n\n"
                "Puedes escribir ambos en un solo mensaje. 😊"
            ),
            
            "user_name": (
                "¿Podrías decirme tu **nombre completo**? "
                "Esto me ayudará a identificarte en el sistema."
            ),
            
            "user_email": (
                "Necesito tu **email corporativo** para verificar tu identidad "
                "y asegurarme de darte la mejor ayuda posible."
            ),
            
            "problem_description": (
                "¿Podrías describir el problema con más detalle? "
                "Cualquier información adicional me ayudará a encontrar la mejor solución:\n\n"
                "• ¿Cuándo empezó a ocurrir?\n"
                "• ¿Qué estabas haciendo cuando pasó?\n"
                "• ¿Has intentado algo para solucionarlo?"
            ),
            
            "hardware_info": (
                "Para resolver tu problema de hardware, necesito conocer:\n"
                "• **Modelo y marca** del equipo\n"
                "• **Qué componente** está fallando\n"
                "• **Mensajes de error** si los hay"
            ),
            
            "software_info": (
                "Para resolver el problema de software, ayúdame con:\n"
                "• **¿Qué aplicación** está causando problemas?\n"
                "• **¿Cuándo empezó** a ocurrir?\n"
                "• **¿Qué mensaje de error** aparece?"
            ),
            
            "network_info": (
                "Para resolver el problema de conectividad:\n"
                "• ¿El problema es **solo en tu equipo** o afecta otros dispositivos?\n"
                "• ¿Puedes **acceder a internet** desde otros dispositivos?\n"
                "• ¿Cuándo empezó el problema?"
            ),
            
            "confirmation": (
                "Por favor, confirma si la información es correcta:\n"
                f"✅ **Sí, es correcto**\n"
                f"❌ **No, hay errores**\n\n"
                f"O escribe las correcciones que necesites hacer."
            ),
            
            "clarification": (
                f"Necesito aclarar algunos detalles. {reason}\n\n"
                f"¿Puedes proporcionar más información?"
            ),
            
            "general": "Necesito más información para continuar ayudándote. ¿Puedes darme más detalles?"
        }
        
        # Seleccionar mensaje apropiado
        message = message_templates.get(input_type, message_templates["general"])
        
        # Agregar razón específica si está disponible y no está ya incluida
        if reason and reason not in message:
            message = f"{reason}\n\n{message}"
        
        return message
    
    async def _create_fallback_response(self, state: Dict[str, Any]) -> Command:
        """
        Crear respuesta de fallback en caso de error.
        """
        
        fallback_message = (
            "Necesito más información para continuar. "
            "¿Puedes proporcionarme los detalles que faltan?"
        )
        
        return Command(update=self.create_message_update(
            fallback_message,
            {
                "requires_user_input": True,
                "workflow_state": {
                    "waiting_for_user": True,
                    "last_node": "recopilar_input_usuario",
                    "resume_node": "identificar_usuario",
                    "error_fallback": True
                },
                "pending_questions": [fallback_message],
                "awaiting_input": False,
                "interruption_reason": "fallback_error"
            }
        ))
    
    def should_continue_after_input(self, state: Dict[str, Any]) -> bool:
        """
        Determinar si el flujo debe continuar después de recibir input.
        
        Este método puede ser usado por otros nodos para verificar
        si hay input pendiente de procesar.
        """
        
        workflow_state = state.get("workflow_state", {})
        return (
            not workflow_state.get("waiting_for_user", False) and
            state.get("requires_user_input", False) == False
        )
    
    def get_resume_node(self, state: Dict[str, Any]) -> str:
        """
        Obtener el nodo donde debe continuar el flujo después del input.
        """
        
        workflow_state = state.get("workflow_state", {})
        return workflow_state.get("resume_node", "identificar_usuario")
    
    def get_execution_metrics(self) -> Dict[str, Any]:
        """
        Obtener métricas específicas de este nodo.
        """
        base_metrics = super().get_execution_metrics()
        
        # Agregar métricas específicas de interrupciones
        base_metrics.update({
            "node_type": "interruption_handler",
            "purpose": "user_input_collection",
            "interruption_patterns": [
                "awaiting_input",
                "requires_user_input", 
                "workflow_state.waiting_for_user"
            ]
        })
        
        return base_metrics


# =====================================================
# Función wrapper para usar con LangGraph
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
    return await node.execute_with_monitoring(state)


# =====================================================
# Nodo de continuación (opcional)
# =====================================================
class ProcesarInputRecibidoNode(BaseNode):
    """
    Nodo opcional para procesar input recibido después de una interrupción.
    
    Este nodo puede ser usado para:
    - Validar el input recibido
    - Extraer datos específicos
    - Determinar el próximo paso en el flujo
    - Limpiar flags de interrupción
    """
    
    def __init__(self):
        super().__init__("ProcesarInputRecibido", timeout_seconds=15)
    
    def get_required_fields(self) -> List[str]:
        return ["messages", "workflow_state"]
    
    def get_node_description(self) -> str:
        return (
            "Procesa input recibido del usuario después de una interrupción "
            "y determina cómo continuar el flujo"
        )
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """
        Procesar input recibido y limpiar flags de interrupción.
        """
        
        try:
            workflow_state = state.get("workflow_state", {})
            awaiting_context = workflow_state.get("awaiting_context", {})
            resume_node = workflow_state.get("resume_node", "identificar_usuario")
            
            # Obtener último mensaje del usuario
            last_user_message = self.get_last_user_message(state)
            
            self.logger.info(f"🔄 Procesando input recibido: {last_user_message[:50]}...")
            
            # Procesar input según el contexto
            processed_data = await self._process_user_input(last_user_message, awaiting_context)
            
            # Limpiar flags de interrupción y establecer próximo paso
            update_data = {
                "requires_user_input": False,
                "workflow_state": {
                    **workflow_state,
                    "waiting_for_user": False,
                    "awaiting_context": {},
                    "input_processed": True
                },
                "_next_actor": resume_node,  # Señal para el router
                **processed_data
            }
            
            self.logger.info(f"✅ Input procesado, continuando en: {resume_node}")
            
            return Command(update=update_data)
            
        except Exception as e:
            self.logger.error(f"❌ Error procesando input: {e}")
            return await self.handle_error(e, state)
    
    async def _process_user_input(
        self, 
        user_input: str, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Procesar el input del usuario según el contexto.
        """
        
        input_type = context.get("type", "general")
        
        if input_type == "user_identification":
            return await self._extract_user_identification(user_input)
        
        elif input_type in ["user_name", "user_email"]:
            return await self._extract_specific_user_field(user_input, input_type)
        
        elif input_type == "problem_description":
            return {
                "descripcion_problema": user_input,
                "problema_detallado": True
            }
        
        elif input_type == "confirmation":
            return await self._process_confirmation(user_input)
        
        else:
            # Input general
            return {
                "informacion_adicional": user_input,
                "input_recibido": True
            }
    
    async def _extract_user_identification(self, user_input: str) -> Dict[str, Any]:
        """Extraer información de identificación del usuario."""
        
        # Aquí podrías usar la función extraer_datos_usuario de tus utils
        try:
            from utils import extraer_datos_usuario
            datos = await extraer_datos_usuario(user_input)
            
            return {
                "nombre": datos.nombre if hasattr(datos, 'nombre') else None,
                "email": datos.email if hasattr(datos, 'email') else None,
                "datos_extraidos": True
            }
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error extrayendo datos: {e}")
            
            # Fallback simple con regex
            import re
            
            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', user_input)
            email = email_match.group(0) if email_match else None
            
            # El resto se considera nombre (simplificado)
            name = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '', user_input).strip()
            name = re.sub(r'\s+', ' ', name) if name else None
            
            return {
                "nombre": name,
                "email": email,
                "datos_extraidos": True
            }
    
    async def _extract_specific_user_field(self, user_input: str, field_type: str) -> Dict[str, Any]:
        """Extraer campo específico del usuario."""
        
        if field_type == "user_email":
            import re
            email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', user_input)
            return {
                "email": email_match.group(0) if email_match else user_input.strip(),
                "email_actualizado": True
            }
        
        elif field_type == "user_name":
            return {
                "nombre": user_input.strip(),
                "nombre_actualizado": True
            }
        
        return {}
    
    async def _process_confirmation(self, user_input: str) -> Dict[str, Any]:
        """Procesar confirmación del usuario."""
        
        user_input_lower = user_input.lower().strip()
        
        # Detectar confirmación positiva
        positive_indicators = ["si", "sí", "yes", "correcto", "ok", "vale", "confirmo", "1", "✅"]
        negative_indicators = ["no", "incorrecto", "mal", "error", "2", "❌"]
        
        if any(indicator in user_input_lower for indicator in positive_indicators):
            return {
                "confirmacion": True,
                "datos_confirmados": True
            }
        elif any(indicator in user_input_lower for indicator in negative_indicators):
            return {
                "confirmacion": False,
                "datos_rechazados": True
            }
        else:
            return {
                "confirmacion": None,
                "respuesta_ambigua": True,
                "respuesta_original": user_input
            }


async def procesar_input_recibido(state: Dict[str, Any]) -> Command:
    """
    Wrapper function para el nodo de procesamiento de input.
    
    Args:
        state: Estado actual del grafo
        
    Returns:
        Command con el input procesado y flags limpiados
    """
    node = ProcesarInputRecibidoNode()
    return await node.execute_with_monitoring(state)