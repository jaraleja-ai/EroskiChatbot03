# =====================================================
# nodes/authenticate_enhanced.py - Nodo de Autenticación Completo
# =====================================================
"""
Nodo de autenticación completo que recopila toda la información necesaria.

FUNCIONALIDAD:
1. Autentica usuario por email en BD
2. Si está en BD: Confirma tienda y pregunta sección
3. Si NO está en BD: Recopila todos los datos fundamentales
4. Usa LLM para mensajes naturales e iteraciones múltiples
5. Detecta intención de cancelar en cualquier momento
"""

from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging
import re

from models.eroski_state import EroskiState
from nodes.base_node import BaseNode
from utils.eroski_database_auth import EroskiEmployeeDatabaseAuth
from utils.llm_client import get_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

class UserResponseAnalysis(BaseModel):
    """Análisis de la respuesta del usuario por LLM"""
    wants_to_cancel: bool = Field(description="Si el usuario quiere cancelar el proceso")
    has_email: bool = Field(description="Si se encontró un email corporativo")
    has_name: bool = Field(description="Si se encontró nombre completo")
    has_store_code: bool = Field(description="Si se encontró código de tienda")
    has_store_name: bool = Field(description="Si se encontró nombre de tienda")
    has_section: bool = Field(description="Si se encontró nombre de sección")
    confirmed_same_store: Optional[bool] = Field(description="Si confirmó que la incidencia es en su tienda registrada")
    email: Optional[str] = Field(description="Email extraído")
    name: Optional[str] = Field(description="Nombre completo extraído")
    store_code: Optional[str] = Field(description="Código de tienda extraído")
    store_name: Optional[str] = Field(description="Nombre de tienda extraído")
    section: Optional[str] = Field(description="Sección extraída")
    missing_fields: List[str] = Field(description="Campos que faltan")
    next_message: str = Field(description="Mensaje natural para continuar")

class AuthenticateEmployeeNodeComplete(BaseNode):
    """
    Nodo de autenticación completo que recopila toda la información necesaria.
    """
    
    def __init__(self):
        super().__init__("authenticate")
        self.max_attempts = 7  # Más intentos para recopilar toda la información
        self.db_auth = EroskiEmployeeDatabaseAuth()
        self.llm = get_llm()
        
        # Parser para análisis LLM
        self.parser = JsonOutputParser(pydantic_object=UserResponseAnalysis)
        
        # Prompt para analizar respuesta del usuario
        self.analysis_prompt = PromptTemplate(
            template="""Eres un asistente experto en procesar respuestas de empleados de Eroski.

Tu tarea es analizar la respuesta del usuario y extraer información para el proceso de autenticación e incidencias.

DATOS QUE NECESITAMOS RECOPILAR:
- Email corporativo (@eroski.es)
- Nombre completo
- Código de tienda (ej: "T001", "ERO_BCN", etc.)
- Nombre de tienda (ej: "Eroski Bilbao Centro")
- Sección donde ocurrió la incidencia (ej: "Carnicería", "Caja", "Almacén")

INFORMACIÓN ACTUAL YA RECOPILADA:
{current_data}

ETAPA ACTUAL: {current_stage}

MENSAJE DEL USUARIO:
"{user_message}"

INSTRUCCIONES:
1. PRIMERO: Detecta si el usuario quiere CANCELAR (palabras como: "cancelar", "salir", "no quiero", "déjalo", "olvídalo", "hasta luego", "adiós")
2. Extrae TODA la información nueva del mensaje
3. Si estamos preguntando sobre la tienda registrada, detecta confirmación (sí/no)
4. Identifica qué información aún falta
5. Genera un mensaje natural, breve y amable para continuar

EJEMPLOS DE MENSAJES NATURALES POR SITUACIÓN:
- Pidiendo email: "¿Podrías decirme tu email corporativo de Eroski?"
- Pidiendo nombre: "Perfecto, ¿y tu nombre completo?"
- Confirmando tienda: "Veo que trabajas en Eroski Madrid Sur. ¿La incidencia ha ocurrido en esa misma tienda?"
- Pidiendo nueva tienda: "Entiendo, ¿podrías decirme el código y nombre de la tienda donde ocurrió?"
- Pidiendo sección: "¿En qué sección específica ha tenido lugar la incidencia?"

{format_instructions}
""",
            input_variables=["current_data", "current_stage", "user_message"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
    
    def get_required_fields(self) -> List[str]:
        return ["messages"]
    
    def get_actor_description(self) -> str:
        return "Autentico empleados y recopilo información completa para procesar incidencias"
    
    async def execute(self, state: EroskiState) -> Command:
        """Ejecutar proceso de autenticación completo"""
        print("🎗️" * 50)
        print(f"Entra en el nodo: {self.__class__.__name__}")
        
        try:
            # Caso 1: Proceso completado - pasar al siguiente nodo
            if self._is_authentication_complete(state):
                return self._complete_authentication(state)
            
            # Caso 2: Primera ejecución
            if self._is_first_execution(state):
                return self._request_initial_credentials(state)
            
            # Caso 3: Procesar respuesta del usuario
            if self._has_user_response(state):
                return await self._process_user_response(state)
            
            # Caso 4: Estado inconsistente
            return self._handle_inconsistent_state(state)
            
        except Exception as e:
            self.logger.error(f"❌ Error en autenticación: {e}")
            return self._handle_authentication_error(state, str(e))
    
    def _is_authentication_complete(self, state: EroskiState) -> bool:
        """Verificar si la autenticación está completa"""
        required_fields = [
            "employee_name",
            "incident_store_code", 
            "incident_store_name",
            "incident_section"
        ]
        
        return all(state.get(field) for field in required_fields)
    
    def _is_first_execution(self, state: EroskiState) -> bool:
        """Verificar si es la primera ejecución"""
        messages = state.get("messages", [])
        return len(messages) == 0 or not any(isinstance(msg, HumanMessage) for msg in messages)
    
    def _has_user_response(self, state: EroskiState) -> bool:
        """Verificar si hay respuesta del usuario"""
        messages = state.get("messages", [])
        return any(isinstance(msg, HumanMessage) for msg in messages)
    
    def _request_initial_credentials(self, state: EroskiState) -> Command:
        """Solicitar credenciales iniciales"""
        self.logger.info("📝 Iniciando proceso de autenticación")
        
        welcome_message = """👋 ¡Hola! Soy tu asistente de incidencias técnicas de Eroski.

Para ayudarte, necesito identificarte. ¿Podrías decirme tu **email corporativo**?

**Ejemplo:** maria.garcia@eroski.es 😊

*(En cualquier momento puedes escribir "cancelar" si no deseas continuar)*"""
        
        return Command(update={
            "current_node": "authenticate",
            "messages": state.get("messages", []) + [AIMessage(content=welcome_message)],
            "awaiting_user_input": True,
            "attempts": 1,
            "authentication_stage": "requesting_email",
            "last_activity": datetime.now()
        })
    
    async def _process_user_response(self, state: EroskiState) -> Command:
        """Procesar respuesta del usuario"""
        attempts = state.get("attempts", 0)
        
        # Verificar límite de intentos
        if attempts >= self.max_attempts:
            return self._escalate_max_attempts(state)
        
        # Analizar respuesta del usuario con LLM
        analysis = await self._analyze_user_response(state)
        
        # Verificar si quiere cancelar
        if analysis.wants_to_cancel:
            return self._handle_cancellation_request(state)
        
        # Procesar según la etapa actual
        current_stage = state.get("authentication_stage", "requesting_email")
        
        if current_stage == "requesting_email":
            return await self._handle_email_stage(state, analysis)
        elif current_stage == "found_in_db":
            return await self._handle_found_in_db_stage(state, analysis)
        elif current_stage == "not_found_in_db":
            return await self._handle_not_found_stage(state, analysis)
        elif current_stage == "confirming_store":
            return await self._handle_store_confirmation_stage(state, analysis)
        elif current_stage == "requesting_incident_store":
            return await self._handle_incident_store_stage(state, analysis)
        elif current_stage == "requesting_section":
            return await self._handle_section_stage(state, analysis)
        else:
            return self._continue_data_collection(state, analysis)
    
    async def _analyze_user_response(self, state: EroskiState) -> UserResponseAnalysis:
        """Analizar respuesta del usuario con LLM"""
        try:
            # Obtener último mensaje del usuario
            user_message = self._get_last_user_message(state)
            
            # Preparar datos actuales
            current_data = self._format_current_data(state)
            current_stage = state.get("authentication_stage", "requesting_email")
            
            # Crear prompt
            formatted_prompt = self.analysis_prompt.format(
                current_data=current_data,
                current_stage=current_stage,
                user_message=user_message
            )
            
            # Invocar LLM
            self.logger.debug("🤖 Analizando respuesta del usuario")
            response = await self.llm.ainvoke(formatted_prompt)
            
            # Parsear respuesta
            analysis = self.parser.parse(response.content)
            
            self.logger.info(f"📊 Análisis: Cancelar={analysis.wants_to_cancel}, Email={analysis.has_email}")
            
            return analysis
            
        except Exception as e:
            self.logger.error(f"❌ Error en análisis LLM: {e}")
            # Análisis por defecto en caso de error
            return UserResponseAnalysis(
                wants_to_cancel=False,
                has_email=False,
                has_name=False,
                has_store_code=False,
                has_store_name=False,
                has_section=False,
                missing_fields=["información"],
                next_message="¿Podrías repetir la información, por favor?"
            )
    
    def _get_last_user_message(self, state: EroskiState) -> str:
        """Obtener último mensaje del usuario"""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return msg.content.strip()
        return ""
    
    def _format_current_data(self, state: EroskiState) -> str:
        """Formatear datos actuales recopilados"""
        data_parts = []
        
        if state.get("employee_email"):
            data_parts.append(f"Email: {state.get('employee_email')}")
        if state.get("employee_name"):
            data_parts.append(f"Nombre: {state.get('employee_name')}")
        if state.get("store_name"):
            data_parts.append(f"Tienda registrada: {state.get('store_name')}")
        if state.get("incident_store_name"):
            data_parts.append(f"Tienda incidencia: {state.get('incident_store_name')}")
        if state.get("incident_section"):
            data_parts.append(f"Sección: {state.get('incident_section')}")
        
        return "; ".join(data_parts) if data_parts else "Ningún dato recopilado aún"
    
    async def _handle_email_stage(self, state: EroskiState, analysis: UserResponseAnalysis) -> Command:
        """Manejar etapa de recopilación de email"""
        if not analysis.has_email:
            return self._request_email_again(state, analysis)
        
        # Intentar buscar en base de datos
        auth_result = await self._try_database_lookup(analysis.email)
        
        if auth_result["found"]:
            # Usuario encontrado en BD
            return self._handle_user_found_in_db(state, auth_result["employee"], analysis)
        else:
            # Usuario no encontrado - recopilar datos manualmente
            return self._handle_user_not_found_in_db(state, analysis)
    
    async def _try_database_lookup(self, email: str) -> Dict[str, Any]:
        """Intentar búsqueda en base de datos"""
        try:
            self.logger.info(f"🔍 Buscando en BD: {email}")
            employee_data = await self.db_auth.get_employee_by_email(email)
            
            if employee_data:
                self.logger.info(f"✅ Usuario encontrado: {employee_data.get('name')}")
                return {"found": True, "employee": employee_data}
            else:
                self.logger.info("❌ Usuario no encontrado en BD")
                return {"found": False}
                
        except Exception as e:
            self.logger.error(f"❌ Error en búsqueda BD: {e}")
            return {"found": False, "error": str(e)}
    
    def _handle_user_found_in_db(self, state: EroskiState, employee: Dict[str, Any], analysis: UserResponseAnalysis) -> Command:
        """Manejar usuario encontrado en BD"""
        store_name = employee.get('store_name', 'tu tienda')
        
        message = f"""¡Perfecto, {employee.get('name')}! 👋

Te he identificado correctamente:
🏪 **Tienda registrada:** {store_name}
📧 **Email:** {employee.get('email')}

**Ahora necesito saber:** ¿La incidencia ha ocurrido en {store_name} o en otra tienda?

Responde **"sí"** si es en tu tienda registrada, o **"no"** si es en otra tienda. 😊"""
        
        return Command(update={
            "employee_email": employee.get('email'),
            "employee_name": employee.get('name'),
            "employee_id": employee.get('id'),
            "store_id": employee.get('store_id'),
            "store_name": employee.get('store_name'),
            "department": employee.get('department'),
            "authenticated": True,
            "authentication_stage": "confirming_store",
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "attempts": state.get("attempts", 0) + 1,
            "last_activity": datetime.now()
        })
    
    def _handle_user_not_found_in_db(self, state: EroskiState, analysis: UserResponseAnalysis) -> Command:
        """Manejar usuario no encontrado en BD"""
        message = f"""Gracias por tu email. No te he encontrado en la base de datos, pero puedo ayudarte igual. 😊

Para procesar tu incidencia necesito algunos datos más:

¿Podrías decirme tu **nombre completo**?"""
        
        return Command(update={
            "employee_email": analysis.email,
            "authenticated": False,  # No está en BD, pero podemos continuar
            "authentication_stage": "not_found_in_db",
            "temp_user": True,  # Marcar como usuario temporal
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "attempts": state.get("attempts", 0) + 1,
            "last_activity": datetime.now()
        })
    
    async def _handle_found_in_db_stage(self, state: EroskiState, analysis: UserResponseAnalysis) -> Command:
        """Manejar etapa para usuario encontrado en BD"""
        # Esta etapa ya se maneja en confirming_store
        return await self._handle_store_confirmation_stage(state, analysis)
    
    async def _handle_not_found_stage(self, state: EroskiState, analysis: UserResponseAnalysis) -> Command:
        """Manejar etapa para usuario no encontrado"""
        updates = {"attempts": state.get("attempts", 0) + 1}
        
        # Recopilar nombre si no lo tenemos
        if not state.get("employee_name") and analysis.has_name:
            updates["employee_name"] = analysis.name
        
        # Verificar qué información necesitamos
        missing = []
        if not state.get("employee_name"):
            missing.append("nombre")
        if not state.get("incident_store_name"):
            missing.append("tienda")
        if not state.get("incident_section"):
            missing.append("sección")
        
        if not missing:
            # Tenemos toda la información
            return self._complete_authentication(state)
        elif "tienda" in missing:
            updates["authentication_stage"] = "requesting_incident_store"
            message = "Perfecto. Ahora necesito saber el **código y nombre de la tienda** donde ha ocurrido la incidencia."
        elif "sección" in missing:
            updates["authentication_stage"] = "requesting_section"
            message = "Excelente. Por último, ¿en qué **sección específica** ha tenido lugar la incidencia? (ej: Carnicería, Caja, Almacén)"
        else:
            message = analysis.next_message
        
        updates.update({
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "last_activity": datetime.now()
        })
        
        return Command(update=updates)
    
    async def _handle_store_confirmation_stage(self, state: EroskiState, analysis: UserResponseAnalysis) -> Command:
        """Manejar confirmación de tienda"""
        updates = {"attempts": state.get("attempts", 0) + 1}
        
        if analysis.confirmed_same_store is True:
            # Incidencia en la misma tienda registrada
            updates.update({
                "incident_store_code": state.get("store_id"),
                "incident_store_name": state.get("store_name"),
                "authentication_stage": "requesting_section"
            })
            message = "Perfecto. ¿En qué **sección específica** ha tenido lugar la incidencia? (ej: Carnicería, Caja, Almacén, Recepción)"
            
        elif analysis.confirmed_same_store is False:
            # Incidencia en otra tienda
            updates["authentication_stage"] = "requesting_incident_store"
            message = "Entendido. ¿Podrías decirme el **código y nombre de la tienda** donde ha ocurrido la incidencia?"
            
        else:
            # No se detectó confirmación clara
            message = f"""No estoy seguro de tu respuesta. 

¿La incidencia ha ocurrido en tu tienda registrada (**{state.get('store_name')}**)?

Por favor responde **"sí"** o **"no"**. 😊"""
        
        updates.update({
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "last_activity": datetime.now()
        })
        
        return Command(update=updates)
    
    async def _handle_incident_store_stage(self, state: EroskiState, analysis: UserResponseAnalysis) -> Command:
        """Manejar recopilación de tienda de incidencia"""
        updates = {"attempts": state.get("attempts", 0) + 1}
        
        # Actualizar información de tienda si la tenemos
        if analysis.has_store_code:
            updates["incident_store_code"] = analysis.store_code
        if analysis.has_store_name:
            updates["incident_store_name"] = analysis.store_name
        
        # Verificar si tenemos información completa de tienda
        has_store_info = bool(
            updates.get("incident_store_code") or state.get("incident_store_code") or
            updates.get("incident_store_name") or state.get("incident_store_name")
        )
        
        if has_store_info:
            # Pasar a pedir sección
            updates["authentication_stage"] = "requesting_section"
            message = "Excelente. Por último, ¿en qué **sección específica** ha tenido lugar la incidencia?"
        else:
            # Pedir información de tienda más específica
            message = "Necesito más información sobre la tienda. ¿Podrías decirme el **nombre completo de la tienda**? (ej: 'Eroski Bilbao Centro', 'Hipermercado Eroski Getxo')"
        
        updates.update({
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "last_activity": datetime.now()
        })
        
        return Command(update=updates)
    
    async def _handle_section_stage(self, state: EroskiState, analysis: UserResponseAnalysis) -> Command:
        """Manejar recopilación de sección"""
        updates = {"attempts": state.get("attempts", 0) + 1}
        
        if analysis.has_section:
            # Tenemos la sección - completar autenticación
            updates.update({
                "incident_section": analysis.section,
                "authentication_stage": "completed"
            })
            return self._complete_authentication(state, updates)
        else:
            # Pedir sección más específica
            message = """¿Podrías ser más específico con la sección?

**Ejemplos de secciones:**
• Caja (TPV, cobro)
• Carnicería  
• Pescadería
• Panadería
• Almacén
• Recepción
• Oficina
• Sala de descanso

¿En cuál de estas u otra sección ha ocurrido? 😊"""
            
            updates.update({
                "messages": state.get("messages", []) + [AIMessage(content=message)],
                "awaiting_user_input": True,
                "last_activity": datetime.now()
            })
            
            return Command(update=updates)
    
    def _complete_authentication(self, state: EroskiState, additional_updates: Optional[Dict] = None) -> Command:
        """Completar proceso de autenticación"""
        self.logger.info("✅ Proceso de autenticación completado")
        
        # Preparar mensaje de confirmación
        employee_name = state.get("employee_name", "Usuario")
        store_name = state.get("incident_store_name", "la tienda especificada")
        section = state.get("incident_section", "la sección indicada")
        
        confirmation_message = f"""✅ **Información recopilada correctamente**

👤 **Empleado:** {employee_name}
🏪 **Tienda:** {store_name}
📍 **Sección:** {section}

¡Perfecto! Ahora cuéntame **qué problema técnico** estás experimentando. 🔧

*(Puedes escribir "cancelar" en cualquier momento si cambias de opinión)*"""
        
        updates = {
            "authentication_stage": "completed",
            "awaiting_user_input": True,
            "messages": state.get("messages", []) + [AIMessage(content=confirmation_message)],
            "last_activity": datetime.now(),
            "ready_for_classification": True
        }
        
        if additional_updates:
            updates.update(additional_updates)
        
        return Command(update=updates)
    
    def _handle_cancellation_request(self, state: EroskiState) -> Command:
        """Manejar solicitud de cancelación"""
        self.logger.info("🚫 Usuario solicita cancelar")
        
        confirmation_message = """🤔 ¿Estás seguro de que quieres cancelar?

Si confirmas, cerraré esta conversación. Si cambias de opinión, simplemente escribe "no" y continuamos.

**Responde:**
• **"Sí"** para cancelar definitivamente
• **"No"** para continuar con la incidencia 😊"""
        
        return Command(update={
            "authentication_stage": "confirming_cancellation",
            "messages": state.get("messages", []) + [AIMessage(content=confirmation_message)],
            "awaiting_user_input": True,
            "last_activity": datetime.now()
        })
    
    def _request_email_again(self, state: EroskiState, analysis: UserResponseAnalysis) -> Command:
        """Solicitar email nuevamente"""
        attempts = state.get("attempts", 0)
        
        if attempts >= 3:
            message = """Parece que hay dificultades para obtener tu email corporativo.

📞 **¿Prefieres contactar directamente?**
• Soporte técnico: +34 946 211 000 (ext. 123)
• Email: soporte.tecnico@eroski.es

O puedes intentar una vez más con tu **email completo de Eroski** (que termine en @eroski.es) 😊"""
        else:
            message = analysis.next_message or "Por favor, proporciona tu email corporativo de Eroski (debe terminar en @eroski.es). 😊"
        
        return Command(update={
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "attempts": attempts + 1,
            "last_activity": datetime.now()
        })
    
    def _continue_data_collection(self, state: EroskiState, analysis: UserResponseAnalysis) -> Command:
        """Continuar recopilación de datos según análisis LLM"""
        message = analysis.next_message or "¿Podrías proporcionar más información, por favor?"
        
        return Command(update={
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "attempts": state.get("attempts", 0) + 1,
            "last_activity": datetime.now()
        })
    
    def _escalate_max_attempts(self, state: EroskiState) -> Command:
        """Escalar por máximo de intentos"""
        message = f"""🔼 **Derivando a especialista**

Hemos intentado recopilar la información {self.max_attempts} veces. Te conectaré directamente con un especialista.

📞 **Contacto directo:**
• Soporte técnico: +34 946 211 000 (ext. 123)
• Email: soporte.tecnico@eroski.es

**Datos de la sesión:** {state.get('session_id', 'N/A')}

¡Gracias por tu paciencia! 🙏"""
        
        return Command(update={
            "escalation_needed": True,
            "escalation_reason": f"Máximo de intentos alcanzado en autenticación ({self.max_attempts})",
            "escalation_level": "technical_support",
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": False,
            "last_activity": datetime.now()
        })
    
    def _handle_inconsistent_state(self, state: EroskiState) -> Command:
        """Manejar estado inconsistente"""
        self.logger.warning("⚠️ Estado inconsistente detectado")
        
        return Command(update={
            "escalation_needed": True,
            "escalation_reason": "Estado inconsistente en proceso de autenticación",
            "messages": state.get("messages", []) + [AIMessage(content="Ha ocurrido un error técnico. Te derivaré a un especialista.")],
            "awaiting_user_input": False,
            "last_activity": datetime.now()
        })
    
    def _handle_authentication_error(self, state: EroskiState, error: str) -> Command:
        """Manejar errores de autenticación"""
        self.logger.error(f"💥 Error en autenticación: {error}")
        
        message = """❌ **Error técnico**

Ha ocurrido un problema durante la autenticación.

📞 **Contacta directamente:**
• Soporte técnico: +34 946 211 000 (ext. 123)
• Email: soporte.tecnico@eroski.es

**Código de error:** AUTH_ERROR

¡Disculpa las molestias! 🙏"""
        
        return Command(update={
            "error_count": state.get("error_count", 0) + 1,
            "last_error": error,
            "escalation_needed": True,
            "escalation_reason": f"Error técnico en autenticación: {error}",
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": False,
            "last_activity": datetime.now()
        })

# =====================================================
# Wrapper para LangGraph
# =====================================================

async def authenticate_employee_node_complete(state: EroskiState) -> Command:
    """
    Wrapper function para el nodo de autenticación completo.
    """
    node = AuthenticateEmployeeNodeComplete()
    return await node.execute(state)