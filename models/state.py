from typing import TypedDict, List, Optional, Any, Dict, Tuple
from langchain_core.messages import BaseMessage

InterruptionTrip = Tuple[str, str, str]  # (origen, destino, sentido)

class GraphState(TypedDict, total=False):
    """
    🏗️ Estado del grafo híbrido - Versión corregida para evitar bucles
    
    CAMPOS DE CONTROL DE FLUJO:
    - _actor_decision: Decisión del último actor ejecutado
    - _next_actor: Siguiente actor según la decisión
    - _execution_count: Contador para prevenir bucles infinitos
    - awaiting_input: Indica si el flujo está esperando input del usuario
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
    
    # 🎯 ROUTING SIMPLE
    _routing_stack: List[str]   