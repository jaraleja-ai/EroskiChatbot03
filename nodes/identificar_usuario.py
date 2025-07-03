# =====================================================
# nodes/identificar_usuario.py - IDENTIFICAR USUARIO CORREGIDO
# =====================================================
from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime

from .base_node import BaseNode, ActorDecision
from utils.extractors.user_extractor import extraer_datos_usuario
from utils.interruption_trip import create_interruption_trip
class IdentificarUsuarioNode(BaseNode):
    """
    
    RESPONSABILIDADES:
    - Extraer nombre y email de mensajes
    - Validar completitud de datos
    - Solicitar datos faltantes con mensajes específicos
    - Señalar completitud al router
    """
    
    def __init__(self):
        super().__init__("identificar_usuario", timeout_seconds=45)
    
    def get_required_fields(self) -> List[str]:
        """✅ IMPLEMENTACIÓN REQUERIDA"""
        return ["messages"]
    
    def get_actor_description(self) -> str:
        """✅ IMPLEMENTACIÓN REQUERIDA - Corregida"""
        return (
            "Actor autónomo que identifica y valida datos del usuario. "
            "Evita bucles infinitos mediante señalización clara al router."
        )

    async def execute(self, state: Dict[str, Any]) -> Command:
        """🎭 LÓGICA DEL ACTOR con prevención de bucles CORREGIDA"""
        
        # 🔍 DEBUG AL INICIO
        self.logger.info("🔍 === IDENTIFICAR_USUARIO EXECUTE CON DEBUG COMMAND ===")
        self.logger.info(f"📥 Estado recibido: claves={list(state.keys())}")
        
        current_message = self.get_last_user_message(state)
        last_processed = state.get("_last_processed_message", "")
        execution_count = state.get("_execution_count", 0)
        
        self.logger.info(f"📥 Mensaje actual: '{current_message[:25] if current_message else 'None'}...'")
        self.logger.info(f"📜 Último procesado: '{last_processed}'")
        self.logger.info(f"🔢 Intentos actual: {execution_count}")
        
        # 🛑 PROTECCIÓN ANTI-BUCLE INMEDIATA
        if execution_count > 10:
            self.logger.error(f"🛑 BUCLE INFINITO DETECTADO - {execution_count} ejecuciones")
            update_data = self.signal_escalation(
                state,
                f"Bucle infinito en identificar_usuario después de {execution_count} intentos",
                attempts=execution_count
            )
            return Command(goto="escalar_supervisor",
                           update=update_data)
        
        # 🔄 DETECCIÓN DE MENSAJE REPETIDO 
        if current_message == last_processed and current_message and execution_count > 2:
            self.logger.warning(f"🔄 MENSAJE REPETIDO DETECTADO - ESCALAR")
            

            update_data = self.signal_escalation(
                state,
                f"Bucle infinito en identificar_usuario después de {execution_count} intentos",
                attempts=execution_count
            )
            return Command(goto="escalar_supervisor",
                           update=update_data)
        
        # 📊 ANÁLISIS DEL ESTADO ACTUAL
        nombre = state.get("nombre")
        email = state.get("email")
        intentos = state.get("intentos", 0) + 1
        
        self.logger.info(f"📊 Estado: Nombre={nombre}, Email={email}, Intentos={intentos}")
        
        # 🔍 PROCESAR INPUT DEL USUARIO
        if current_message:
            self.logger.info(f"🔍 _process_user_input - mensaje: '{current_message[:25]}...'")
            try:
                extracted_data = await self._process_user_input(current_message, state)
                
                if extracted_data:
                    nombre = extracted_data.get("nombre") or nombre
                    email = extracted_data.get("email") or email
                    self.logger.info(f"🔍 Extraído: Nombre={nombre}, Email={email}")
            except Exception as e:
                self.logger.error(f"❌ Error extrayendo datos: {e}")
                # Continuar con datos existentes
        
        # 🔧 ACTUALIZAR DATOS FINALES
        final_nombre = nombre
        final_email = email
        self.logger.info(f"🔧 Datos finales: nombre={final_nombre}, email={final_email}")
        
        # 🎯 DECISIÓN PRINCIPAL DEL ACTOR
        if final_nombre and final_email:
            # ✅ TENEMOS TODOS LOS DATOS
            self.logger.info("✅ DATOS COMPLETOS → Continuar flujo")
            
            mensaje_confirmacion = (
                f"¡Perfecto, {final_nombre}! Ya tengo tus datos:\n"
                f"📧 **Email**: {final_email}\n"
                f"👤 **Nombre**: {final_nombre}\n\n"
                f"Ahora cuéntame, ¿cuál es el problema técnico que necesitas resolver?"
            )
            
            update_data = self.signal_completion(
                state,
                completion_message=mensaje_confirmacion,
                nombre=final_nombre,
                email=final_email,
                intentos=intentos,
                datos_usuario_completos=True,
                usuario_encontrado_bd=True,  # Simular por ahora
                _last_processed_message=current_message,
                _execution_count=execution_count + 1
            )
            return Command(goto="procesar_incidencia",
                           update=update_data)
        
        elif intentos >= 5:
            # 🛑 DEMASIADOS INTENTOS
            self.logger.warning("🛑 DEMASIADOS INTENTOS → Escalar")
            
            update_data = self.signal_escalation(
                state,
                f"No se pudieron obtener datos después de {intentos} intentos",
                attempts=intentos
            )
            return Command(goto="escalar_supervisor",
                           update=update_data)

        else:
            # 📥 SOLICITAR DATOS FALTANTES
            if not final_nombre and not final_email:
                self.logger.info("❌ NO TENGO DATOS → Solicitar ambos")
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
                waiting_for = ["nombre", "email"]
                reason = "missing_both_data"
            elif not final_nombre:
                self.logger.info("❌ FALTA NOMBRE → Solicitar nombre")
                mensaje = f"Tengo tu email ({final_email}). ¿Cuál es tu **nombre completo**?"
                waiting_for = ["nombre"]
                reason = "missing_name"
            else:  # not final_email
                self.logger.info("❌ FALTA EMAIL → Solicitar email")
                mensaje = f"Hola {final_nombre}, necesito tu **email corporativo**."
                waiting_for = ["email"]
                reason = "missing_email"
            
            # 🔍 GENERAR COMMAND CON SEÑALES CLARAS
            self.logger.info("🔍 Creando signal_need_input con:")
            self.logger.info(f"   mensaje: '{mensaje[:50]}...'")
            self.logger.info(f"   intentos: {intentos}")
            
            self.logger.info("📥 IdentificarUsuario solicita input del usuario → router → interrupcion_identificar_usuario")
            
            # ✅ USAR EL MÉTODO CORREGIDO
            
            update_data = self.signal_need_input(
                state={**state, 
                       "nombre": final_nombre, 
                       "email": final_email, 
                       "intentos": intentos,
                       "_last_processed_message": current_message,
                       "_execution_count": execution_count + 1},
                request_message=mensaje,
                context={
                    "waiting_for": waiting_for,
                    "reason": reason,
                    "intentos": intentos,
                    "requesting_node": "IdentificarUsuario",
                    "resume_node": "identificar_usuario",
                    "timestamp": datetime.now().isoformat()
                }
            )
            return Command(goto="interrupcion_identificar_usuario",
                           update=update_data)

    # =====================================================
    # MÉTODOS AUXILIARES
    # =====================================================
    
    async def _process_user_input(self, message: str, state: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Procesar input del usuario para extraer datos"""
        try:
            # Usar el extractor de datos de usuario
            datos_extraidos = await extraer_datos_usuario(message)
            
            if datos_extraidos:
                return {
                    "nombre": getattr(datos_extraidos, 'nombre', None),
                    "email": getattr(datos_extraidos, 'email', None)
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error en extracción: {e}")
            return None
    
    def get_last_user_message(self, state: Dict[str, Any]) -> str:
        """✅ CORREGIDO: Obtener el último mensaje del usuario"""
        messages = state.get("messages", [])
        
        for message in reversed(messages):
            # Método 1: Verificar por tipo de clase (más confiable)
            if isinstance(message, HumanMessage):
                return message.content
            
            # Método 2: Verificar por atributo type (backup)
            if hasattr(message, 'type') and message.type == "Human":  # ✅ "Human" con mayúscula
                return message.content
        
        return ""

    def signal_need_input(
        self, 
        state: Dict[str, Any], 
        request_message: str, 
        context: Dict[str, Any] = None
    ) -> dict:
        """
        🎭 Señalar que se necesita input del usuario CORREGIDO.
        
        CAMBIOS PRINCIPALES:
        1. ✅ Señalización clara sin bucles
        2. ✅ Contexto mejorado para continuación
        3. ✅ Logging detallado para debugging
        """
        # Ahora self.name = "identificar_usuario" ✅
        # Actualizar el estado
        messages = state.get("messages", []) + [request_message]
        self.logger.info("📥 IdentificarUsuario solicita input del usuario → router → interrupcion_identificar_usuario")
        self.logger.info(f"📥 IdentificarUsuario SOLICITA INPUT: {request_message[:50]}...")
        # Crear interrupción de ida
        # Preparar contexto por defecto si no se proporciona
        if context is None:
            context = {
                "waiting_for": ["nombre", "email"],
                "reason": "missing_data",
                "requesting_node": "IdentificarUsuario",
                "resume_node": "identificar_usuario",
                "timestamp": datetime.now().isoformat()
            }
        
        # 🎯 COMANDO CORREGIDO CON SEÑALIZACIÓN CLARA

        update={
            "messages": messages,
            "_request_message": request_message,
            "messages": [AIMessage(content=request_message)],
            
        }
        return update

# =====================================================
# WRAPPER PARA LANGGRAPH
# =====================================================
async def identificar_usuario_node(state: Dict[str, Any]) -> Command:
    """
    Wrapper function para el nodo de identificación de usuario.
    """
    node = IdentificarUsuarioNode()
    
    # Debug logging
    node.logger.info(f"🔵 ESTADO ANTES DE EXECUTE: {state.get('_actor_decision')}")
    
    try:
        result = await node.execute_with_monitoring(state)
        
        node.logger.info(f"🔴 COMMAND RETORNADO: type={type(result)}")
        if hasattr(result, 'update'):
            node.logger.info(f"🔴 UPDATE CONTIENE _actor_decision: {result.update.get('_actor_decision')}")
        
        return result
        
    except Exception as e:
        node.logger.error(f"❌ Error en identificar_usuario_node: {e}")
        # Retornar comando de escalación en caso de error
        return Command(update={
            "escalar_a_supervisor": True,
            "razon_escalacion": f"Error en identificar_usuario_node: {str(e)}",
            "_actor_decision": "escalate",
            "_next_actor": "escalar_supervisor"
        })