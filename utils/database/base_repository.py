# =====================================================
# utils/database/base_repository.py - CORREGIDO
# =====================================================
"""
Repositorio base corregido para trabajar con ConnectionManager.
"""
import asyncpg
from typing import Optional, List, TypeVar, Generic
from contextlib import asynccontextmanager
import logging

from config.settings import get_settings

# TypeVar para hacer el repositorio genérico
T = TypeVar('T')

class BaseRepository(Generic[T]):
    """
    Clase base para todos los repositorios con ConnectionManager.
    
    CAMBIOS:
    - Constructor recibe connection_manager
    - Pool gestionado por ConnectionManager
    - Métodos de conexión simplificados
    """
    
    def __init__(self, connection_manager=None):
        self.connection_manager = connection_manager
        self.settings = get_settings()
        self.logger = logging.getLogger(f"Repository.{self.__class__.__name__}")
        self._pool: Optional[asyncpg.Pool] = None
    
    async def get_pool(self) -> asyncpg.Pool:
        """Obtener pool de conexiones (lazy loading)"""
        if self._pool is None:
            db_config = self.settings.database
            try:
                self._pool = await asyncpg.create_pool(
                    host=db_config.host,
                    port=db_config.port,
                    user=db_config.user,
                    password=db_config.password,
                    database=db_config.name,
                    min_size=db_config.pool_min_size,
                    max_size=db_config.pool_max_size,
                    command_timeout=db_config.command_timeout
                )
                self.logger.info("✅ Pool de conexiones creado")
            except Exception as e:
                self.logger.error(f"❌ Error creando pool: {e}")
                raise
        return self._pool
    
    async def close(self):
        """Cerrar pool de conexiones"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self.logger.info("🔒 Pool de conexiones cerrado")
    
    @asynccontextmanager
    async def get_connection(self):
        """Context manager para obtener conexión del pool"""
        pool = await self.get_pool()
        async with pool.acquire() as connection:
            try:
                yield connection
            except Exception as e:
                self.logger.error(f"❌ Error en operación de BD: {e}")
                raise
    
    async def execute_query(self, query: str, *args) -> str:
        """Ejecutar query que no retorna datos"""
        async with self.get_connection() as conn:
            try:
                result = await conn.execute(query, *args)
                self.logger.debug(f"📝 Query ejecutado: {result}")
                return result
            except Exception as e:
                self.logger.error(f"❌ Error ejecutando query: {e}")
                raise
    
    async def fetch_one(self, query: str, *args) -> Optional[asyncpg.Record]:
        """Obtener un registro"""
        async with self.get_connection() as conn:
            try:
                result = await conn.fetchrow(query, *args)
                self.logger.debug(f"📄 Registro obtenido: {'✅' if result else '❌'}")
                return result
            except Exception as e:
                self.logger.error(f"❌ Error obteniendo registro: {e}")
                raise
    
    async def fetch_many(self, query: str, *args) -> List[asyncpg.Record]:
        """Obtener múltiples registros"""
        async with self.get_connection() as conn:
            try:
                results = await conn.fetch(query, *args)
                self.logger.debug(f"📄 Registros obtenidos: {len(results)}")
                return results
            except Exception as e:
                self.logger.error(f"❌ Error obteniendo registros: {e}")
                raise

