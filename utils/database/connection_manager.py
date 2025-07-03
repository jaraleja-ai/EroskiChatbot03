# =====================================================
# utils/database/connection_manager.py - CORREGIDO
# =====================================================
import asyncio
from typing import Dict, Optional, TYPE_CHECKING
import logging

# 🔥 SOLUCIÓN: Usar TYPE_CHECKING para evitar imports circulares
if TYPE_CHECKING:
    from .base_repository import BaseRepository
    from .user_repository import UserRepository
    from .incidencia_repository import IncidenciaRepository

class ConnectionManager:
    """Gestor centralizado de repositorios y conexiones"""
    
    def __init__(self):
        self._repositories: Dict[str, "BaseRepository"] = {}
        self._initialized = False
        self.logger = logging.getLogger("ConnectionManager")
    
    async def initialize(self):
        """Inicializar todos los repositorios"""
        if not self._initialized:
            self.logger.info("🔧 Inicializando repositorios...")
            
            # 🔥 SOLUCIÓN: Importar aquí para evitar circular imports
            from .user_repository import UserRepository
            from .incidencia_repository import IncidenciaRepository
            
            # 🔥 CORRECCIÓN: Pasar self como connection_manager
            self._repositories["user"] = UserRepository(self)
            self._repositories["incidencia"] = IncidenciaRepository(self)
            
            self._initialized = True
            self.logger.info("✅ Repositorios inicializados")
    
    async def close_all(self):
        """Cerrar todas las conexiones"""
        if self._repositories:
            self.logger.info("🔒 Cerrando todas las conexiones...")
            
            close_tasks = [repo.close() for repo in self._repositories.values()]
            await asyncio.gather(*close_tasks, return_exceptions=True)
            
            self._repositories.clear()
            self._initialized = False
            self.logger.info("✅ Todas las conexiones cerradas")
    
    def get_user_repository(self) -> "UserRepository":
        """Obtener repositorio de usuarios"""
        if not self._initialized:
            raise RuntimeError("ConnectionManager no inicializado")
        return self._repositories["user"]
    
    def get_incidencia_repository(self) -> "IncidenciaRepository":
        """Obtener repositorio de incidencias"""
        if not self._initialized:
            raise RuntimeError("ConnectionManager no inicializado")
        return self._repositories["incidencia"]

# Singleton global
_connection_manager: Optional[ConnectionManager] = None

async def get_connection_manager() -> ConnectionManager:
    """Obtener gestor de conexiones (singleton)"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
        await _connection_manager.initialize()
    return _connection_manager

async def init_database():
    """Inicializar conexiones de BD - función legacy para compatibilidad"""
    await get_connection_manager()

async def close_database():
    """Cerrar conexiones de BD - función legacy para compatibilidad"""
    global _connection_manager
    if _connection_manager:
        await _connection_manager.close_all()
        _connection_manager = None