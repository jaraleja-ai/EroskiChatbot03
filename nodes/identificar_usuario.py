# =====================================================
# nodes/identificar_usuario.py - Nodo de identificación de usuario
# =====================================================
from typing import Dict, Any, Optional, Tuple
from langchain_core.messages import AIMessage
from langgraph.types import Command

from models.conversation_step import ConversationSteps

from .base_node import BaseNode, NodeExecutionResult
from nodes import (validate_email_format, 
                   validate_name_format, 
                   names_are_similar)

from utils import UserRepository 
from models import UsuarioDB

# Imports opcionales
try:
    from utils import UserRepository
    from models import UsuarioDB
except ImportError:
    UserRepository = None
    UsuarioDB = None

# ✅ DEBERÍA SER:
from utils.extractors.user_extractor import extraer_datos_usuario
from utils.llm.message_generator import generate_natural_message, detect_confirmation_intent

class IdentificarUsuarioNode(BaseNode):
    """
    Nodo especializado para identificar y validar datos del usuario.
    
    Funcionalidades:
    - Extraer datos de usuario de mensajes naturales
    - Validar formato de email y nombre
    - Buscar usuario en base de datos
    - Manejar confirmaciones de datos
    - Resolver conflictos de nombres
    - Escalar cuando sea necesario
    """
    
    def __init__(self):
        super().__init__("IdentificarUsuario", timeout_seconds=45)
        self.user_repository = UserRepository() if UserRepository else None
    
    def _safe_get_from_state(self, state, key, default=None):
        """Método helper para acceso seguro al state"""
        if state is None:
            self.logger.warning(f"⚠️ State es None al acceder a {key}")
            return default
        
        try:
            return state.get(key, default)
        except Exception as e:
            self.logger.error(f"❌ Error accediendo a state[{key}]: {e}")
            return default

    def _safe_get_context(self, state, context_key, default=None):
        """Método helper para acceso seguro al contexto adicional"""
        if state is None:
            return default
        
        try:
            contexto = state.get("contexto_adicional", {})
            if contexto is None:
                return default
            return contexto.get(context_key, default)
        except Exception as e:
            self.logger.error(f"❌ Error accediendo a contexto[{context_key}]: {e}")
            return default

    def transition_to(self, state: Dict[str, Any],next_step: str, awaiting_input: bool = False, **updates):
        """Helper para transiciones limpias"""
        update_data = {
            "current_step": next_step,
            "awaiting_input": awaiting_input,
            "flow_history": self._get_updated_history(state, next_step),
            **updates
        }
        
        self.logger.info(f"🔄 Transición: {self.name} → {next_step}")
        return Command(update=update_data)

    def wait_for_input(self, state: Dict[str, Any], next_step: str, message: str, next_action: str = None):
        """Helper para esperar input del usuario"""
        return self.transition_to(
            state,
            next_step=next_step,
            awaiting_input=True,
            messages=[AIMessage(content=message)],
            next_action=next_action or f"process_{next_step}"
        )

    def _get_updated_history(self, state: Dict[str, Any], step: str):  # ✅ Agregar state como parámetro
        """Actualizar historial de flujo"""
        history = self._safe_get_from_state(state, "flow_history", [])
        return history + [step]

    def get_required_fields(self) -> list[str]:
        """Campos requeridos en el estado"""
        return ["messages"]
    
    def get_node_description(self) -> str:
        """Descripción del nodo"""
        return (
            "Identifica y valida datos del usuario mediante extracción de NLP, "
            "búsqueda en BD y gestión de confirmaciones interactivas"
        )

    async def execute(self, state: Dict[str, Any]) -> Command:
        """Ejecutar lógica principal de identificación"""
        
        # Incrementar intentos y verificar escalación
        intentos = self.increment_attempts(state, "intentos")
        # Verificar si estamos procesando respuesta del usuario
        if state.get("awaiting_input") and state.get("next_action"):
            return await self._handle_user_response(state, intentos)
        
        if self.should_escalate(state, "intentos"):
            return self.create_escalation_command(
                state, 
                "obtener y validar tus datos de usuario", 
                intentos
            )
        
        # Determinar el flujo a seguir según el estado actual
        return await self._determine_flow(state, intentos)
    
    async def _determine_flow(self, state: Dict[str, Any], intentos: int) -> Command:
        """Determinar qué flujo seguir según el estado actual"""
        
        # 1. Verificar si necesitamos buscar en BD
        if await self._should_search_database(state):
            return await self._handle_database_search_flow(state, intentos)
        
        # 2. Verificar si estamos procesando confirmación
        if await self._should_process_confirmation(state):
            return await self._handle_confirmation_flow(state, intentos)
        
        # 3. Verificar si hay conflicto de nombres
        if await self._should_resolve_name_conflict(state):
            return await self._handle_name_conflict_flow(state, intentos)
        
        # 4. Extraer y procesar nuevos datos
        return await self._handle_data_extraction_flow(state, intentos)
    
    async def _should_search_database(self, state: Dict[str, Any]) -> bool:
        """Determinar si debemos buscar en la base de datos"""
        if not self.settings.workflow.enable_database_lookup:
            return False
        
        # 🔥 FIX: Uso seguro del state
        email = self._safe_get_from_state(state, "email")
        usuario_encontrado_bd = self._safe_get_from_state(state, "usuario_encontrado_bd", False)
        
        return (
            email and 
            validate_email_format(email) and 
            not usuario_encontrado_bd
        )
    
    async def _handle_database_search_flow(self, state: Dict[str, Any], intentos: int) -> Command:
        """Manejar flujo de búsqueda en base de datos"""
        # 🔥 FIX: Uso seguro del state
        email = self._safe_get_from_state(state, "email")
        
        if not email:
            self.logger.warning("⚠️ No hay email para buscar en BD")
            return await self._continue_without_database(state, intentos)
        
        self.logger.info(f"🔍 Buscando usuario en BD: {email}")
        
        try:
            usuario_bd = await self.user_repository.buscar_por_email(email)
            
            if usuario_bd:
                return await self._process_user_found_in_db(state, usuario_bd, intentos)
            else:
                return await self._process_user_not_found_in_db(state, intentos)
                
        except Exception as e:
            self.logger.error(f"❌ Error consultando BD: {e}")
            return await self._continue_without_database(state, intentos)
    
    async def _process_user_found_in_db(
        self, 
        state: Dict[str, Any], 
        usuario_bd: UsuarioDB, 
        intentos: int
    ) -> Command:
        """Procesar cuando se encuentra usuario en BD"""
        
        self.logger.info(f"✅ Usuario encontrado: {usuario_bd.nombre_completo}")
        
        # 🔥 FIX: Uso seguro del state
        nombre_estado = self._safe_get_from_state(state, "nombre")
        
        # Si no teníamos nombre, usar el de la BD y confirmar
        if not nombre_estado:
            return await self._auto_confirm_with_bd_data(state, usuario_bd, intentos)
        
        # Si hay conflicto de nombres, manejarlo
        if not names_are_similar(nombre_estado, usuario_bd.nombre_completo):
            return await self._create_name_conflict_scenario(state, usuario_bd, intentos)
        
        # Nombres coinciden, proceder con confirmación
        return await self._create_matching_names_confirmation(state, usuario_bd, intentos)

    async def _auto_confirm_with_bd_data(
        self, 
        state: Dict[str, Any], 
        usuario_bd: UsuarioDB, 
        intentos: int
    ) -> Command:
        """Auto-confirmación cuando solo tenemos email y encontramos usuario en BD"""
        
        mensaje = await generate_natural_message("confirmacion_datos_bd", {
            "nombre": usuario_bd.nombre_completo,
            "email": usuario_bd.email,
            "numero_empleado": usuario_bd.numero_empleado
        })
        
        return Command(update=self.create_message_update(mensaje, {
            "nombre": usuario_bd.nombre_completo,
            "email": usuario_bd.email,
            "numero_empleado": usuario_bd.numero_empleado,
            "nombre_confirmado": True,
            "email_confirmado": True,
            "usuario_encontrado_bd": True,
            "intentos": intentos,
            "escalar_a_supervisor": False,
            "datos_usuario_completos": False  # Aún necesita confirmación del usuario
        }))
    
    async def _create_name_conflict_scenario(
        self, 
        state: Dict[str, Any], 
        usuario_bd: UsuarioDB, 
        intentos: int
    ) -> Command:
        """Crear escenario de conflicto de nombres"""
        
        nombre_usuario = state.get("nombre")
        
        mensaje_conflicto = (
            f"He encontrado una diferencia en los nombres:\n\n"
            f"🗣️ **Tú dijiste:** {nombre_usuario}\n"
            f"💾 **En nuestro sistema:** {usuario_bd.nombre_completo}\n\n"
            f"¿Cuál prefieres usar?\n"
            f"1️⃣ Usar '{nombre_usuario}' (actualizaré el sistema)\n"
            f"2️⃣ Usar '{usuario_bd.nombre_completo}' (del sistema)\n\n"
            f"Responde con **1** o **2**, o escribe el nombre correcto."
        )
        
        return Command(update=self.create_message_update(mensaje_conflicto, {
            "nombre": nombre_usuario,
            "email": usuario_bd.email,
            "numero_empleado": usuario_bd.numero_empleado,
            "nombre_confirmado": False,
            "email_confirmado": True,
            "usuario_encontrado_bd": True,
            "intentos": intentos,
            "escalar_a_supervisor": False,
            "contexto_adicional": {
                "conflicto_nombres": True,
                "nombre_bd": usuario_bd.nombre_completo,
                "nombre_usuario": nombre_usuario
            }
        }))
    
    async def _should_process_confirmation(self, state):
        """Determinar si debe procesar confirmación"""
        
        # 🔥 SOLUCIÓN: Verificación defensiva de state
        if state is None:
            self.logger.warning("⚠️ State es None en _should_process_confirmation")
            return False
        
        try:
            # Extraer contexto de forma segura
            contexto = state.get("contexto_adicional", {})
            conflicto_nombres = contexto.get("conflicto_nombres", False)
            usuario_pendiente_confirmacion = contexto.get("usuario_pendiente_confirmacion", False)
            confirmacion_requerida = state.get("confirmacion_requerida", False)
            
            # Log de debug
            self.logger.debug(f"🔍 Verificando confirmación: conflicto={conflicto_nombres}, "
                            f"pendiente={usuario_pendiente_confirmacion}, requerida={confirmacion_requerida}")
            
            # Determinar si debe procesar confirmación
            should_process = (
                conflicto_nombres or 
                usuario_pendiente_confirmacion or 
                confirmacion_requerida
            )
            
            if should_process:
                self.logger.info("✅ Debe procesar confirmación")
            else:
                self.logger.debug("📋 No requiere confirmación")
            
            return should_process
            
        except Exception as e:
            self.logger.error(f"❌ Error verificando confirmación: {e}")
            return False

    async def _handle_confirmation_flow(self, state: Dict[str, Any], intentos: int) -> Command:
        """Manejar flujo de confirmación de datos"""
        ultimo_mensaje = self.get_last_user_message(state)
        nombre = state.get("nombre")
        email = state.get("email")
        
        self.logger.info("🔧 Procesando confirmación de datos")
        
        # Detectar intención usando LLM
        intencion = await detect_confirmation_intent(ultimo_mensaje, nombre, email)
        
        if intencion == "CONFIRMA":
            return await self._process_data_confirmed(state, intentos)
        elif intencion == "RECHAZA":
            return await self._process_data_rejected(state, intentos)
        else:  # AMBIGUO
            return await self._request_clarification(state, nombre, email, intentos)
    
    async def _should_resolve_name_conflict(self, state):
        """Determinar si debe resolver conflicto de nombres"""
        
        # 🔥 SOLUCIÓN: Verificación defensiva de state
        if state is None:
            self.logger.warning("⚠️ State es None en _should_resolve_name_conflict")
            return False
        
        try:
            contexto = state.get("contexto_adicional")
            if contexto is None:
                self.logger.debug("📋 No hay contexto adicional")
                return False
            
            conflicto = contexto.get("conflicto_nombres", False)
            self.logger.debug(f"🔍 Verificando conflicto de nombres: {conflicto}")
            
            return conflicto
            
        except Exception as e:
            self.logger.error(f"❌ Error verificando conflicto de nombres: {e}")
            return False

    async def _handle_name_conflict_flow(self, state: Dict[str, Any], intentos: int) -> Command:
        """Manejar resolución de conflicto de nombres"""
        ultimo_mensaje = self.get_last_user_message(state).lower().strip()
        
        # 🔥 FIX: Uso seguro del contexto
        nombre_bd = self._safe_get_context(state, "nombre_bd")
        nombre_usuario = self._safe_get_context(state, "nombre_usuario")
        email = self._safe_get_from_state(state, "email")
        
        if not nombre_bd or not nombre_usuario:
            self.logger.warning("⚠️ Datos de conflicto incompletos, escalando")
            return self.create_escalation_command(state, "resolver conflicto de nombres", intentos)
        
        if "1" in ultimo_mensaje or "actualiza" in ultimo_mensaje:
            return await self._resolve_conflict_update_db(state, nombre_usuario, email, intentos)
        elif "2" in ultimo_mensaje or "sistema" in ultimo_mensaje:
            return await self._resolve_conflict_use_db_name(state, nombre_bd, intentos)
        elif validate_name_format(self.get_last_user_message(state)):
            return await self._resolve_conflict_new_name(state, intentos)
        else:
            return await self._request_conflict_clarification(state, intentos)

    # =====================================================
    # identificar_usuario.py - MODIFICACIONES NECESARIAS
    # =====================================================
    async def _handle_data_extraction_flow(self, state: Dict[str, Any], intentos: int) -> Command:
        """Manejar flujo de extracción de datos del último mensaje"""
        
        # ✅ PRESERVAR datos existentes del estado (múltiples fuentes)
        nombre_existente = (
            state.get("nombre") or 
            state.get("user_name") or 
            self._safe_get_from_state(state, "nombre")
        )
        email_existente = (
            state.get("email") or 
            state.get("user_email") or 
            self._safe_get_from_state(state, "email")
        )
        
        self.logger.info(f"📋 Estado actual - Nombre: {nombre_existente}, Email: {email_existente}")
        
        # Si ya tenemos ambos datos, ir directo a confirmación
        if nombre_existente and email_existente:
            self.logger.info("✅ Datos ya completos en estado")
            return await self._request_data_confirmation(state, nombre_existente, email_existente, intentos)
        
        # Extraer datos del último mensaje
        ultimo_mensaje = self.get_last_user_message(state)
        datos_extraidos = await extraer_datos_usuario(ultimo_mensaje)
        
        # ✅ CONSOLIDAR datos (preservar existentes, agregar nuevos)
        nombre_final = (
            datos_extraidos.nombre if validate_name_format(datos_extraidos.nombre) 
            else nombre_existente
        )
        email_final = (
            datos_extraidos.email if validate_email_format(datos_extraidos.email) 
            else email_existente
        )
        
        self.logger.info(f"📋 Datos consolidados - Nombre: {nombre_final}, Email: {email_final}")
        
        # ✅ CREAR UPDATE BASE CON TODOS LOS DATOS PRESERVADOS
        base_update = {
            "intentos": intentos,
            # Preservar TODOS los datos existentes del estado
            **{k: v for k, v in state.items() if v is not None and k not in ["messages"]},
            # Actualizar con nuevos datos
            "nombre": nombre_final,
            "email": email_final,
            "user_name": nombre_final,  # Alias adicional
            "user_email": email_final,  # Alias adicional
        }
        
        if not nombre_final or not email_final:
            # Faltan datos - solicitar pero GUARDAR lo que tenemos
            mensaje = self._generate_missing_data_message(nombre_final, email_final)
            
            return Command(update={
                **base_update,
                "awaiting_input": True,
                "messages": [AIMessage(content=mensaje)]
            })
        
        # Datos completos - ir a confirmación
        mensaje = await generate_natural_message("confirmacion_datos", {
            "nombre": nombre_final,
            "email": email_final
        })
        
        return Command(update={
            **base_update,
            "awaiting_input": True,
            "current_step": "waiting_user_confirmation",
            "messages": [AIMessage(content=mensaje)]
        })

    async def _request_data_confirmation(
        self, 
        state: Dict[str, Any], 
        nombre: str, 
        email: str, 
        intentos: int
    ) -> Command:
        """Solicitar confirmación de datos completos"""
        
        mensaje = await generate_natural_message("confirmacion_datos", {
            "nombre": nombre,
            "email": email
        })
        
        return Command(update={
            "intentos": intentos,
            "nombre": nombre,
            "email": email,
            "user_name": nombre,
            "user_email": email,
            "awaiting_input": True,
            "current_step": "waiting_user_confirmation",
            "next_action": "confirm_data",
            "messages": [AIMessage(content=mensaje)]
        })

    def _generate_missing_data_message(self, nombre: Optional[str], email: Optional[str]) -> str:
        """Generar mensaje específico para datos faltantes"""
        if not nombre and not email:
            return "Necesito tu **nombre completo** y **email corporativo** para identificarte.\n¿Puedes ayudarme con más información?"
        elif not nombre:
            return f"Tengo tu email ({email}). ¿Cuál es tu **nombre completo**?\n¿Puedes ayudarme con más información?"
        elif not email:
            return f"Tengo tu nombre ({nombre}). ¿Cuál es tu **email corporativo**?\n¿Puedes ayudarme con más información?"
        else:
            return "¿Puedes confirmar tu nombre y email?\n¿Puedes ayudarme con más información?"

    # =====================================================
    # TAMBIÉN NECESITAS ESTOS MÉTODOS AUXILIARES
    # =====================================================

    async def _continue_without_database(self, state: Dict[str, Any], intentos: int) -> Command:
        """Continuar sin base de datos en caso de error"""
        self.logger.warning("⚠️ Continuando sin búsqueda en BD debido a error")
        
        updated_state = dict(state)
        updated_state["usuario_encontrado_bd"] = True
        
        return await self._handle_data_extraction_flow(updated_state, intentos)

    async def _process_user_not_found_in_db(self, state: Dict[str, Any], intentos: int) -> Command:
        """Procesar cuando no se encuentra usuario en BD"""
        self.logger.info("❌ Usuario no encontrado en BD")
        
        # Marcar como buscado y continuar
        updated_state = dict(state)
        updated_state["usuario_encontrado_bd"] = True
        
        return await self._handle_data_extraction_flow(updated_state, intentos)

    async def _process_data_confirmed(self, state: Dict[str, Any], intentos: int) -> Command:
        """Procesar cuando el usuario confirma sus datos"""
        self.logger.info("✅ Usuario confirmó sus datos")
        # ✅ DEBUG TEMPORAL
        self.logger.info(f"🔍 Estado antes de confirmar: awaiting_input={state.get('awaiting_input')}")
    
        mensaje = await generate_natural_message("datos_confirmados")
        
        return Command(update={
            "intentos": intentos,
            "datos_usuario_completos": True,
            "nombre_confirmado": True,
            "email_confirmado": True,
            "awaiting_input": False,
            "current_step": "processing_incident",
            "messages": [AIMessage(content=mensaje)]
        })

    async def _process_data_rejected(self, state: Dict[str, Any], intentos: int) -> Command:
        """Procesar cuando el usuario rechaza sus datos"""
        self.logger.info("❌ Usuario rechazó sus datos")
        
        mensaje = "Entendido. Vamos a corregir la información. ¿Cuál es tu nombre y email correctos?"
        
        return Command(update={
            "intentos": intentos,
            "nombre": None,
            "email": None,
            "nombre_confirmado": False,
            "email_confirmado": False,
            "datos_usuario_completos": False,
            "awaiting_input": True,
            "messages": [AIMessage(content=mensaje)]
        })

    async def _request_clarification(self, state: Dict[str, Any], nombre: str, email: str, intentos: int) -> Command:
        """Solicitar clarificación cuando la respuesta es ambigua"""
        mensaje = f"No estoy seguro de tu respuesta. ¿Puedes confirmar si estos datos son correctos?\n\n" \
                f"**Nombre:** {nombre}\n**Email:** {email}\n\n" \
                f"Responde **SÍ** para confirmar o **NO** para corregir."
        
        return Command(update={
            "intentos": intentos,
            "awaiting_input": True,
            "messages": [AIMessage(content=mensaje)]
        })

    async def _handle_user_response(self, state: Dict[str, Any], intentos: int) -> Command:
        """Manejar respuesta del usuario según la acción pendiente"""
        
        next_action = state.get("next_action")
        current_step = state.get("current_step")
        
        self.logger.info(f"🔄 Procesando respuesta del usuario: {next_action}")
        
        if next_action == "process_user_data":
            # Reset awaiting_input y procesar datos
            return await self._handle_data_extraction_flow(
                {**state, "awaiting_input": False}, intentos
            )
        
        elif next_action == "confirm_data":
            # Reset awaiting_input y procesar confirmación
            return await self._handle_confirmation_flow(
                {**state, "awaiting_input": False}, intentos
            )
        
        else:
            # Acción no reconocida, continuar flujo normal
            return await self._determine_flow(
                {**state, "awaiting_input": False}, intentos
            )

    # =====================================================
    # MÉTODOS DE RESOLUCIÓN DE CONFLICTOS FALTANTES
    # =====================================================

    async def _resolve_conflict_update_db(self, state: Dict[str, Any], nombre_usuario: str, email: str, intentos: int) -> Command:
        """Resolver conflicto actualizando BD con nombre del usuario"""
        self.logger.info(f"🔄 Resolviendo conflicto: actualizando BD con '{nombre_usuario}'")
        
        mensaje = f"Perfecto, usaré '{nombre_usuario}' y actualizaré nuestro sistema. ¿Continuamos?"
        
        return Command(update={
            "intentos": intentos,
            "nombre": nombre_usuario,
            "email": email,
            "nombre_confirmado": True,
            "email_confirmado": True,
            "datos_usuario_completos": True,
            "usuario_encontrado_bd": True,
            "awaiting_input": True,
            "contexto_adicional": {},  # Limpiar contexto de conflicto
            "messages": [AIMessage(content=mensaje)]
        })

    async def _resolve_conflict_use_db_name(self, state: Dict[str, Any], nombre_bd: str, intentos: int) -> Command:
        """Resolver conflicto usando nombre de la BD"""
        self.logger.info(f"🔄 Resolviendo conflicto: usando nombre de BD '{nombre_bd}'")
        
        mensaje = f"Perfecto, usaré '{nombre_bd}' como aparece en nuestro sistema. ¿Continuamos?"
        
        return Command(update={
            "intentos": intentos,
            "nombre": nombre_bd,
            "nombre_confirmado": True,
            "email_confirmado": True,
            "datos_usuario_completos": True,
            "usuario_encontrado_bd": True,
            "awaiting_input": True,
            "contexto_adicional": {},  # Limpiar contexto de conflicto
            "messages": [AIMessage(content=mensaje)]
        })

    async def _resolve_conflict_new_name(self, state: Dict[str, Any], intentos: int) -> Command:
        """Resolver conflicto con un nombre completamente nuevo"""
        nuevo_nombre = self.get_last_user_message(state).strip()
        
        self.logger.info(f"🔄 Resolviendo conflicto: nuevo nombre '{nuevo_nombre}'")
        
        if not validate_name_format(nuevo_nombre):
            mensaje = "El nombre que proporcionaste no parece válido. ¿Puedes escribirlo de nuevo?"
            return Command(update={
                "intentos": intentos,
                "awaiting_input": True,
                "messages": [AIMessage(content=mensaje)]
            })
        
        mensaje = f"Perfecto, usaré '{nuevo_nombre}'. ¿Es correcto?"
        
        return Command(update={
            "intentos": intentos,
            "nombre": nuevo_nombre,
            "awaiting_input": True,
            "contexto_adicional": {},  # Limpiar contexto de conflicto
            "messages": [AIMessage(content=mensaje)]
        })

    async def _request_conflict_clarification(self, state: Dict[str, Any], intentos: int) -> Command:
        """Solicitar clarificación cuando no se entiende la resolución del conflicto"""
        nombre_bd = self._safe_get_context(state, "nombre_bd", "nombre del sistema")
        nombre_usuario = self._safe_get_context(state, "nombre_usuario", "tu nombre")
        
        mensaje = (
            f"No entendí tu elección. Por favor responde:\n\n"
            f"**1** - Para usar '{nombre_usuario}'\n"
            f"**2** - Para usar '{nombre_bd}'\n"
            f"O escribe el nombre correcto directamente."
        )
        
        return Command(update={
            "intentos": intentos,
            "awaiting_input": True,
            "messages": [AIMessage(content=mensaje)]
        })

    async def _create_matching_names_confirmation(self, state: Dict[str, Any], usuario_bd, intentos: int) -> Command:
        """Crear confirmación cuando los nombres del usuario y BD coinciden"""
        mensaje = await generate_natural_message("confirmacion_datos_bd", {
            "nombre": usuario_bd.nombre_completo,
            "email": usuario_bd.email,
            "numero_empleado": getattr(usuario_bd, 'numero_empleado', 'N/A')
        })
        
        return Command(update={
            "intentos": intentos,
            "nombre": usuario_bd.nombre_completo,
            "email": usuario_bd.email,
            "numero_empleado": getattr(usuario_bd, 'numero_empleado', None),
            "nombre_confirmado": True,
            "email_confirmado": True,
            "usuario_encontrado_bd": True,
            "awaiting_input": True,
            "current_step": "waiting_user_confirmation",
            "next_action": "confirm_data",
            "messages": [AIMessage(content=mensaje)]
        })




# =====================================================
# Función wrapper para usar con LangGraph
# =====================================================
async def identificar_usuario_node(state: Dict[str, Any]) -> Command:
    """
    Wrapper function para el nodo de identificación de usuario.
    
    Args:
        state: Estado actual del grafo
        
    Returns:
        Command con las actualizaciones del estado
    """
    node = IdentificarUsuarioNode()
    return await node.execute_with_monitoring(state)



    #async def _should_process_confirmation(self, state: Dict[str, Any]) -> bool:
    #    """Verificar si debemos procesar confirmación de datos"""
    #    nombre_confirmado = state.get("nombre_confirmado", False)
    #    email_confirmado = state.get("email_confirmado", False)
    #    datos_completos = state.get("datos_usuario_completos", False)
    #    conflicto_nombres = state.get("contexto_adicional", {}).get("conflicto_nombres", False)
    #    
    #    return (
    #        nombre_confirmado and 
    #        email_confirmado and 
    #        not datos_completos and 
    #        not conflicto_nombres
    #    )
    
        
    #async def _should_resolve_name_conflict(self, state: Dict[str, Any]) -> bool:
    #    """Verificar si debemos resolver conflicto de nombres"""
    #    contexto = state.get("contexto_adicional", {})
    #    return contexto.get("conflicto_nombres", False)
