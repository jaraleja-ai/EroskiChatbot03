# =====================================================
# utils/database/__init__.py - Exportaciones SIN imports circulares
# =====================================================

# 🔥 SOLUCIÓN: Solo importar desde módulos específicos, nunca del padre
from .base_repository import BaseRepository
from .connection_manager import ConnectionManager, get_connection_manager, init_database, close_database
from .user_repository import UserRepository
from .incidencia_repository import IncidenciaRepository

__all__ = [
    "BaseRepository",
    "ConnectionManager",
    "get_connection_manager", 
    "init_database",
    "close_database",
    "UserRepository", 
    "IncidenciaRepository"
]