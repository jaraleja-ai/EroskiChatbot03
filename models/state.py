# =====================================================
# models/state.py - Estado del grafo de LangGraph
# =====================================================
from typing import Annotated, List, Optional, Dict, Any
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
from operator import add

class GraphState(TypedDict):
    """
    Estado del grafo de conversación con manejo correcto de actualizaciones concurrentes.
    
    Este estado se pasa entre todos los nodos del grafo y mantiene:
    - Mensajes de la conversación
    - Datos del usuario
    - Información de la incidencia
    - Metadatos de control de flujo
    """
    
    # ========================================
    # MENSAJES DE LA CONVERSACIÓN
    # ========================================
    # Los mensajes se pueden agregar múltiples veces durante la ejecución
    messages: Annotated[List[BaseMessage], add_messages]
    
    # ========================================
    # DATOS DEL USUARIO
    # ========================================
    # Campos que pueden ser actualizados, manteniendo el último valor válido
    nombre: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    email: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    numero_empleado: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    
    # Estados de confirmación (mantienen último valor)
    nombre_confirmado: Annotated[bool, lambda x, y: y]
    email_confirmado: Annotated[bool, lambda x, y: y]
    datos_usuario_completos: Annotated[bool, lambda x, y: y]
    usuario_encontrado_bd: Annotated[bool, lambda x, y: y]
    
    # ========================================
    # INFORMACIÓN DE INCIDENCIA
    # ========================================
    tipo_incidencia: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    descripcion_incidencia: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    prioridad_incidencia: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    categoria_incidencia: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    preguntas_contestadas: Annotated[Optional[Dict[str, str]], lambda x, y: y if y is not None else x]
    incidencia_resuelta: Annotated[bool, lambda x, y: y]
    
    # ========================================
    # CONTROL DE FLUJO
    # ========================================
    # Contadores que se suman
    intentos: Annotated[int, add]
    intentos_incidencia: Annotated[int, add]
    
    # Estados de control
    escalar_a_supervisor: Annotated[bool, lambda x, y: y]
    razon_escalacion: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    flujo_completado: Annotated[bool, lambda x, y: y]
    
    # ========================================
    # METADATOS Y CONTEXTO
    # ========================================
    contexto_adicional: Annotated[Optional[Dict[str, Any]], lambda x, y: y if y is not None else x]
    sesion_id: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    timestamp_inicio: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    
    # Información de errores
    error_info: Annotated[Optional[Dict[str, Any]], lambda x, y: y if y is not None else x]


    # ========================================
    # CONTROL DE FLUJO ESCALABLE (NUEVO)
    # ========================================
    current_step: Annotated[str, lambda x, y: y if y is not None else x]
    awaiting_input: Annotated[bool, lambda x, y: y]
    next_action: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    flow_history: Annotated[List[str], add]

    # ========================================
    # DATOS EXTENDIDOS DE INCIDENCIA (NUEVO)
    # ========================================
    subcategoria: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    urgencia: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    pasos_reproducir: Annotated[Optional[List[str]], lambda x, y: y if y is not None else x]
    solucion_intentada: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    solucion_propuesta: Annotated[Optional[str], lambda x, y: y if y is not None else x]
    ticket_id: Annotated[Optional[str], lambda x, y: y if y is not None else x]

    # ========================================
    # CONFIRMACIONES EXTENDIDAS (NUEVO)
    # ========================================
    categoria_confirmada: Annotated[bool, lambda x, y: y]
    descripcion_confirmada: Annotated[bool, lambda x, y: y]
    solucion_aceptada: Annotated[bool, lambda x, y: y]


