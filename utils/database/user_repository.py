# =====================================================
# utils/database/user_repository.py - Repositorio de usuarios
# =====================================================
from models.user import UsuarioDB, UsuarioCreate, UsuarioUpdate, EstadoUsuario
from typing import Optional, List
from .base_repository import BaseRepository
import asyncpg


class UserRepository(BaseRepository[UsuarioDB]):
    """Repositorio para operaciones de usuarios"""
    
    async def buscar_por_email(self, email: str) -> Optional[UsuarioDB]:
        """
        Buscar usuario por email.
        
        Args:
            email: Email a buscar
            
        Returns:
            UsuarioDB si se encuentra, None si no existe
        """
        query = """
            SELECT id, nombre, apellido, email, numero_empleado, 
                   rol, departamento, estado, fecha_creacion, 
                   fecha_actualizacion, ultimo_acceso
            FROM usuarios 
            WHERE LOWER(email) = LOWER($1) AND estado = $2
        """
        
        try:
            row = await self.fetch_one(query, email, EstadoUsuario.ACTIVO.value)
            
            if row:
                return UsuarioDB(
                    id=row['id'],
                    nombre=row['nombre'],
                    apellido=row['apellido'],
                    email=row['email'],
                    numero_empleado=row['numero_empleado'],
                    rol=row['rol'],
                    departamento=row['departamento'],
                    estado=EstadoUsuario(row['estado']),
                    fecha_creacion=row['fecha_creacion'],
                    fecha_actualizacion=row['fecha_actualizacion'],
                    ultimo_acceso=row['ultimo_acceso']
                )
            
            self.logger.info(f"🔍 Usuario {'encontrado' if row else 'no encontrado'}: {email}")
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando usuario por email {email}: {e}")
            raise
    
    async def buscar_por_numero_empleado(self, numero: str) -> Optional[UsuarioDB]:
        """Buscar usuario por número de empleado"""
        query = """
            SELECT id, nombre, apellido, email, numero_empleado,
                   rol, departamento, estado, fecha_creacion,
                   fecha_actualizacion, ultimo_acceso
            FROM usuarios 
            WHERE numero_empleado = $1 AND estado = $2
        """
        
        try:
            row = await self.fetch_one(query, numero, EstadoUsuario.ACTIVO.value)
            
            if row:
                return UsuarioDB(**dict(row))
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando por número de empleado {numero}: {e}")
            raise
    
    async def actualizar_nombre(self, email: str, nombre: str, apellido: str) -> bool:
        """
        Actualizar nombre y apellido de usuario.
        
        Args:
            email: Email del usuario
            nombre: Nuevo nombre
            apellido: Nuevo apellido
            
        Returns:
            True si se actualizó correctamente
        """
        query = """
            UPDATE usuarios 
            SET nombre = $2, apellido = $3, fecha_actualizacion = NOW()
            WHERE LOWER(email) = LOWER($1) AND estado = $4
        """
        
        try:
            result = await self.execute_query(query, email, nombre, apellido, EstadoUsuario.ACTIVO.value)
            
            # Verificar si se actualizó algún registro
            updated = result.split()[-1] == "1"
            
            if updated:
                self.logger.info(f"✅ Nombre actualizado para {email}: {nombre} {apellido}")
            else:
                self.logger.warning(f"⚠️ No se encontró usuario para actualizar: {email}")
            
            return updated
            
        except Exception as e:
            self.logger.error(f"❌ Error actualizando nombre para {email}: {e}")
            raise
    
    async def crear_usuario(self, usuario_data: UsuarioCreate) -> Optional[UsuarioDB]:
        """
        Crear nuevo usuario.
        
        Args:
            usuario_data: Datos del usuario a crear
            
        Returns:
            UsuarioDB del usuario creado o None si hubo error
        """
        query = """
            INSERT INTO usuarios (nombre, apellido, email, numero_empleado, rol, departamento, estado)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING id, nombre, apellido, email, numero_empleado, 
                     rol, departamento, estado, fecha_creacion, fecha_actualizacion
        """
        
        try:
            row = await self.fetch_one(
                query,
                usuario_data.nombre,
                usuario_data.apellido,
                usuario_data.email,
                usuario_data.numero_empleado,
                usuario_data.rol.value,
                usuario_data.departamento,
                EstadoUsuario.ACTIVO.value
            )
            
            if row:
                usuario = UsuarioDB(**dict(row))
                self.logger.info(f"✅ Usuario creado: {usuario.nombre_completo} ({usuario.numero_empleado})")
                return usuario
            
            return None
            
        except asyncpg.UniqueViolationError as e:
            self.logger.warning(f"⚠️ Usuario ya existe: {usuario_data.email}")
            raise ValueError(f"Usuario con email {usuario_data.email} ya existe")
        except Exception as e:
            self.logger.error(f"❌ Error creando usuario: {e}")
            raise
    
    async def buscar_usuarios_similares(self, nombre: str, limite: int = 5) -> List[UsuarioDB]:
        """
        Buscar usuarios con nombres similares usando PostgreSQL similarity.
        
        Args:
            nombre: Nombre a buscar
            limite: Número máximo de resultados
            
        Returns:
            Lista de usuarios similares
        """
        query = """
            SELECT id, nombre, apellido, email, numero_empleado,
                   rol, departamento, estado, fecha_creacion,
                   fecha_actualizacion, ultimo_acceso,
                   similarity(nombre || ' ' || apellido, $1) as sim_score
            FROM usuarios 
            WHERE estado = $2 
              AND similarity(nombre || ' ' || apellido, $1) > 0.3
            ORDER BY sim_score DESC
            LIMIT $3
        """
        
        try:
            rows = await self.fetch_many(query, nombre, EstadoUsuario.ACTIVO.value, limite)
            
            usuarios = []
            for row in rows:
                usuario_dict = dict(row)
                # Remover sim_score antes de crear el objeto
                usuario_dict.pop('sim_score', None)
                usuarios.append(UsuarioDB(**usuario_dict))
            
            self.logger.debug(f"🔍 Usuarios similares encontrados: {len(usuarios)} para '{nombre}'")
            return usuarios
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando usuarios similares: {e}")
            return []
    
    async def actualizar_ultimo_acceso(self, user_id: int) -> bool:
        """Actualizar timestamp de último acceso"""
        query = """
            UPDATE usuarios 
            SET ultimo_acceso = NOW(), fecha_actualizacion = NOW()
            WHERE id = $1
        """
        
        try:
            result = await self.execute_query(query, user_id)
            return result.split()[-1] == "1"
        except Exception as e:
            self.logger.error(f"❌ Error actualizando último acceso: {e}")
            return False

