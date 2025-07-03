from typing import TypedDict, List, Optional, Any, Dict, Tuple
from langchain_core.messages import BaseMessage

# Definición del tipo para la tupla de interrupción
InterruptionTrip = Tuple[str, str, str]  # (origen, destino, sentido)

class GraphState(TypedDict, total=False):
    """
    🏗️ Estado del grafo híbrido - Versión corregida para evitar bucles
    
    CAMPOS DE CONTROL DE FLUJO:
    - _actor_decision: Decisión del último actor ejecutado
    - _next_actor: Siguiente actor según la decisión
    - _execution_count: Contador para prevenir bucles infinitos
    - awaiting_input: Indica si el flujo está esperando input del usuario
    - interruption_trip: Tupla para manejar interrupciones (origen, destino, sentido)
    """
    
    # ✅ CONTROL DE FLUJO Y ROUTING
    _actor_decision: Optional[str]          # 'need_input', 'continue', 'escalate', etc.
    _next_actor: Optional[str]              # Próximo nodo/actor a ejecutar
    _execution_count: int                   # Contador de ejecuciones (anti-bucle)
    _last_processed_message: str            # Último mensaje procesado (anti-repetición)
    _request_message: Optional[str]         # Mensaje a mostrar al usuario
    _input_context: Optional[Dict[str, Any]] # Contexto de la solicitud de input
    
    # ⏸️ ESTADO DE INTERRUPCIÓN
    awaiting_input: bool                    # True cuando esperamos input del usuario
    current_step: Optional[str]             # Paso actual del flujo
    next_action: Optional[str]              # Próxima acción a ejecutar
    interruption_trip: Optional[InterruptionTrip]  # 🆕 Tupla de interrupción (origen, destino, sentido)
    is_interrupted: bool                    # 🆕 Indica si hay una interrupción activa
    router_context: Optional[Dict[str, Any]] # 🆕 Contexto del router para manejar interrupciones
    
    # 💬 MENSAJES Y COMUNICACIÓN
    messages: List[BaseMessage]             # Historia de mensajes
    
    # 👤 DATOS DEL USUARIO
    nombre: Optional[str]                   # Nombre del usuario
    email: Optional[str]                    # Email corporativo
    numero_empleado: Optional[str]          # Número de empleado
    nombre_confirmado: bool                 # Si el nombre está confirmado
    email_confirmado: bool                  # Si el email está confirmado
    datos_usuario_completos: bool           # Si tenemos todos los datos necesarios
    usuario_encontrado_bd: bool             # Si el usuario existe en BD
    
    # 🎫 DATOS DE LA INCIDENCIA
    tipo_incidencia: Optional[str]          # Tipo de incidencia
    descripcion_incidencia: Optional[str]   # Descripción detallada
    prioridad_incidencia: Optional[str]     # Prioridad (alta, media, baja)
    categoria_incidencia: Optional[str]     # Categoría de la incidencia
    categoria_confirmada: bool              # Si la categoría está confirmada
    descripcion_confirmada: bool            # Si la descripción está confirmada
    solucion_aceptada: Optional[bool]       # Si el usuario aceptó la solución propuesta
    
    # 🔄 ESTADO DEL FLUJO
    preguntas_contestadas: List[str]        # Preguntas ya respondidas
    incidencia_resuelta: bool               # Si la incidencia está resuelta
    intentos: int                           # Número de intentos
    intentos_incidencia: int                # Intentos específicos de incidencia
    
    # 🔼 ESCALACIÓN
    escalar_a_supervisor: bool              # Si debe escalarse
    razon_escalacion: Optional[str]         # Razón de la escalación
    
    # 🏁 FINALIZACIÓN
    flujo_completado: bool                  # Si el flujo está completado
    
    # 🔧 METADATA Y DEBUG
    contexto_adicional: Optional[Dict[str, Any]]  # Contexto adicional
    sesion_id: Optional[str]                # ID de la sesión
    timestamp_inicio: Optional[str]         # Timestamp de inicio
    error_info: Optional[Dict[str, Any]]    # Información de errores
    flow_history: List[str]                 # Historia del flujo ejecutado


# ==========================================
# FUNCIONES AUXILIARES PARA INTERRUPTION_TRIP
# ==========================================

def create_interruption_trip(origen: str, destino: str, sentido: str) -> InterruptionTrip:
    """
    Crea una nueva tupla de interrupción.
    
    Args:
        origen: Nodo desde donde se origina la interrupción
        destino: Nodo de destino de la interrupción  
        sentido: 'ida' para ir a la interrupción, 'vuelta' para regresar
        
    Returns:
        InterruptionTrip: Tupla (origen, destino, sentido)
        
    Example:
        >>> trip = create_interruption_trip("router", "interruption_handler", "ida")
        >>> print(trip)  # ("router", "interruption_handler", "ida")
    """
    return (origen, destino, sentido)


def get_trip_info(trip: Optional[InterruptionTrip]) -> Dict[str, Optional[str]]:
    """
    Extrae información de la tupla de interrupción para facilitar su uso.
    
    Args:
        trip: Tupla de interrupción o None
        
    Returns:
        Dict con las claves 'origen', 'destino', 'sentido'
        
    Example:
        >>> trip = ("router", "interruption_handler", "ida")
        >>> info = get_trip_info(trip)
        >>> print(info)  # {"origen": "router", "destino": "interruption_handler", "sentido": "ida"}
    """
    if trip is None:
        return {"origen": None, "destino": None, "sentido": None}
    return {
        "origen": trip[0],
        "destino": trip[1], 
        "sentido": trip[2]
    }


def is_return_trip(trip: Optional[InterruptionTrip]) -> bool:
    """
    Verifica si es un viaje de vuelta desde una interrupción.
    
    Args:
        trip: Tupla de interrupción o None
        
    Returns:
        bool: True si es un viaje de vuelta, False en caso contrario
        
    Example:
        >>> trip_ida = ("router", "interruption_handler", "ida")
        >>> trip_vuelta = ("interruption_handler", "router", "vuelta")
        >>> print(is_return_trip(trip_ida))     # False
        >>> print(is_return_trip(trip_vuelta))  # True
    """
    if trip is None:
        return False
    return trip[2] == "vuelta"


def is_outbound_trip(trip: Optional[InterruptionTrip]) -> bool:
    """
    Verifica si es un viaje de ida hacia una interrupción.
    
    Args:
        trip: Tupla de interrupción o None
        
    Returns:
        bool: True si es un viaje de ida, False en caso contrario
    """
    if trip is None:
        return False
    return trip[2] == "ida"


def get_trip_origin(trip: Optional[InterruptionTrip]) -> Optional[str]:
    """
    Obtiene el nodo de origen de la interrupción.
    
    Args:
        trip: Tupla de interrupción o None
        
    Returns:
        str: Nodo de origen o None si no hay trip
    """
    if trip is None:
        return None
    return trip[0]


def get_trip_destination(trip: Optional[InterruptionTrip]) -> Optional[str]:
    """
    Obtiene el nodo de destino de la interrupción.
    
    Args:
        trip: Tupla de interrupción o None
        
    Returns:
        str: Nodo de destino o None si no hay trip
    """
    if trip is None:
        return None
    return trip[1]


def create_return_trip(original_trip: InterruptionTrip) -> InterruptionTrip:
    """
    Crea un trip de vuelta basado en un trip de ida.
    
    Args:
        original_trip: Trip original de ida
        
    Returns:
        InterruptionTrip: Nuevo trip de vuelta
        
    Example:
        >>> trip_ida = ("router", "interruption_handler", "ida")
        >>> trip_vuelta = create_return_trip(trip_ida)
        >>> print(trip_vuelta)  # ("interruption_handler", "router", "vuelta")
    """
    origen, destino, _ = original_trip
    return (destino, origen, "vuelta")


def clear_interruption_state(state: GraphState) -> GraphState:
    """
    Limpia el estado de interrupción cuando se completa el ciclo.
    
    Args:
        state: Estado actual del grafo
        
    Returns:
        GraphState: Estado actualizado sin información de interrupción
    """
    return {
        **state,
        "interruption_trip": None,
        "is_interrupted": False,
        "router_context": {}
    }


def has_active_interruption(state: GraphState) -> bool:
    """
    Verifica si hay una interrupción activa en el estado.
    
    Args:
        state: Estado actual del grafo
        
    Returns:
        bool: True si hay interrupción activa, False en caso contrario
    """
    return (
        state.get("is_interrupted", False) or 
        state.get("interruption_trip") is not None
    )


def should_return_from_interruption(state: GraphState) -> bool:
    """
    Determina si se debe regresar de una interrupción.
    
    Args:
        state: Estado actual del grafo
        
    Returns:
        bool: True si se debe regresar, False en caso contrario
    """
    trip = state.get("interruption_trip")
    return trip is not None and is_return_trip(trip)


# ==========================================
# CONSTANTES PARA TIPOS DE SENTIDO
# ==========================================

class InterruptionDirection:
    """Constantes para los tipos de dirección de interrupciones."""
    OUTBOUND = "ida"      # Ir hacia la interrupción
    RETURN = "vuelta"     # Regresar de la interrupción
    CIRCULAR = "circular" # Interrupción que regresa al mismo nodo (casos especiales)