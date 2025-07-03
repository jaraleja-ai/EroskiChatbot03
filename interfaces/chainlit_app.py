# =====================================================
# interfaces/chainlit_app.py - Integración Chainlit Actualizada
# =====================================================
"""
Aplicación Chainlit actualizada para usar la nueva arquitectura optimizada.

CAMBIOS PRINCIPALES:
- Usa EroskiChatInterface en lugar del sistema anterior
- Gestión simplificada de sesiones
- Manejo robusto de errores
- Métricas integradas
- UI mejorada específica para Eroski

CARACTERÍSTICAS:
- Un mensaje = un ciclo completo del grafo
- Estado persistente automático
- Respuestas inmediatas
- Debug y logging integrado
"""

import asyncio
import chainlit as cl
from typing import Dict, Any, Optional
from datetime import datetime
import logging
import uuid

# Importar la nueva interfaz optimizada
from interfaces.eroski_chat_interface import get_global_chat_interface
from config.settings import get_settings
from config.logging_config import setup_logging

# Configurar logging
setup_logging()
logger = logging.getLogger("ChainlitApp")

# Obtener configuración
settings = get_settings()

# Obtener interfaz global
chat_interface = get_global_chat_interface()

# ========== CONFIGURACIÓN DE CHAINLIT ==========

@cl.on_chat_start
async def start():
    """
    Inicializar nueva sesión de chat.
    """
    try:
        # Generar ID único de sesión
        session_id = f"eroski_{uuid.uuid4().hex[:8]}"
        
        # Guardar en sesión de Chainlit
        cl.user_session.set("session_id", session_id)
        cl.user_session.set("start_time", datetime.now())
        
        logger.info(f"🆕 Nueva sesión iniciada: {session_id}")
        
        # Mensaje de bienvenida personalizado para Eroski
        welcome_message = """# ¡Bienvenido al Asistente de Incidencias de Eroski! 🤖

Soy tu asistente virtual especializado en ayudarte con problemas técnicos y consultas operativas.

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

¡Estoy aquí para ayudarte! 😊
"""
        
        # Enviar mensaje de bienvenida
        await cl.Message(
            content=welcome_message,
            author="Asistente Eroski"
        ).send()
        
        # Enviar primera solicitud de autenticación
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
        
        # Estadísticas de sesiones activas
        stats = chat_interface.get_interface_stats()
        logger.info(f"📊 Sesiones activas: {stats['total_active_sessions']}")
        
    except Exception as e:
        logger.error(f"❌ Error inicializando sesión: {e}")
        await cl.Message(
            content="Ha ocurrido un error al inicializar la sesión. Por favor, recarga la página.",
            author="Sistema"
        ).send()

@cl.on_message
async def main(message: cl.Message):
    """
    Procesar mensaje del usuario con la nueva arquitectura.
    """
    try:
        # Obtener información de la sesión
        session_id = cl.user_session.get("session_id")
        if not session_id:
            await handle_session_error()
            return
        
        user_message = message.content.strip()
        if not user_message:
            await cl.Message(
                content="Por favor, escribe un mensaje para que pueda ayudarte.",
                author="Sistema"
            ).send()
            return
        
        logger.info(f"📨 Mensaje recibido en sesión {session_id}: {user_message[:100]}...")
        
        # Mostrar indicador de escritura
        await cl.Message(
            content="🤔 Analizando tu mensaje...",
            author="Sistema"
        ).send()
        
        # Procesar mensaje con la nueva interfaz
        result = await chat_interface.process_message(
            user_message=user_message,
            session_id=session_id,
            user_context={
                "platform": "chainlit",
                "user_agent": "web",
                "timestamp": datetime.now()
            }
        )
        
        # Manejar resultado
        if result["success"]:
            await handle_successful_response(result)
        else:
            await handle_error_response(result)
            
    except Exception as e:
        logger.error(f"❌ Error procesando mensaje: {e}")
        await handle_processing_error(str(e))

async def handle_successful_response(result: Dict[str, Any]):
    """
    Manejar respuesta exitosa del workflow.
    """
    try:
        response_content = result["response"]
        status = result.get("status", "unknown")
        metadata = result.get("metadata", {})
        
        # Personalizar autor según el estado
        if status == "escalated":
            author = "Supervisor"
            response_content += "\n\n*Tu consulta ha sido derivada a un supervisor especializado.*"
        elif status == "resolved":
            author = "Asistente ✅"
            response_content += "\n\n*¡Problema resuelto exitosamente!*"
        else:
            author = "Asistente Eroski"
        
        # Enviar respuesta principal
        await cl.Message(
            content=response_content,
            author=author
        ).send()
        
        # Enviar información adicional si es relevante
        await send_metadata_info(metadata, status)
        
        # Logging para métricas
        log_interaction_metrics(result)
        
    except Exception as e:
        logger.error(f"❌ Error manejando respuesta exitosa: {e}")
        await handle_processing_error("Error enviando respuesta")

async def send_metadata_info(metadata: Dict[str, Any], status: str):
    """
    Enviar información adicional basada en metadatos.
    """
    try:
        # Si hay información del empleado, mostrarla discretamente
        if metadata.get("employee_name") and status not in ["escalated", "resolved"]:
            employee_info = f"""
*Información de sesión:*
👤 **Empleado:** {metadata['employee_name']}
🏪 **Tienda:** {metadata.get('store_name', 'No especificada')}
"""
            await cl.Message(
                content=employee_info,
                author="Sistema",
                indent=1
            ).send()
        
        # Si hay información de incidencia crítica
        if metadata.get("urgency_level") and metadata["urgency_level"] >= 3:
            await cl.Message(
                content="⚠️ *Esta consulta ha sido marcada como de alta prioridad.*",
                author="Sistema",
                indent=1
            ).send()
            
    except Exception as e:
        logger.warning(f"⚠️ Error enviando metadata: {e}")

def log_interaction_metrics(result: Dict[str, Any]):
    """
    Registrar métricas de la interacción para análisis.
    """
    try:
        metadata = result.get("metadata", {})
        
        metrics = {
            "session_id": result.get("session_id"),
            "status": result.get("status"),
            "resolved": result.get("resolved", False),
            "escalated": result.get("escalated", False),
            "employee_id": metadata.get("employee_id"),
            "store_id": metadata.get("store_id"),
            "query_type": metadata.get("query_type"),
            "incident_type": metadata.get("incident_type"),
            "total_messages": metadata.get("total_messages", 0),
            "resolution_time": metadata.get("resolution_time"),
            "platform": "chainlit"
        }
        
        logger.info(f"📊 Métricas de interacción: {metrics}")
        
    except Exception as e:
        logger.warning(f"⚠️ Error registrando métricas: {e}")

async def handle_error_response(result: Dict[str, Any]):
    """
    Manejar respuesta de error del workflow.
    """
    error_message = result.get("response", "Ha ocurrido un error desconocido.")
    
    await cl.Message(
        content=error_message,
        author="Sistema ⚠️"
    ).send()
    
    # Ofrecer opciones de recuperación
    recovery_options = """
**Opciones disponibles:**
🔄 Intenta enviar tu mensaje nuevamente
📞 Contacta con soporte: +34 900 123 456
📧 Email directo: soporte.tecnico@eroski.es
"""
    
    await cl.Message(
        content=recovery_options,
        author="Sistema",
        indent=1
    ).send()

async def handle_processing_error(error_message: str):
    """
    Manejar errores técnicos durante el procesamiento.
    """
    await cl.Message(
        content=f"""Ha ocurrido un error técnico: {error_message}

Por favor:
1. **Intenta nuevamente** en unos segundos
2. **Si persiste**, contacta con soporte técnico

📞 **Soporte:** +34 900 123 456
📧 **Email:** soporte.tecnico@eroski.es""",
        author="Sistema ❌"
    ).send()

async def handle_session_error():
    """
    Manejar errores de sesión.
    """
    await cl.Message(
        content="""Error de sesión detectado. Por favor:

1. **Recarga la página** para iniciar una nueva sesión
2. **Si el problema persiste**, limpia el cache del navegador

¡Disculpa las molestias! 🙏""",
        author="Sistema ⚠️"
    ).send()

# ========== COMANDOS ESPECIALES ==========

@cl.on_message
async def handle_special_commands(message: cl.Message):
    """
    Manejar comandos especiales del sistema.
    """
    content = message.content.strip().lower()
    
    # Comando de ayuda
    if content in ["/ayuda", "/help", "ayuda"]:
        await send_help_message()
        return True
    
    # Comando de estadísticas (solo para administradores)
    if content in ["/stats", "/estadisticas"]:
        await send_stats_message()
        return True
    
    # Comando de reset de sesión
    if content in ["/reset", "/reiniciar"]:
        await reset_current_session()
        return True
    
    return False

async def send_help_message():
    """Enviar mensaje de ayuda."""
    help_content = """# 🆘 **Ayuda del Asistente Eroski**

## **Comandos disponibles:**
• `/ayuda` - Mostrar esta ayuda
• `/reset` - Reiniciar sesión
• `/stats` - Estadísticas del sistema

## **Tipos de consultas:**
🔧 **Incidencias técnicas**: TPV, impresoras, red, software
❓ **Consultas generales**: Procedimientos, información
🆘 **Urgencias**: Problemas críticos

## **Formato recomendado:**
"Tengo un problema con [equipo/sistema]. [Descripción del problema]. Empezó [cuándo]."

**Ejemplo:** "El TPV de la caja 3 no enciende desde esta mañana. Sale un error en pantalla."
"""
    
    await cl.Message(
        content=help_content,
        author="Ayuda"
    ).send()

async def send_stats_message():
    """Enviar estadísticas del sistema."""
    try:
        stats = chat_interface.get_interface_stats()
        
        stats_content = f"""# 📊 **Estadísticas del Sistema**

**Sesiones activas:** {stats['total_active_sessions']}

**Por estado:**
{_format_dict(stats.get('sessions_by_status', {}))}

**Por tienda:**
{_format_dict(stats.get('sessions_by_store', {}))}

**Última actualización:** {datetime.now().strftime('%H:%M:%S')}
"""
        
        await cl.Message(
            content=stats_content,
            author="Estadísticas"
        ).send()
        
    except Exception as e:
        await cl.Message(
            content=f"Error obteniendo estadísticas: {e}",
            author="Sistema"
        ).send()

def _format_dict(data: Dict[str, int]) -> str:
    """Formatear diccionario para mostrar estadísticas."""
    if not data:
        return "• No hay datos disponibles"
    
    lines = []
    for key, value in data.items():
        lines.append(f"• **{key}**: {value}")
    
    return "\n".join(lines)

async def reset_current_session():
    """Reiniciar sesión actual."""
    try:
        session_id = cl.user_session.get("session_id")
        if session_id:
            success = await chat_interface.reset_session(session_id)
            if success:
                await cl.Message(
                    content="✅ Sesión reiniciada correctamente. Puedes empezar de nuevo.",
                    author="Sistema"
                ).send()
            else:
                await cl.Message(
                    content="❌ Error reiniciando sesión. Recarga la página.",
                    author="Sistema"
                ).send()
        else:
            await cl.Message(
                content="⚠️ No hay sesión activa para reiniciar.",
                author="Sistema"
            ).send()
            
    except Exception as e:
        logger.error(f"Error reiniciando sesión: {e}")
        await cl.Message(
            content="Error técnico reiniciando sesión.",
            author="Sistema"
        ).send()

# ========== CONFIGURACIÓN DE LA APLICACIÓN ==========

@cl.on_settings_update
async def setup_agent(settings):
    """
    Actualizar configuración del agente.
    """
    logger.info("🔧 Configuración actualizada")

@cl.on_chat_end
async def end():
    """
    Finalizar sesión de chat.
    """
    session_id = cl.user_session.get("session_id")
    start_time = cl.user_session.get("start_time")
    
    if session_id and start_time:
        duration = (datetime.now() - start_time).total_seconds() / 60
        logger.info(f"🏁 Sesión finalizada: {session_id} (duración: {duration:.1f} min)")

# ========== PUNTO DE ENTRADA ==========

if __name__ == "__main__":
    logger.info("🚀 Iniciando aplicación Chainlit para Eroski")
    
    # Configurar puerto desde settings
    port = getattr(settings, 'chainlit_port', 8000)
    host = getattr(settings, 'chainlit_host', '0.0.0.0')
    
    logger.info(f"🌐 Servidor iniciando en {host}:{port}")
    
    # La aplicación se ejecuta automáticamente cuando se importa chainlit