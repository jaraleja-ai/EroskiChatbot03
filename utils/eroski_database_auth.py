# =====================================================
# utils/eroski_database_auth.py - ACTUALIZADO PARA ESTRUCTURA REAL
# =====================================================
"""
EroskiDatabaseEmployeeValidator adaptado a la estructura real de la tabla usuarios.

ESTRUCTURA REAL:
- id, nombre, apellido, email, numero_empleado (VARCHAR(4))
- rol, departamento, activo (boolean), created_at, updated_at
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import re

# Importar sistema de BD existente
from utils.database.user_repository import UserRepository
from utils.database.connection_manager import get_connection_manager

logger = logging.getLogger("EroskiDatabaseAuth")

class EroskiDatabaseEmployeeValidator:
    """
    Validador de empleados adaptado a la estructura real de PostgreSQL.
    
    CARACTERÍSTICAS:
    - Usa estructura real: activo (boolean) en lugar de estado
    - Trabaja con created_at/updated_at en lugar de fecha_creacion
    - Maneja numero_empleado como VARCHAR(4)
    - Sin ultimo_acceso (usa updated_at)
    """
    
    def __init__(self):
        self.logger = logging.getLogger("DatabaseEmployeeValidator")
        self.user_repository: Optional[UserRepository] = None
        
        # Mapping de departamentos a información de tienda
        self.store_mapping = {
            "Desarrollo": {
                "store_id": "ERO001",
                "store_name": "Eroski Oficinas Centrales - IT",
                "store_type": "oficina_central",
                "address": "Barrio San Agustín s/n, 48230 Elorrio, Bizkaia",
                "phone": "+34 946 211 000"
            },
            "Marketing": {
                "store_id": "ERO002", 
                "store_name": "Eroski Oficinas Centrales - Marketing",
                "store_type": "oficina_central",
                "address": "Barrio San Agustín s/n, 48230 Elorrio, Bizkaia",
                "phone": "+34 946 211 000"
            },
            "Ventas": {
                "store_id": "ERO003",
                "store_name": "Eroski Oficinas Centrales - Ventas", 
                "store_type": "oficina_central",
                "address": "Barrio San Agustín s/n, 48230 Elorrio, Bizkaia",
                "phone": "+34 946 211 000"
            },
            "Recursos Humanos": {
                "store_id": "ERO004",
                "store_name": "Eroski Oficinas Centrales - RRHH",
                "store_type": "oficina_central", 
                "address": "Barrio San Agustín s/n, 48230 Elorrio, Bizkaia",
                "phone": "+34 946 211 000"
            },
            "Operaciones": {
                "store_id": "ERO005",
                "store_name": "Eroski Oficinas Centrales - Operaciones",
                "store_type": "oficina_central",
                "address": "Barrio San Agustín s/n, 48230 Elorrio, Bizkaia", 
                "phone": "+34 946 211 000"
            }
        }
    
    async def _ensure_repository(self):
        """Asegurar que el repositorio esté inicializado"""
        if self.user_repository is None:
            connection_manager = await get_connection_manager()
            self.user_repository = connection_manager.get_user_repository()
    
    async def validate_employee(
        self, 
        email: str, 
        store_hint: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Validar empleado contra la base de datos PostgreSQL.
        
        Args:
            email: Email del empleado
            store_hint: Pista sobre la tienda (opcional)
            
        Returns:
            Datos del empleado si es válido, None en caso contrario
        """
        try:
            self.logger.info(f"🔍 Validando empleado en BD: {email}")
            
            # Asegurar repositorio inicializado
            await self._ensure_repository()
            
            # Validar formato de email
            if not self._is_valid_eroski_email(email):
                self.logger.warning(f"❌ Email no válido para Eroski: {email}")
                return None
            
            # 🔥 CORRECCIÓN: Usar get_by_email que ahora funciona con estructura real
            usuario_db = await self.user_repository.get_by_email(email)
            
            if not usuario_db:
                self.logger.warning(f"❌ Empleado no encontrado en BD: {email}")
                return None
            
            # 🔥 CORRECCIÓN: Verificar que esté activo (boolean)
            if not usuario_db.get("activo", False):
                self.logger.warning(f"❌ Empleado inactivo: {email}")
                return None
            
            # Actualizar timestamp de acceso
            await self._update_access_timestamp(usuario_db["id"])
            
            # Convertir a formato compatible con el sistema de autenticación
            employee_data = await self._convert_to_auth_format(usuario_db, store_hint)
            
            self.logger.info(f"✅ Empleado validado desde BD: {employee_data['name']}")
            return employee_data
            
        except Exception as e:
            self.logger.error(f"❌ Error validando empleado en BD {email}: {e}")
            return None
    
    def _is_valid_eroski_email(self, email: str) -> bool:
        """Validar que el email sea del dominio correcto"""
        # Permitir tanto @eroski.es como @empresa.com para testing
        email_pattern = r'^[a-zA-Z0-9._%+-]+@(eroski\.es|empresa\.com)$'
        return bool(re.match(email_pattern, email, re.IGNORECASE))
    
    async def _update_access_timestamp(self, user_id: int):
        """Actualizar timestamp de acceso usando updated_at"""
        try:
            await self.user_repository.update_last_access(user_id)
            self.logger.debug(f"🕐 Timestamp actualizado para usuario {user_id}")
        except Exception as e:
            self.logger.warning(f"⚠️ Error actualizando timestamp para usuario {user_id}: {e}")
    
    async def _convert_to_auth_format(
        self, 
        usuario_db: Dict[str, Any], 
        store_hint: Optional[str]
    ) -> Dict[str, Any]:
        """
        Convertir datos de BD a formato compatible con sistema de autenticación.
        
        Args:
            usuario_db: Usuario desde la base de datos
            store_hint: Pista sobre la tienda
            
        Returns:
            Diccionario con formato esperado por el sistema de autenticación
        """
        # Determinar información de tienda basada en departamento
        departamento = usuario_db.get("departamento", "Desarrollo")
        store_info = self.store_mapping.get(
            departamento, 
            self.store_mapping["Desarrollo"]  # Default
        )
        
        # Construir respuesta en formato esperado
        return {
            "employee_id": usuario_db.get("numero_empleado", "0000"),
            "name": usuario_db.get("nombre_completo", f"{usuario_db.get('nombre', '')} {usuario_db.get('apellido', '')}").strip(),
            "email": usuario_db.get("email", ""),
            "department": departamento,
            "role": usuario_db.get("rol", "empleado"),
            "store_id": store_info["store_id"],
            "store_name": store_info["store_name"],
            "store_type": store_info["store_type"],
            "store_address": store_info["address"],
            "store_phone": store_info["phone"],
            "employee_status": "activo" if usuario_db.get("activo", False) else "inactivo",
            "last_access": usuario_db.get("updated_at", datetime.now()).isoformat(),
            "authenticated_at": datetime.now().isoformat(),
            "validation_source": "postgresql_database",
            # Campos adicionales para el sistema
            "user_id": usuario_db.get("id"),
            "created_at": usuario_db.get("created_at", datetime.now()).isoformat()
        }
    
    async def get_employee_by_numero(self, numero_empleado: str) -> Optional[Dict[str, Any]]:
        """
        Obtener empleado por número de empleado.
        
        Args:
            numero_empleado: Número de empleado (4 caracteres)
            
        Returns:
            Datos del empleado o None si no se encuentra
        """
        try:
            await self._ensure_repository()
            
            usuario_db = await self.user_repository.get_by_numero_empleado(numero_empleado)
            
            if usuario_db and usuario_db.get("activo", False):
                return await self._convert_to_auth_format(usuario_db, None)
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo empleado por número {numero_empleado}: {e}")
            return None
    
    async def get_employees_by_department(self, department: str) -> List[Dict[str, Any]]:
        """
        Obtener empleados por departamento.
        
        Args:
            department: Nombre del departamento
            
        Returns:
            Lista de empleados del departamento
        """
        try:
            await self._ensure_repository()
            
            usuarios = await self.user_repository.get_users_by_department(department)
            
            employees = []
            for usuario in usuarios:
                if usuario.get("activo", False):
                    employee_data = await self._convert_to_auth_format(usuario, None)
                    employees.append(employee_data)
            
            self.logger.info(f"✅ Encontrados {len(employees)} empleados en departamento '{department}'")
            return employees
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo empleados del departamento {department}: {e}")
            return []
    
    async def search_employees(self, search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Buscar empleados por nombre.
        
        Args:
            search_term: Término de búsqueda
            limit: Límite de resultados
            
        Returns:
            Lista de empleados que coinciden
        """
        try:
            await self._ensure_repository()
            
            usuarios = await self.user_repository.search_users_by_name(search_term, limit)
            
            employees = []
            for usuario in usuarios:
                if usuario.get("activo", False):
                    employee_data = await self._convert_to_auth_format(usuario, None)
                    employees.append(employee_data)
            
            self.logger.info(f"✅ Encontrados {len(employees)} empleados para búsqueda '{search_term}'")
            return employees
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando empleados: {e}")
            return []
    
    async def get_employee_statistics(self) -> Dict[str, Any]:
        """
        Obtener estadísticas de empleados.
        
        Returns:
            Diccionario con estadísticas
        """
        try:
            await self._ensure_repository()
            
            # Obtener todos los usuarios activos
            usuarios_activos = await self.user_repository.get_all_active_users(1000)
            
            # Contar por departamento
            departamentos = {}
            for usuario in usuarios_activos:
                dept = usuario.get("departamento", "Sin departamento")
                departamentos[dept] = departamentos.get(dept, 0) + 1
            
            return {
                "total_employees": len(usuarios_activos),
                "active_employees": len(usuarios_activos),
                "inactive_employees": 0,  # TODO: Implementar conteo de inactivos
                "departments": departamentos,
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo estadísticas: {e}")
            return {
                "total_employees": 0,
                "active_employees": 0,
                "inactive_employees": 0,
                "departments": {},
                "last_updated": datetime.now().isoformat()
            }

# ========== INSTANCIAS GLOBALES ==========

_global_database_validator: Optional[EroskiDatabaseEmployeeValidator] = None

def get_database_employee_validator() -> EroskiDatabaseEmployeeValidator:
    """Obtener instancia global del validador de base de datos"""
    global _global_database_validator
    if _global_database_validator is None:
        _global_database_validator = EroskiDatabaseEmployeeValidator()
    return _global_database_validator

# ========== FUNCIONES DE CONVENIENCIA ==========

async def validate_eroski_employee_db(
    email: str, 
    store_hint: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Función de conveniencia para validar empleado desde BD"""
    validator = get_database_employee_validator()
    return await validator.validate_employee(email, store_hint)

async def get_employee_by_numero_db(numero_empleado: str) -> Optional[Dict[str, Any]]:
    """Función de conveniencia para obtener empleado por número desde BD"""
    validator = get_database_employee_validator()
    return await validator.get_employee_by_numero(numero_empleado)

async def search_employees_db(search_term: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Función de conveniencia para buscar empleados desde BD"""
    validator = get_database_employee_validator()
    return await validator.search_employees(search_term, limit)