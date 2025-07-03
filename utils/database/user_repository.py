# =====================================================
# utils/database/user_repository.py - CORREGIDO PARA ESTRUCTURA REAL
# =====================================================
"""
UserRepository adaptado a la estructura real de la tabla usuarios:

COLUMNAS REALES:
- id
- nombre  
- apellido
- email
- numero_empleado (VARCHAR(4))
- rol
- departamento  
- activo (boolean)
- created_at
- updated_at
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from .base_repository import BaseRepository

class UserRepository(BaseRepository):
    """Repositorio para operaciones de usuarios - ADAPTADO A ESTRUCTURA REAL"""
    
    def __init__(self, connection_manager):
        super().__init__(connection_manager)
        self.logger = logging.getLogger("UserRepository")
    
    async def get_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Obtener usuario por email usando la estructura real de BD.
        
        Args:
            email: Email a buscar
            
        Returns:
            Diccionario con datos del usuario o None si no existe
        """
        try:
            # 🔥 CORRECCIÓN: Query adaptado a estructura real
            query = """
                SELECT id, nombre, apellido, email, numero_empleado, 
                       rol, departamento, activo, created_at, updated_at
                FROM usuarios 
                WHERE LOWER(email) = LOWER($1) AND activo = true
            """
            
            row = await self.fetch_one(query, email)
            
            if row:
                user_data = {
                    "id": row["id"],
                    "nombre": row["nombre"],
                    "apellido": row["apellido"], 
                    "email": row["email"],
                    "numero_empleado": row["numero_empleado"],
                    "rol": row["rol"],
                    "departamento": row["departamento"],
                    "activo": row["activo"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    # Campos derivados para compatibilidad
                    "nombre_completo": f"{row['nombre']} {row['apellido']}",
                    "estado": "activo" if row["activo"] else "inactivo"
                }
                
                self.logger.info(f"✅ Usuario encontrado: {user_data['nombre_completo']} ({email})")
                return user_data
            else:
                self.logger.info(f"❌ Usuario no encontrado: {email}")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Error buscando usuario por email {email}: {e}")
            raise
    
    async def get_by_numero_empleado(self, numero_empleado: str) -> Optional[Dict[str, Any]]:
        """
        Obtener usuario por número de empleado.
        
        Args:
            numero_empleado: Número de empleado (4 caracteres)
            
        Returns:
            Diccionario con datos del usuario o None si no existe
        """
        try:
            query = """
                SELECT id, nombre, apellido, email, numero_empleado,
                       rol, departamento, activo, created_at, updated_at
                FROM usuarios 
                WHERE numero_empleado = $1 AND activo = true
            """
            
            row = await self.fetch_one(query, numero_empleado)
            
            if row:
                user_data = {
                    "id": row["id"],
                    "nombre": row["nombre"],
                    "apellido": row["apellido"],
                    "email": row["email"],
                    "numero_empleado": row["numero_empleado"],
                    "rol": row["rol"],
                    "departamento": row["departamento"],
                    "activo": row["activo"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "nombre_completo": f"{row['nombre']} {row['apellido']}",
                    "estado": "activo" if row["activo"] else "inactivo"
                }
                
                self.logger.info(f"✅ Usuario encontrado por número: {user_data['nombre_completo']} ({numero_empleado})")
                return user_data
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando por número de empleado {numero_empleado}: {e}")
            raise
    
    async def update_last_access(self, user_id: int) -> bool:
        """
        Actualizar timestamp de acceso (usando updated_at ya que no hay ultimo_acceso).
        
        Args:
            user_id: ID del usuario
            
        Returns:
            True si se actualizó correctamente
        """
        try:
            # 🔥 CORRECCIÓN: Usar updated_at ya que ultimo_acceso no existe
            query = """
                UPDATE usuarios 
                SET updated_at = NOW() 
                WHERE id = $1 AND activo = true
            """
            
            result = await self.execute_query(query, user_id)
            self.logger.info(f"✅ Timestamp actualizado para usuario {user_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error actualizando timestamp: {e}")
            return False
    
    async def get_all_active_users(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Obtener todos los usuarios activos.
        
        Args:
            limit: Límite de usuarios a retornar
            
        Returns:
            Lista de usuarios activos
        """
        try:
            query = """
                SELECT id, nombre, apellido, email, numero_empleado,
                       rol, departamento, activo, created_at, updated_at
                FROM usuarios 
                WHERE activo = true
                ORDER BY apellido, nombre
                LIMIT $1
            """
            
            rows = await self.fetch_many(query, limit)
            
            users = []
            for row in rows:
                user_data = {
                    "id": row["id"],
                    "nombre": row["nombre"],
                    "apellido": row["apellido"],
                    "email": row["email"],
                    "numero_empleado": row["numero_empleado"],
                    "rol": row["rol"],
                    "departamento": row["departamento"],
                    "activo": row["activo"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "nombre_completo": f"{row['nombre']} {row['apellido']}",
                    "estado": "activo"
                }
                users.append(user_data)
            
            self.logger.info(f"✅ Obtenidos {len(users)} usuarios activos")
            return users
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo usuarios activos: {e}")
            return []
    
    async def search_users_by_name(self, search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Buscar usuarios por nombre o apellido.
        
        Args:
            search_term: Término de búsqueda
            limit: Límite de resultados
            
        Returns:
            Lista de usuarios que coinciden
        """
        try:
            query = """
                SELECT id, nombre, apellido, email, numero_empleado,
                       rol, departamento, activo, created_at, updated_at
                FROM usuarios 
                WHERE activo = true 
                AND (
                    LOWER(nombre) LIKE LOWER($1) OR 
                    LOWER(apellido) LIKE LOWER($1) OR
                    LOWER(CONCAT(nombre, ' ', apellido)) LIKE LOWER($1)
                )
                ORDER BY apellido, nombre
                LIMIT $2
            """
            
            search_pattern = f"%{search_term}%"
            rows = await self.fetch_many(query, search_pattern, limit)
            
            users = []
            for row in rows:
                user_data = {
                    "id": row["id"],
                    "nombre": row["nombre"],
                    "apellido": row["apellido"],
                    "email": row["email"],
                    "numero_empleado": row["numero_empleado"],
                    "rol": row["rol"],
                    "departamento": row["departamento"],
                    "activo": row["activo"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "nombre_completo": f"{row['nombre']} {row['apellido']}",
                    "estado": "activo"
                }
                users.append(user_data)
            
            self.logger.info(f"✅ Encontrados {len(users)} usuarios para '{search_term}'")
            return users
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando usuarios: {e}")
            return []
    
    async def get_users_by_department(self, department: str) -> List[Dict[str, Any]]:
        """
        Obtener usuarios por departamento.
        
        Args:
            department: Nombre del departamento
            
        Returns:
            Lista de usuarios del departamento
        """
        try:
            query = """
                SELECT id, nombre, apellido, email, numero_empleado,
                       rol, departamento, activo, created_at, updated_at
                FROM usuarios 
                WHERE activo = true AND LOWER(departamento) = LOWER($1)
                ORDER BY apellido, nombre
            """
            
            rows = await self.fetch_many(query, department)
            
            users = []
            for row in rows:
                user_data = {
                    "id": row["id"],
                    "nombre": row["nombre"],
                    "apellido": row["apellido"],
                    "email": row["email"],
                    "numero_empleado": row["numero_empleado"],
                    "rol": row["rol"],
                    "departamento": row["departamento"],
                    "activo": row["activo"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "nombre_completo": f"{row['nombre']} {row['apellido']}",
                    "estado": "activo"
                }
                users.append(user_data)
            
            self.logger.info(f"✅ Encontrados {len(users)} usuarios en departamento '{department}'")
            return users
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo usuarios por departamento: {e}")
            return []
    
    async def create_user(self, user_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crear nuevo usuario.
        
        Args:
            user_data: Datos del usuario a crear
            
        Returns:
            Usuario creado o None si hubo error
        """
        try:
            query = """
                INSERT INTO usuarios (nombre, apellido, email, numero_empleado, rol, departamento, activo)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id, nombre, apellido, email, numero_empleado, rol, departamento, activo, created_at, updated_at
            """
            
            row = await self.fetch_one(
                query,
                user_data["nombre"],
                user_data["apellido"],
                user_data["email"],
                user_data["numero_empleado"],
                user_data["rol"],
                user_data["departamento"],
                user_data.get("activo", True)
            )
            
            if row:
                created_user = {
                    "id": row["id"],
                    "nombre": row["nombre"],
                    "apellido": row["apellido"],
                    "email": row["email"],
                    "numero_empleado": row["numero_empleado"],
                    "rol": row["rol"],
                    "departamento": row["departamento"],
                    "activo": row["activo"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "nombre_completo": f"{row['nombre']} {row['apellido']}",
                    "estado": "activo" if row["activo"] else "inactivo"
                }
                
                self.logger.info(f"✅ Usuario creado: {created_user['nombre_completo']} ({created_user['email']})")
                return created_user
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error creando usuario: {e}")
            return None