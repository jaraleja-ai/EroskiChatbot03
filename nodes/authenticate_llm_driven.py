# =====================================================
# nodes/authenticate_llm_driven.py - Nodo de Autenticación LLM-Driven
# =====================================================
"""
Nodo de autenticación inteligente dirigido completamente por LLM.

FUNCIONALIDAD NUEVA:
1. LLM dirige toda la conversación desde el primer mensaje
2. Recopila datos de forma natural y eficiente
3. Maneja información múltiple en un solo intercambio
4. Busca en BD automáticamente cuando detecta email
5. Adaptación contextual inteligente
6. Fallback robusto en caso de errores
"""

from typing import Dict, Any, Optional, List, Union
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging
import json
import re

from models.eroski_state import EroskiState
from nodes.base_node import BaseNode
from utils.eroski_database_auth import EroskiEmployeeDatabaseAuth
from utils.llm.providers import get_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field


# =============================================================================
# MODELOS DE DATOS
# =============================================================================

class ConversationDecision(BaseModel):
    """Decisión del LLM sobre qué hacer en la conversación"""
    
    # Estado de la recopilación
    is_complete: bool = Field(description="Si tiene todos los datos necesarios")
    should_search_database: bool = Field(description="Si debe buscar en base de datos")
    wants_to_cancel: bool = Field(description="Si el usuario quiere cancelar")
    
    # Datos extraídos del mensaje actual
    extracted_data: Dict[str, Any] = Field(description="Datos extraídos del mensaje")
    
    # Próxima acción
    next_action: str = Field(description="Próxima acción: collect_data, search_db, complete, cancel, clarify")
    message_to_user: str = Field(description="Mensaje natural para el usuario")
    
    # Información de estado
    missing_fields: List[str] = Field(description="Campos que aún faltan", default=[])
    confidence_level: float = Field(description="Confianza en la extracción (0-1)", default=0.0)


# =============================================================================
# NODO PRINCIPAL LLM-DRIVEN
# =============================================================================

class LLMDrivenAuthenticateNode(BaseNode):
    """
    Nodo de autenticación completamente dirigido por LLM.
    
    CARACTERÍSTICAS:
    - Conversación natural desde el primer intercambio
    - Recopilación inteligente de múltiples datos por mensaje
    - Búsqueda automática en BD cuando detecta email
    - Sin etapas fijas - flujo adaptativo
    - Fallback robusto ante errores
    """
    
    def __init__(self):
        super().__init__("authenticate")
        self.max_attempts = 5  # Menos intentos porque es más eficiente
        self.db_auth = EroskiEmployeeDatabaseAuth()
        self.llm = get_llm()
        
        # Parser para decisiones LLM
        self.parser = JsonOutputParser(pydantic_object=ConversationDecision)
        
        # Sistema principal de conversación
        self.conversation_prompt = self._build_conversation_prompt()
        
        # Campos requeridos para completar autenticación
        self.required_fields = {
            "name": "Nombre completo del empleado",
            "email": "Email (no obligatorio que sea @eroski.es)",
            "store_name": "Nombre de la tienda donde trabaja",
            "section": "Sección específica donde ocurrió la incidencia"
        }
    
    def get_required_fields(self) -> List[str]:
        return ["messages"]
    
    def get_actor_description(self) -> str:
        return "Recopilo datos de empleados usando conversación natural dirigida por IA"
    
    async def execute(self, state: EroskiState) -> Command:
        """
        Ejecutar autenticación LLM-driven.
        
        Args:
            state: Estado actual del workflow
            
        Returns:
            Command con la siguiente acción
        """

        self.logger.info("🏅"*50)
        self.logger.info(f"🌄JGL entrando en {self.__class__.__name__}")
        try:
            self.logger.info("🤖 Iniciando autenticación LLM-driven")
            
            # 1. Verificar si ya está completo
            if self._is_authentication_complete(state):
                return self._proceed_to_next_step(state)
            
            # 2. Primera visita - mensaje inteligente de bienvenida
            if self._is_first_visit(state):
                return await self._start_intelligent_conversation(state)
            
            # 3. Continuar conversación dirigida por LLM
            return await self._continue_llm_conversation(state)
            
        except Exception as e:
            self.logger.error(f"❌ Error en autenticación LLM: {e}")
            return await self._handle_llm_error(state, str(e))
    
    # =========================================================================
    # LÓGICA PRINCIPAL DE CONVERSACIÓN
    # =========================================================================
    
    async def _start_intelligent_conversation(self, state: EroskiState) -> Command:
        """Iniciar conversación inteligente"""
        
        welcome_message = """¡Hola! 👋 Soy tu asistente de incidencias técnicas de Eroski.

Para ayudarte de la manera más eficiente, necesito conocer algunos datos:

🔹 **Tu nombre completo**
🔹 **Tu email** (no tiene que ser necesariamente @eroski.es)  
🔹 **Nombre de tu tienda** (ej: "Eroski Bilbao Centro")
🔹 **Sección donde ocurrió el problema** (ej: "Carnicería", "Caja", "Almacén")

Puedes darme **toda la información de una vez** o por partes, como prefieras. 😊

**Ejemplo:** *"Hola, soy María García, mi email es maria@eroski.es, trabajo en Eroski Madrid Centro en la sección de panadería"*

*(Escribe "cancelar" si cambias de opinión)*"""
        
        return Command(update={
            "current_node": "authenticate",
            "messages": state.get("messages", []) + [AIMessage(content=welcome_message)],
            "awaiting_user_input": True,
            "attempts": 1,
            "auth_data_collected": {},
            "auth_conversation_started": True,
            "last_activity": datetime.now()
        })
    
    async def _continue_llm_conversation(self, state: EroskiState) -> Command:
        """Continuar conversación dirigida por LLM"""
        
        try:
            # Obtener decisión del LLM
            decision = await self._get_llm_decision(state)
            
            # Ejecutar la acción decidida por el LLM
            return await self._execute_llm_decision(state, decision)
            
        except Exception as e:
            self.logger.error(f"❌ Error en conversación LLM: {e}")
            return await self._fallback_to_manual_mode(state)
    
    async def _get_llm_decision(self, state: EroskiState) -> ConversationDecision:
        """Obtener decisión inteligente del LLM"""
        
        # Preparar contexto completo
        context = self._build_conversation_context(state)
        
        # Formatear prompt
        formatted_prompt = self.conversation_prompt.format(**context)
        
        # Invocar LLM
        self.logger.debug("🤖 Solicitando decisión a LLM...")
        response = await self.llm.ainvoke(formatted_prompt)
        
        # Parsear respuesta
        try:
            decision = self.parser.parse(response.content)
            self.logger.info(f"🎯 LLM decidió: {decision.next_action}")
            return decision
            
        except Exception as parse_error:
            self.logger.warning(f"⚠️ Error parseando LLM, usando fallback: {parse_error}")
            return self._create_fallback_decision(state)
    
    async def _execute_llm_decision(self, state: EroskiState, decision: ConversationDecision) -> Command:
        """Ejecutar la decisión tomada por el LLM"""
        
        # Actualizar datos recopilados
        current_data = state.get("auth_data_collected", {})
        current_data.update(decision.extracted_data)
        
        base_update = {
            "auth_data_collected": current_data,
            "attempts": state.get("attempts", 0) + 1,
            "last_activity": datetime.now(),
            "messages": state.get("messages", []) + [AIMessage(content=decision.message_to_user)]
        }
        
        # Ejecutar acción específica
        if decision.wants_to_cancel:
            return await self._handle_cancellation(state, decision)
            
        elif decision.next_action == "search_db":
            return await self._search_database_and_continue(state, decision, base_update)
            
        elif decision.next_action == "complete":
            return self._complete_authentication(state, decision, base_update)
            
        elif decision.next_action == "collect_data":
            return self._continue_data_collection(state, decision, base_update)
            
        else:  # clarify or unknown
            return self._request_clarification(state, decision, base_update)
    
    # =========================================================================
    # ACCIONES ESPECÍFICAS
    # =========================================================================
    
    async def _search_database_and_continue(self, state: EroskiState, decision: ConversationDecision, base_update: Dict) -> Command:
        """Buscar en base de datos y continuar conversación"""
        
        email = decision.extracted_data.get("email")
        if not email:
            self.logger.warning("⚠️ LLM decidió buscar en BD pero no hay email")
            return self._continue_data_collection(state, decision, base_update)
        
        # Buscar en base de datos
        db_result = await self._search_employee_database(email)
        
        if db_result["found"]:
            # Usuario encontrado - actualizar con datos de BD
            employee = db_result["employee"]
            
            # Combinar datos de BD con datos recopilados
            enhanced_data = {
                **base_update["auth_data_collected"],
                "name": employee.get("name", decision.extracted_data.get("name")),
                "email": email,
                "employee_id": employee.get("id"),
                "store_name": employee.get("store_name"),
                "registered_store": employee.get("store_name"),
                "department": employee.get("department"),
                "found_in_database": True
            }
            
            # Mensaje personalizado con datos de BD
            enhanced_message = f"""¡Perfecto! Te he encontrado en nuestro sistema. 👍

✅ **Datos confirmados:**
👤 {employee.get('name')}
📧 {email}
🏪 Tienda registrada: {employee.get('store_name')}

{decision.message_to_user}"""
            
            base_update.update({
                "auth_data_collected": enhanced_data,
                "authenticated": True,
                "employee_data": employee,
                "messages": state.get("messages", []) + [AIMessage(content=enhanced_message)]
            })
        
        else:
            # Usuario no encontrado - continuar recopilación manual
            base_update["auth_data_collected"]["found_in_database"] = False
        
        # Verificar si ya tenemos todos los datos
        if self._has_all_required_data(base_update["auth_data_collected"]):
            return self._complete_authentication(state, decision, base_update)
        else:
            return Command(update=base_update)
    
    def _complete_authentication(self, state: EroskiState, decision: ConversationDecision, base_update: Dict) -> Command:
        """Completar proceso de autenticación"""
        
        collected_data = base_update["auth_data_collected"]
        
        # Mensaje de confirmación final
        confirmation_message = f"""✅ **¡Información recopilada correctamente!**

👤 **Empleado:** {collected_data.get('name')}
📧 **Email:** {collected_data.get('email')}
🏪 **Tienda:** {collected_data.get('store_name')}
📍 **Sección:** {collected_data.get('section')}

🔧 **Ahora cuéntame:** ¿Qué problema técnico estás experimentando?

*(Describe el problema con el mayor detalle posible)*"""
        
        # Preparar datos finales
        final_update = {
            **base_update,
            "authentication_stage": "completed",
            "datos_usuario_completos": True,
            "employee_email": collected_data.get("email"),
            "employee_name": collected_data.get("name"),
            "incident_store_name": collected_data.get("store_name"),
            "incident_section": collected_data.get("section"),
            "ready_for_classification": True,
            "messages": state.get("messages", []) + [AIMessage(content=confirmation_message)]
        }
        
        # Si está en BD, agregar datos adicionales
        if collected_data.get("found_in_database"):
            final_update.update({
                "employee_id": collected_data.get("employee_id"),
                "store_id": collected_data.get("store_id"),
                "department": collected_data.get("department")
            })
        
        self.logger.info(f"✅ Autenticación completada para: {collected_data.get('name')}")
        return Command(update=final_update)
    
    def _continue_data_collection(self, state: EroskiState, decision: ConversationDecision, base_update: Dict) -> Command:
        """Continuar recopilando datos"""
        
        base_update["awaiting_user_input"] = True
        return Command(update=base_update)
    
    async def _handle_cancellation(self, state: EroskiState, decision: ConversationDecision) -> Command:
        """Manejar solicitud de cancelación"""
        
        cancellation_message = """🤔 Entiendo que quieres cancelar.

¿Estás seguro? Si confirmas, cerraré esta conversación.

**Responde:**
• **"Sí"** para cancelar definitivamente
• **"No"** para continuar con tu consulta 😊"""
        
        return Command(update={
            "awaiting_cancellation_confirmation": True,
            "messages": state.get("messages", []) + [AIMessage(content=cancellation_message)],
            "awaiting_user_input": True,
            "last_activity": datetime.now()
        })
    
    def _request_clarification(self, state: EroskiState, decision: ConversationDecision, base_update: Dict) -> Command:
        """Solicitar clarificación al usuario"""
        
        base_update["awaiting_user_input"] = True
        return Command(update=base_update)
    
    # =========================================================================
    # FUNCIONES AUXILIARES
    # =========================================================================
    
    def _build_conversation_context(self, state: EroskiState) -> Dict[str, str]:
        """Construir contexto completo para el LLM"""
        
        # Obtener último mensaje del usuario
        user_message = self._get_last_user_message(state)
        
        # Obtener datos ya recopilados
        collected_data = state.get("auth_data_collected", {})
        
        # Construir historial de conversación
        conversation_history = self._get_conversation_summary(state)
        
        # Determinar qué campos faltan
        missing_fields = self._get_missing_fields(collected_data)
        
        return {
            "user_message": user_message,
            "collected_data": json.dumps(collected_data, indent=2, ensure_ascii=False),
            "conversation_history": conversation_history,
            "missing_fields": ", ".join(missing_fields),
            "required_fields_desc": json.dumps(self.required_fields, indent=2, ensure_ascii=False),
            "attempt_number": state.get("attempts", 0)
        }
    
    def _get_conversation_summary(self, state: EroskiState) -> str:
        """Obtener resumen de la conversación"""
        
        messages = state.get("messages", [])
        if len(messages) <= 2:
            return "Conversación recién iniciada"
        
        # Obtener últimos 3 intercambios
        recent_messages = messages[-6:]  # 3 intercambios = 6 mensajes
        
        summary_parts = []
        for i, msg in enumerate(recent_messages):
            if isinstance(msg, HumanMessage):
                summary_parts.append(f"Usuario: {msg.content[:100]}")
            elif isinstance(msg, AIMessage):
                summary_parts.append(f"Asistente: {msg.content[:100]}")
        
        return " | ".join(summary_parts)
    
    def _get_missing_fields(self, collected_data: Dict) -> List[str]:
        """Determinar qué campos aún faltan"""
        
        missing = []
        for field, description in self.required_fields.items():
            if not collected_data.get(field):
                missing.append(field)
        
        return missing
    
    def _has_all_required_data(self, collected_data: Dict) -> bool:
        """Verificar si tenemos todos los datos requeridos"""
        
        return all(collected_data.get(field) for field in self.required_fields.keys())
    
    def _is_authentication_complete(self, state: EroskiState) -> bool:
        """Verificar si la autenticación ya está completa"""
        
        return (
            state.get("authentication_stage") == "completed" and
            state.get("datos_usuario_completos") and
            state.get("employee_name") and
            state.get("incident_store_name") and
            state.get("incident_section")
        )
    
    def _is_first_visit(self, state: EroskiState) -> bool:
        """Verificar si es la primera visita al nodo"""
        
        return not state.get("auth_conversation_started", False)
    
    def _proceed_to_next_step(self, state: EroskiState) -> Command:
        """Proceder al siguiente paso cuando la autenticación está completa"""
        
        self.logger.info("✅ Autenticación ya completa, procediendo a clasificación")
        
        return Command(update={
            "current_node": "authenticate",
            "last_activity": datetime.now()
        })
    
    # =========================================================================
    # BÚSQUEDA EN BASE DE DATOS
    # =========================================================================
    
    async def _search_employee_database(self, email: str) -> Dict[str, Any]:
        """Buscar empleado en base de datos"""
        
        try:
            self.logger.info(f"🔍 Buscando empleado en BD: {email}")
            
            employee_data = await self.db_auth.get_employee_by_email(email)
            
            if employee_data:
                self.logger.info(f"✅ Empleado encontrado: {employee_data.get('name')}")
                return {"found": True, "employee": employee_data}
            else:
                self.logger.info("❌ Empleado no encontrado en BD")
                return {"found": False}
                
        except Exception as e:
            self.logger.error(f"❌ Error buscando en BD: {e}")
            return {"found": False, "error": str(e)}
    
    # =========================================================================
    # MANEJO DE ERRORES Y FALLBACKS
    # =========================================================================
    
    async def _handle_llm_error(self, state: EroskiState, error_message: str) -> Command:
        """Manejar errores del LLM"""
        
        self.logger.error(f"❌ Error LLM en autenticación: {error_message}")
        
        # Fallback a modo manual
        return await self._fallback_to_manual_mode(state)
    
    async def _fallback_to_manual_mode(self, state: EroskiState) -> Command:
        """Fallback a modo manual cuando LLM falla"""
        
        self.logger.warning("⚠️ Activando modo fallback manual")
        
        fallback_message = """Disculpa, he tenido un problema técnico momentáneo. 😅

Vamos paso a paso. ¿Podrías decirme tu **nombre completo**?"""
        
        return Command(update={
            "fallback_mode": True,
            "fallback_stage": "requesting_name",
            "messages": state.get("messages", []) + [AIMessage(content=fallback_message)],
            "awaiting_user_input": True,
            "attempts": state.get("attempts", 0) + 1,
            "last_activity": datetime.now()
        })
    
    def _create_fallback_decision(self, state: EroskiState) -> ConversationDecision:
        """Crear decisión de fallback cuando el parser falla"""
        
        # Análisis simple basado en palabras clave
        user_message = self._get_last_user_message(state).lower()
        
        # Detectar cancelación
        if any(word in user_message for word in ["cancelar", "salir", "no quiero", "adiós"]):
            return ConversationDecision(
                is_complete=False,
                wants_to_cancel=True,
                extracted_data={},
                next_action="cancel",
                message_to_user="Entiendo que quieres cancelar. ¿Estás seguro?"
            )
        
        # Detectar email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', user_message)
        if email_match:
            return ConversationDecision(
                is_complete=False,
                should_search_database=True,
                extracted_data={"email": email_match.group()},
                next_action="search_db",
                message_to_user="Perfecto, déjame buscar tu información..."
            )
        
        # Por defecto, continuar recopilando
        return ConversationDecision(
            is_complete=False,
            extracted_data={},
            next_action="collect_data",
            message_to_user="Gracias por la información. ¿Podrías darme más detalles?"
        )
    
    def _get_last_user_message(self, state: EroskiState) -> str:
        """Obtener último mensaje del usuario"""
        
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return msg.content.strip()
        return ""
    
    # =========================================================================
    # PROMPT DEL LLM CONVERSACIONAL
    # =========================================================================
    
    def _build_conversation_prompt(self) -> PromptTemplate:
        """Construir prompt principal para el LLM conversacional"""
        
        return PromptTemplate(
            template="""Eres un asistente experto de Eroski especializado en recopilar información de empleados de forma natural y eficiente.

OBJETIVO PRINCIPAL:
Recopilar estos datos de manera conversacional:
{required_fields_desc}

DATOS YA RECOPILADOS:
{collected_data}

HISTORIAL DE CONVERSACIÓN:
{conversation_history}

MENSAJE ACTUAL DEL USUARIO:
"{user_message}"

CAMPOS QUE AÚN FALTAN:
{missing_fields}

INTENTO NÚMERO: {attempt_number}

INSTRUCCIONES PARA TU ANÁLISIS:

1. **DETECTAR CANCELACIÓN**: Si el usuario dice palabras como "cancelar", "salir", "no quiero", "adiós", marcar wants_to_cancel=true

2. **EXTRAER INFORMACIÓN**: Del mensaje actual, extraer TODA la información disponible:
   - Nombres completos (Juan Pérez, María García)
   - Emails (cualquier formato, no solo @eroski.es)
   - Nombres de tienda (Eroski + ubicación, o códigos)
   - Secciones (carnicería, caja, panadería, almacén, etc.)

3. **DECIDIR PRÓXIMA ACCIÓN**:
   - Si extraes un email → next_action="search_db" (buscar en base de datos)
   - Si tienes TODOS los campos requeridos → next_action="complete"
   - Si faltan campos → next_action="collect_data"
   - Si el mensaje es confuso → next_action="clarify"

4. **GENERAR MENSAJE NATURAL**:
   - Si extraes email: "Perfecto [nombre], déjame buscar tu información..."
   - Si tienes todo: "¡Excelente! Ya tengo todos tus datos..."
   - Si falta info: "Gracias [nombre/usuario], ¿podrías decirme también [campo específico que falta]?"
   - Si es confuso: "No estoy seguro de entender, ¿podrías repetir [lo que necesitas]?"

5. **SER EFICIENTE**: 
   - Extrae MÚLTIPLE información por mensaje
   - No preguntes datos que ya tienes
   - Personaliza usando el nombre si lo sabes

EJEMPLOS DE RESPUESTAS:

Usuario: "Hola, soy Juan Pérez, mi email es juan@eroski.es, trabajo en Eroski Bilbao Centro"
→ Extraer: name="Juan Pérez", email="juan@eroski.es", store_name="Eroski Bilbao Centro"
→ next_action="search_db"
→ mensaje="¡Hola Juan! Déjame buscar tu información... ¿En qué sección específica ocurrió el problema?"

Usuario: "María García, maria@empresa.com, Eroski Madrid, panadería"
→ Extraer: name="María García", email="maria@empresa.com", store_name="Eroski Madrid", section="panadería"
→ next_action="complete"
→ mensaje="¡Perfecto María! Ya tengo toda tu información..."

Usuario: "trabajo en caja en Eroski"
→ Extraer: section="caja", store_name="Eroski"
→ next_action="collect_data"
→ mensaje="Entiendo que trabajas en caja. ¿Podrías decirme tu nombre y en qué Eroski específico?"

RESPONDE ÚNICAMENTE CON JSON VÁLIDO:

{{
    "is_complete": false,
    "should_search_database": false,
    "wants_to_cancel": false,
    "extracted_data": {{}},
    "next_action": "collect_data",
    "message_to_user": "Mensaje natural aquí",
    "missing_fields": [],
    "confidence_level": 0.8
}}""",
            input_variables=["user_message", "collected_data", "conversation_history", "missing_fields", "required_fields_desc", "attempt_number"]
        )


# =============================================================================
# FUNCIÓN PARA CREAR INSTANCIA
# =============================================================================

async def llm_driven_authenticate_node(state: EroskiState) -> Command:
    """
    Crear instancia del nodo de autenticación LLM-driven.
    
    Returns:
        Instancia configurada del nodo
    """
    
    node = LLMDrivenAuthenticateNode()
    return await node.execute(state)

