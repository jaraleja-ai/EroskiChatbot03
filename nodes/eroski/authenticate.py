# =====================================================
# nodes/eroski/authenticate.py - Nodo de Autenticación de Empleados
# =====================================================
"""
Nodo de autenticación optimizado para empleados de Eroski.

RESPONSABILIDADES:
- Identificar empleados por email corporativo
- Validar pertenencia a tienda específica
- Manejar reintentos y escalación
- Preparar contexto para siguientes nodos

FLUJO:
1. Primera vez: Solicitar credenciales
2. Respuesta recibida: Validar y procesar
3. Información válida: Continuar al siguiente nodo
4. Información inválida: Reintentar o escalar
5. Demasiados intentos: Escalar a supervisor
"""

from typing import Dict, Any, Optional, Tuple
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging
import re

from models.eroski_state import EroskiState
from utils.eroski_systems import EroskiEmployeeValidator  # Sistema de validación

class AuthenticateEmployeeNode:
    """
    Nodo optimizado para autenticación de empleados de Eroski.
    
    CARACTERÍSTICAS:
    - Validación en tiempo real contra sistemas Eroski
    - Extracción inteligente de credenciales
    - Manejo robusto de errores
    - Logging detallado para auditoría
    """
    
    def __init__(self):
        self.logger = logging.getLogger("AuthenticateNode")
        self.employee_validator = EroskiEmployeeValidator()
        self.max_attempts = 3
        
    async def execute(self, state: EroskiState) -> Command:
        """
        Ejecutar lógica de autenticación con gestión de estado.
        
        Args:
            state: Estado actual del workflow
            
        Returns:
            Command con actualización de estado
        """
        try:
            self.logger.info("🔐 Iniciando proceso de autenticación")
            
            # Caso 1: Usuario ya autenticado - continuar
            if self._is_already_authenticated(state):
                return self._continue_authenticated_user(state)
            
            # Caso 2: Primera ejecución - solicitar credenciales
            if self._is_first_execution(state):
                return self._request_initial_credentials(state)
            
            # Caso 3: Procesar respuesta del usuario
            if self._has_user_response(state):
                return await self._process_user_credentials(state)
            
            # Caso 4: Estado inconsistente - escalar
            return self._handle_inconsistent_state(state)
            
        except Exception as e:
            self.logger.error(f"❌ Error en autenticación: {e}")
            return self._handle_authentication_error(state, str(e))
    
    def _is_already_authenticated(self, state: EroskiState) -> bool:
        """Verificar si el usuario ya está autenticado"""
        return bool(
            state.get("employee_email") and 
            state.get("store_id") and 
            state.get("authenticated")
        )
    
    def _is_first_execution(self, state: EroskiState) -> bool:
        """Verificar si es la primera ejecución del nodo"""
        messages = state.get("messages", [])
        return len(messages) == 0 or not any(
            isinstance(msg, HumanMessage) for msg in messages
        )
    
    def _has_user_response(self, state: EroskiState) -> bool:
        """Verificar si hay respuesta del usuario para procesar"""
        messages = state.get("messages", [])
        return any(isinstance(msg, HumanMessage) for msg in messages)
    
    def _continue_authenticated_user(self, state: EroskiState) -> Command:
        """Continuar con usuario ya autenticado"""
        employee_name = state.get("employee_name", "")
        
        self.logger.info(f"✅ Usuario ya autenticado: {employee_name}")
        
        return Command(update={
            "current_node": "authenticate",
            "last_activity": datetime.now(),
            "attempts": 0  # Reset intentos para siguiente nodo
        })
    
    def _request_initial_credentials(self, state: EroskiState) -> Command:
        """Solicitar credenciales iniciales al usuario"""
        self.logger.info("📝 Solicitando credenciales iniciales")
        
        welcome_message = """¡Hola! Soy el asistente de incidencias de Eroski 🤖

Para ayudarte de la mejor manera, necesito identificarte. Por favor, proporciona:

📧 **Tu email corporativo** (ejemplo: nombre.apellido@eroski.es)
🏪 **Tu tienda** (nombre o código de tienda)

**Ejemplo:**
"Mi email es juan.perez@eroski.es y trabajo en Eroski Bilbao Centro"

¿Podrías proporcionarme esta información? 😊"""
        
        return Command(update={
            "messages": state.get("messages", []) + [AIMessage(content=welcome_message)],
            "current_node": "authenticate",
            "attempts": 1,
            "awaiting_user_input": True,
            "last_activity": datetime.now(),
            "authentication_stage": "requesting_credentials"
        })
    
    async def _process_user_credentials(self, state: EroskiState) -> Command:
        """Procesar credenciales proporcionadas por el usuario"""
        self.logger.info("🔍 Procesando credenciales del usuario")
        
        # Extraer último mensaje del usuario
        user_message = self._get_last_user_message(state)
        if not user_message:
            return self._request_credentials_retry(state, "No se encontró mensaje del usuario")
        
        # Extraer credenciales del mensaje
        credentials = self._extract_credentials(user_message)
        
        if not credentials["valid"]:
            return self._request_credentials_retry(state, credentials.get("error", "Credenciales no válidas"))
        
        # Validar credenciales contra sistemas Eroski
        validation_result = await self._validate_employee_credentials(credentials)
        
        if validation_result["valid"]:
            return self._handle_successful_authentication(state, validation_result)
        else:
            return self._request_credentials_retry(state, validation_result.get("error", "Validación fallida"))
    
    def _get_last_user_message(self, state: EroskiState) -> Optional[str]:
        """Obtener último mensaje del usuario"""
        messages = state.get("messages", [])
        
        for message in reversed(messages):
            if isinstance(message, HumanMessage) and message.content.strip():
                return message.content.strip()
        
        return None
    
    def _extract_credentials(self, user_message: str) -> Dict[str, Any]:
        """
        Extraer credenciales del mensaje del usuario.
        
        Args:
            user_message: Mensaje del usuario
            
        Returns:
            Diccionario con credenciales extraídas
        """
        try:
            credentials = {"valid": False}
            
            # Extraer email corporativo
            email_pattern = r'\b[A-Za-z0-9._%+-]+@eroski\.es\b'
            email_match = re.search(email_pattern, user_message, re.IGNORECASE)
            
            if not email_match:
                return {
                    "valid": False, 
                    "error": "No se encontró email corporativo válido (@eroski.es)"
                }
            
            email = email_match.group().lower()
            credentials["email"] = email
            
            # Extraer nombre del email
            name_part = email.split('@')[0]
            name = name_part.replace('.', ' ').replace('_', ' ').title()
            credentials["name"] = name
            
            # Extraer información de tienda
            store_info = self._extract_store_info(user_message)
            if store_info:
                credentials["store_info"] = store_info
                credentials["valid"] = True
            else:
                credentials["store_info"] = "No especificada"
                credentials["valid"] = True  # Email válido es suficiente inicialmente
            
            self.logger.info(f"📧 Credenciales extraídas para: {name}")
            
            return credentials
            
        except Exception as e:
            self.logger.error(f"❌ Error extrayendo credenciales: {e}")
            return {"valid": False, "error": f"Error procesando credenciales: {str(e)}"}
    
    def _extract_store_info(self, message: str) -> Optional[str]:
        """Extraer información de tienda del mensaje"""
        
        # Patrones para detectar tienda
        store_patterns = [
            r'eroski\s+([a-záéíóúñ\s]+)',
            r'tienda\s+([a-záéíóúñ\s\d]+)',
            r'trabajo\s+en\s+([a-záéíóúñ\s]+)',
            r'centro\s+([a-záéíóúñ\s]+)',
            r'hipermercado\s+([a-záéíóúñ\s]+)',
            r'supermercado\s+([a-záéíóúñ\s]+)',
            r'código\s+(\d+)',
            r'tienda\s+(\d+)'
        ]
        
        message_lower = message.lower()
        
        for pattern in store_patterns:
            match = re.search(pattern, message_lower, re.IGNORECASE)
            if match:
                store_info = match.group(1).strip()
                # Limpiar y capitalizar
                store_info = ' '.join(word.capitalize() for word in store_info.split())
                return store_info
        
        return None
    
    async def _validate_employee_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validar credenciales contra sistemas de Eroski.
        
        Args:
            credentials: Credenciales extraídas
            
        Returns:
            Resultado de validación
        """
        try:
            # Validar empleado en sistemas Eroski
            employee_data = await self.employee_validator.validate_employee(
                email=credentials["email"],
                store_hint=credentials.get("store_info")
            )
            
            if employee_data:
                self.logger.info(f"✅ Empleado validado: {employee_data['name']}")
                return {
                    "valid": True,
                    "employee": employee_data
                }
            else:
                self.logger.warning(f"❌ Empleado no encontrado: {credentials['email']}")
                return {
                    "valid": False,
                    "error": "No se encontró el empleado en los sistemas de Eroski"
                }
                
        except Exception as e:
            self.logger.error(f"❌ Error validando empleado: {e}")
            return {
                "valid": False,
                "error": f"Error de conexión con sistemas Eroski: {str(e)}"
            }
    
    def _handle_successful_authentication(self, state: EroskiState, validation_result: Dict[str, Any]) -> Command:
        """Manejar autenticación exitosa"""
        employee = validation_result["employee"]
        
        self.logger.info(f"🎉 Autenticación exitosa: {employee['name']}")
        
        success_message = f"""¡Perfecto, {employee['name']}! 👋

Ya te tengo identificado:
🏪 **Tienda:** {employee['store_name']}
📍 **Departamento:** {employee.get('department', 'No especificado')}

¿En qué puedo ayudarte hoy? Puedes contarme sobre:
• 🔧 **Problemas técnicos** (TPV, impresoras, red, etc.)
• ❓ **Consultas generales** (procedimientos, información)
• 🆘 **Urgencias** (problemas que impiden trabajar)

¡Describe tu situación! 😊"""
        
        return Command(update={
            "employee_email": employee["email"],
            "employee_name": employee["name"],
            "employee_id": employee.get("id"),
            "store_id": employee["store_id"],
            "store_name": employee["store_name"],
            "store_type": employee.get("store_type"),
            "department": employee.get("department"),
            "employee_level": employee.get("level", 1),
            "authenticated": True,
            "awaiting_user_input": False,
            "attempts": 0,
            "messages": state.get("messages", []) + [AIMessage(content=success_message)],
            "current_node": "authenticate",
            "last_activity": datetime.now(),
            "authentication_stage": "completed"
        })
    
    def _request_credentials_retry(self, state: EroskiState, error_reason: str) -> Command:
        """Solicitar credenciales nuevamente después de error"""
        attempts = state.get("attempts", 0)
        
        # Verificar límite de intentos
        if attempts >= self.max_attempts:
            self.logger.warning(f"⚠️ Límite de intentos alcanzado: {attempts}")
            return self._escalate_authentication_failure(state, error_reason)
        
        self.logger.info(f"🔄 Solicitando credenciales nuevamente (intento {attempts + 1}/{self.max_attempts})")
        
        retry_message = f"""No he podido verificar tu identidad (intento {attempts + 1}/{self.max_attempts}).

**Problema detectado:** {error_reason}

Por favor, asegúrate de incluir:
📧 **Email corporativo completo** (debe terminar en @eroski.es)
🏪 **Nombre de tu tienda** (ej: "Eroski Bilbao Centro")

**Ejemplo correcto:**
"Mi email es maria.garcia@eroski.es y trabajo en Eroski Madrid Salamanca"

¿Puedes intentar de nuevo? 🙏"""
        
        return Command(update={
            "messages": state.get("messages", []) + [AIMessage(content=retry_message)],
            "attempts": attempts + 1,
            "awaiting_user_input": True,
            "current_node": "authenticate",
            "last_activity": datetime.now(),
            "authentication_stage": "retrying_credentials",
            "last_error": error_reason
        })
    
    def _escalate_authentication_failure(self, state: EroskiState, final_error: str) -> Command:
        """Escalar por fallo en autenticación"""
        self.logger.error(f"🚨 Escalando por fallo de autenticación: {final_error}")
        
        escalation_message = """Lo siento, no he podido verificar tu identidad después de varios intentos. 😔

He derivado tu consulta a un supervisor que te ayudará a identificarte correctamente.

📧 **Recibirás una respuesta por email** en las próximas 2 horas
📞 **Para urgencias, contacta directamente:**
   • Soporte técnico: +34 900 123 456
   • Email directo: soporte.urgente@eroski.es

¡Gracias por tu paciencia! 🙏"""
        
        return Command(update={
            "escalation_needed": True,
            "escalation_reason": f"Fallo de autenticación después de {self.max_attempts} intentos: {final_error}",
            "escalation_level": "supervisor",
            "awaiting_user_input": False,
            "messages": state.get("messages", []) + [AIMessage(content=escalation_message)],
            "current_node": "authenticate",
            "last_activity": datetime.now(),
            "authentication_stage": "escalated"
        })
    
    def _handle_inconsistent_state(self, state: EroskiState) -> Command:
        """Manejar estado inconsistente"""
        self.logger.warning("⚠️ Estado inconsistente en autenticación")
        
        return Command(update={
            "escalation_needed": True,
            "escalation_reason": "Estado inconsistente en proceso de autenticación",
            "awaiting_user_input": False,
            "current_node": "authenticate",
            "last_activity": datetime.now()
        })
    
    def _handle_authentication_error(self, state: EroskiState, error_message: str) -> Command:
        """Manejar errores técnicos en autenticación"""
        self.logger.error(f"💥 Error técnico en autenticación: {error_message}")
        
        error_response = """Ha ocurrido un error técnico durante la autenticación. 🔧

Por favor:
1. **Intenta nuevamente** en unos minutos
2. **Si persiste el problema**, contacta con soporte técnico

📞 **Soporte técnico:** +34 900 123 456
📧 **Email:** soporte.tecnico@eroski.es

¡Disculpa las molestias! 😊"""
        
        return Command(update={
            "escalation_needed": True,
            "escalation_reason": f"Error técnico en autenticación: {error_message}",
            "messages": state.get("messages", []) + [AIMessage(content=error_response)],
            "awaiting_user_input": False,
            "current_node": "authenticate",
            "last_activity": datetime.now(),
            "error_count": state.get("error_count", 0) + 1
        })

# ========== SISTEMA DE VALIDACIÓN DE EMPLEADOS ==========

class EroskiEmployeeValidator:
    """
    Sistema de validación de empleados de Eroski.
    
    NOTA: Esta es una implementación mock para desarrollo.
    En producción debe conectar con Active Directory y sistemas HR reales.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("EmployeeValidator")
        
        # Mock database de empleados para desarrollo
        self.mock_employees = {
            "juan.perez@eroski.es": {
                "id": "E001",
                "name": "Juan Pérez",
                "email": "juan.perez@eroski.es",
                "store_id": "ERO001",
                "store_name": "Eroski Bilbao Centro",
                "store_type": "hipermercado",
                "department": "Tecnología",
                "level": 2
            },
            "maria.garcia@eroski.es": {
                "id": "E002", 
                "name": "María García",
                "email": "maria.garcia@eroski.es",
                "store_id": "ERO002",
                "store_name": "Eroski Madrid Salamanca",
                "store_type": "supermercado",
                "department": "Caja",
                "level": 1
            },
            "admin.test@eroski.es": {
                "id": "E999",
                "name": "Admin Test",
                "email": "admin.test@eroski.es", 
                "store_id": "ERO999",
                "store_name": "Eroski Test Store",
                "store_type": "test",
                "department": "IT",
                "level": 3
            }
        }
    
    async def validate_employee(self, email: str, store_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Validar empleado contra sistemas Eroski.
        
        Args:
            email: Email del empleado
            store_hint: Pista sobre la tienda
            
        Returns:
            Datos del empleado si es válido, None en caso contrario
        """
        try:
            self.logger.info(f"🔍 Validando empleado: {email}")
            
            # Simular latencia de red
            import asyncio
            await asyncio.sleep(0.5)
            
            # Buscar en mock database
            employee = self.mock_employees.get(email.lower())
            
            if employee:
                self.logger.info(f"✅ Empleado encontrado: {employee['name']}")
                return employee.copy()
            else:
                self.logger.warning(f"❌ Empleado no encontrado: {email}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error validando empleado: {e}")
            return None

# ========== WRAPPER PARA LANGGRAPH ==========

async def authenticate_employee_node(state: EroskiState) -> Command:
    """
    Wrapper function para el nodo de autenticación.
    
    Args:
        state: Estado actual del workflow
        
    Returns:
        Command con la actualización de estado
    """
    node = AuthenticateEmployeeNode()
    return await node.execute(state)