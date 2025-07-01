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
        """
        🎭 LÓGICA DEL ACTOR: Identificación autónoma de usuario
        
        FLUJO:
        1. Verificar si ya tengo datos completos → COMPLETAR
        2. Extraer datos del último mensaje
        3. Decidir autónomamente el próximo paso
        4. Señalar claramente la decisión al router
        """
        
        # 🔍 ANÁLISIS DEL ESTADO ACTUAL
        nombre_actual = state.get("nombre")
        email_actual = state.get("email")
        intentos = self.increment_attempts(state, "intentos")
        
        self.logger.info(f"📊 Estado: Nombre={nombre_actual}, Email={email_actual}, Intentos={intentos}")
        
        # ✅ DECISIÓN 1: Si ya tengo datos completos, COMPLETAR
        if nombre_actual and email_actual:
            return self._actor_complete_with_data(nombre_actual, email_actual)
        
        # ✅ DECISIÓN 2: Si muchos intentos, ESCALAR
        if self.should_escalate_after_attempts(intentos, max_attempts=3):
            return self.signal_escalation(
                state,
                "obtener datos de usuario completos",
                attempts=intentos
            )
        
        # ✅ DECISIÓN 3: Procesar nuevo input del usuario
        return await self._process_user_input(state, nombre_actual, email_actual, intentos)
    
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
            nombre_extraido = datos_extraidos.get("nombre")
            email_extraido = datos_extraidos.get("email")
            
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
            next_actor="procesar_incidencia",
            completion_message=mensaje_confirmacion,
            # Datos actualizados
            nombre=nombre,
            email=email,
            datos_usuario_completos=True,  # 🔑 CLAVE: Evita bucles
            intentos=0  # Reset intentos
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

# =====================================================
# WRAPPER PARA LANGGRAPH
# =====================================================
async def identificar_usuario_node(state: Dict[str, Any]) -> Command:
    """Wrapper híbrido para LangGraph"""
    node = IdentificarUsuarioNode()
    return await node.execute_with_monitoring(state)