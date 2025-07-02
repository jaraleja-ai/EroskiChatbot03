# =====================================================
# nodes/identificar_usuario.py - HÍBRIDO ACTUALIZADO SIN INTERRUPCIONES DIRECTAS
# =====================================================
from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage
from langgraph.types import Command
import logging

from .base_node import BaseNode, ActorDecision
from utils.extractors.user_extractor import extraer_datos_usuario

class IdentificarUsuarioNode(BaseNode):
    """
    🎭 ACTOR HÍBRIDO ACTUALIZADO: Identificar y validar datos del usuario
    
    CAMBIOS IMPORTANTES:
    - ✅ YA NO interrumpe directamente (sin __interrupt__)
    - ✅ Solo señala al router que necesita input
    - ✅ Router dirige a recopilar_input_usuario para interrupciones
    - ✅ Usa get_state_diff para optimizar Command.update
    
    COMPORTAMIENTO ACTOR:
    - ✅ Autonomía total en decisiones
    - ✅ Señales claras al router
    - ✅ Estado encapsulado
    - ✅ Evita bucles infinitos
    
    RESPONSABILIDADES:
    - Extraer nombre y email de mensajes
    - Validar completitud de datos
    - Solicitar datos faltantes mediante señalización al router
    - Señalar completitud al router
    """
    
    def __init__(self):
        super().__init__("IdentificarUsuario", timeout_seconds=45)
    
    def get_required_fields(self) -> List[str]:
        return ["messages"]
    
    def get_node_description(self) -> str:
        return (
            "Actor autónomo que identifica y valida datos del usuario. "
            "Señala necesidades de input al router en lugar de interrumpir directamente."
        )

    async def execute(self, state: Dict[str, Any]) -> Command:
        """🎭 LÓGICA DEL ACTOR ACTUALIZADA - Sin interrupciones directas"""
    
        # 🔍 DEBUG AL INICIO
        self.logger.info("🔍 === IDENTIFICAR_USUARIO EXECUTE ACTUALIZADO ===")
        self.logger.info(f"📥 Estado recibido: claves={list(state.keys())}")
        
        current_message = self.get_last_user_message(state)
        last_processed = state.get("_last_processed_message", "")
        
        self.logger.info(f"📥 Mensaje actual: '{current_message}'")
        self.logger.info(f"📜 Último procesado: '{last_processed}'")

        # 🛑 DETECCIÓN DE MENSAJE REPETIDO - PREVENIR BUCLES
        if current_message == last_processed and current_message:
            self.logger.warning(f"🔄 MENSAJE REPETIDO DETECTADO - SEÑALANDO NECESIDAD DE INPUT NUEVO")
            
            # Señalar que necesitamos input nuevo (NO interrumpir directamente)
            return self.signal_need_input(
                state=state,
                request_message="Estoy esperando tu respuesta con tu nombre y email. ¿Puedes proporcionármelos?",
                context={"waiting_for": ["nombre", "email"], "reason": "repeated_message"},
                resume_node="identificar_usuario"
            )
        
        # ✅ MARCAR MENSAJE COMO PROCESADO
        old_state = state.copy()
        new_state = {**state, "_last_processed_message": current_message, "waiting_for_new_input": False}
        
        # 🔍 ANÁLISIS DEL ESTADO
        nombre_actual = new_state.get("nombre")
        email_actual = new_state.get("email")
        intentos = self.increment_attempts(new_state, "intentos")
        new_state["intentos"] = intentos
        
        self.logger.info(f"📊 Estado: Nombre={nombre_actual}, Email={email_actual}, Intentos={intentos}")

        # ✅ DECISIÓN 1: Datos completos
        if nombre_actual and email_actual:
            return await self._actor_complete_with_data(old_state, new_state)
        
        # ✅ DECISIÓN 2: Escalar si muchos intentos
        if intentos > 3:
            return self.signal_escalation(new_state, "obtener datos de usuario después de múltiples intentos")
        
        # ✅ DECISIÓN 3: Procesar input del usuario
        return await self._process_user_input(old_state, new_state)

    async def _process_user_input(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> Command:
        """Procesar input del usuario y tomar decisión autónoma ACTUALIZADA"""
        
        ultimo_mensaje = self.get_last_user_message(new_state)
        nombre_actual = new_state.get("nombre")
        email_actual = new_state.get("email")
        intentos = new_state.get("intentos")
        
        try:
            # Extraer datos del mensaje
            datos_extraidos = await extraer_datos_usuario(ultimo_mensaje)
            nombre_extraido = getattr(datos_extraidos, 'nombre', None)
            email_extraido = getattr(datos_extraidos, 'email', None)
            
            self.logger.info(f"🔍 Extraído: Nombre={nombre_extraido}, Email={email_extraido}")
            
            # Consolidar datos (mantener los que ya tenía)
            nombre_final = nombre_extraido or nombre_actual
            email_final = email_extraido or email_actual
            
            self.logger.debug(f"🔧 Datos finales: nombre_final={nombre_final}, email_final={email_final}")

            # Actualizar estado con datos extraídos
            updated_state = {**new_state, "nombre": nombre_final, "email": email_final}

            # 🎯 DECISIÓN AUTÓNOMA basada en datos disponibles
            if nombre_final and email_final:
                # ✅ TENGO TODO → Actualizar estado y completar
                return await self._actor_complete_with_data(old_state, updated_state)
                
            elif nombre_final and not email_final:
                # 📧 TENGO NOMBRE, NECESITO EMAIL
                return self._request_email_specifically(nombre_final, intentos, old_state, updated_state)
                
            elif email_final and not nombre_final:
                # 👤 TENGO EMAIL, NECESITO NOMBRE  
                return self._request_nombre_specifically(email_final, intentos, old_state, updated_state)
                
            else:
                # ❌ NO TENGO NADA → Solicitar ambos
                return self._request_both_data(old_state, updated_state, intentos)
                
        except Exception as e:
            self.logger.error(f"❌ Error procesando input: {e}")
            return await self.handle_error(e, new_state)

    def _request_nombre_specifically(self, email: str, intentos: int, old_state: Dict[str, Any], current_state: Dict[str, Any]) -> Command:
        """🎯 DECISIÓN DEL ACTOR: Solicitar nombre específicamente - ACTUALIZADA"""
        
        mensaje = (
            f"Tengo tu email: {email}. "
            f"¿Cuál es tu **nombre completo**?"
        )
        
        # ✅ SEÑAL AL ROUTER: "Necesito input específico" - NO interrumpir directamente
        final_state = {
            **current_state,
            "email": email, 
            "intentos": intentos
        }
        
        # Usar signal_need_input que ya usa get_state_diff
        return self.signal_need_input(
            state=final_state,
            request_message=mensaje,
            context={
                "waiting_for": "nombre", 
                "have_email": email,
                "reason": "missing_name"
            },
            resume_node="identificar_usuario"
        )

    def _request_email_specifically(self, nombre: str, intentos: int, old_state: Dict[str, Any], current_state: Dict[str, Any]) -> Command:
        """🎯 DECISIÓN DEL ACTOR: Solicitar email específicamente - ACTUALIZADA"""
        
        mensaje = (
            f"Hola {nombre}, necesito tu **email corporativo** "
            f"para completar tu identificación."
        )
        
        # ✅ SEÑAL AL ROUTER: "Necesito input específico"
        final_state = {
            **current_state,
            "nombre": nombre,
            "intentos": intentos
        }
        
        return self.signal_need_input(
            state=final_state,
            request_message=mensaje,
            context={
                "waiting_for": "email", 
                "have_name": nombre,
                "reason": "missing_email"
            },
            resume_node="identificar_usuario"
        )

    def _request_both_data(self, old_state: Dict[str, Any], current_state: Dict[str, Any], intentos: int) -> Command:
        """🎯 DECISIÓN DEL ACTOR: Solicitar ambos datos - ACTUALIZADA"""

        if intentos == 1:
            mensaje = (
                "¡Hola! Para ayudarte mejor, necesito que me proporciones:\n"
                "👤 **Tu nombre completo**\n"
                "📧 **Tu email corporativo**\n\n"
                "Puedes escribirlos en el mismo mensaje."
            )
        else:
            mensaje = (
                "Necesito tu **nombre completo** y **email corporativo** "
                "para identificarte correctamente. ¿Puedes proporcionármelos?"
            )
    
        # ✅ SEÑAL AL ROUTER: "Necesito input de usuario"
        final_state = {**current_state, "intentos": intentos}
        
        return self.signal_need_input(
            state=final_state,
            request_message=mensaje,
            context={
                "waiting_for": ["nombre", "email"],
                "reason": "missing_both_data"
            },
            resume_node="identificar_usuario"
        )

    async def _actor_complete_with_data(self, old_state: Dict[str, Any], current_state: Dict[str, Any]) -> Command:
        """✅ CONFIRMAR DATOS Y SEÑALAR COMPLETITUD AL ROUTER - ACTUALIZADA"""
        
        nombre = current_state.get("nombre")
        email = current_state.get("email")
        
        # 📝 Mensaje de confirmación para el usuario
        mensaje_confirmacion = (
            f"¡Perfecto, {nombre}! Ya tengo tus datos:\n"
            f"📧 **Email**: {email}\n"
            f"👤 **Nombre**: {nombre}\n\n"
            f"Ahora cuéntame, ¿cuál es el problema técnico que necesitas resolver?"
        )
        
        # ✅ SEÑAL CLARA AL ROUTER: "Estoy completo, ir a procesar incidencia"
        completion_updates = {
            "nombre": nombre,
            "email": email,
            "datos_usuario_completos": True,  # 🔑 EVITA BUCLES
            "intentos": 0,  # Reset intentos
            "_actor_decision": "complete",
            "_next_actor": "procesar_incidencia",
            "messages": [AIMessage(content=mensaje_confirmacion)]
        }
        
        final_state = {**current_state, **completion_updates}
        
        self.logger.info(f"✅ {self.name} completado con datos: {nombre}, {email}")
        
        return self.create_optimized_command(old_state, final_state)

    # =====================================================
    # PREVENIR BUCLES - Límite de recursión mejorado
    # =====================================================

    def _prevent_infinite_loops(self, state: Dict[str, Any]) -> Optional[Command]:
        """
        Prevenir bucles infinitos con límite de intentos ACTUALIZADO.
        
        Si se exceden los intentos, escalar automáticamente.
        """
        intentos = state.get("intentos", 0)
        
        if intentos >= 5:  # Límite máximo
            self.logger.warning(f"🔄 BUCLE DETECTADO: {intentos} intentos en identificar_usuario")
            
            # Escalar a supervisor en lugar de continuar el bucle
            return self.signal_escalation(
                state,
                f"identificar usuario después de {intentos} intentos fallidos",
                attempts=intentos,
                usuario_datos={"nombre": state.get("nombre"), "email": state.get("email")}
            )
        
        return None  # Continuar normalmente

    def get_identification_status(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Obtener estado actual de la identificación del usuario
        
        Returns:
            Diccionario con el estado de identificación
        """
        nombre = state.get("nombre")
        email = state.get("email")
        intentos = state.get("intentos", 0)
        
        return {
            "tiene_nombre": bool(nombre),
            "tiene_email": bool(email),
            "datos_completos": bool(nombre and email),
            "intentos_realizados": intentos,
            "progreso_porcentaje": (
                100 if (nombre and email)
                else 50 if (nombre or email)
                else 0
            ),
            "siguiente_accion": (
                "procesar_incidencia" if (nombre and email)
                else "solicitar_email" if nombre
                else "solicitar_nombre" if email
                else "solicitar_ambos"
            )
        }


# =====================================================
# WRAPPER PARA LANGGRAPH - ACTUALIZADO
# =====================================================
async def identificar_usuario_node(state: Dict[str, Any]) -> Command:
    """
    Wrapper ACTUALIZADO para el nodo de identificación de usuario
    
    Args:
        state: Estado actual del grafo
        
    Returns:
        Command con las actualizaciones optimizadas del estado
    """
    node = IdentificarUsuarioNode()
    
    # Debug mejorado
    if node.logger.isEnabledFor(logging.DEBUG):
        node.logger.debug(f"🔵 ESTADO ANTES DE EXECUTE: _actor_decision={state.get('_actor_decision')}")
    
    result = await node.execute_with_monitoring(state)
    
    # Debug del resultado
    if node.logger.isEnabledFor(logging.DEBUG):
        node.logger.debug(f"🔴 COMMAND RETORNADO con {len(result.update)} actualizaciones")
        node.logger.debug(f"🔴 Nuevas claves: {list(result.update.keys())}")
        if "_actor_decision" in result.update:
            node.logger.debug(f"🔴 Nueva decisión: {result.update['_actor_decision']}")
        if "_next_actor" in result.update:
            node.logger.debug(f"🔴 Próximo actor: {result.update['_next_actor']}")
    
    return result