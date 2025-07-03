# =====================================================
# nodes/base_node.py - Clase Base para Nodos de LangGraph
# =====================================================
"""
Clase base para todos los nodos del workflow de Eroski.

CARACTERÍSTICAS:
- Abstracción común para todos los nodos
- Manejo de errores estandarizado
- Logging integrado
- Utilidades comunes
- Validaciones básicas
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
import logging
from datetime import datetime

from models.eroski_state import EroskiState

class BaseNode(ABC):
    """
    Clase base para todos los nodos del workflow.
    
    Proporciona funcionalidad común y define la interfaz
    que deben implementar todos los nodos.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Node.{name}")
        self.execution_count = 0
        self.error_count = 0
        
    @abstractmethod
    async def execute(self, state: EroskiState) -> Command:
        """
        Ejecutar la lógica principal del nodo.
        
        Args:
            state: Estado actual del workflow
            
        Returns:
            Command con las actualizaciones de estado
        """
        pass
    
    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """
        Obtener campos requeridos en el estado.
        
        Returns:
            Lista de campos requeridos
        """
        pass
    
    @abstractmethod
    def get_actor_description(self) -> str:
        """
        Obtener descripción de las responsabilidades del nodo.
        
        Returns:
            Descripción del nodo
        """
        pass
    
    def validate_state(self, state: EroskiState) -> bool:
        """
        Validar que el estado tenga los campos requeridos.
        
        Args:
            state: Estado a validar
            
        Returns:
            True si el estado es válido
        """
        required_fields = self.get_required_fields()
        
        for field in required_fields:
            if field not in state:
                self.logger.warning(f"⚠️ Campo requerido faltante: {field}")
                return False
        
        return True
    
    def get_last_user_message(self, state: EroskiState) -> str:
        """
        Obtener el último mensaje del usuario.
        
        Args:
            state: Estado actual
            
        Returns:
            Contenido del último mensaje del usuario
        """
        messages = state.get("messages", [])
        
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return message.content
            elif hasattr(message, 'type') and message.type == "human":
                return message.content
        
        return ""
    
    def increment_attempts(self, state: EroskiState) -> int:
        """
        Incrementar contador de intentos.
        
        Args:
            state: Estado actual
            
        Returns:
            Nuevo número de intentos
        """
        return state.get("attempts", 0) + 1
    
    def should_escalate(self, state: EroskiState, max_attempts: int = 3) -> bool:
        """
        Determinar si se debe escalar por exceso de intentos.
        
        Args:
            state: Estado actual
            max_attempts: Máximo número de intentos
            
        Returns:
            True si debe escalar
        """
        attempts = state.get("attempts", 0)
        return attempts >= max_attempts
    
    def create_error_response(self, error_message: str, 
                            escalate: bool = False) -> Dict[str, Any]:
        """
        Crear respuesta de error estandarizada.
        
        Args:
            error_message: Mensaje de error
            escalate: Si debe escalar por error
            
        Returns:
            Diccionario con respuesta de error
        """
        error_response = {
            "error": True,
            "error_message": error_message,
            "error_count": self.error_count + 1,
            "current_node": self.name,
            "last_activity": datetime.now(),
            "messages": [AIMessage(content=f"❌ Error: {error_message}")]
        }
        
        if escalate:
            error_response.update({
                "escalation_needed": True,
                "escalation_reason": f"Error técnico en {self.name}: {error_message}",
                "escalation_level": "technical"
            })
        
        return error_response
    
    def create_success_response(self, message: str, 
                              additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Crear respuesta de éxito estandarizada.
        
        Args:
            message: Mensaje de éxito
            additional_data: Datos adicionales
            
        Returns:
            Diccionario con respuesta de éxito
        """
        success_response = {
            "success": True,
            "current_node": self.name,
            "last_activity": datetime.now(),
            "messages": [AIMessage(content=message)]
        }
        
        if additional_data:
            success_response.update(additional_data)
        
        return success_response
    
    def create_input_request(self, message: str, 
                           additional_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Crear solicitud de input del usuario.
        
        Args:
            message: Mensaje para el usuario
            additional_data: Datos adicionales
            
        Returns:
            Diccionario con solicitud de input
        """
        input_request = {
            "awaiting_user_input": True,
            "current_node": self.name,
            "last_activity": datetime.now(),
            "messages": [AIMessage(content=message)]
        }
        
        if additional_data:
            input_request.update(additional_data)
        
        return input_request
    
    def create_escalation_request(self, reason: str, 
                                escalation_level: str = "supervisor") -> Dict[str, Any]:
        """
        Crear solicitud de escalación.
        
        Args:
            reason: Motivo de escalación
            escalation_level: Nivel de escalación
            
        Returns:
            Diccionario con solicitud de escalación
        """
        escalation_message = f"""🔼 **Escalando consulta**

{reason}

Te he derivado a un especialista que podrá ayudarte mejor.

📞 **Contacto directo:**
• Soporte técnico: +34 946 211 000
• Email: soporte.tecnico@eroski.es

¡Gracias por tu paciencia! 🙏"""
        
        return {
            "escalation_needed": True,
            "escalation_reason": reason,
            "escalation_level": escalation_level,
            "current_node": self.name,
            "last_activity": datetime.now(),
            "awaiting_user_input": False,
            "messages": [AIMessage(content=escalation_message)]
        }
    
    def log_execution(self, state: EroskiState, action: str, details: str = ""):
        """
        Registrar ejecución del nodo.
        
        Args:
            state: Estado actual
            action: Acción realizada
            details: Detalles adicionales
        """
        self.execution_count += 1
        
        session_id = state.get("session_id", "unknown")
        employee_id = state.get("employee_id", "unknown")
        
        self.logger.info(
            f"🔄 {self.name} - {action} "
            f"(Session: {session_id}, Employee: {employee_id}) "
            f"{details}"
        )
    
    def validate_email_format(self, email: str) -> bool:
        """
        Validar formato de email corporativo.
        
        Args:
            email: Email a validar
            
        Returns:
            True si el formato es válido
        """
        import re
        
        if not email or not isinstance(email, str):
            return False
        
        # Patrón básico de email
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(pattern, email.strip()):
            return False
        
        # Verificar dominio Eroski
        return email.strip().lower().endswith('@eroski.es')
    
    def validate_name_format(self, name: str) -> bool:
        """
        Validar formato de nombre.
        
        Args:
            name: Nombre a validar
            
        Returns:
            True si el formato es válido
        """
        import re
        
        if not name or not isinstance(name, str):
            return False
        
        name = name.strip()
        
        if len(name) < 2:
            return False
        
        # Permitir letras, espacios, acentos y caracteres especiales de nombres
        pattern = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\-\'\.]+$'
        return bool(re.match(pattern, name))
    
    def extract_serial_number(self, text: str) -> Optional[str]:
        """
        Extraer número de serie del texto.
        
        Args:
            text: Texto a analizar
            
        Returns:
            Número de serie si se encuentra
        """
        import re
        
        patterns = [
            r'serie[:\s]+([A-Z0-9]{6,})',
            r'número[:\s]+([A-Z0-9]{6,})',
            r'sn[:\s]+([A-Z0-9]{6,})',
            r'serial[:\s]+([A-Z0-9]{6,})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text.upper())
            if match:
                return match.group(1)
        
        return None
    
    def extract_error_codes(self, text: str) -> List[str]:
        """
        Extraer códigos de error del texto.
        
        Args:
            text: Texto a analizar
            
        Returns:
            Lista de códigos de error encontrados
        """
        import re
        
        patterns = [
            r'error[:\s]+([A-Z0-9]{3,})',
            r'código[:\s]+([A-Z0-9]{3,})',
            r'code[:\s]+([A-Z0-9]{3,})'
        ]
        
        error_codes = []
        for pattern in patterns:
            matches = re.findall(pattern, text.upper())
            error_codes.extend(matches)
        
        return list(set(error_codes))  # Eliminar duplicados
    
    def calculate_time_elapsed(self, state: EroskiState) -> float:
        """
        Calcular tiempo transcurrido desde el inicio.
        
        Args:
            state: Estado actual
            
        Returns:
            Tiempo en minutos
        """
        start_time = state.get("start_time")
        if not start_time:
            return 0.0
        
        elapsed = datetime.now() - start_time
        return elapsed.total_seconds() / 60
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """
        Obtener resumen de ejecución del nodo.
        
        Returns:
            Diccionario con estadísticas
        """
        return {
            "node_name": self.name,
            "execution_count": self.execution_count,
            "error_count": self.error_count,
            "success_rate": (
                (self.execution_count - self.error_count) / self.execution_count * 100
                if self.execution_count > 0 else 0
            )
        }

# ========== UTILIDADES ADICIONALES ==========

def node_wrapper(func):
    """
    Decorator para nodos con manejo de errores automático.
    
    Args:
        func: Función del nodo a decorar
        
    Returns:
        Función decorada
    """
    import functools
    
    @functools.wraps(func)
    async def wrapper(state: EroskiState) -> Command:
        try:
            return await func(state)
        except Exception as e:
            logger = logging.getLogger(f"NodeWrapper.{func.__name__}")
            logger.error(f"❌ Error en {func.__name__}: {e}")
            
            error_response = {
                "error": True,
                "error_message": str(e),
                "current_node": func.__name__,
                "last_activity": datetime.now(),
                "escalation_needed": True,
                "escalation_reason": f"Error técnico en {func.__name__}",
                "messages": [AIMessage(content="Ha ocurrido un error técnico. Te derivo a soporte.")]
            }
            
            return Command(update=error_response)
    
    return wrapper