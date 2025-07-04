# =====================================================
# interfaces/chainlit_app.py - INTERFAZ ÚNICA Y FUNCIONAL
# =====================================================
"""
Interfaz Chainlit única y limpia para Eroski.
Esta es la ÚNICA interfaz que debe existir.

FUNCIONALIDADES:
- Gestión de sesiones con EroskiChatInterface
- Handlers de Chainlit correctamente implementados
- Debug y logging integrado
- UI específica para Eroski
- Sin conflictos con otras interfaces
"""

import asyncio
import chainlit as cl
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import uuid
from langchain_core.messages import AIMessage

# ========== IMPORTS SIMPLIFICADOS ==========

try:
    # Intentar importar la interfaz optimizada
    from interfaces.eroski_chat_interface import get_global_chat_interface
    INTERFACE_AVAILABLE = True
except ImportError as e:
    logging.warning(f"EroskiChatInterface no disponible: {e}")
    INTERFACE_AVAILABLE = False

try:
    from config.settings import get_settings
    from config.logging_config import setup_logging
    SETTINGS_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Settings no disponibles: {e}")
    SETTINGS_AVAILABLE = False

# ========== CONFIGURACIÓN ==========

# Configurar logging básico
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ChainlitApp")

# Configurar logging avanzado si está disponible
if SETTINGS_AVAILABLE:
    try:
        setup_logging()
        settings = get_settings()
        logger.info("✅ Configuración avanzada cargada")
    except Exception as e:
        logger.warning(f"Configuración avanzada falló: {e}")
        settings = None
else:
    settings = None

# Obtener interfaz global si está disponible
if INTERFACE_AVAILABLE:
    try:
        chat_interface = get_global_chat_interface()
        logger.info("✅ EroskiChatInterface cargada")
    except Exception as e:
        logger.error(f"Error cargando EroskiChatInterface: {e}")
        chat_interface = None
else:
    chat_interface = None

# ========== FALLBACK SIMPLE ==========

class SimpleChatManager:
    """Manager simple como fallback"""
    
    def __init__(self):
        self.sessions = {}
        self.logger = logger
    
    async def process_message(self, message: str, session_id: str) -> str:
        """Procesar mensaje de forma simple"""
        self.logger.info(f"📩 Procesando mensaje: {message[:50]}...")
        
        # Respuestas simples para testing
        if "hola" in message.lower():
            return "¡Hola! Soy el Asistente de Eroski. ¿En qué puedo ayudarte hoy?"
        elif "problema" in message.lower() or "incidencia" in message.lower():
            return "Entiendo que tienes un problema. Para ayudarte mejor, necesito:\n\n📧 Tu email corporativo\n🏪 Tu tienda\n🔧 Descripción del problema"
        elif "@eroski.es" in message.lower():
            return "Perfecto, he registrado tu email. Ahora cuéntame: ¿qué problema estás experimentando?"
        elif "gracias" in message.lower():
            return "¡De nada! ¿Hay algo más en lo que pueda ayudarte?"
        else:
            return f"He recibido tu mensaje: '{message}'\n\n¿Podrías proporcionar más detalles sobre tu consulta?"

# Usar interfaz avanzada o fallback
if chat_interface:
    message_processor = chat_interface
    ADVANCED_MODE = True
else:
    message_processor = SimpleChatManager()
    ADVANCED_MODE = False

logger.info(f"🔧 Modo: {'Avanzado' if ADVANCED_MODE else 'Fallback'}")

# ========== EVENTOS DE CHAINLIT ==========

@cl.on_chat_start
async def start():
    """Inicializar nueva sesión de chat"""
    try:
        # Generar ID único de sesión
        session_id = f"eroski_{uuid.uuid4().hex[:8]}"
        
        # Guardar en sesión de Chainlit
        cl.user_session.set("session_id", session_id)
        cl.user_session.set("start_time", datetime.now())
        
        logger.info(f"🆕 Nueva sesión iniciada: {session_id}")
        
        # Mensaje de bienvenida
        welcome_message = """# ¡Bienvenido al Asistente de Incidencias de Eroski! 🤖

Soy tu asistente virtual especializado en ayudarte a resolver incidencias.

## ¿Cómo puedo ayudarte?

🔧 **Reportar incidencias técnicas**
   • Problemas de TPV, impresoras, red
   • Software corporativo, email
   • Equipamiento de tienda

❓ **Consultas generales**
   • Procedimientos operativos
   • Estado de tickets existentes
   • Información de sistemas

🆘 **Soporte urgente**
   • Problemas críticos que impiden trabajar
   • Escalación inmediata a supervisores

---
**Para comenzar, comparte tu información de empleado y describe tu consulta.**

¡Estoy aquí para ayudarte! 😊"""
        
        # Agregar información de modo si es necesario
        if not ADVANCED_MODE:
            welcome_message += "\n\n⚠️ **Modo Simplificado** - Funcionalidad básica activa"
        
        await cl.Message(
            content=welcome_message,
            author="Asistente Eroski"
        ).send()
        
        # Solicitud de autenticación
        auth_message = """Para poder ayudarte de la mejor manera, necesito identificarte.

Por favor, proporciona:
📧 **Tu email corporativo** (nombre@eroski.es)
🏪 **Tu tienda** (nombre o código)

**Ejemplo:** "Mi email es juan.perez@eroski.es y trabajo en Eroski Bilbao Centro"
"""
        
        await cl.Message(
            content=auth_message,
            author="Sistema"
        ).send()
        
        logger.info("✅ Sesión inicializada correctamente")
        
    except Exception as e:
        logger.error(f"❌ Error inicializando sesión: {e}")
        await cl.Message(
            content="Ha ocurrido un error al inicializar la sesión. Por favor, recarga la página.",
            author="Sistema"
        ).send()

@cl.on_message
async def main(message: cl.Message):
    """Procesar mensaje del usuario - HANDLER PRINCIPAL"""
    try:
        session_id = cl.user_session.get("session_id")
        if not session_id:
            session_id = f"fallback_{uuid.uuid4().hex[:8]}"
            cl.user_session.set("session_id", session_id)
            logger.warning(f"Sesión no encontrada, creando fallback: {session_id}")

        user_message = message.content.strip()
        if not user_message:
            await cl.Message("Por favor, escribe un mensaje para que pueda ayudarte.", author="Sistema").send()
            return

        logger.info(f"📨 Mensaje recibido en sesión {session_id}: {user_message[:100]}")

        # Mensaje de espera
        processing_msg = cl.Message(content="🤔 Analizando tu mensaje...", author="Sistema")
        await processing_msg.send()

        try:
            if ADVANCED_MODE:
                # Ejecutar el grafo con EroskiChatInterface
                result = await message_processor.process_message(
                    user_message=user_message,
                    session_id=session_id,
                    user_context={"platform": "chainlit", "timestamp": datetime.now()}
                )

                # Guardar el resultado en la sesión
                cl.user_session.set("state", result)

                # Obtener respuesta
                response = result.get("response", "Sin respuesta del asistente.")
                author = result.get("status", "") == "error" and "Sistema ⚠️" or "Asistente Eroski"
            else:
                response = await message_processor.process_message(user_message, session_id)
                author = "Asistente Eroski"

            await processing_msg.remove()
            await cl.Message(content=response, author=author).send()
            logger.info("✅ Mensaje procesado exitosamente")

        except Exception as proc_error:
            logger.error(f"❌ Error procesando mensaje: {proc_error}")
            await processing_msg.remove()
            await cl.Message(
                content=f"❌ Error procesando tu mensaje: {str(proc_error)}",
                author="Sistema"
            ).send()

    except Exception as e:
        logger.error(f"❌ Error crítico en handler: {e}")
        await cl.Message(
            content=f"❌ Error crítico: {str(e)}",
            author="Sistema"
        ).send()




@cl.on_chat_end
async def end():
    """Finalizar sesión de chat"""
    try:
        session_id = cl.user_session.get("session_id")
        start_time = cl.user_session.get("start_time")
        
        if session_id and start_time:
            duration = (datetime.now() - start_time).total_seconds() / 60
            logger.info(f"🏁 Sesión finalizada: {session_id} (duración: {duration:.1f} min)")
        
    except Exception as e:
        logger.error(f"❌ Error finalizando sesión: {e}")

# ========== CONFIGURACIÓN DE CHAINLIT ==========

@cl.set_starters
async def set_starters():
    """Configurar mensajes de inicio sugeridos"""
    return [
        cl.Starter(
            label="🖥️ Problema con computadora",
            message="Hola, tengo un problema con mi computadora. Se está ejecutando muy lenta.",
            icon="💻",
        ),
        cl.Starter(
            label="📧 Problema con email",
            message="No puedo acceder a mi correo electrónico corporativo.",
            icon="📧",
        ),
        cl.Starter(
            label="🌐 Problema de internet",
            message="Tengo problemas de conexión a internet en mi área de trabajo.",
            icon="🌐",
        ),
        cl.Starter(
            label="🔧 Otro problema",
            message="Tengo otro tipo de problema técnico que necesito resolver.",
            icon="🔧",
        )
    ]

# ========== INFORMACIÓN DE DESARROLLO ==========

if __name__ == "__main__":
    print("🚀 Interfaz Chainlit de Eroski - ÚNICA Y LIMPIA")
    print("=" * 50)
    print(f"🔧 Modo: {'Avanzado' if ADVANCED_MODE else 'Fallback Simple'}")
    print(f"⚙️  Settings: {'✅ Disponibles' if SETTINGS_AVAILABLE else '❌ No disponibles'}")
    print(f"🤖 Interface: {'✅ EroskiChatInterface' if INTERFACE_AVAILABLE else '❌ SimpleChatManager'}")
    print()
    print("Para ejecutar:")
    print("  chainlit run interfaces/chainlit_app.py --port 8000")
    print("  python main.py")
    print()
    print("¡Esta es la ÚNICA interfaz que debes usar!")