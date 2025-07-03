# =====================================================
# models/eroski_state.py - Estado optimizado para Eroski IMPLEMENTADO
# =====================================================
"""
Estado simplificado y específico para el chatbot de Eroski.

DIFERENCIAS CON EL ESTADO ANTERIOR:
- Campos específicos para empleados de Eroski
- Estado mínimo pero completo
- Orientado a resultados de negocio
- Fácil de debuggear y mantener
- Tipos de incidencia desde configuración JSON

PRINCIPIOS DE DISEÑO:
- Un estado para todo el workflow
- Campos específicos del negocio de Eroski
- Métricas integradas desde el diseño
- Fácil serialización y persistencia
"""

from typing import TypedDict, Optional, Any, Dict
from typing import Annotated, List
from langchain_core.messages import BaseMessage
from datetime import datetime
from enum import Enum
from langgraph.graph.message import add_messages

# ========== ENUMS PARA TIPOS ESPECÍFICOS ==========

class ConsultaType(Enum):
    """Tipos de consulta que maneja el chatbot"""
    INCIDENCIA = "incidencia"
    CONSULTA = "consulta"
    URGENTE = "urgente"
    NO_CLARO = "no_claro"

class UrgencyLevel(Enum):
    """Niveles de urgencia para incidencias"""
    BAJA = 1
    MEDIA = 2 
    ALTA = 3
    CRITICA = 4

class SolutionType(Enum):
    """Tipos de solución aplicada"""
    AUTOMATICA = "automatica"      # Resuelta automáticamente
    GUIA_MANUAL = "guia_manual"    # Guía paso a paso
    ESCALADA = "escalada"          # Escalada a supervisor
    TICKET_SAP = "ticket_sap"      # Ticket creado en SAP

class StoreType(Enum):
    """Tipos de tienda Eroski"""
    HIPERMERCADO = "hipermercado"
    SUPERMERCADO = "supermercado"
    CASH_CARRY = "cash_carry"
    GASOLINERA = "gasolinera"
    FRANQUICIA = "franquicia"

class EmployeeLevel(Enum):
    """Niveles de empleado"""
    EMPLEADO = 1
    RESPONSABLE = 2
    SUPERVISOR = 3
    GERENTE = 4

# ========== ESTADO PRINCIPAL ==========

class EroskiState(TypedDict, total=False):
    """
    Estado optimizado para el chatbot de Eroski.
    
    DISEÑO PRINCIPLES:
    - Campos específicos para el negocio de Eroski
    - Estado mínimo pero completo
    - Fácil de entender y debuggear
    - Orientado a métricas de negocio
    - Compatible con LangGraph checkpointer
    """
    
    # ========== IDENTIFICACIÓN DEL EMPLEADO ==========
    session_id: str                        # ID único de la sesión
    employee_id: Optional[str]              # Número de empleado
    employee_name: Optional[str]            # Nombre completo
    employee_email: Optional[str]           # Email corporativo
    store_id: Optional[str]                 # Código de tienda
    store_name: Optional[str]               # Nombre de la tienda
    store_type: Optional[str]               # Tipo: hipermercado, supermercado, etc.
    department: Optional[str]               # Departamento: caja, carnicería, etc.
    shift: Optional[str]                    # Turno: mañana, tarde, noche
    employee_level: Optional[int]           # Nivel: 1=empleado, 2=responsable, 3=supervisor
    authenticated: bool                     # Si el empleado está autenticado
    
    # ========== CONVERSACIÓN ==========
    messages: Annotated[List[BaseMessage], add_messages]             # Historia de mensajes
    
    # ========== CLASIFICACIÓN DE LA CONSULTA ==========
    query_type: Optional[ConsultaType]      # Tipo de consulta identificado
    urgency_level: Optional[UrgencyLevel]   # Nivel de urgencia
    confidence_score: Optional[float]       # Confianza en la clasificación (0-1)
    
    # ========== INFORMACIÓN DE LA INCIDENCIA ==========
    incident_type: Optional[str]            # Tipo específico (desde JSON config)
    incident_description: Optional[str]     # Descripción del problema
    incident_details: Optional[Dict[str, Any]] # Detalles específicos
    affected_equipment: Optional[str]       # Equipo afectado
    error_codes: Optional[List[str]]        # Códigos de error reportados
    incident_location: Optional[str]        # Ubicación específica en tienda
    
    # ========== BÚSQUEDA DE SOLUCIÓN ==========
    solution_found: bool                    # Si se encontró solución
    solution_type: Optional[SolutionType]  # Tipo de solución aplicada
    solution_content: Optional[str]        # Contenido de la solución
    resolution_steps: Optional[List[str]]  # Pasos para resolver
    kb_articles: Optional[List[Dict]]      # Artículos de KB consultados
    
    # ========== ESCALACIÓN ==========
    escalation_needed: bool                # Si requiere escalación
    escalation_reason: Optional[str]       # Motivo de escalación
    escalation_level: Optional[str]        # A quién escalar: supervisor, técnico, etc.
    supervisor_id: Optional[str]           # ID del supervisor asignado
    escalation_contacts: Optional[List[str]] # Contactos de escalación
    
    # ========== TICKETS Y SEGUIMIENTO ==========
    ticket_id: Optional[str]               # ID de ticket en SAP
    ticket_created: bool                   # Si se creó ticket
    follow_up_needed: bool                 # Si requiere seguimiento
    related_tickets: Optional[List[str]]   # Tickets relacionados
    
    # ========== CONTROL DE FLUJO ==========
    current_node: str                      # Nodo actual en el grafo
    attempts: int                          # Intentos en el nodo actual
    max_attempts: int                      # Máximo de intentos permitidos
    can_retry: bool                        # Si puede reintentar
    flow_completed: bool                   # Si el flujo terminó
    awaiting_user_input: bool              # Si está esperando input del usuario
    
    # ========== RESULTADO Y MÉTRICAS ==========
    resolved: bool                         # Si se resolvió el problema
    satisfaction_score: Optional[int]      # Puntuación de satisfacción (1-5)
    resolution_time_minutes: Optional[float] # Tiempo total de resolución
    automated_resolution: bool             # Si se resolvió automáticamente
    
    # ========== METADATOS TEMPORALES ==========
    start_time: datetime                   # Inicio de la conversación
    end_time: Optional[datetime]           # Fin de la conversación
    last_activity: datetime                # Última actividad
    timezone: str                          # Zona horaria del empleado
    
    # ========== CONTEXTO ADICIONAL ==========
    store_context: Optional[Dict[str, Any]]  # Contexto específico de la tienda
    employee_context: Optional[Dict[str, Any]] # Contexto del empleado
    previous_tickets: Optional[List[str]]    # Tickets previos relacionados
    
    # ========== DEBUG Y LOGGING ==========
    debug_info: Optional[Dict[str, Any]]     # Información de debug
    execution_path: Optional[List[str]]      # Ruta de ejecución en el grafo
    error_count: int                         # Número de errores encontrados

# ========== FUNCIONES DE CREACIÓN Y MANIPULACIÓN ==========

def create_initial_eroski_state(
    session_id: str,
    timezone: str = "Europe/Madrid"
) -> EroskiState:
    """
    Crear estado inicial para una nueva conversación.
    
    Args:
        session_id: ID único de la sesión
        timezone: Zona horaria (por defecto Madrid)
        
    Returns:
        Estado inicial configurado
    """
    now = datetime.now()
    
    return EroskiState(
        # Identificación
        session_id=session_id,
        authenticated=False,
        
        # Conversación
        messages=[],
        
        # Control de flujo
        current_node="authenticate",
        attempts=0,
        max_attempts=3,
        can_retry=True,
        flow_completed=False,
        awaiting_user_input=False,
        
        # Resultado
        resolved=False,
        automated_resolution=False,
        escalation_needed=False,
        ticket_created=False,
        follow_up_needed=False,
        solution_found=False,
        
        # Temporal
        start_time=now,
        last_activity=now,
        timezone=timezone,
        
        # Debug
        execution_path=["start"],
        error_count=0
    )

def update_state_node(state: EroskiState, new_node: str) -> EroskiState:
    """
    Actualizar el nodo actual y resetear intentos.
    
    Args:
        state: Estado actual
        new_node: Nuevo nodo
        
    Returns:
        Estado actualizado
    """
    updated = dict(state)
    updated.update({
        "current_node": new_node,
        "attempts": 0,
        "last_activity": datetime.now(),
        "execution_path": state.get("execution_path", []) + [new_node]
    })
    return EroskiState(updated)

def increment_attempts(state: EroskiState) -> EroskiState:
    """
    Incrementar contador de intentos en el nodo actual.
    
    Args:
        state: Estado actual
        
    Returns:
        Estado con intentos incrementados
    """
    updated = dict(state)
    updated.update({
        "attempts": state.get("attempts", 0) + 1,
        "last_activity": datetime.now()
    })
    return EroskiState(updated)

def should_escalate_by_attempts(state: EroskiState) -> bool:
    """
    Determinar si se debe escalar por exceso de intentos.
    
    Args:
        state: Estado actual
        
    Returns:
        True si debe escalar
    """
    attempts = state.get("attempts", 0)
    max_attempts = state.get("max_attempts", 3)
    return attempts >= max_attempts

def mark_as_authenticated(
    state: EroskiState, 
    employee_data: Dict[str, Any]
) -> EroskiState:
    """
    Marcar usuario como autenticado con sus datos.
    
    Args:
        state: Estado actual
        employee_data: Datos del empleado validado
        
    Returns:
        Estado con empleado autenticado
    """
    updated = dict(state)
    updated.update({
        "authenticated": True,
        "employee_id": employee_data.get("id"),
        "employee_name": employee_data.get("name"),
        "employee_email": employee_data.get("email"),
        "store_id": employee_data.get("store_id"),
        "store_name": employee_data.get("store_name"),
        "store_type": employee_data.get("store_type"),
        "department": employee_data.get("department"),
        "employee_level": employee_data.get("level", 1),
        "shift": employee_data.get("shift"),
        "attempts": 0,  # Reset intentos después de autenticación exitosa
        "awaiting_user_input": False,
        "last_activity": datetime.now()
    })
    return EroskiState(updated)

def set_incident_details(
    state: EroskiState,
    incident_type: str,
    description: str,
    details: Optional[Dict[str, Any]] = None
) -> EroskiState:
    """
    Establecer detalles de la incidencia.
    
    Args:
        state: Estado actual
        incident_type: Tipo de incidencia
        description: Descripción del problema
        details: Detalles adicionales
        
    Returns:
        Estado con incidencia configurada
    """
    updated = dict(state)
    updated.update({
        "incident_type": incident_type,
        "incident_description": description,
        "incident_details": details or {},
        "last_activity": datetime.now()
    })
    return EroskiState(updated)

def mark_as_resolved(
    state: EroskiState,
    solution_type: SolutionType,
    solution_content: Optional[str] = None,
    satisfaction_score: Optional[int] = None
) -> EroskiState:
    """
    Marcar problema como resuelto.
    
    Args:
        state: Estado actual
        solution_type: Tipo de solución aplicada
        solution_content: Contenido de la solución
        satisfaction_score: Puntuación de satisfacción
        
    Returns:
        Estado con problema resuelto
    """
    now = datetime.now()
    updated = dict(state)
    
    updated.update({
        "resolved": True,
        "solution_found": True,
        "solution_type": solution_type,
        "solution_content": solution_content,
        "satisfaction_score": satisfaction_score,
        "end_time": now,
        "flow_completed": True,
        "last_activity": now,
        "automated_resolution": solution_type == SolutionType.AUTOMATICA
    })
    
    # Calcular tiempo de resolución
    start_time = state.get("start_time")
    if start_time:
        resolution_time = (now - start_time).total_seconds() / 60.0
        updated["resolution_time_minutes"] = resolution_time
    
    return EroskiState(updated)

def mark_as_escalated(
    state: EroskiState,
    escalation_reason: str,
    escalation_level: str = "supervisor",
    escalation_contacts: Optional[List[str]] = None
) -> EroskiState:
    """
    Marcar como escalado a supervisor.
    
    Args:
        state: Estado actual
        escalation_reason: Motivo de escalación
        escalation_level: Nivel de escalación
        escalation_contacts: Contactos de escalación
        
    Returns:
        Estado con escalación configurada
    """
    updated = dict(state)
    updated.update({
        "escalation_needed": True,
        "escalation_reason": escalation_reason,
        "escalation_level": escalation_level,
        "escalation_contacts": escalation_contacts or [],
        "flow_completed": True,
        "last_activity": datetime.now()
    })
    return EroskiState(updated)

def calculate_resolution_time(state: EroskiState) -> Optional[float]:
    """
    Calcular tiempo de resolución en minutos.
    
    Args:
        state: Estado actual
        
    Returns:
        Tiempo en minutos o None si no ha terminado
    """
    start = state.get("start_time")
    end = state.get("end_time")
    
    if start and end:
        return (end - start).total_seconds() / 60.0
    elif start and (state.get("resolved") or state.get("escalation_needed")):
        return (datetime.now() - start).total_seconds() / 60.0
    
    return None

def add_debug_info(state: EroskiState, key: str, value: Any) -> EroskiState:
    """
    Agregar información de debug al estado.
    
    Args:
        state: Estado actual
        key: Clave de debug
        value: Valor a agregar
        
    Returns:
        Estado con información de debug agregada
    """
    updated = dict(state)
    debug_info = updated.get("debug_info", {})
    debug_info[key] = value
    updated["debug_info"] = debug_info
    updated["last_activity"] = datetime.now()
    return EroskiState(updated)

def increment_error_count(state: EroskiState, error_description: str) -> EroskiState:
    """
    Incrementar contador de errores.
    
    Args:
        state: Estado actual
        error_description: Descripción del error
        
    Returns:
        Estado con error registrado
    """
    updated = dict(state)
    error_count = updated.get("error_count", 0) + 1
    updated.update({
        "error_count": error_count,
        "last_activity": datetime.now()
    })
    
    # Agregar error al debug info
    debug_info = updated.get("debug_info", {})
    if "errors" not in debug_info:
        debug_info["errors"] = []
    
    debug_info["errors"].append({
        "timestamp": datetime.now().isoformat(),
        "description": error_description,
        "error_number": error_count
    })
    
    updated["debug_info"] = debug_info
    return EroskiState(updated)

# ========== VALIDACIONES ==========

def validate_employee_data(state: EroskiState) -> List[str]:
    """
    Validar que los datos del empleado están completos.
    
    Args:
        state: Estado a validar
        
    Returns:
        Lista de errores encontrados
    """
    errors = []
    
    if not state.get("employee_id"):
        errors.append("Falta employee_id")
    
    if not state.get("employee_email"):
        errors.append("Falta employee_email")
    
    if not state.get("store_id"):
        errors.append("Falta store_id")
    
    if not state.get("authenticated"):
        errors.append("Usuario no autenticado")
    
    return errors

def validate_incident_data(state: EroskiState) -> List[str]:
    """
    Validar que los datos de la incidencia están completos.
    
    Args:
        state: Estado a validar
        
    Returns:
        Lista de errores encontrados
    """
    errors = []
    
    if not state.get("incident_type"):
        errors.append("Falta incident_type")
    
    if not state.get("incident_description"):
        errors.append("Falta incident_description")
    elif len(state["incident_description"]) < 10:
        errors.append("incident_description demasiado corta")
    
    return errors

def validate_state_integrity(state: EroskiState) -> List[str]:
    """
    Validar integridad general del estado.
    
    Args:
        state: Estado a validar
        
    Returns:
        Lista de errores encontrados
    """
    errors = []
    
    # Validar campos requeridos
    required_fields = ["session_id", "messages", "current_node", "start_time"]
    for field in required_fields:
        if field not in state:
            errors.append(f"Campo requerido faltante: {field}")
    
    # Validar tipos de datos
    if "attempts" in state and not isinstance(state["attempts"], int):
        errors.append("attempts debe ser entero")
    
    if "error_count" in state and not isinstance(state["error_count"], int):
        errors.append("error_count debe ser entero")
    
    # Validar coherencia lógica
    if state.get("resolved") and state.get("escalation_needed"):
        errors.append("Estado inconsistente: no puede estar resuelto y escalado")
    
    if state.get("authenticated") and not state.get("employee_email"):
        errors.append("Autenticado pero sin email de empleado")
    
    return errors

# ========== HELPERS PARA MÉTRICAS ==========

def get_session_summary(state: EroskiState) -> Dict[str, Any]:
    """
    Obtener resumen de la sesión para métricas.
    
    Args:
        state: Estado actual
        
    Returns:
        Diccionario con resumen
    """
    return {
        "session_id": state.get("session_id"),
        "employee_id": state.get("employee_id"),
        "employee_name": state.get("employee_name"),
        "store_id": state.get("store_id"),
        "store_name": state.get("store_name"),
        "query_type": state.get("query_type"),
        "incident_type": state.get("incident_type"),
        "resolved": state.get("resolved", False),
        "escalated": state.get("escalation_needed", False),
        "automated": state.get("automated_resolution", False),
        "satisfaction": state.get("satisfaction_score"),
        "resolution_time": calculate_resolution_time(state),
        "total_messages": len(state.get("messages", [])),
        "execution_path": state.get("execution_path", []),
        "error_count": state.get("error_count", 0),
        "current_node": state.get("current_node"),
        "authenticated": state.get("authenticated", False)
    }

def get_state_for_persistence(state: EroskiState) -> Dict[str, Any]:
    """
    Preparar estado para persistencia (serialización).
    
    Args:
        state: Estado actual
        
    Returns:
        Estado serializable
    """
    # Crear copia sin objetos no serializables
    serializable_state = {}
    
    for key, value in state.items():
        if key == "messages":
            # Convertir mensajes a formato serializable
            serializable_state[key] = [
                {
                    "type": type(msg).__name__,
                    "content": msg.content,
                    "timestamp": getattr(msg, "timestamp", None)
                }
                for msg in value
            ]
        elif isinstance(value, datetime):
            # Convertir datetime a ISO string
            serializable_state[key] = value.isoformat()
        elif isinstance(value, Enum):
            # Convertir enums a su valor
            serializable_state[key] = value.value
        else:
            serializable_state[key] = value
    
    return serializable_state

# ========== FUNCIONES DE CONVENIENCIA ==========

def is_user_authenticated(state: EroskiState) -> bool:
    """Verificar si el usuario está autenticado"""
    return bool(
        state.get("authenticated") and
        state.get("employee_email") and
        state.get("store_id")
    )

def has_complete_incident_info(state: EroskiState) -> bool:
    """Verificar si tiene información completa de incidencia"""
    return bool(
        state.get("incident_type") and
        state.get("incident_description") and
        len(state.get("incident_description", "")) >= 10
    )

def should_escalate(state: EroskiState) -> bool:
    """Determinar si se debe escalar"""
    # Por número de intentos
    if should_escalate_by_attempts(state):
        return True
    
    # Por urgencia crítica
    urgency = state.get("urgency_level")
    if urgency == UrgencyLevel.CRITICA:
        return True
    
    # Por número de errores
    if state.get("error_count", 0) >= 3:
        return True
    
    return False