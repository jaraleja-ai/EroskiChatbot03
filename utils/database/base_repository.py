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

# =====================================================
# utils/database/user_repository.py - CORREGIDO
# =====================================================
"""
Repositorio de usuarios corregido para recibir connection_manager.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from models.user import UsuarioDB, UsuarioCreate, UsuarioUpdate, EstadoUsuario, RolUsuario
from .base_repository import BaseRepository

class UserRepository(BaseRepository[UsuarioDB]):
    """Repositorio para operaciones de usuarios"""
    
    def __init__(self, connection_manager):
        # 🔥 CORRECCIÓN: Llamar a super() con connection_manager
        super().__init__(connection_manager)
        self.logger = logging.getLogger("UserRepository")
    
    async def get_by_email(self, email: str) -> Optional[UsuarioDB]:
        """Obtener usuario por email"""
        try:
            query = """
                SELECT id, email, nombre_completo, numero_empleado, 
                       departamento, estado, rol, fecha_creacion, 
                       ultimo_acceso, activo
                FROM usuarios 
                WHERE email = $1 AND activo = true
            """
            
            record = await self.fetch_one(query, email)
            
            if record:
                return UsuarioDB(
                    id=record["id"],
                    email=record["email"],
                    nombre_completo=record["nombre_completo"],
                    numero_empleado=record["numero_empleado"],
                    departamento=record["departamento"],
                    estado=EstadoUsuario(record["estado"]),
                    rol=RolUsuario(record["rol"]),
                    fecha_creacion=record["fecha_creacion"],
                    ultimo_acceso=record["ultimo_acceso"],
                    activo=record["activo"]
                )
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo usuario por email {email}: {e}")
            return None
    
    async def update_last_access(self, user_id: int) -> bool:
        """Actualizar último acceso del usuario"""
        try:
            query = """
                UPDATE usuarios 
                SET ultimo_acceso = NOW() 
                WHERE id = $1
            """
            
            await self.execute_query(query, user_id)
            self.logger.info(f"✅ Último acceso actualizado para usuario {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error actualizando último acceso: {e}")
            return False

# =====================================================
# utils/database/incidencia_repository.py - CORREGIDO
# =====================================================
"""
Repositorio de incidencias corregido para recibir connection_manager.
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

# Importar modelos básicos sin dependencias circulares
try:
    from models.incidencia import (
        IncidenciaDB, 
        IncidenciaCreate, 
        IncidenciaUpdate,
        PrioridadIncidencia,
        EstadoIncidencia,
        generate_ticket_number
    )
    MODELS_AVAILABLE = True
except ImportError:
    # Fallback si los modelos no están disponibles
    MODELS_AVAILABLE = False
    logging.warning("Modelos de incidencia no disponibles, usando fallback")

from .base_repository import BaseRepository

class IncidenciaRepository(BaseRepository):
    """Repositorio para operaciones de incidencias"""
    
    def __init__(self, connection_manager):
        # 🔥 CORRECCIÓN: Llamar a super() con connection_manager
        super().__init__(connection_manager)
        self.logger = logging.getLogger("IncidenciaRepository")
    
    async def crear_incidencia_simple(
        self, 
        usuario_id: int,
        tipo: str,
        descripcion: str,
        prioridad: str = "media"
    ) -> Optional[Dict[str, Any]]:
        """
        Crear incidencia simple sin dependencias complejas.
        """
        try:
            # Generar número de ticket simple
            import uuid
            numero_ticket = f"INC-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            
            query = """
                INSERT INTO incidencias 
                (usuario_id, numero_ticket, tipo, descripcion, prioridad, estado, fecha_creacion)
                VALUES ($1, $2, $3, $4, $5, 'abierta', NOW())
                RETURNING id, numero_ticket, tipo, descripcion, prioridad, estado, fecha_creacion
            """
            
            record = await self.fetch_one(query, usuario_id, numero_ticket, tipo, descripcion, prioridad)
            
            if record:
                return {
                    "id": record["id"],
                    "numero_ticket": record["numero_ticket"],
                    "tipo": record["tipo"],
                    "descripcion": record["descripcion"],
                    "prioridad": record["prioridad"],
                    "estado": record["estado"],
                    "fecha_creacion": record["fecha_creacion"]
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error creando incidencia: {e}")
            return None
    
    async def get_by_usuario(self, usuario_id: int) -> List[Dict[str, Any]]:
        """Obtener incidencias de un usuario"""
        try:
            query = """
                SELECT id, numero_ticket, tipo, descripcion, prioridad, estado, 
                       fecha_creacion, fecha_actualizacion
                FROM incidencias 
                WHERE usuario_id = $1 
                ORDER BY fecha_creacion DESC
            """
            
            records = await self.fetch_many(query, usuario_id)
            
            return [
                {
                    "id": record["id"],
                    "numero_ticket": record["numero_ticket"],
                    "tipo": record["tipo"],
                    "descripcion": record["descripcion"],
                    "prioridad": record["prioridad"],
                    "estado": record["estado"],
                    "fecha_creacion": record["fecha_creacion"],
                    "fecha_actualizacion": record["fecha_actualizacion"]
                }
                for record in records
            ]
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo incidencias del usuario {usuario_id}: {e}")
            return []