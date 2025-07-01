# =====================================================
# nodes/base_node.py - Clase base para todos los nodos
# =====================================================
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
import logging
from datetime import datetime
import asyncio

from config.settings import get_settings

class NodeExecutionResult:
    """
    Constantes para resultados de ejecución de nodos.
    Estandariza los códigos de resultado para mejor control de flujo.
    """
    
    # Resultados exitosos
    SUCCESS = "success"
    CONTINUE = "continue"
    REPEAT = "repeat"
    
    # Resultados que requieren acción del usuario
    AWAIT_USER_INPUT = "await_input"
    AWAIT_CONFIRMATION = "await_confirmation"
    
    # Resultados de control de flujo
    ESCALATE = "escalate"
    REDIRECT = "redirect"
    
    # Resultados finales
    COMPLETE = "complete"
    ERROR = "error"

class BaseNode(ABC):
    """
    Clase base abstracta para todos los nodos del grafo de LangGraph.
    
    Proporciona funcionalidad común como:
    - Logging estandarizado con contexto
    - Validación automática de estado
    - Manejo centralizado de errores
    - Patrones de actualización consistentes
    - Métricas y monitoreo básico
    - Timeout management
    """
    
    def __init__(self, name: str, timeout_seconds: Optional[int] = None):
        """
        Inicializar nodo base.
        
        Args:
            name: Nombre único del nodo
            timeout_seconds: Timeout opcional para la ejecución del nodo
        """
        self.name = name
        self.logger = logging.getLogger(f"Node.{name}")
        self.settings = get_settings()
        self.timeout_seconds = timeout_seconds or 30
        
        # Contadores para métricas
        self._execution_count = 0
        self._error_count = 0
        self._last_execution_time = None
        
        self.logger.debug(f"🔧 Nodo {name} inicializado")
    
    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> Command:
        """
        Lógica principal del nodo - debe ser implementada por cada nodo hijo.
        
        Args:
            state: Estado actual del grafo
            
        Returns:
            Command: Comando con las actualizaciones del estado
            
        Raises:
            NotImplementedError: Si no se implementa en la clase hija
        """
        pass
    
    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """
        Campos requeridos en el estado para que este nodo funcione correctamente.
        
        Returns:
            Lista de nombres de campos requeridos en el estado
        """
        pass
    
    @abstractmethod
    def get_node_description(self) -> str:
        """
        Descripción del propósito y funcionamiento del nodo.
        
        Returns:
            Descripción human-readable del nodo
        """
        pass
    
    async def execute_with_monitoring(self, state: Dict[str, Any]) -> Command:
        """
        Wrapper que ejecuta el nodo con monitoreo, timeout y manejo de errores.
        
        Args:
            state: Estado actual del grafo
            
        Returns:
            Command con resultado de la ejecución
        """
        start_time = datetime.now()
        self._execution_count += 1
        
        try:
            self.log_execution_start(state)
            
            # Validar estado antes de ejecutar
            if not self.validate_state(state):
                return await self.handle_error(
                    ValueError(f"Estado inválido para nodo {self.name}"), 
                    state
                )
            
            # Ejecutar con timeout
            try:
                result = await asyncio.wait_for(
                    self.execute(state), 
                    timeout=self.timeout_seconds
                )
            except asyncio.TimeoutError:
                raise TimeoutError(f"Nodo {self.name} excedió timeout de {self.timeout_seconds}s")
            
            # Validar resultado
            if not isinstance(result, Command):
                raise ValueError(f"Nodo {self.name} debe retornar Command, retornó {type(result)}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            self._last_execution_time = execution_time
            
            self.log_execution_end(NodeExecutionResult.SUCCESS, execution_time)
            return result
            
        except Exception as e:
            self._error_count += 1
            execution_time = (datetime.now() - start_time).total_seconds()
            self.log_execution_end(NodeExecutionResult.ERROR, execution_time)
            return await self.handle_error(e, state)
    
    def validate_state(self, state: Dict[str, Any]) -> bool:
        """
        Validar que el estado tiene todos los campos requeridos.
        
        Args:
            state: Estado a validar
            
        Returns:
            True si el estado es válido, False en caso contrario
        """
        required_fields = self.get_required_fields()
        missing_fields = []
        
        for field in required_fields:
            if field not in state:
                missing_fields.append(field)
            elif state[field] is None and field in ["messages"]:  # Campos críticos
                missing_fields.append(f"{field} (None)")
        
        if missing_fields:
            self.logger.error(f"❌ Campos faltantes/inválidos: {missing_fields}")
            return False
        
        self.logger.debug(f"✅ Estado válido para nodo {self.name}")
        return True
    
    def should_escalate(self, state: Dict[str, Any], field_name: str = "intentos") -> bool:
        """
        Determinar si el nodo debe escalar por múltiples intentos.
        
        Args:
            state: Estado actual
            field_name: Campo de intentos a verificar
            
        Returns:
            True si debe escalar, False en caso contrario
        """
        current_attempts = state.get(field_name, 0)
        max_attempts = self._get_max_attempts_for_field(field_name)
        
        should_escalate = current_attempts >= max_attempts
        
        if should_escalate:
            self.logger.warning(
                f"⚠️ Escalando por múltiples intentos: {current_attempts}/{max_attempts}"
            )
        
        return should_escalate
    
    def _get_max_attempts_for_field(self, field_name: str) -> int:
        """Obtener máximo de intentos según el campo"""
        max_attempts_map = {
            "intentos": self.settings.app.max_intentos_identificacion,
            "intentos_incidencia": self.settings.app.max_intentos_incidencia,
        }
        return max_attempts_map.get(field_name, 5)
    
    def increment_attempts(self, state: Dict[str, Any], field_name: str = "intentos") -> int:
        """
        Incrementar contador de intentos.
        
        Args:
            state: Estado actual
            field_name: Campo de intentos a incrementar
            
        Returns:
            Nuevo número de intentos
        """
        current_attempts = state.get(field_name, 0)
        new_attempts = current_attempts + 1
        self.logger.debug(f"🔄 Incrementando {field_name}: {new_attempts}")
        return new_attempts
    
    def create_message_update(
        self, 
        content: str, 
        additional_updates: Optional[Dict[str, Any]] = None,
        message_type: str = "ai"
    ) -> Dict[str, Any]:
        """
        Helper para crear actualizaciones con mensajes de forma consistente.
        
        Args:
            content: Contenido del mensaje a agregar
            additional_updates: Actualizaciones adicionales al estado
            message_type: Tipo de mensaje ("ai" o "human")
            
        Returns:
            Diccionario con la actualización completa
        """
        # Crear mensaje según el tipo
        if message_type.lower() == "ai":
            message = AIMessage(content=content)
        else:
            message = HumanMessage(content=content)
        
        update = {"messages": [message]}
        
        if additional_updates:
            update.update(additional_updates)
        
        self.logger.debug(f"💬 Creando mensaje ({message_type}): {content[:50]}...")
        return update
    
    async def handle_error(self, error: Exception, state: Dict[str, Any]) -> Command:
        """
        Manejo centralizado de errores para todos los nodos.
        
        Args:
            error: Excepción ocurrida
            state: Estado actual cuando ocurrió el error
            
        Returns:
            Command que escala a supervisor con información del error
        """
        error_id = f"{self.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        self.logger.error(
            f"❌ Error en nodo {self.name} (ID: {error_id}): {error}", 
            exc_info=True
        )
        
        # Mensaje de error amigable para el usuario
        if isinstance(error, TimeoutError):
            error_message = (
                "El procesamiento está tomando más tiempo del esperado. "
                "Un supervisor revisará tu consulta para asegurar una respuesta rápida."
            )
        elif isinstance(error, ValueError):
            error_message = (
                "Hemos detectado un problema con la información proporcionada. "
                "Un supervisor revisará tu caso para ayudarte mejor."
            )
        else:
            error_message = (
                "Ha ocurrido un error técnico inesperado. "
                "Tu consulta será derivada a un supervisor para revisión inmediata."
            )
        
        return Command(update=self.create_message_update(
            error_message,
            {
                "escalar_a_supervisor": True,
                "razon_escalacion": f"Error técnico en {self.name}",
                "error_info": {
                    "error_id": error_id,
                    "node": self.name,
                    "error_type": type(error).__name__,
                    "error_message": str(error),
                    "timestamp": datetime.now().isoformat()
                }
            }
        ))
    
    def log_execution_start(self, state: Dict[str, Any]):
        """Log detallado del inicio de ejecución del nodo"""
        messages_count = len(state.get("messages", []))
        intentos = state.get("intentos", 0)
        session_id = state.get("sesion_id", "unknown")
        
        self.logger.info(f"🔍 === INICIANDO {self.name.upper()} ===")
        self.logger.info(f"📊 Sesión: {session_id}, Mensajes: {messages_count}, Intentos: {intentos}")
        self.logger.debug(f"📋 Descripción: {self.get_node_description()}")
    
    def log_execution_end(self, result_type: str, execution_time: float):
        """Log del final de ejecución del nodo"""
        self.logger.info(
            f"✅ {self.name} completado - Resultado: {result_type} "
            f"({execution_time:.2f}s)"
        )
        
        if execution_time > 5.0:  # Warn sobre ejecuciones lentas
            self.logger.warning(f"⚠️ Ejecución lenta detectada: {execution_time:.2f}s")
    
    def get_last_user_message(self, state: Dict[str, Any]) -> str:
        """
        Obtener el último mensaje del usuario del estado.
        
        Args:
            state: Estado actual del grafo
            
        Returns:
            Contenido del último mensaje del usuario
        """
        try:
            messages = state.get("messages", [])
            
            # Buscar el último mensaje humano en orden inverso
            for message in reversed(messages):
                # Verificar si es un mensaje humano (varios tipos posibles)
                if hasattr(message, 'type') and message.type == "human":
                    return message.content.strip()
                elif hasattr(message, '__class__') and 'Human' in message.__class__.__name__:
                    return message.content.strip()
                elif str(type(message)) == "<class 'langchain_core.messages.human.HumanMessage'>":
                    return message.content.strip()
            
            # Si no encontramos ningún mensaje humano
            self.logger.warning("⚠️ No se encontró ningún mensaje del usuario")
            return ""
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo último mensaje del usuario: {e}")
            return ""
    
    def get_conversation_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extraer contexto relevante de la conversación.
        
        Args:
            state: Estado actual
            
        Returns:
            Diccionario con contexto relevante
        """
        messages = state.get("messages", [])
        
        return {
            "total_messages": len(messages),
            "user_messages": len([m for m in messages if isinstance(m, HumanMessage)]),
            "ai_messages": len([m for m in messages if isinstance(m, AIMessage)]),
            "last_user_message": self.get_last_user_message(state),
            "conversation_length": sum(len(m.content) for m in messages),
            "session_id": state.get("sesion_id"),
            "timestamp": datetime.now().isoformat()
        }
    
    def transition_to(self, state: Dict[str, Any], next_step: str, awaiting_input: bool = False, **updates) -> Command:
        """
        Helper para crear transiciones limpias entre pasos del workflow.
        
        Args:
            state: Estado actual del grafo
            next_step: Paso siguiente del workflow
            awaiting_input: Si el nodo debe esperar input del usuario
            **updates: Actualizaciones adicionales al estado
            
        Returns:
            Command con la transición configurada
        """
        update_data = {
            "current_step": next_step,
            "awaiting_input": awaiting_input,
            "flow_history": self._get_updated_history(state, next_step),
            **updates
        }
        
        self.logger.info(f"🔄 Transición: {self.name} → {next_step}")
        if awaiting_input:
            self.logger.debug(f"⏸️ Esperando input del usuario en paso: {next_step}")
        
        return Command(update=update_data)

    def wait_for_input(self, state: Dict[str, Any], next_step: str, message: str, next_action: str = None) -> Command:
        """
        Helper para esperar input del usuario con mensaje específico.
        
        Args:
            state: Estado actual del grafo
            next_step: Paso del workflow donde esperar
            message: Mensaje a mostrar al usuario
            next_action: Acción específica a realizar con la respuesta
            
        Returns:
            Command configurado para esperar input
        """
        return self.transition_to(
            state=state,
            next_step=next_step,
            awaiting_input=True,
            messages=[AIMessage(content=message)],
            next_action=next_action or f"process_{next_step}"
        )

    def _get_updated_history(self, state: Dict[str, Any], step: str) -> List[str]:
        """
        Actualizar historial de flujo del workflow.
        
        Args:
            state: Estado actual que contiene el historial
            step: Nuevo paso a agregar al historial
            
        Returns:
            Lista actualizada del historial de pasos
        """
        current_history = state.get("flow_history", [])
        return current_history + [step]

    def create_escalation_command(
        self, 
        state: Dict[str, Any], 
        reason: str, 
        attempts: int,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> Command:
        """
        Crear comando de escalación estandarizado.
        
        Args:
            state: Estado actual
            reason: Razón de la escalación
            attempts: Número de intentos realizados
            additional_context: Contexto adicional para la escalación
            
        Returns:
            Command para escalar a supervisor
        """
        mensaje_escalacion = (
            f"He intentado {reason} sin éxito después de {attempts} intentos. "
            f"Voy a derivar tu consulta a un supervisor para que pueda ayudarte mejor. "
            f"Un momento, por favor... 🔄"
        )
        
        escalation_context = {
            "node_origin": self.name,
            "reason": reason,
            "attempts": attempts,
            "conversation_context": self.get_conversation_context(state)
        }
        
        if additional_context:
            escalation_context.update(additional_context)
        
        return Command(update=self.create_message_update(
            mensaje_escalacion,
            {
                "intentos": attempts,
                "escalar_a_supervisor": True,
                "razon_escalacion": reason,
                "contexto_escalacion": escalation_context
            }
        ))
    
    def get_execution_metrics(self) -> Dict[str, Any]:
        """
        Obtener métricas de ejecución del nodo.
        
        Returns:
            Diccionario con métricas del nodo
        """
        return {
            "node_name": self.name,
            "execution_count": self._execution_count,
            "error_count": self._error_count,
            "error_rate": self._error_count / max(self._execution_count, 1),
            "last_execution_time": self._last_execution_time,
            "timeout_seconds": self.timeout_seconds
        }


