# =====================================================
# nodes/recopilar_input_usuario.py - NODO DE INTERRUPCIÓN HÍBRIDO
# =====================================================
from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command

from .base_node import BaseNode, ActorDecision
from utils.llm.providers import get_llm


class RecopilarInputUsuarioNode(BaseNode):
    """
    🎭 ACTOR HÍBRIDO: Gestor especializado de interrupciones de usuario
    
    RESPONSABILIDADES DEL ACTOR:
    - ✅ Detectar cuándo se necesita input del usuario
    - ✅ Generar mensajes contextuales apropiados
    - ✅ Establecer flags correctos para interrumpir el flujo
    - ✅ Mantener contexto para resumir después del input
    - ✅ Gestionar transición desde "__interrupt__" hacia nodos válidos
    
    PRINCIPIOS ACTOR:
    - 🎯 Autonomía: Decide cómo solicitar input según contexto
    - 🔒 Encapsulación: Maneja toda la lógica de interrupción internamente
    - 📡 Señalización: Comunica claramente al router sus intenciones
    - 🎪 Responsabilidad única: Solo gestiona interrupciones de usuario
    
    COMPATIBILIDAD LANGGRAPH:
    - ✅ Usa Command para actualizaciones de estado
    - ✅ Se integra con el sistema de interrupciones "__interrupt__"
    - ✅ Compatible con el routing híbrido del workflow
    """
    
    def __init__(self):
        super().__init__("RecopilarInputUsuario", timeout_seconds=30)
        self.llm = get_llm()
    
    def get_required_fields(self) -> List[str]:
        """Campos mínimos requeridos para funcionar"""
        return ["messages"]
    
    def get_actor_description(self) -> str:
        """Descripción de las responsabilidades de este actor"""
        return (
            "Actor especializado en gestionar interrupciones del flujo para "
            "recopilar input del usuario de forma contextual y eficiente"
        )
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """
        🎯 EJECUCIÓN PRINCIPAL: Analizar contexto y gestionar interrupción
        
        Este actor siempre interrumpe el flujo y solicita input del usuario
        de manera contextual basada en el estado actual.
        """
        
        try:
            self.logger.info("⏸️ 🎭 ACTOR iniciando gestión de interrupción")
            
            # 🔍 ANÁLISIS AUTÓNOMO: ¿Qué necesitamos del usuario?
            input_context = await self._analyze_input_needs(state)
            
            # 🎨 GENERACIÓN AUTÓNOMA: Crear mensaje contextual
            user_message = await self._generate_contextual_message(input_context, state)
            
            # 🔧 DECISIÓN AUTÓNOMA: Configurar interrupción
            interruption_config = self._configure_interruption(input_context, state)
            
            # 📡 SEÑALIZACIÓN: Comunicar intención de interrupción al router
            result = self.signal_need_input(
                state=state,
                request_message=user_message,
                context=interruption_config
            )
            
            # 🧹 ASEGURAR LIMPIEZA para evitar loops al resumir
            # La señal "_actor_decision": "need_input" debe limpiarse después del router
            self.logger.info("⏸️ Interrupción configurada, devolviendo control al usuario")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error en actor de interrupción: {e}")
            return await self._handle_interruption_error(state, e)
    
    async def _analyze_input_needs(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        🧠 ANÁLISIS INTELIGENTE: Determinar qué input necesitamos
        
        El actor analiza el estado actual y decide autónomamente
        qué tipo de información necesita solicitar al usuario.
        """
        
        # Obtener contexto de la señal original
        original_context = state.get("_input_context", {})
        waiting_for = original_context.get("waiting_for", [])
        request_type = original_context.get("type", "general")
        
        # Análisis del estado actual
        datos_usuario_completos = state.get("datos_usuario_completos", False)
        nombre = state.get("nombre", "")
        email = state.get("email", "")
        descripcion_problema = state.get("descripcion_problema", "")
        
        # 🎯 DECISIÓN AUTÓNOMA: ¿Qué falta?
        missing_fields = []
        input_category = "general"
        priority_level = "normal"
        
        if not datos_usuario_completos:
            if not nombre or len(nombre.strip()) < 2:
                missing_fields.append("nombre")
            if not email or "@" not in email:
                missing_fields.append("email")
            input_category = "identificacion"
            priority_level = "high"
        
        elif not descripcion_problema:
            missing_fields.append("descripcion_problema")
            input_category = "incidencia"
            priority_level = "high"
        
        elif waiting_for:
            missing_fields = waiting_for
            input_category = request_type
        
        context = {
            "missing_fields": missing_fields,
            "category": input_category,
            "priority": priority_level,
            "original_context": original_context,
            "analysis_timestamp": self._get_timestamp(),
            "user_completion_status": {
                "datos_completos": datos_usuario_completos,
                "nombre_presente": bool(nombre),
                "email_presente": bool(email),
                "descripcion_presente": bool(descripcion_problema)
            }
        }
        
        self.logger.info(f"🧠 Análisis completado: {missing_fields} ({input_category})")
        return context
    
    async def _generate_contextual_message(
        self, 
        input_context: Dict[str, Any], 
        state: Dict[str, Any]
    ) -> str:
        """
        🎨 GENERACIÓN INTELIGENTE: Crear mensaje contextual para el usuario
        
        El actor genera un mensaje natural y específico basado en
        lo que necesita y el contexto de la conversación.
        """
        
        missing_fields = input_context.get("missing_fields", [])
        category = input_context.get("category", "general")
        
        # Obtener contexto de la conversación
        messages = state.get("messages", [])
        last_user_message = ""
        if messages:
            for msg in reversed(messages):
                if hasattr(msg, 'type') and msg.type == "human":
                    last_user_message = msg.content
                    break
        
        # 🎯 GENERACIÓN CONTEXTUAL BASADA EN CATEGORÍA
        if category == "identificacion":
            return await self._generate_identification_message(missing_fields, state)
        
        elif category == "incidencia":
            return await self._generate_incident_message(missing_fields, state)
        
        elif category == "confirmacion":
            return await self._generate_confirmation_message(input_context, state)
        
        else:
            # Mensaje general con IA
            return await self._generate_ai_message(input_context, state, last_user_message)
    
    async def _generate_identification_message(
        self, 
        missing_fields: List[str], 
        state: Dict[str, Any]
    ) -> str:
        """Generar mensaje específico para identificación de usuario"""
        
        nombre = state.get("nombre", "")
        email = state.get("email", "")
        
        if "nombre" in missing_fields and "email" in missing_fields:
            return (
                "¡Hola! Para ayudarte mejor, necesito conocerte un poco. "
                "¿Podrías decirme tu nombre completo y tu email?"
            )
        
        elif "nombre" in missing_fields:
            return (
                f"Perfecto, ya tengo tu email ({email}). "
                "Ahora, ¿cuál es tu nombre completo?"
            )
        
        elif "email" in missing_fields:
            return (
                f"Hola {nombre}! Para continuar, necesito tu dirección de email. "
                "¿Podrías proporcionármela?"
            )
        
        else:
            return "Necesito completar tu información para continuar."
    
    async def _generate_incident_message(
        self, 
        missing_fields: List[str], 
        state: Dict[str, Any]
    ) -> str:
        """Generar mensaje específico para detalles de incidencia"""
        
        nombre = state.get("nombre", "Usuario")
        
        if "descripcion_problema" in missing_fields:
            return (
                f"Perfecto {nombre}, ya tienes acceso al sistema. "
                "Ahora cuéntame, ¿qué problema técnico estás experimentando? "
                "Por favor describe los detalles para poder ayudarte mejor."
            )
        
        elif "categoria" in missing_fields:
            return (
                "Entiendo tu problema. Para darte la mejor solución, "
                "¿podrías decirme si se trata de un problema de red, "
                "software, hardware o acceso?"
            )
        
        else:
            return "Necesito más detalles sobre tu incidencia para poder ayudarte."
    
    async def _generate_confirmation_message(
        self, 
        input_context: Dict[str, Any], 
        state: Dict[str, Any]
    ) -> str:
        """Generar mensaje de confirmación"""
        
        confirmation_data = input_context.get("confirmation_data", {})
        
        return (
            "Por favor confirma si la información es correcta:\n"
            f"- Nombre: {confirmation_data.get('nombre', 'N/A')}\n"
            f"- Email: {confirmation_data.get('email', 'N/A')}\n"
            f"- Problema: {confirmation_data.get('descripcion', 'N/A')[:100]}...\n\n"
            "¿Es correcto? (Sí/No)"
        )
    
    async def _generate_ai_message(
        self, 
        input_context: Dict[str, Any], 
        state: Dict[str, Any], 
        last_user_message: str
    ) -> str:
        """Generar mensaje usando IA para casos complejos"""
        
        try:
            prompt = f"""
            Contexto: Eres un asistente que necesita información adicional del usuario.
            
            Estado actual:
            - Datos faltantes: {input_context.get('missing_fields', [])}
            - Categoría: {input_context.get('category', 'general')}
            - Último mensaje del usuario: {last_user_message[:200]}
            
            Genera un mensaje natural y conciso (máximo 2 frases) pidiendo
            la información que falta. Sé amigable y específico.
            """
            
            response = await self.llm.ainvoke(prompt)
            return response.content.strip()
            
        except Exception as e:
            self.logger.warning(f"⚠️ Error generando mensaje IA: {e}")
            return (
                "Disculpa, necesito información adicional para continuar. "
                "¿Podrías proporcionarme los datos que faltan?"
            )
    
    def _configure_interruption(
        self, 
        input_context: Dict[str, Any], 
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        🔧 CONFIGURACIÓN INTELIGENTE: Preparar configuración de interrupción
        
        El actor decide autónomamente cómo configurar la interrupción
        para optimizar la experiencia del usuario y la continuación del flujo.
        """
        
        # Determinar nodo de continuación
        category = input_context.get("category", "general")
        resume_node = "identificar_usuario"  # Default
        
        if category == "identificacion":
            resume_node = "identificar_usuario"
        elif category == "incidencia":
            resume_node = "procesar_incidencia"
        elif category == "confirmacion":
            resume_node = "finalizar_ticket"
        
        # Configuración de la interrupción
        config = {
            "waiting_for": input_context.get("missing_fields", []),
            "type": category,
            "actor": self.name,
            "resume_node": resume_node,
            "priority": input_context.get("priority", "normal"),
            "timeout_seconds": 300,  # 5 minutos timeout
            "retry_attempts": 3,
            "validation_rules": self._get_validation_rules(category),
            "next_action": "process_input",
            "interruption_id": f"{category}_{self._get_timestamp()}",
            "original_state_snapshot": {
                "nombre": state.get("nombre", ""),
                "email": state.get("email", ""),
                "datos_usuario_completos": state.get("datos_usuario_completos", False)
            }
        }
        
        self.logger.info(f"🔧 Configuración de interrupción: {category} → {resume_node}")
        return config
    
    def _get_validation_rules(self, category: str) -> Dict[str, Any]:
        """Obtener reglas de validación según la categoría"""
        
        rules = {
            "identificacion": {
                "nombre": {"min_length": 2, "max_length": 100, "required": True},
                "email": {"format": "email", "required": True}
            },
            "incidencia": {
                "descripcion_problema": {"min_length": 10, "max_length": 1000, "required": True}
            },
            "confirmacion": {
                "respuesta": {"options": ["si", "sí", "yes", "no"], "required": True}
            }
        }
        
        return rules.get(category, {})
    
    async def _handle_interruption_error(
        self, 
        state: Dict[str, Any], 
        error: Exception
    ) -> Command:
        """
        🚨 MANEJO DE ERRORES: Fallback cuando algo sale mal
        
        El actor maneja errores de forma autónoma y proporciona
        una experiencia de usuario degradada pero funcional.
        """
        
        self.logger.error(f"🚨 Error en gestión de interrupción: {error}")
        
        # Mensaje de fallback simple
        fallback_message = (
            "Disculpa, hay un problema técnico temporal. "
            "¿Podrías volver a proporcionar la información que necesito?"
        )
        
        # Configuración mínima de interrupción
        fallback_config = {
            "waiting_for": ["input_general"],
            "type": "fallback",
            "actor": self.name,
            "resume_node": "identificar_usuario",
            "priority": "high",
            "error_recovery": True,
            "original_error": str(error)
        }
        
        return self.signal_need_input(
            state=state,
            request_message=fallback_message,
            context=fallback_config
        )
    
    def _get_timestamp(self) -> str:
        """Obtener timestamp actual"""
        from datetime import datetime
        return datetime.now().isoformat()


# =====================================================
# WRAPPER FUNCTION PARA LANGGRAPH
# =====================================================
async def recopilar_input_usuario(state: Dict[str, Any]) -> Command:
    """
    🎭 Función wrapper para integración con LangGraph
    
    Esta función actúa como puente entre el sistema de nodos de LangGraph
    y nuestro actor híbrido de gestión de interrupciones.
    
    Args:
        state: Estado actual del grafo de LangGraph
        
    Returns:
        Command con las actualizaciones necesarias para interrumpir el flujo
        y solicitar input del usuario de forma contextual
    """
    
    # Crear e inicializar el actor
    actor = RecopilarInputUsuarioNode()
    
    # Ejecutar con monitoreo y manejo de errores
    try:
        return await actor.execute(state)
    except Exception as e:
        # Fallback de emergencia
        actor.logger.error(f"💥 FALLO CRÍTICO en recopilar_input_usuario: {e}")
        
        return Command(update={
            "messages": [AIMessage(content="Necesito más información para continuar.")],
            "requires_user_input": True,
            "workflow_state": {
                "waiting_for_user": True,
                "last_node": "recopilar_input_usuario",
                "resume_node": "identificar_usuario",
                "error_recovery": True
            },
            "pending_questions": ["Proporciona la información que falta."],
            "interruption_reason": "critical_error"
        })


# =====================================================
# ACTOR COMPLEMENTARIO: PROCESADOR DE INPUT RECIBIDO
# =====================================================
class ProcesarInputRecibidoNode(BaseNode):
    """
    🎭 ACTOR COMPLEMENTARIO: Procesa input recibido después de interrupción
    
    Este actor opcional se encarga de:
    - ✅ Validar input recibido del usuario
    - ✅ Extraer y estructurar datos
    - ✅ Limpiar flags de interrupción
    - ✅ Determinar próximo paso en el flujo
    """
    
    def __init__(self):
        super().__init__("ProcesarInputRecibido", timeout_seconds=15)
    
    def get_required_fields(self) -> List[str]:
        return ["messages", "workflow_state"]
    
    def get_actor_description(self) -> str:
        return (
            "Actor que procesa y valida input recibido del usuario "
            "después de una interrupción, limpiando flags y determinando continuación"
        )
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """
        🎯 PROCESAMIENTO: Validar input y continuar flujo
        """
        
        try:
            # Obtener contexto de la interrupción
            workflow_state = state.get("workflow_state", {})
            awaiting_context = workflow_state.get("awaiting_context", {})
            resume_node = workflow_state.get("resume_node", "identificar_usuario")
            
            # Extraer último mensaje del usuario
            last_user_message = self._get_last_user_message(state)
            
            self.logger.info(f"🔄 Procesando input: {last_user_message[:50]}...")
            
            # Procesar y validar input
            processed_data = await self._process_and_validate_input(
                last_user_message, 
                awaiting_context, 
                state
            )
            
            # Preparar actualización del estado
            update_data = {
                # Limpiar flags de interrupción
                "requires_user_input": False,
                "workflow_state": {
                    **workflow_state,
                    "waiting_for_user": False,
                    "awaiting_context": {},
                    "input_processed": True,
                    "last_input_timestamp": self._get_timestamp()
                },
                # Señalar próximo actor
                "_next_actor": resume_node,
                "_actor_decision": ActorDecision.COMPLETE,
                # Datos procesados
                **processed_data
            }
            
            return self.signal_completion(
                state=update_data,
                next_actor=resume_node,
                completion_message=f"Input procesado, continuando en {resume_node}"
            )
            
        except Exception as e:
            self.logger.error(f"❌ Error procesando input: {e}")
            return await self.handle_error(e, state)
    
    def _get_last_user_message(self, state: Dict[str, Any]) -> str:
        """Extraer último mensaje del usuario"""
        
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == "human":
                return msg.content
        return ""
    
    async def _process_and_validate_input(
        self, 
        user_input: str, 
        context: Dict[str, Any], 
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Procesar y validar input del usuario según el contexto
        """
        
        input_type = context.get("type", "general")
        validation_rules = context.get("validation_rules", {})
        
        # Extraer datos usando utilidades existentes
        extracted_data = {}
        
        if input_type == "identificacion":
            extracted_data = await self._extract_identification_data(user_input, state)
        elif input_type == "incidencia":
            extracted_data = await self._extract_incident_data(user_input, state)
        elif input_type == "confirmacion":
            extracted_data = await self._extract_confirmation_data(user_input, state)
        
        # Validar datos extraídos
        validation_result = self._validate_extracted_data(extracted_data, validation_rules)
        
        if validation_result["valid"]:
            self.logger.info("✅ Input válido y procesado")
            return extracted_data
        else:
            self.logger.warning(f"⚠️ Input inválido: {validation_result['errors']}")
            # Devolver datos parciales con indicador de error
            return {
                **extracted_data,
                "validation_errors": validation_result["errors"],
                "requires_retry": True
            }
    
    async def _extract_identification_data(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extraer datos de identificación del input del usuario"""
        
        # Usar extractor existente (si está disponible)
        try:
            from utils.extractors.user_extractor import extract_user_data
            return await extract_user_data(user_input, state)
        except ImportError:
            # Fallback simple
            return {"raw_input": user_input, "needs_processing": True}
    
    async def _extract_incident_data(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extraer datos de incidencia del input del usuario"""
        
        return {
            "descripcion_problema": user_input.strip(),
            "timestamp": self._get_timestamp(),
            "needs_categorization": True
        }
    
    async def _extract_confirmation_data(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        """Extraer confirmación del usuario"""
        
        user_input_lower = user_input.lower().strip()
        confirmed = any(word in user_input_lower for word in ["si", "sí", "yes", "ok", "correcto"])
        
        return {
            "confirmation_result": confirmed,
            "raw_confirmation": user_input
        }
    
    def _validate_extracted_data(self, data: Dict[str, Any], rules: Dict[str, Any]) -> Dict[str, Any]:
        """Validar datos extraídos según las reglas"""
        
        errors = []
        
        for field, rule in rules.items():
            value = data.get(field)
            
            if rule.get("required", False) and not value:
                errors.append(f"Campo {field} es requerido")
                continue
            
            if value and "min_length" in rule:
                if len(str(value)) < rule["min_length"]:
                    errors.append(f"Campo {field} debe tener al menos {rule['min_length']} caracteres")
            
            if value and "format" in rule and rule["format"] == "email":
                if "@" not in str(value):
                    errors.append(f"Campo {field} debe ser un email válido")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _get_timestamp(self) -> str:
        """Obtener timestamp actual"""
        from datetime import datetime
        return datetime.now().isoformat()


# =====================================================
# FUNCIÓN WRAPPER PARA PROCESADOR
# =====================================================
async def procesar_input_recibido(state: Dict[str, Any]) -> Command:
    """
    Función wrapper para el procesador de input recibido
    """
    actor = ProcesarInputRecibidoNode()
    return await actor.execute(state)