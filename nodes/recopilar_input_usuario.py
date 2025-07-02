# =====================================================
# nodes/recopilar_input_usuario.py - MANEJO CENTRALIZADO DE INTERRUPCIONES
# =====================================================
from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage
from langgraph.types import Command
from datetime import datetime

from .base_node import BaseNode

class RecopilarInputUsuarioNode(BaseNode):
    """
    🎯 NODO ESPECIALIZADO ACTUALIZADO: Manejo CENTRALIZADO de todas las interrupciones
    
    NUEVAS RESPONSABILIDADES:
    - ✅ ÚNICO punto de interrupciones en todo el workflow
    - ✅ Recibe señales de TODOS los nodos que necesitan input
    - ✅ Establece flags correctos para el sistema de interrupciones
    - ✅ Usa get_state_diff para optimizar actualizaciones
    - ✅ Maneja contexto completo para continuación después de input
    
    ESTE NODO:
    - Recibe todas las señales de necesidad de input
    - Genera mensajes apropiados según el contexto recibido
    - Establece la interrupción (__interrupt__)
    - Mantiene el contexto para continuar después del input
    - Proporciona transición limpia hacia nodos válidos después de input
    
    FLUJO:
    1. Nodo X detecta necesidad de input
    2. Nodo X señala: _actor_decision="need_input", _next_actor="recopilar_input_usuario"
    3. Router dirige a recopilar_input_usuario
    4. recopilar_input_usuario establece interrupción (__interrupt__)
    5. Usuario proporciona input
    6. Flujo continúa desde resume_node especificado
    
    Funcionalidades:
    - Detección automática del tipo de input requerido
    - Generación de mensajes contextuales inteligentes
    - Configuración optimizada de flags de interrupción
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
            "Maneja CENTRALIZADAMENTE todas las interrupciones del flujo para "
            "recopilar input del usuario. Único punto de interrupciones en el workflow."
        )
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """
        Ejecutar lógica principal de recopilación de input CENTRALIZADA.
        
        Este es el ÚNICO nodo en todo el workflow que maneja interrupciones.
        Todos los demás nodos señalan a este para solicitar input del usuario.
        """
        
        try:
            self.logger.info("⏸️ === INICIANDO RECOPILACIÓN CENTRALIZADA DE INPUT ===")
            
            # Obtener contexto de la solicitud de input
            request_message = state.get("_request_message")
            input_context = state.get("_input_context", {})
            resume_node = input_context.get("resume_node", "identificar_usuario")
            requesting_node = input_context.get("requesting_node", "unknown")
            
            self.logger.info(f"📨 Solicitud de: {requesting_node} → continuar en: {resume_node}")
            
            # Si no hay mensaje específico, generar uno inteligente
            if not request_message:
                request_message = await self._generate_smart_input_request(input_context, state)
            
            self.logger.info(f"⏸️ Mensaje generado: {request_message[:80]}...")
            
            # Preparar estado para la interrupción con optimización
            old_state = state.copy()
            interruption_updates = {
                # Enviar mensaje al usuario
                "messages": [AIMessage(content=request_message)],
                
                # FLAGS CRÍTICOS para el sistema de interrupciones de LangGraph
                "requires_user_input": True,
                
                # Estado del workflow para continuación
                "workflow_state": {
                    "waiting_for_user": True,
                    "awaiting_context": input_context,
                    "last_node": "recopilar_input_usuario",
                    "resume_node": resume_node,
                    "requesting_node": requesting_node,
                    "original_step": state.get("current_step", "unknown"),
                    "interruption_timestamp": datetime.now().isoformat()
                },
                
                # Limpiar flags temporales que nos trajeron aquí
                "_actor_decision": None,
                "_request_message": None, 
                "_input_context": None,
                "_next_actor": None,
                
                # Información para debugging y continuación
                "interruption_reason": input_context.get("reason", "input_required"),
                "pending_questions": [request_message],
                "awaiting_input": False,  # Lo manejamos con requires_user_input
                "interruption_count": state.get("interruption_count", 0) + 1,
                
                # Información adicional para el contexto
                "last_interruption_context": {
                    "requesting_node": requesting_node,
                    "resume_node": resume_node,
                    "reason": input_context.get("reason", "input_required"),
                    "waiting_for": input_context.get("waiting_for", "user_input")
                }
            }
            
            self.logger.info(f"⏸️ Configurando interrupción. Usuario debe proporcionar input.")
            self.logger.debug(f"🔧 Contexto de interrupción: {input_context}")
            
            # Usar get_state_diff para optimizar la actualización
            return self.create_optimized_command(old_state, interruption_updates)
            
        except Exception as e:
            self.logger.error(f"❌ Error en recopilar_input_usuario: {e}")
            return await self._create_fallback_response(state)
    
    async def _generate_smart_input_request(self, context: Dict[str, Any], state: Dict[str, Any]) -> str:
        """
        Generar mensaje inteligente basado en el contexto y estado actual.
        
        Args:
            context: Contexto de la solicitud de input
            state: Estado actual del grafo
            
        Returns:
            Mensaje apropiado para solicitar input del usuario
        """
        waiting_for = context.get("waiting_for", "information")
        requesting_node = context.get("requesting_node", "sistema")
        reason = context.get("reason", "input_required")
        
        # Obtener datos actuales del usuario
        nombre_actual = state.get("nombre")
        email_actual = state.get("email")
        
        # Generar mensaje según el contexto específico
        if isinstance(waiting_for, list):
            # Múltiples datos requeridos
            if "nombre" in waiting_for and "email" in waiting_for:
                return (
                    "Para poder ayudarte mejor, necesito algunos datos:\n"
                    "👤 **Tu nombre completo**\n"
                    "📧 **Tu email corporativo**\n\n"
                    "Puedes escribir ambos en el mismo mensaje."
                )
        elif waiting_for == "nombre":
            if email_actual:
                return f"Ya tengo tu email ({email_actual}). ¿Cuál es tu **nombre completo**?"
            else:
                return "¿Cuál es tu **nombre completo**?"
                
        elif waiting_for == "email":
            if nombre_actual:
                return f"Hola {nombre_actual}, necesito tu **email corporativo** para continuar."
            else:
                return "¿Cuál es tu **email corporativo**?"
                
        elif waiting_for == "incidencia":
            return "¿Cuál es el problema técnico que necesitas resolver? Describe los detalles."
            
        elif waiting_for == "confirmacion":
            return "¿Confirmas que esta información es correcta? (Sí/No)"
            
        else:
            # Mensaje genérico inteligente
            if reason == "missing_data":
                return "Necesito información adicional para continuar. ¿Puedes proporcionármela?"
            elif reason == "clarification":
                return "¿Podrías aclarar tu respuesta anterior?"
            elif reason == "repeated_message":
                return "Parece que necesito una respuesta diferente. ¿Puedes intentar de nuevo?"
            else:
                return "Necesito más información para poder ayudarte. ¿Qué puedes decirme?"
    
    def _safe_get_awaiting_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Obtener contexto de forma segura, proporcionando defaults apropiados.
        """
        try:
            # Intentar obtener contexto específico
            awaiting_context = state.get("_input_context", {})
            
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
        nombre = state.get("nombre")
        email = state.get("email")
        
        # Inferir qué datos faltan
        if not nombre and not email:
            return {
                "waiting_for": ["nombre", "email"],
                "reason": "missing_user_data",
                "resume_node": "identificar_usuario"
            }
        elif not nombre:
            return {
                "waiting_for": "nombre",
                "have_email": email,
                "reason": "missing_name",
                "resume_node": "identificar_usuario"
            }
        elif not email:
            return {
                "waiting_for": "email", 
                "have_name": nombre,
                "reason": "missing_email",
                "resume_node": "identificar_usuario"
            }
        else:
            # Si tenemos datos básicos, probablemente necesitamos info de incidencia
            return {
                "waiting_for": "incidencia",
                "reason": "missing_incident_details",
                "resume_node": "procesar_incidencia"
            }
    
    def _get_default_context(self) -> Dict[str, Any]:
        """
        Contexto por defecto cuando no se puede inferir otro.
        """
        return {
            "waiting_for": "information",
            "reason": "general_input_required",
            "resume_node": "identificar_usuario",
            "timestamp": datetime.now().isoformat()
        }
    
    async def _create_fallback_response(self, state: Dict[str, Any]) -> Command:
        """
        Crear respuesta de fallback en caso de error.
        """
        fallback_message = (
            "Necesito más información para continuar. "
            "¿Puedes proporcionarme los detalles que faltan?"
        )
        
        old_state = state.copy()
        fallback_updates = self.create_message_update(
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
        )
        
        return self.create_optimized_command(old_state, fallback_updates)
    
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
    
    def get_interruption_metrics(self) -> Dict[str, Any]:
        """
        Obtener métricas específicas de interrupciones.
        """
        base_metrics = self.get_execution_metrics()
        
        # Agregar métricas específicas de interrupciones
        base_metrics.update({
            "node_type": "centralized_interruption_handler",
            "purpose": "user_input_collection",
            "interruption_patterns": [
                "requires_user_input",
                "_actor_decision=need_input", 
                "_request_message exists",
                "workflow_state.waiting_for_user"
            ],
            "supported_contexts": [
                "missing_user_data",
                "missing_incident_details", 
                "clarification_needed",
                "confirmation_required"
            ]
        })
        
        return base_metrics


# =====================================================
# Función wrapper para usar con LangGraph
# =====================================================
async def recopilar_input_usuario(state: Dict[str, Any]) -> Command:
    """
    Wrapper function ACTUALIZADA para el nodo de recopilación centralizada de input.
    
    Este es el ÚNICO punto de interrupciones en todo el workflow.
    
    Args:
        state: Estado actual del grafo
        
    Returns:
        Command con las actualizaciones optimizadas para interrumpir el flujo
    """
    node = RecopilarInputUsuarioNode()
    return await node.execute_with_monitoring(state)