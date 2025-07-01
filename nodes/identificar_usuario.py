# =====================================================
# nodes/identificar_usuario.py - HÍBRIDO MEJORADO
# =====================================================
from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage
from langgraph.types import Command

from .base_node import BaseNode, ActorDecision
from utils.extractors.user_extractor import extraer_datos_usuario

class IdentificarUsuarioNode(BaseNode):
    """
    🎭 ACTOR HÍBRIDO: Identificar y validar datos del usuario
    
    COMPORTAMIENTO ACTOR:
    - ✅ Autonomía total en decisiones
    - ✅ Señales claras al router
    - ✅ Estado encapsulado
    - ✅ Evita bucles infinitos
    
    RESPONSABILIDADES:
    - Extraer nombre y email de mensajes
    - Validar completitud de datos
    - Solicitar datos faltantes con mensajes específicos
    - Señalar completitud al router
    """
    
    def __init__(self):
        super().__init__("IdentificarUsuario", timeout_seconds=45)
    
    def get_required_fields(self) -> List[str]:
        return ["messages"]
    
    def get_actor_description(self) -> str:
        return (
            "Actor autónomo que identifica y valida datos del usuario. "
            "Evita bucles infinitos mediante señalización clara al router."
        )

    async def execute(self, state: Dict[str, Any]) -> Command:
        """🎭 LÓGICA DEL ACTOR con protección contra bucles"""
        
        # 🔍 ANÁLISIS DEL ESTADO ACTUAL
        nombre_actual = state.get("nombre")
        email_actual = state.get("email")
        
        # ✅ CONTADOR DE EJECUCIONES EN LUGAR DE INTENTOS
        execution_count = state.get("_execution_count", 0) + 1
        state["_execution_count"] = execution_count
        
        # 🛑 EARLY STOPPING AGRESIVO
        if execution_count > 3:
            self.logger.warning(f"🛑 BUCLE DETECTADO: {execution_count} ejecuciones")
            
            # FORZAR ESCALACIÓN INMEDIATAMENTE
            return Command(update={
                "escalar_a_supervisor": True,
                "razon_escalacion": f"Bucle infinito detectado después de {execution_count} ejecuciones",
                "messages": [AIMessage(content="He detectado un problema técnico. Derivando a un supervisor para ayudarte mejor.")],
                "_next_actor": "escalar_supervisor"
            })
        
        self.logger.info(f"📊 Estado: Nombre={nombre_actual}, Email={email_actual}, Ejecución={execution_count}")
        
        # ✅ DECISIÓN 1: Si ya tengo datos completos, COMPLETAR INMEDIATAMENTE
        if nombre_actual and email_actual:
            self.logger.info("✅ DATOS COMPLETOS - Finalizando")
            return Command(update={
                "datos_usuario_completos": True,
                "flujo_completado": True,
                "_next_actor": "procesar_incidencia",
                "messages": [AIMessage(content=f"¡Perfecto {nombre_actual}! Ahora cuéntame tu problema técnico.")]
            })
        
        # ✅ EXTRACCIÓN DE DATOS (solo si no tengo datos)
        ultimo_mensaje = self.get_last_user_message(state)
        
        try:
            datos_extraidos = await extraer_datos_usuario(ultimo_mensaje)
            nombre_extraido = datos_extraidos.nombre
            email_extraido = datos_extraidos.email
            
            # Consolidar datos
            nombre_final = nombre_extraido or nombre_actual
            email_final = email_extraido or email_actual
            
            if nombre_final and email_final:
                # COMPLETAR INMEDIATAMENTE
                return Command(update={
                    "nombre": nombre_final,
                    "email": email_final,
                    "datos_usuario_completos": True,
                    "_next_actor": "procesar_incidencia",
                    "messages": [AIMessage(content=f"¡Perfecto {nombre_final}! Ahora cuéntame tu problema técnico.")]
                })
            else:
                # PEDIR DATOS CON LÍMITE
                if execution_count >= 2:
                    # Después de 2 intentos, usar formato simple
                    return Command(update={
                        "escalar_a_supervisor": True,
                        "razon_escalacion": "No se pudieron obtener datos de usuario",
                        "messages": [AIMessage(content="Tengo dificultades para obtener tus datos. Derivando a un supervisor.")],
                        "_next_actor": "escalar_supervisor"
                    })
                else:
                    # Primer intento normal
                    return Command(update={
                        "messages": [AIMessage(content="¡Hola! Necesito tu nombre completo y email para ayudarte. Por favor compártelos.")],
                        # NO establecer _next_actor para que el router decida
                    })
                    
        except Exception as e:
            self.logger.error(f"❌ Error: {e}")
            return Command(update={
                "escalar_a_supervisor": True,
                "razon_escalacion": f"Error técnico: {str(e)}",
                "messages": [AIMessage(content="He tenido un error técnico. Derivando a un supervisor.")],
                "_next_actor": "escalar_supervisor"
            })



    async def _process_user_input(
        self, 
        state: Dict[str, Any], 
        nombre_actual: str, 
        email_actual: str, 
        intentos: int
    ) -> Command:
        """Procesar input del usuario y tomar decisión autónoma"""
        
        ultimo_mensaje = self.get_last_user_message(state)
        
        try:
            # Extraer datos del mensaje
            datos_extraidos = await extraer_datos_usuario(ultimo_mensaje)
            nombre_extraido = getattr(datos_extraidos, 'nombre', None)
            email_extraido = getattr(datos_extraidos, 'email', None)
            
            self.logger.info(f"🔍 Extraído: Nombre={nombre_extraido}, Email={email_extraido}")
            
            # Consolidar datos (mantener los que ya tenía)
            nombre_final = nombre_extraido or nombre_actual
            email_final = email_extraido or email_actual
            
            # 🎯 DECISIÓN AUTÓNOMA basada en datos disponibles
            if nombre_final and email_final:
                # ✅ TENGO TODO → Actualizar estado y completar
                return self._actor_complete_with_data(nombre_final, email_final)
            
            elif email_final and not nombre_final:
                # 📥 TENGO EMAIL, FALTA NOMBRE → Solicitar nombre específicamente
                return self._request_name_specifically(email_final, intentos)
            
            elif nombre_final and not email_final:
                # 📥 TENGO NOMBRE, FALTA EMAIL → Solicitar email específicamente
                return self._request_email_specifically(nombre_final, intentos)
            
            else:
                # 📥 NO TENGO NADA → Solicitar ambos
                return self._request_both_data(intentos)
                
        except Exception as e:
            self.logger.error(f"❌ Error extrayendo datos: {e}")
            return self._request_both_data(intentos)
    
    def _actor_complete_with_data(self, nombre: str, email: str) -> Command:
        """
        🎯 DECISIÓN DEL ACTOR: COMPLETAR TAREA
        
        El actor ha obtenido todos los datos necesarios y señala
        completitud al router con próximo paso específico.
        """
        mensaje_confirmacion = (
            f"¡Perfecto, {nombre}! Ya tengo tus datos:\n"
            f"📧 **Email**: {email}\n"
            f"👤 **Nombre**: {nombre}\n\n"
            f"Ahora cuéntame, ¿cuál es el problema técnico que necesitas resolver?"
        )
        
        # ✅ SEÑAL CLARA AL ROUTER: "Estoy completo, ir a procesar incidencia"
        return self.signal_completion(
            state={},
            next_actor="procesar_incidencia",  # ✅ SEÑAL EXPLÍCITA
            completion_message=mensaje_confirmacion,
            # Datos actualizados
            nombre=nombre,
            email=email,
            datos_usuario_completos=True,  # 🔑 CLAVE: Evita bucles
            intentos=0  # Reset intentos para el siguiente actor
        )
    
    def _request_name_specifically(self, email: str, intentos: int) -> Command:
        """🎯 DECISIÓN DEL ACTOR: Solicitar nombre específicamente"""
        
        mensaje = (
            f"Tengo tu email ({email}). "
            f"¿Cuál es tu **nombre completo**?"
        )
        
        # ✅ SEÑAL AL ROUTER: "Necesito input específico"
        return self.signal_need_input(
            state={"email": email, "intentos": intentos},
            request_message=mensaje,
            context={"waiting_for": "nombre", "have_email": email}
        )
    
    def _request_email_specifically(self, nombre: str, intentos: int) -> Command:
        """🎯 DECISIÓN DEL ACTOR: Solicitar email específicamente"""
        
        mensaje = (
            f"Hola {nombre}, necesito tu **email corporativo** "
            f"para completar tu identificación."
        )
        
        # ✅ SEÑAL AL ROUTER: "Necesito input específico"
        return self.signal_need_input(
            state={"nombre": nombre, "intentos": intentos},
            request_message=mensaje,
            context={"waiting_for": "email", "have_name": nombre}
        )
    
    def _request_both_data(self, intentos: int) -> Command:
        """🎯 DECISIÓN DEL ACTOR: Solicitar ambos datos"""
        
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
        return self.signal_need_input(
            state={"intentos": intentos},
            request_message=mensaje,
            context={"waiting_for": ["nombre", "email"]}
        )

    async def _confirm_user_data(self, state: Dict[str, Any], nombre: str, email: str, intentos: int) -> Command:
        """✅ CONFIRMAR DATOS Y SEÑALAR COMPLETITUD AL ROUTER"""
        
        # 📝 Mensaje de confirmación para el usuario
        mensaje_confirmacion = (
            f"¡Perfecto, {nombre}! Ya tengo tus datos:\n"
            f"📧 **Email**: {email}\n"
            f"👤 **Nombre**: {nombre}\n\n"
            f"Ahora cuéntame, ¿cuál es el problema técnico que necesitas resolver?"
        )
        
        # ✅ SEÑAL CLARA AL ROUTER: "Estoy completo, ir a procesar incidencia"
        return self.signal_completion(
            state=state,
            next_actor="procesar_incidencia",
            completion_message=mensaje_confirmacion,
            # Datos actualizados
            nombre=nombre,
            email=email,
            datos_usuario_completos=True,  # 🔑 EVITA BUCLES
            intentos=0  # Reset intentos
        )

    async def _handle_data_extraction_flow(self, state: Dict[str, Any], intentos: int) -> Command:
        """
        Flujo principal de extracción de datos del usuario.
        
        VERSIÓN HÍBRIDA que evita bucles infinitos mediante señalización clara.
        """
        ultimo_mensaje = self.get_last_user_message(state)
        
        try:
            # Extraer datos del mensaje del usuario
            datos_extraidos = await extraer_datos_usuario(ultimo_mensaje)
            nombre_extraido = getattr(datos_extraidos, 'nombre', None)
            email_extraido = getattr(datos_extraidos, 'email', None)
            
            # Obtener datos que ya teníamos (mantener estado)
            nombre_actual = state.get("nombre")
            email_actual = state.get("email")
            
            # Consolidar datos (mantener los que ya teníamos)
            nombre_final = nombre_extraido or nombre_actual
            email_final = email_extraido or email_actual
            
            self.logger.info(f"🔍 Datos consolidados - Nombre: {nombre_final}, Email: {email_final}")
            
            # ✅ DECISIÓN AUTÓNOMA basada en datos disponibles
            if nombre_final and email_final:
                # TENGO TODO → Completar inmediatamente
                return await self._confirm_user_data(state, nombre_final, email_final, intentos)
            else:
                # FALTAN DATOS → Solicitar específicamente lo que falta
                return await self._handle_incomplete_data(state, nombre_final, email_final, intentos)
                
        except Exception as e:
            self.logger.error(f"❌ Error extrayendo datos: {e}")
            
            # En caso de error, solicitar datos básicos
            return self.signal_need_input(
                state={"intentos": intentos},
                request_message="Disculpa, no pude procesar tu mensaje. ¿Puedes proporcionarme tu nombre completo y email corporativo?",
                context={"error": str(e), "waiting_for": ["nombre", "email"]}
            )

    async def _handle_incomplete_data(self, state: Dict[str, Any], nombre: str, email: str, intentos: int) -> Command:
        """📥 MANEJAR DATOS INCOMPLETOS SIN BUCLES"""
        
        if email and not nombre:
            mensaje = f"Tengo tu email ({email}). ¿Cuál es tu **nombre completo**?"
        elif nombre and not email:
            mensaje = f"Hola {nombre}, necesito tu **email corporativo**."
        else:
            mensaje = "Necesito tu **nombre completo** y **email corporativo**. ¿Puedes proporcionármelos?"
        
        # ✅ SEÑAL AL ROUTER: "Necesito input específico"
        return self.signal_need_input(
            state={"email": email, "nombre": nombre, "intentos": intentos},
            request_message=mensaje,
            context={"waiting_for": "user_data", "have_email": bool(email), "have_name": bool(nombre)}
        )

    # =====================================================
    # PREVENIR BUCLES - Agregar límite de recursión
    # =====================================================

    def _prevent_infinite_loops(self, state: Dict[str, Any]) -> Command:
        """
        Prevenir bucles infinitos con límite de intentos.
        
        Si se exceden los intentos, escalar o cambiar estrategia.
        """
        intentos = state.get("intentos", 0)
        
        if intentos >= 5:  # Límite máximo
            self.logger.warning(f"🔄 BUCLE DETECTADO: {intentos} intentos en identificar_usuario")
            
            # Escalar a supervisor en lugar de continuar el bucle
            return self.signal_escalation(
                state,
                f"identificar usuario después de {intentos} intentos",
                attempts=intentos
            )
        
        return None  # Continuar normalmente


# =====================================================
# WRAPPER PARA LANGGRAPH
# =====================================================
async def identificar_usuario_node(state: Dict[str, Any]) -> Command:
    """Wrapper híbrido para LangGraph"""
    node = IdentificarUsuarioNode()
    return await node.execute_with_monitoring(state)