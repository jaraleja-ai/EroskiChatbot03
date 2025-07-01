# =====================================================
# utils/crear_estado_inicial.py - Creación de estado inicial
# =====================================================
"""
Utilidades para crear y manejar el estado inicial del grafo.

Este módulo proporciona funciones para:
- Crear estado inicial limpio
- Resetear estado para nueva conversación
- Configurar estado desde contexto externo
- Validar integridad del estado
"""

from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid
import logging

from models.state import GraphState
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

logger = logging.getLogger("EstadoInicial")

def crear_estado_inicial(
    sesion_id: Optional[str] = None,
    mensajes_iniciales: Optional[List[BaseMessage]] = None,
    contexto_adicional: Optional[Dict[str, Any]] = None
) -> GraphState:
    """
    Crear un estado inicial limpio con todos los campos inicializados.
    
    Args:
        sesion_id: ID de sesión específico (se genera automáticamente si no se proporciona)
        mensajes_iniciales: Mensajes iniciales de la conversación
        contexto_adicional: Contexto adicional para inicializar
        
    Returns:
        GraphState: Estado inicial del grafo con valores por defecto
    """
    try:
        logger.debug("🔧 Creando estado inicial del grafo")
        
        # Generar sesion_id si no se proporciona
        if not sesion_id:
            sesion_id = str(uuid.uuid4())
        
        # Timestamp actual
        timestamp_actual = datetime.now().isoformat()
        
        # Mensajes iniciales
        messages = mensajes_iniciales or []
        
        # Crear estado base
        estado = GraphState(
            # ===== MENSAJES =====
            messages=messages,
            
            # ===== DATOS DE USUARIO =====
            nombre=None,
            email=None,
            numero_empleado=None,
            nombre_confirmado=False,
            email_confirmado=False,
            datos_usuario_completos=False,
            usuario_encontrado_bd=False,
            
            # ===== INFORMACIÓN DE INCIDENCIA =====
            tipo_incidencia=None,
            descripcion_incidencia=None,
            prioridad_incidencia=None,
            categoria_incidencia=None,
            preguntas_contestadas=None,
            incidencia_resuelta=False,
            
            # ===== CONTROL DE FLUJO =====
            intentos=0,
            intentos_incidencia=0,
            escalar_a_supervisor=False,
            razon_escalacion=None,
            flujo_completado=False,
            
            # ===== METADATOS =====
            contexto_adicional=contexto_adicional,
            sesion_id=sesion_id,
            timestamp_inicio=timestamp_actual,
            error_info=None
        )
        
        logger.info(f"✅ Estado inicial creado - Sesión: {sesion_id}")
        logger.debug(f"📋 Mensajes iniciales: {len(messages)}")
        
        return estado
        
    except Exception as e:
        logger.error(f"❌ Error creando estado inicial: {e}")
        raise

def crear_estado_desde_mensaje(
    mensaje_usuario: str,
    sesion_id: Optional[str] = None,
    contexto: Optional[Dict[str, Any]] = None
) -> GraphState:
    """
    Crear estado inicial a partir de un mensaje del usuario.
    
    Args:
        mensaje_usuario: Primer mensaje del usuario
        sesion_id: ID de sesión opcional
        contexto: Contexto adicional
        
    Returns:
        GraphState inicializado con el mensaje del usuario
    """
    try:
        logger.debug(f"🗣️ Creando estado desde mensaje: {mensaje_usuario[:50]}...")
        
        # Crear mensaje inicial
        mensaje_inicial = HumanMessage(content=mensaje_usuario)
        
        # Crear estado con el mensaje
        estado = crear_estado_inicial(
            sesion_id=sesion_id,
            mensajes_iniciales=[mensaje_inicial],
            contexto_adicional=contexto
        )
        
        logger.info("✅ Estado creado desde mensaje inicial")
        return estado
        
    except Exception as e:
        logger.error(f"❌ Error creando estado desde mensaje: {e}")
        raise

def reset_estado_usuario(estado_actual: GraphState) -> GraphState:
    """
    Resetear solo los campos relacionados con el usuario, manteniendo mensajes.
    
    Args:
        estado_actual: Estado actual del grafo
        
    Returns:
        GraphState: Estado con campos de usuario reseteados
    """
    try:
        logger.debug("🔄 Reseteando datos de usuario")
        
        # Preservar información importante
        mensajes_existentes = estado_actual.get("messages", [])
        sesion_existente = estado_actual.get("sesion_id")
        timestamp_existente = estado_actual.get("timestamp_inicio")
        
        # Crear nuevo estado manteniendo conversación
        estado_reset = crear_estado_inicial(
            sesion_id=sesion_existente,
            mensajes_iniciales=mensajes_existentes
        )
        
        # Restaurar timestamp original si existe
        if timestamp_existente:
            estado_reset["timestamp_inicio"] = timestamp_existente
        
        logger.info("✅ Datos de usuario reseteados")
        return estado_reset
        
    except Exception as e:
        logger.error(f"❌ Error reseteando estado de usuario: {e}")
        raise

def crear_estado_para_tests(
    incluir_usuario_completo: bool = False,
    incluir_incidencia: bool = False,
    incluir_escalacion: bool = False
) -> GraphState:
    """
    Crear estado inicial para testing con datos predefinidos.
    
    Args:
        incluir_usuario_completo: Si incluir datos de usuario completos
        incluir_incidencia: Si incluir datos de incidencia
        incluir_escalacion: Si marcar para escalación
        
    Returns:
        GraphState configurado para tests
    """
    try:
        logger.debug("🧪 Creando estado para tests")
        
        # Estado base
        estado = crear_estado_inicial(sesion_id="test-session-123")
        
        # Mensajes de test
        mensajes_test = [
            HumanMessage(content="Hola, soy Juan Pérez de prueba"),
            AIMessage(content="¡Hola Juan! ¿En qué puedo ayudarte?")
        ]
        estado["messages"] = mensajes_test
        
        # Datos de usuario para tests
        if incluir_usuario_completo:
            estado.update({
                "nombre": "Juan Pérez",
                "email": "juan.test@empresa.com",
                "numero_empleado": "EMP001",
                "nombre_confirmado": True,
                "email_confirmado": True,
                "datos_usuario_completos": True,
                "usuario_encontrado_bd": True
            })
        
        # Datos de incidencia para tests  
        if incluir_incidencia:
            estado.update({
                "tipo_incidencia": "software",
                "descripcion_incidencia": "Problema de test con aplicación",
                "prioridad_incidencia": "media",
                "categoria_incidencia": "aplicacion_no_abre"
            })
        
        # Escalación para tests
        if incluir_escalacion:
            estado.update({
                "escalar_a_supervisor": True,
                "razon_escalacion": "Test de escalación",
                "intentos": 5
            })
        
        logger.info("✅ Estado de test creado")
        return estado
        
    except Exception as e:
        logger.error(f"❌ Error creando estado para tests: {e}")
        raise

def validar_integridad_estado(estado: GraphState) -> List[str]:
    """
    Validar la integridad del estado del grafo.
    
    Args:
        estado: Estado a validar
        
    Returns:
        Lista de errores encontrados (vacía si todo está bien)
    """
    errores = []
    
    try:
        # Validar campos requeridos
        campos_requeridos = ["messages", "intentos", "sesion_id"]
        for campo in campos_requeridos:
            if campo not in estado:
                errores.append(f"Campo requerido faltante: {campo}")
        
        # Validar tipos de datos
        if "messages" in estado:
            if not isinstance(estado["messages"], list):
                errores.append("Campo 'messages' debe ser una lista")
            else:
                for i, msg in enumerate(estado["messages"]):
                    if not isinstance(msg, BaseMessage):
                        errores.append(f"Mensaje {i} no es instancia de BaseMessage")
        
        # Validar coherencia de datos de usuario
        if estado.get("datos_usuario_completos", False):
            if not estado.get("nombre_confirmado", False):
                errores.append("datos_usuario_completos=True pero nombre_confirmado=False")
            if not estado.get("email_confirmado", False):
                errores.append("datos_usuario_completos=True pero email_confirmado=False")
        
        # Validar intentos
        intentos = estado.get("intentos", 0)
        if intentos < 0:
            errores.append("Intentos no puede ser negativo")
        
        # Validar sesion_id
        sesion_id = estado.get("sesion_id")
        if not sesion_id or not isinstance(sesion_id, str):
            errores.append("sesion_id debe ser un string no vacío")
        
        logger.debug(f"🔍 Validación de estado: {len(errores)} errores encontrados")
        
    except Exception as e:
        errores.append(f"Error durante validación: {str(e)}")
        logger.error(f"❌ Error validando estado: {e}")
    
    return errores

def obtener_resumen_estado(estado: GraphState) -> Dict[str, Any]:
    """
    Obtener resumen legible del estado actual.
    
    Args:
        estado: Estado del grafo
        
    Returns:
        Diccionario con resumen del estado
    """
    try:
        mensajes = estado.get("messages", [])
        
        resumen = {
            "sesion_id": estado.get("sesion_id"),
            "timestamp_inicio": estado.get("timestamp_inicio"),
            "total_mensajes": len(mensajes),
            "mensajes_usuario": len([m for m in mensajes if isinstance(m, HumanMessage)]),
            "mensajes_asistente": len([m for m in mensajes if isinstance(m, AIMessage)]),
            
            "usuario": {
                "nombre": estado.get("nombre"),
                "email": estado.get("email"),
                "datos_completos": estado.get("datos_usuario_completos", False),
                "encontrado_bd": estado.get("usuario_encontrado_bd", False)
            },
            
            "incidencia": {
                "tipo": estado.get("tipo_incidencia"),
                "estado": "resuelta" if estado.get("incidencia_resuelta", False) else "en_proceso",
                "prioridad": estado.get("prioridad_incidencia")
            },
            
            "flujo": {
                "intentos": estado.get("intentos", 0),
                "intentos_incidencia": estado.get("intentos_incidencia", 0),
                "debe_escalar": estado.get("escalar_a_supervisor", False),
                "completado": estado.get("flujo_completado", False)
            }
        }
        
        return resumen
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo resumen de estado: {e}")
        return {"error": str(e)}

def copiar_estado(estado_original: GraphState) -> GraphState:
    """
    Crear una copia profunda del estado.
    
    Args:
        estado_original: Estado a copiar
        
    Returns:
        Copia del estado original
    """
    import copy
    
    try:
        logger.debug("📋 Copiando estado")
        estado_copia = copy.deepcopy(dict(estado_original))
        logger.debug("✅ Estado copiado exitosamente")
        return GraphState(estado_copia)
        
    except Exception as e:
        logger.error(f"❌ Error copiando estado: {e}")
        raise

# =====================================================
# Funciones de conveniencia adicionales
# =====================================================

def agregar_mensaje_al_estado(
    estado: GraphState, 
    mensaje: BaseMessage
) -> GraphState:
    """
    Agregar un mensaje al estado existente.
    
    Args:
        estado: Estado actual
        mensaje: Mensaje a agregar
        
    Returns:
        Estado actualizado con el nuevo mensaje
    """
    mensajes_actuales = list(estado.get("messages", []))
    mensajes_actuales.append(mensaje)
    
    estado_actualizado = dict(estado)
    estado_actualizado["messages"] = mensajes_actuales
    
    return GraphState(estado_actualizado)

def marcar_usuario_completo(estado: GraphState) -> GraphState:
    """
    Marcar datos de usuario como completos en el estado.
    
    Args:
        estado: Estado actual
        
    Returns:
        Estado con datos de usuario marcados como completos
    """
    estado_actualizado = dict(estado)
    estado_actualizado.update({
        "nombre_confirmado": True,
        "email_confirmado": True,
        "datos_usuario_completos": True
    })
    
    return GraphState(estado_actualizado)

# =====================================================
# Exportaciones del módulo
# =====================================================
__all__ = [
    "crear_estado_inicial",
    "crear_estado_desde_mensaje", 
    "reset_estado_usuario",
    "crear_estado_para_tests",
    "validar_integridad_estado",
    "obtener_resumen_estado",
    "copiar_estado",
    "agregar_mensaje_al_estado",
    "marcar_usuario_completo"
]