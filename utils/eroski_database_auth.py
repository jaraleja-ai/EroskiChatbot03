# =====================================================
# utils/eroski_database_auth.py - Integración BD + Autenticación
# =====================================================
"""
Integración entre el sistema de autenticación de Eroski y la base de datos PostgreSQL.

REEMPLAZA: El sistema mock de EroskiEmployeeValidator
INTEGRA: Base de datos PostgreSQL existente + lógica de autenticación

RESPONSABILIDADES:
- Validar empleados contra la base de datos real
- Recuperar datos completos del empleado
- Actualizar último acceso
- Gestionar información de tiendas
- Mantener sincronización con sistemas HR
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import re

# Importar sistema de BD existente
from utils.database.user_repository import UserRepository
from utils.database.connection_manager import get_connection_manager
from models.user import UsuarioDB, EstadoUsuario, RolUsuario

logger = logging.getLogger("EroskiDatabaseAuth")

class EroskiDatabaseEmployeeValidator:
    """
    Validador de empleados que usa la base de datos PostgreSQL existente.
    
    REEMPLAZA: EroskiEmployeeValidator mock
    USA: Sistema de BD ya implementado en el proyecto
    
    CARACTERÍSTICAS:
    - Validación real contra PostgreSQL
    - Recuperación completa de datos de empleado
    - Actualización de último acceso
    - Gestión de estados de empleado
    - Integración con sistema de tiendas
    """
    
    def __init__(self):
        self.logger = logging.getLogger("DatabaseEmployeeValidator")
        self.user_repository: Optional[UserRepository] = None
        
        # Mapping de datos para compatibilidad con el sistema nuevo
        self.store_mapping = {
            # Mapeo de departamentos a información de tienda
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
            # TODO: Agregar más mapeos según estructura real de Eroski
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
            
            # Buscar empleado en base de datos
            usuario_db = await self.user_repository.obtener_por_email(email)
            
            if not usuario_db:
                self.logger.warning(f"❌ Empleado no encontrado en BD: {email}")
                return None
            
            # Verificar que esté activo
            if usuario_db.estado != EstadoUsuario.ACTIVO:
                self.logger.warning(f"❌ Empleado inactivo: {email} (estado: {usuario_db.estado})")
                return None
            
            # Actualizar último acceso
            await self._update_last_access(email)
            
            # Convertir a formato compatible con el nuevo sistema
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
    
    async def _update_last_access(self, email: str):
        """Actualizar timestamp de último acceso"""
        try:
            await self.user_repository.actualizar_ultimo_acceso(email)
            self.logger.debug(f"🕐 Último acceso actualizado para {email}")
        except Exception as e:
            self.logger.warning(f"⚠️ Error actualizando último acceso para {email}: {e}")
    
    async def _convert_to_auth_format(
        self, 
        usuario_db: UsuarioDB, 
        store_hint: Optional[str]
    ) -> Dict[str, Any]:
        """
        Convertir UsuarioDB a formato compatible con sistema de autenticación.
        
        Args:
            usuario_db: Usuario de la base de datos
            store_hint: Pista de tienda del usuario
            
        Returns:
            Diccionario con formato del nuevo sistema
        """
        # Obtener información de tienda basada en departamento
        store_info = self._get_store_info_for_department(
            usuario_db.departamento, 
            store_hint
        )
        
        # Mapear rol a nivel numérico
        level_mapping = {
            RolUsuario.EMPLEADO: 1,
            RolUsuario.SUPERVISOR: 3,
            RolUsuario.ADMINISTRADOR: 4
        }
        
        return {
            "id": str(usuario_db.numero_empleado),  # Usar numero_empleado como ID
            "name": usuario_db.nombre_completo,
            "email": usuario_db.email,
            "store_id": store_info["store_id"],
            "store_name": store_info["store_name"],
            "store_type": store_info["store_type"],
            "department": usuario_db.departamento or "No especificado",
            "level": level_mapping.get(usuario_db.rol, 1),
            "shift": "completa",  # Por defecto, podría venir de otra tabla
            "active": usuario_db.estado == EstadoUsuario.ACTIVO,
            
            # Información adicional de tienda
            "store_address": store_info.get("address"),
            "store_phone": store_info.get("phone"),
            "store_region": self._get_region_from_address(store_info.get("address", "")),
            
            # Metadatos adicionales
            "employee_since": usuario_db.fecha_creacion.isoformat() if usuario_db.fecha_creacion else None,
            "last_updated": usuario_db.fecha_actualizacion.isoformat() if usuario_db.fecha_actualizacion else None,
            "last_access": usuario_db.ultimo_acceso.isoformat() if usuario_db.ultimo_acceso else None,
        }
    
    def _get_store_info_for_department(
        self, 
        departamento: Optional[str], 
        store_hint: Optional[str]
    ) -> Dict[str, str]:
        """
        Obtener información de tienda basada en departamento.
        
        Args:
            departamento: Departamento del empleado
            store_hint: Pista adicional de tienda
            
        Returns:
            Información de la tienda
        """
        # Usar mapeo de departamento si existe
        if departamento and departamento in self.store_mapping:
            store_info = self.store_mapping[departamento].copy()
            
            # Ajustar basado en store_hint si se proporciona
            if store_hint:
                store_info = self._adjust_store_by_hint(store_info, store_hint)
            
            return store_info
        
        # Fallback: tienda genérica
        return {
            "store_id": "ERO999",
            "store_name": "Eroski - Ubicación por Determinar",
            "store_type": "generic",
            "address": "Por determinar",
            "phone": "+34 946 211 000"
        }
    
    def _adjust_store_by_hint(
        self, 
        base_store_info: Dict[str, str], 
        store_hint: str
    ) -> Dict[str, str]:
        """Ajustar información de tienda basada en pista del usuario"""
        store_hint_lower = store_hint.lower()
        
        # Mapeo de ciudades/ubicaciones conocidas
        location_mapping = {
            "bilbao": {
                "store_id": "ERO001", 
                "store_name": "Eroski Bilbao Centro",
                "address": "Gran Vía 1, 48001 Bilbao, Bizkaia"
            },
            "madrid": {
                "store_id": "ERO002",
                "store_name": "Eroski Madrid Salamanca", 
                "address": "Calle Salamanca 100, 28006 Madrid"
            },
            "barcelona": {
                "store_id": "ERO003",
                "store_name": "Eroski Barcelona Diagonal",
                "address": "Avda. Diagonal 200, 08018 Barcelona"
            }
        }
        
        # Buscar coincidencias en el hint
        for location, info in location_mapping.items():
            if location in store_hint_lower:
                base_store_info.update(info)
                break
        
        return base_store_info
    
    def _get_region_from_address(self, address: str) -> str:
        """Extraer región de la dirección"""
        if "Bizkaia" in address or "Bilbao" in address:
            return "País Vasco"
        elif "Madrid" in address:
            return "Madrid"
        elif "Barcelona" in address:
            return "Cataluña"
        else:
            return "España"
    
    # ========== MÉTODOS ADICIONALES PARA COMPATIBILIDAD ==========
    
    async def get_employee_by_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Obtener empleado por número de empleado"""
        try:
            await self._ensure_repository()
            
            usuario_db = await self.user_repository.obtener_por_numero_empleado(employee_id)
            
            if usuario_db and usuario_db.estado == EstadoUsuario.ACTIVO:
                return await self._convert_to_auth_format(usuario_db, None)
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo empleado por ID {employee_id}: {e}")
            return None
    
    async def get_store_employees(self, store_id: str) -> List[Dict[str, Any]]:
        """
        Obtener todos los empleados de una tienda.
        
        NOTA: Implementación básica. En un sistema real, 
        habría una tabla separada para tiendas.
        """
        try:
            await self._ensure_repository()
            
            # Por ahora, filtrar por departamento que mapee a la tienda
            # En el futuro, debería haber una tabla de tiendas y relación
            
            # Buscar empleados activos
            # TODO: Implementar búsqueda por tienda cuando se tenga tabla dedicada
            usuarios = await self.user_repository.buscar_usuarios_similares("", limite=100)
            
            employees = []
            for usuario in usuarios:
                if usuario.estado == EstadoUsuario.ACTIVO:
                    employee_data = await self._convert_to_auth_format(usuario, None)
                    if employee_data["store_id"] == store_id:
                        employees.append(employee_data)
            
            return employees
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo empleados de tienda {store_id}: {e}")
            return []
    
    async def get_supervisors_for_store(self, store_id: str) -> List[Dict[str, Any]]:
        """Obtener supervisores de una tienda específica"""
        try:
            # Obtener todos los empleados de la tienda
            store_employees = await self.get_store_employees(store_id)
            
            # Filtrar solo supervisores (level >= 3)
            supervisors = [
                emp for emp in store_employees 
                if emp.get("level", 1) >= 3
            ]
            
            return supervisors
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo supervisores de tienda {store_id}: {e}")
            return []
    
    # ========== MÉTODOS DE ADMINISTRACIÓN ==========
    
    async def create_employee(self, employee_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crear nuevo empleado en la base de datos.
        
        Args:
            employee_data: Datos del empleado
            
        Returns:
            Datos del empleado creado
        """
        try:
            await self._ensure_repository()
            
            from models.user import UsuarioCreate
            
            # Convertir a formato UsuarioCreate
            usuario_create = UsuarioCreate(
                nombre=employee_data["name"].split()[0],
                apellido=" ".join(employee_data["name"].split()[1:]),
                email=employee_data["email"],
                numero_empleado=employee_data["id"],
                departamento=employee_data.get("department"),
                rol=RolUsuario.EMPLEADO  # Por defecto empleado
            )
            
            # Crear en base de datos
            usuario_db = await self.user_repository.crear_usuario(usuario_create)
            
            if usuario_db:
                # Convertir a formato de respuesta
                return await self._convert_to_auth_format(usuario_db, None)
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error creando empleado: {e}")
            return None
    
    async def update_employee(
        self, 
        email: str, 
        update_data: Dict[str, Any]
    ) -> bool:
        """
        Actualizar información de empleado.
        
        Args:
            email: Email del empleado
            update_data: Datos a actualizar
            
        Returns:
            True si se actualizó correctamente
        """
        try:
            await self._ensure_repository()
            
            # Por ahora, solo actualizar nombre (expandir según necesidades)
            if "name" in update_data:
                name_parts = update_data["name"].split()
                nombre = name_parts[0] if name_parts else ""
                apellido = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""
                
                return await self.user_repository.actualizar_nombre(email, nombre, apellido)
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error actualizando empleado {email}: {e}")
            return False
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas de la base de datos"""
        try:
            await self._ensure_repository()
            
            # Contar usuarios por estado
            # TODO: Implementar métodos de estadísticas en UserRepository
            
            return {
                "total_employees": 0,  # TODO: Implementar
                "active_employees": 0,  # TODO: Implementar  
                "inactive_employees": 0,  # TODO: Implementar
                "departments": [],  # TODO: Implementar
                "last_updated": datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo estadísticas: {e}")
            return {}

# ========== REEMPLAZO DEL VALIDADOR MOCK ==========

# Instancia global que reemplaza al mock
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

async def get_employee_by_id_db(employee_id: str) -> Optional[Dict[str, Any]]:
    """Función de conveniencia para obtener empleado por ID desde BD"""
    validator = get_database_employee_validator()
    return await validator.get_employee_by_id(employee_id)

async def get_store_supervisors_db(store_id: str) -> List[Dict[str, Any]]:
    """Función de conveniencia para obtener supervisores desde BD"""
    validator = get_database_employee_validator()
    return await validator.get_supervisors_for_store(store_id)