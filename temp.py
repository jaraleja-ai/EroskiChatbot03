# =====================================================
# nodes/authenticate_llm_driven.py - Nodo de Autenticación LLM-Driven SIMPLIFICADO
# =====================================================
"""
Nodo de autenticación simplificado que funciona como wrapper.
Esta versión garantiza compatibilidad mientras se desarrolla la versión completa.
"""

from typing import Dict, Any, Optional
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging

from models.eroski_state import EroskiState


# =============================================================================
# LOGGER
# =============================================================================

logger = logging.getLogger("LLMDrivenAuth")


# =============================================================================
# NODO SIMPLIFICADO PARA COMPATIBILIDAD
# =============================================================================

async def llm_driven_authenticate_node(state: EroskiState) -> Command:
    """
    Nodo de autenticación LLM-driven simplificado.
    
    Esta versión funciona como wrapper temporal mientras se implementa 
    la versión completa con LLM.
    
    Args:
        state: Estado actual del workflow
        
    Returns:
        Command con la actualización del estado
    """
    
    logger.info("🔑 Ejecutando nodo de autenticación LLM-driven")
    
    # 1. VERIFICAR SI YA ESTÁ AUTENTICADO
    if _is_authentication_complete(state):
        logger.info("✅ Usuario ya autenticado - continuando")
        return Command(update={
            "current_node": "authenticate",
            "awaiting_user_input": False,
            "last_activity": datetime.now()
        })
    
    # 2. PRIMERA VISITA - MENSAJE DE BIENVENIDA
    if _is_first_visit(state):
        logger.info("👋 Primera visita - enviando mensaje de bienvenida")
        
        welcome_message = """¡Hola! Soy el asistente de incidencias de Eroski 🤖

Para ayudarte de la mejor manera, necesito identificarte. Por favor, proporciona:

📧 **Tu email corporativo** (@eroski.es)
🏪 **Tu tienda** (nombre o código)
🏢 **Tu sección/departamento**

¿Podrías compartir esta información conmigo?"""
        
        return Command(update={
            "current_node": "authenticate",
            "messages": [AIMessage(content=welcome_message)],
            "awaiting_user_input": True,
            "auth_conversation_started": True,
            "attempts": 1,
            "auth_data_collected": {},
            "last_activity": datetime.now()
        })
    
    # 3. PROCESAR MENSAJE DEL USUARIO
    last_message = _get_last_user_message(state)
    
    if last_message:
        logger.info(f"📨 Procesando mensaje del usuario: {last_message[:50]}...")
        
        # Extraer datos del mensaje
        extracted_data = _extract_user_data(last_message)
        
        # Combinar con datos ya recopilados
        auth_data = state.get("auth_data_collected", {})
        auth_data.update(extracted_data)
        
        # Verificar si tenemos datos suficientes
        missing_fields = _check_missing_fields(auth_data)
        
        if not missing_fields:
            # DATOS COMPLETOS - SIMULAR VALIDACIÓN
            logger.info("✅ Datos completos - validando usuario")
            
            # Simular datos del empleado (reemplazar con búsqueda real en BD)
            employee_data = _simulate_employee_lookup(auth_data)
            
            success_message = f"""✅ **Usuario autenticado correctamente**

Bienvenido **{employee_data['name']}** de **{employee_data['store_name']}**

¿En qué puedo ayudarte hoy?"""
            
            return Command(update={
                "current_node": "authenticate",
                "messages": [AIMessage(content=success_message)],
                "authenticated": True,
                "employee_name": employee_data["name"],
                "employee_email": employee_data["email"],
                "employee_id": employee_data.get("id", "TEMP001"),
                "incident_store_name": employee_data["store_name"],
                "incident_section": employee_data["section"],
                "store_id": employee_data.get("store_id", "TEMP001"),
                "authentication_stage": "completed",
                "datos_usuario_completos": True,
                "awaiting_user_input": False,
                "auth_data_collected": auth_data,
                "last_activity": datetime.now()
            })
        
        else:
            # FALTAN DATOS - SOLICITAR MÁS INFORMACIÓN
            logger.info(f"📋 Faltan datos: {missing_fields}")
            
            request_message = _generate_data_request_message(missing_fields, auth_data)
            
            return Command(update={
                "current_node": "authenticate",
                "messages": [AIMessage(content=request_message)],
                "awaiting_user_input": True,
                "auth_data_collected": auth_data,
                "attempts": state.get("attempts", 0) + 1,
                "last_activity": datetime.now()
            })
    
    # 4. FALLBACK - SOLICITAR INFORMACIÓN NUEVAMENTE
    logger.warning("⚠️ No se pudo procesar el mensaje - solicitando información nuevamente")
    
    fallback_message = """No he podido entender tu mensaje anterior.

Por favor, proporciona:
📧 Tu email corporativo (@eroski.es)
🏪 Tu tienda
🏢 Tu sección/departamento

¿Podrías intentar de nuevo?"""
    
    return Command(update={
        "current_node": "authenticate",
        "messages": [AIMessage(content=fallback_message)],
        "awaiting_user_input": True,
        "attempts": state.get("attempts", 0) + 1,
        "last_activity": datetime.now()
    })


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================

def _is_authentication_complete(state: EroskiState) -> bool:
    """Verificar si la autenticación ya está completa"""
    return (
        state.get("authentication_stage") == "completed" and
        state.get("datos_usuario_completos") and
        state.get("employee_name") and
        state.get("incident_store_name") and
        state.get("incident_section")
    )


def _is_first_visit(state: EroskiState) -> bool:
    """Verificar si es la primera visita al nodo"""
    return not state.get("auth_conversation_started", False)


def _get_last_user_message(state: EroskiState) -> Optional[str]:
    """Obtener el último mensaje del usuario"""
    messages = state.get("messages", [])
    
    for message in reversed(messages):
        if hasattr(message, 'type') and message.type == "human":
            return message.content
        elif isinstance(message, HumanMessage):
            return message.content
    
    return None


def _extract_user_data(message: str) -> Dict[str, Any]:
    """Extraer datos del usuario del mensaje (versión simplificada)"""
    import re
    
    data = {}
    message_lower = message.lower()
    
    # Buscar email
    email_match = re.search(r'([a-zA-Z0-9._%+-]+@eroski\.es)', message)
    if email_match:
        data["email"] = email_match.group(1)
    
    # Buscar nombre (patrón simple)
    if "soy" in message_lower:
        name_match = re.search(r'soy\s+([a-záéíóúñ\s]+)', message_lower)
        if name_match:
            data["name"] = name_match.group(1).strip().title()
    
    # Buscar tienda
    if "eroski" in message_lower and ("centro" in message_lower or "tienda" in message_lower or "madrid" in message_lower):
        # Buscar patrones como "Eroski Madrid Centro"
        store_match = re.search(r'eroski\s+([a-záéíóúñ\s]+)', message_lower)
        if store_match:
            data["store_name"] = f"Eroski {store_match.group(1).strip().title()}"
    
    # Buscar sección
    sections = ["carnicería", "pescadería", "frutería", "panadería", "charcutería", "caja", "reposición", "seguridad", "administración", "it", "informática"]
    for section in sections:
        if section in message_lower:
            data["section"] = section.capitalize()
            break
    
    return data


def _check_missing_fields(auth_data: Dict[str, Any]) -> list:
    """Verificar qué campos faltan"""
    required_fields = ["email", "name", "store_name", "section"]
    missing = []
    
    for field in required_fields:
        if not auth_data.get(field):
            missing.append(field)
    
    return missing


def _generate_data_request_message(missing_fields: list, current_data: Dict[str, Any]) -> str:
    """Generar mensaje solicitando datos faltantes"""
    
    # Confirmar datos ya recibidos
    confirmation_parts = []
    if current_data.get("name"):
        confirmation_parts.append(f"👤 Nombre: {current_data['name']}")
    if current_data.get("email"):
        confirmation_parts.append(f"📧 Email: {current_data['email']}")
    if current_data.get("store_name"):
        confirmation_parts.append(f"🏪 Tienda: {current_data['store_name']}")
    if current_data.get("section"):
        confirmation_parts.append(f"🏢 Sección: {current_data['section']}")
    
    # Solicitar datos faltantes
    request_parts = []
    if "name" in missing_fields:
        request_parts.append("👤 Tu nombre completo")
    if "email" in missing_fields:
        request_parts.append("📧 Tu email corporativo (@eroski.es)")
    if "store_name" in missing_fields:
        request_parts.append("🏪 Tu tienda")
    if "section" in missing_fields:
        request_parts.append("🏢 Tu sección/departamento")
    
    message = "Perfecto, he registrado:\n\n"
    if confirmation_parts:
        message += "\n".join(confirmation_parts)
    
    message += "\n\nPara completar tu identificación, necesito:\n\n"
    message += "\n".join(request_parts)
    
    return message


def _simulate_employee_lookup(auth_data: Dict[str, Any]) -> Dict[str, Any]:
    """Simular búsqueda en base de datos (reemplazar con función real)"""
    
    # Datos simulados basados en la información proporcionada
    return {
        "id": "EMP001",
        "name": auth_data.get("name", "Usuario Temporal"),
        "email": auth_data.get("email", "temp@eroski.es"),
        "store_id": "STORE001",
        "store_name": auth_data.get("store_name", "Eroski Temporal"),
        "section": auth_data.get("section", "General"),
        "department": auth_data.get("section", "General"),
        "level": 2
    }


# =============================================================================
# WRAPPER FUNCTION PARA COMPATIBILIDAD
# =============================================================================

def authenticate_employee_node():
    """Función wrapper para compatibilidad con importaciones anteriores"""
    return llm_driven_authenticate_node


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = ["llm_driven_authenticate_node", "authenticate_employee_node"]