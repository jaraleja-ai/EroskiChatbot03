# =====================================================
# models/user.py - Modelos de usuario
# =====================================================
from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum

class RolUsuario(str, Enum):
    """Roles de usuario en el sistema"""
    EMPLEADO = "empleado"
    SUPERVISOR = "supervisor"
    ADMINISTRADOR = "administrador"

class EstadoUsuario(str, Enum):
    """Estados de usuario"""
    ACTIVO = "activo"
    INACTIVO = "inactivo"
    SUSPENDIDO = "suspendido"

class UsuarioBase(BaseModel):
    """Modelo base de usuario"""
    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre del usuario")
    apellido: str = Field(..., min_length=2, max_length=100, description="Apellido del usuario")
    email: EmailStr = Field(..., description="Correo electrónico corporativo")
    numero_empleado: str = Field(..., min_length=3, max_length=50, description="Número de empleado único")
    
    @property
    def nombre_completo(self) -> str:
        """Nombre completo del usuario"""
        return f"{self.nombre} {self.apellido}"
    
    def nombres_similares(self, otro_nombre: str) -> bool:
        """Verificar si otro nombre es similar al actual"""
        palabras_actuales = set(self.nombre_completo.lower().split())
        palabras_comparar = set(otro_nombre.lower().split())
        return bool(palabras_actuales & palabras_comparar)

class UsuarioCreate(UsuarioBase):
    """Modelo para crear nuevo usuario"""
    rol: RolUsuario = RolUsuario.EMPLEADO
    departamento: Optional[str] = Field(None, max_length=100, description="Departamento del usuario")

class UsuarioUpdate(BaseModel):
    """Modelo para actualizar usuario"""
    nombre: Optional[str] = Field(None, min_length=2, max_length=100)
    apellido: Optional[str] = Field(None, min_length=2, max_length=100)
    email: Optional[EmailStr] = None
    departamento: Optional[str] = Field(None, max_length=100)
    estado: Optional[EstadoUsuario] = None

class UsuarioDB(UsuarioBase):
    """Modelo de usuario en base de datos"""
    id: int = Field(..., description="ID único del usuario")
    rol: RolUsuario = RolUsuario.EMPLEADO
    departamento: Optional[str] = None
    estado: EstadoUsuario = EstadoUsuario.ACTIVO
    fecha_creacion: datetime = Field(default_factory=datetime.now)
    fecha_actualizacion: Optional[datetime] = None
    ultimo_acceso: Optional[datetime] = None
    
    class Config:
        from_attributes = True

class UsuarioExtracted(BaseModel):
    """Modelo para datos extraídos de mensajes"""
    nombre: Optional[str] = Field(None, description="Nombre extraído del mensaje")
    email: Optional[str] = Field(None, description="Email extraído del mensaje")
    confianza_nombre: float = Field(0.0, ge=0.0, le=1.0, description="Confianza en el nombre extraído")
    confianza_email: float = Field(0.0, ge=0.0, le=1.0, description="Confianza en el email extraído")
