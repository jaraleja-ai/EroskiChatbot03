# =====================================================
# utils/__init__.py - Exportaciones SIN imports circulares
# =====================================================

# 🔥 SOLUCIÓN: Importar usando rutas absolutas específicas
# En lugar de from .database import X, usamos from .database.module import X

# Database imports con rutas específicas
from .database.base_repository import BaseRepository
from .database.connection_manager import ConnectionManager, get_connection_manager, init_database, close_database
from .database.incidencia_repository import IncidenciaRepository  
from .database.user_repository import UserRepository

# Extractor imports con rutas específicas
from .extractors.user_extractor import extraer_datos_usuario, UsuarioExtraido
from .extractors.incident_extractor import (
    extraer_tipo_incidencia,
    extraer_detalles_incidencia, 
    IncidenciaExtraida
)

# LLM imports con rutas específicas  
from .llm.providers import get_llm, reset_llm
from .llm.prompts import (
    URGENCY_CLASSIFICATION_PROMPT,
    INCIDENT_SUMMARY_PROMPT
)

from .llm.message_generator import (generate_natural_message, 
                                    detect_confirmation_intent, 
                                    generate_followup_questions)

__all__ = [
    # Database
    "BaseRepository",
    "ConnectionManager", 
    "get_connection_manager",
    "init_database",
    "close_database",
    "IncidenciaRepository",
    "UserRepository",
    
    # Extractors
    "extraer_datos_usuario",
    "UsuarioExtraido", 
    "extraer_tipo_incidencia",
    "extraer_detalles_incidencia",
    "IncidenciaExtraida",
    
    # LLM
    "get_llm",
    "reset_llm",
    "generate_natural_message", 
    "detect_confirmation_intent",
    "generate_followup_questions",
    "URGENCY_CLASSIFICATION_PROMPT",
    "INCIDENT_SUMMARY_PROMPT"
]