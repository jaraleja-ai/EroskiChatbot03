# =====================================================
# models/__init__.py - Exportaciones del módulo actualizado
# =====================================================
"""
Módulo de modelos para el chatbot de Eroski.

Incluye:
- Estado optimizado para Eroski (EroskiState)
- Enums específicos del dominio
- Funciones de manipulación de estado
- Validaciones y helpers
"""

# ========== ESTADO PRINCIPAL ==========
from .eroski_state import (
    # Estado principal
    EroskiState,
    create_initial_eroski_state,
    
    # Enums
    ConsultaType,
    UrgencyLevel, 
    SolutionType,
    StoreType,
    EmployeeLevel,
    
    # Funciones de manipulación
    update_state_node,
    increment_attempts,
    should_escalate_by_attempts,
    mark_as_authenticated,
    set_incident_details,
    mark_as_resolved,
    mark_as_escalated,
    calculate_resolution_time,
    add_debug_info,
    increment_error_count,
    
    # Validaciones
    validate_employee_data,
    validate_incident_data,
    validate_state_integrity,
    
    # Helpers
    get_session_summary,
    get_state_for_persistence,
    is_user_authenticated,
    has_complete_incident_info,
    should_escalate
)

# ========== MANTENER COMPATIBILIDAD CON CÓDIGO EXISTENTE ==========
try:
    # Importar modelos existentes si están disponibles
    from .state import EroskiState
    from .user import (
        UsuarioBase, UsuarioCreate, UsuarioUpdate, UsuarioDB, 
        UsuarioExtracted, RolUsuario, EstadoUsuario
    )
    from .incidencia import (
        IncidenciaBase, IncidenciaCreate, IncidenciaUpdate, IncidenciaDB,
        TipoIncidencia, PrioridadIncidencia, EstadoIncidencia, CategoriaIncidencia
    )
    from .conversation import ConversationContext
    from .conversation_step import (
        ConversationSteps, ConversationStepsMeta, ConversationStepValidator
    )
    
    # Lista extendida si hay modelos existentes
    __all__ = [
        # ========== ESTADO PRINCIPAL EROSKI ==========
        "EroskiState",
        "create_initial_eroski_state",
        
        # Enums
        "ConsultaType",
        "UrgencyLevel", 
        "SolutionType",
        "StoreType",
        "EmployeeLevel",
        
        # Funciones de manipulación
        "update_state_node",
        "increment_attempts", 
        "should_escalate_by_attempts",
        "mark_as_authenticated",
        "set_incident_details",
        "mark_as_resolved",
        "mark_as_escalated",
        "calculate_resolution_time",
        "add_debug_info",
        "increment_error_count",
        
        # Validaciones
        "validate_employee_data",
        "validate_incident_data", 
        "validate_state_integrity",
        
        # Helpers
        "get_session_summary",
        "get_state_for_persistence",
        "is_user_authenticated",
        "has_complete_incident_info",
        "should_escalate",
        
        # ========== MODELOS EXISTENTES (COMPATIBILIDAD) ==========
        "EroskiState",
        "UsuarioBase", "UsuarioCreate", "UsuarioUpdate", "UsuarioDB", 
        "UsuarioExtracted", "RolUsuario", "EstadoUsuario",
        "IncidenciaBase", "IncidenciaCreate", "IncidenciaUpdate", "IncidenciaDB",
        "TipoIncidencia", "PrioridadIncidencia", "EstadoIncidencia", "CategoriaIncidencia",
        "ConversationContext",
        "ConversationSteps", "ConversationStepsMeta", "ConversationStepValidator",
    ]
    
except ImportError as e:
    # Si no existen modelos antiguos, solo exportar los nuevos
    __all__ = [
        # Estado principal Eroski
        "EroskiState",
        "create_initial_eroski_state",
        
        # Enums
        "ConsultaType",
        "UrgencyLevel", 
        "SolutionType", 
        "StoreType",
        "EmployeeLevel",
        
        # Funciones de manipulación
        "update_state_node",
        "increment_attempts",
        "should_escalate_by_attempts", 
        "mark_as_authenticated",
        "set_incident_details",
        "mark_as_resolved",
        "mark_as_escalated",
        "calculate_resolution_time",
        "add_debug_info",
        "increment_error_count",
        
        # Validaciones
        "validate_employee_data",
        "validate_incident_data",
        "validate_state_integrity",
        
        # Helpers
        "get_session_summary",
        "get_state_for_persistence", 
        "is_user_authenticated",
        "has_complete_incident_info",
        "should_escalate"
    ]

# ========== ALIAS PARA COMPATIBILIDAD ==========

# Si alguien importa EroskiState, usar EroskiState
EroskiState = EroskiState