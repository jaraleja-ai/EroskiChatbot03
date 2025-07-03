# =====================================================
# nodes/__init__.py - CORREGIDO: Imports con manejo de errores
# =====================================================

from .base_node import BaseNode

# ========== IMPORTS CON MANEJO DE ERRORES ==========
try:
    from .authenticate_enhanced import authenticate_employee_node
    AUTHENTICATE_AVAILABLE = True
    print("✅ authenticate disponible")
except ImportError as e:
    print(f"⚠️ Warning: authenticate no disponible: {e}")
    AUTHENTICATE_AVAILABLE = False

try:
    from .classify_enhanced import classify_query_node 
    CLASSIFY_AVAILABLE = True
    print("✅ classify disponible")
except ImportError as e:
    print(f"⚠️ Warning: classify no disponible: {e}")
    CLASSIFY_AVAILABLE = False

# Otros nodos (crear si no existen)
try:
    from .collect_incident import collect_incident_details_node
    COLLECT_AVAILABLE = True
except ImportError:
    COLLECT_AVAILABLE = False

try:
    from .search_solution import search_solution_node
    SEARCH_SOLUTION_AVAILABLE = True
except ImportError:
    SEARCH_SOLUTION_AVAILABLE = False

try:
    from .search_knowledge import search_knowledge_node
    SEARCH_KNOWLEDGE_AVAILABLE = True
except ImportError:
    SEARCH_KNOWLEDGE_AVAILABLE = False

try:
    from .escalate import escalate_supervisor_node
    ESCALATE_AVAILABLE = True
except ImportError:
    ESCALATE_AVAILABLE = False

try:
    from .verify import verify_resolution_node
    VERIFY_AVAILABLE = True
except ImportError:
    VERIFY_AVAILABLE = False

try:
    from .finalize import finalize_conversation_node
    FINALIZE_AVAILABLE = True
except ImportError:
    FINALIZE_AVAILABLE = False

# ========== EXPORTS DINÁMICOS ==========
__all__ = ["BaseNode"]

if AUTHENTICATE_AVAILABLE:
    __all__.extend(["authenticate_employee_node"])

if CLASSIFY_AVAILABLE:
    __all__.extend(["classify_query_node"])

if COLLECT_AVAILABLE:
    __all__.append("collect_incident_details_node")

if SEARCH_SOLUTION_AVAILABLE:
    __all__.append("search_solution_node")

if SEARCH_KNOWLEDGE_AVAILABLE:
    __all__.append("search_knowledge_node")

if ESCALATE_AVAILABLE:
    __all__.append("escalate_supervisor_node")

if VERIFY_AVAILABLE:
    __all__.append("verify_resolution_node")

if FINALIZE_AVAILABLE:
    __all__.append("finalize_conversation_node")

print(f"📋 Nodos disponibles: {len(__all__)}")