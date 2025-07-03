# =====================================================
# models/user.py - Modelos de usuario para Eroski
# =====================================================
"""
Modelos Pydantic para usuarios del sistema de Eroski.
Incluye validaciones específicas para empleados de Eroski.
"""

from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

# ==================== ENUMS ====================

class RolUsuario(str, Enum):
    """Roles de usuario en Eroski"""
    EMPLEADO = "empleado"
    SUPERVISOR = "supervisor"
    ADMINISTRADOR = "administrador"
    JEFE_SECCION = "jefe_seccion"
    GERENTE_TIENDA = "gerente_tienda"

class EstadoUsuario(str, Enum):
    """Estados posibles de un usuario"""
    ACTIVO = "activo"
    INACTIVO = "inactivo" 
    SUSPENDIDO = "suspendido"
    BAJA = "baja"

# ==================== MODELOS BASE ====================

class UsuarioBase(BaseModel):
    """Modelo base para usuarios"""
    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre del empleado")
    apellido: str = Field(..., min_length=2, max_length=100, description="Apellido del empleado")
    email: EmailStr = Field(..., description="Email corporativo de Eroski")
    numero_empleado: str = Field(..., min_length=3, max_length=50, description="Número de empleado único")
    rol: RolUsuario = Field(default=RolUsuario.EMPLEADO, description="Rol del empleado")
    departamento: Optional[str] = Field(None, max_length=100, description="Departamento de trabajo")
    tienda: Optional[str] = Field(None, max_length=100, description="Tienda donde trabaja")

    @validator('email')
    def validar_email_eroski(cls, v):
        """Validar que el email sea de dominio Eroski"""
        if not v.endswith('@eroski.es'):
            raise ValueError('El email debe ser del dominio @eroski.es')
        return v.lower()

    @validator('numero_empleado')
    def validar_numero_empleado(cls, v):
        """Validar formato del número de empleado"""
        v = v.upper().strip()
        if not v:
            raise ValueError('Número de empleado requerido')
        return v

    @validator('nombre', 'apellido')
    def validar_nombres(cls, v):
        """Validar que nombres contengan solo letras y espacios"""
        if not v.replace(' ', '').replace('-', '').isalpha():
            raise ValueError('Nombres solo pueden contener letras, espacios y guiones')
        return v.title()

class UsuarioCreate(UsuarioBase):
    """Modelo para crear usuarios"""
    estado: EstadoUsuario = Field(default=EstadoUsuario.ACTIVO, description="Estado inicial del usuario")

class UsuarioUpdate(BaseModel):
    """Modelo para actualizar usuarios"""
    nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    apellido: Optional[str] = Field(None, min_length=2, max_length=100)
    rol: Optional[RolUsuario] = None
    departamento: Optional[str] = Field(None, max_length=100)
    tienda: Optional[str] = Field(None, max_length=100)
    estado: Optional[EstadoUsuario] = None

    @validator('nombre', 'apellido')
    def validar_nombres_update(cls, v):
        """Validar nombres en actualización"""
        if v is not None:
            if not v.replace(' ', '').replace('-', '').isalpha():
                raise ValueError('Nombres solo pueden contener letras, espacios y guiones')
            return v.title()
        return v

# ==================== MODELO DE BASE DE DATOS ====================

class UsuarioDB(UsuarioBase):
    """Modelo completo de usuario desde base de datos"""
    id: int = Field(..., description="ID único del usuario")
    estado: EstadoUsuario = Field(..., description="Estado actual del usuario")
    fecha_creacion: datetime = Field(..., description="Fecha de creación del registro")
    fecha_actualizacion: datetime = Field(..., description="Última actualización")
    ultimo_acceso: Optional[datetime] = Field(None, description="Último acceso al sistema")

    class Config:
        from_attributes = True  # Para compatibilidad con SQLAlchemy/asyncpg
        
    @property
    def nombre_completo(self) -> str:
        """Nombre completo del usuario"""
        return f"{self.nombre} {self.apellido}"
    
    @property
    def activo(self) -> bool:
        """Si el usuario está activo"""
        return self.estado == EstadoUsuario.ACTIVO
    
    @property
    def info_tienda(self) -> str:
        """Información formateada de la tienda"""
        return self.tienda or "Oficinas Centrales"
    
    def to_dict(self) -> dict:
        """Convertir a diccionario para uso en workflows"""
        return {
            "id": self.id,
            "nombre": self.nombre,
            "apellido": self.apellido,
            "nombre_completo": self.nombre_completo,
            "email": self.email,
            "numero_empleado": self.numero_empleado,
            "rol": self.rol.value,
            "departamento": self.departamento,
            "tienda": self.info_tienda,
            "estado": self.estado.value,
            "activo": self.activo,
            "ultimo_acceso": self.ultimo_acceso.isoformat() if self.ultimo_acceso else None
        }

# ==================== MODELO PARA EXTRACCIÓN DE DATOS ====================

class UsuarioExtracted(BaseModel):
    """Modelo para datos extraídos del texto del usuario"""
    email: Optional[str] = Field(None, description="Email extraído del mensaje")
    nombre: Optional[str] = Field(None, description="Nombre extraído del mensaje") 
    departamento: Optional[str] = Field(None, description="Departamento mencionado")
    numero_empleado: Optional[str] = Field(None, description="Número de empleado mencionado")
    
    @validator('email')
    def limpiar_email(cls, v):
        """Limpiar y validar email extraído"""
        if v:
            v = v.lower().strip()
            if '@' in v and v.endswith('eroski.es'):
                return v
        return v

    def tiene_datos_identificacion(self) -> bool:
        """Verificar si tiene datos suficientes para identificación"""
        return bool(self.email or self.numero_empleado)

# ==================== FUNCIONES HELPER ====================

def crear_usuario_desde_dict(data: dict) -> UsuarioDB:
    """Crear UsuarioDB desde diccionario de base de datos"""
    return UsuarioDB(
        id=data['id'],
        nombre=data['nombre'],
        apellido=data['apellido'],
        email=data['email'],
        numero_empleado=data['numero_empleado'],
        rol=RolUsuario(data['rol']),
        departamento=data.get('departamento'),
        tienda=data.get('tienda'),
        estado=EstadoUsuario(data['estado']),
        fecha_creacion=data['fecha_creacion'],
        fecha_actualizacion=data['fecha_actualizacion'],
        ultimo_acceso=data.get('ultimo_acceso')
    )

def normalizar_email_eroski(email: str) -> str:
    """Normalizar email de Eroski"""
    email = email.lower().strip()
    if not email.endswith('@eroski.es'):
        if '@' not in email:
            email = f"{email}@eroski.es"
    return email

def generar_numero_empleado(nombre: str, apellido: str, departamento: str = "GEN") -> str:
    """Generar número de empleado único"""
    import hashlib
    import time
    
    # Crear hash único basado en datos y timestamp
    data = f"{nombre}{apellido}{departamento}{time.time()}"
    hash_obj = hashlib.md5(data.encode())
    hash_hex = hash_obj.hexdigest()[:6].upper()
    
    return f"{departamento[:3].upper()}{hash_hex}"

# ==================== VALIDADORES ESPECÍFICOS ====================

def validar_estructura_usuario(usuario_data: dict) -> bool:
    """Validar que un diccionario tenga la estructura correcta de usuario"""
    campos_requeridos = ['nombre', 'apellido', 'email', 'numero_empleado']
    return all(campo in usuario_data for campo in campos_requeridos)

def es_email_valido_eroski(email: str) -> bool:
    """Verificar si un email es válido para Eroski"""
    try:
        return (
            '@' in email and 
            email.endswith('@eroski.es') and
            len(email.split('@')[0]) >= 2
        )
    except:
        return False