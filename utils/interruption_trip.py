

# ==========================================
# FUNCIONES AUXILIARES PARA INTERRUPTION_TRIP
# ==========================================

from typing import Dict, Optional
from models.state import InterruptionTrip

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
