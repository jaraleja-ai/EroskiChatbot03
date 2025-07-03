# =====================================================
# models/incidencia.py - Modelos de Incidencia SIMPLIFICADOS
# =====================================================
"""
Modelos optimizados para gestión de incidencias.

PRINCIPIOS:
- Los tipos de incidencia se leen desde JSON (config/eroski_incidents.json)
- Solo guardamos strings en la BD, no enums fijos
- Validación flexible que se adapta a cambios en JSON
- Compatibilidad total con el sistema de configuración existente
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, validator
import uuid

# ========== ENUMS BÁSICOS (Solo para estados y prioridades) ==========

from enum import Enum

class PrioridadIncidencia(str, Enum):
    """Niveles de prioridad - estos sí son fijos"""
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"

class EstadoIncidencia(str, Enum):
    """Estados de la incidencia - estos sí son fijos"""
    ABIERTA = "abierta"
    EN_PROGRESO = "en_progreso"
    PENDIENTE_USUARIO = "pendiente_usuario"
    RESUELTA = "resuelta"
    CERRADA = "cerrada"
    ESCALADA = "escalada"

# ========== MODELOS BASE ==========

class IncidenciaBase(BaseModel):
    """Modelo base para incidencias"""
    # Tipo viene del JSON - almacenamos como string
    tipo: str = Field(..., description="Tipo de incidencia según config JSON")
    descripcion: str = Field(..., min_length=10, max_length=2000)
    prioridad: PrioridadIncidencia = PrioridadIncidencia.MEDIA
    
    # Campos específicos de Eroski
    codigo_tienda: Optional[str] = None
    nombre_tienda: Optional[str] = None
    nombre_seccion: Optional[str] = None
    numero_serie_equipo: Optional[str] = None  # Para balanzas, TPVs, etc.
    
    @validator('descripcion')
    def validate_descripcion(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('La descripción debe tener al menos 10 caracteres')
        return v.strip()
    
    @validator('tipo')
    def validate_tipo(cls, v):
        if not v or not v.strip():
            raise ValueError('El tipo de incidencia es obligatorio')
        return v.strip().lower()

class IncidenciaCreate(IncidenciaBase):
    """Modelo para crear nueva incidencia"""
    # Información del empleado que reporta
    empleado_id: Optional[int] = None  # Desde BD de empleados
    nombre_empleado: str = Field(..., description="Nombre completo del empleado")
    email_empleado: str = Field(..., description="Email corporativo")
    
    # Campos opcionales adicionales
    pasos_reproducir: Optional[str] = None
    impacto_operativo: Optional[str] = None
    ubicacion_exacta: Optional[str] = None  # "Caja 3", "Sección Frutería", etc.
    
    # Metadatos adicionales
    metadata: Optional[Dict[str, Any]] = {}

class IncidenciaUpdate(BaseModel):
    """Modelo para actualizar incidencia"""
    tipo: Optional[str] = None
    descripcion: Optional[str] = None
    prioridad: Optional[PrioridadIncidencia] = None
    estado: Optional[EstadoIncidencia] = None
    solucion_aplicada: Optional[str] = None
    notas_internas: Optional[str] = None
    numero_serie_equipo: Optional[str] = None

# ========== MODELO DE BASE DE DATOS ==========

class IncidenciaDB(IncidenciaBase):
    """
    Modelo completo de incidencia para la base de datos.
    
    Compatible con el esquema PostgreSQL definido para Eroski.
    """
    # Campos principales
    id: int
    empleado_id: Optional[int] = None
    numero_ticket: str
    estado: EstadoIncidencia = EstadoIncidencia.ABIERTA
    
    # Información del empleado (desnormalizada para consultas rápidas)
    nombre_empleado: str
    email_empleado: str
    
    # Campos de fechas
    fecha_creacion: datetime
    fecha_actualizacion: datetime
    fecha_resolucion: Optional[datetime] = None
    
    # Campos de resolución
    solucion_aplicada: Optional[str] = None
    tiempo_resolucion_minutos: Optional[int] = None
    
    # Tracking y métricas
    preguntas_realizadas: Optional[List[str]] = []
    respuestas_usuario: Optional[Dict[str, Any]] = {}
    intentos_resolucion: int = 0
    
    # Escalación
    escalado_a: Optional[str] = None
    notas_internas: Optional[str] = None
    
    # Campos específicos para Eroski
    ubicacion_exacta: Optional[str] = None
    
    class Config:
        from_attributes = True  # Para compatibilidad con SQLAlchemy/AsyncPG
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario para JSON"""
        data = self.dict()
        # Convertir enums a strings
        for key, value in data.items():
            if isinstance(value, Enum):
                data[key] = value.value
        return data
    
    @property
    def is_resolved(self) -> bool:
        """Verificar si la incidencia está resuelta"""
        return self.estado in [EstadoIncidencia.RESUELTA, EstadoIncidencia.CERRADA]
    
    @property
    def is_escalated(self) -> bool:
        """Verificar si la incidencia está escalada"""
        return self.estado == EstadoIncidencia.ESCALADA
    
    @property
    def tiempo_transcurrido_minutos(self) -> Optional[int]:
        """Calcular tiempo transcurrido desde creación"""
        if self.fecha_resolucion:
            delta = self.fecha_resolucion - self.fecha_creacion
        else:
            delta = datetime.now() - self.fecha_creacion
        return int(delta.total_seconds() / 60)
    
    def get_incident_config(self) -> Optional[Dict[str, Any]]:
        """
        Obtener configuración del tipo de incidencia desde JSON.
        
        Esta función importa el loader para evitar imports circulares.
        """
        try:
            from config.incident_config import IncidentConfigLoader
            loader = IncidentConfigLoader()
            incident_type = loader.get_incident_type(self.tipo)
            
            if incident_type:
                return {
                    "id": incident_type.id,
                    "name": incident_type.name,
                    "description": incident_type.description,
                    "urgency_level": incident_type.urgency_level,
                    "category": incident_type.category,
                    "requires_technical_support": incident_type.requires_technical_support,
                    "estimated_resolution_minutes": incident_type.estimated_resolution_minutes,
                    "common_issues": incident_type.common_issues,
                    "escalation_contacts": incident_type.escalation_contacts
                }
        except Exception:
            return None
        
        return None

# ========== MODELOS DE RESPUESTA ==========

class IncidenciaResponse(BaseModel):
    """Modelo de respuesta para APIs"""
    id: int
    numero_ticket: str
    tipo: str
    tipo_descripcion: Optional[str] = None  # Viene del JSON
    descripcion: str
    prioridad: str
    estado: str
    fecha_creacion: datetime
    tiempo_transcurrido_minutos: int
    
    # Información del empleado
    nombre_empleado: str
    codigo_tienda: Optional[str] = None
    nombre_tienda: Optional[str] = None
    
    @classmethod
    def from_db(cls, incidencia: IncidenciaDB) -> "IncidenciaResponse":
        """Crear desde modelo de BD"""
        # Obtener descripción del tipo desde JSON
        config = incidencia.get_incident_config()
        tipo_descripcion = config["name"] if config else None
        
        return cls(
            id=incidencia.id,
            numero_ticket=incidencia.numero_ticket,
            tipo=incidencia.tipo,
            tipo_descripcion=tipo_descripcion,
            descripcion=incidencia.descripcion,
            prioridad=incidencia.prioridad.value,
            estado=incidencia.estado.value,
            fecha_creacion=incidencia.fecha_creacion,
            tiempo_transcurrido_minutos=incidencia.tiempo_transcurrido_minutos or 0,
            nombre_empleado=incidencia.nombre_empleado,
            codigo_tienda=incidencia.codigo_tienda,
            nombre_tienda=incidencia.nombre_tienda
        )

class IncidenciaListResponse(BaseModel):
    """Modelo de respuesta para listas de incidencias"""
    incidencias: List[IncidenciaResponse]
    total: int
    pagina: int = 1
    por_pagina: int = 10

# ========== MODELOS PARA EXTRACCIÓN ==========

class IncidenciaExtracted(BaseModel):
    """Modelo para incidencia extraída por LLM"""
    tipo: str  # Viene del JSON, no enum fijo
    descripcion_original: str
    descripcion_procesada: str
    prioridad_sugerida: PrioridadIncidencia = PrioridadIncidencia.MEDIA
    palabras_clave: List[str] = []
    confianza: float = Field(ge=0.0, le=1.0, default=0.0)
    
    # Información adicional extraída
    equipo_afectado: Optional[str] = None
    numero_serie_detectado: Optional[str] = None
    ubicacion_detectada: Optional[str] = None
    
    def to_create_model(self, nombre_empleado: str, email_empleado: str) -> IncidenciaCreate:
        """Convertir a modelo de creación"""
        return IncidenciaCreate(
            tipo=self.tipo,
            descripcion=self.descripcion_procesada,
            prioridad=self.prioridad_sugerida,
            nombre_empleado=nombre_empleado,
            email_empleado=email_empleado,
            numero_serie_equipo=self.numero_serie_detectado,
            ubicacion_exacta=self.ubicacion_detectada,
            metadata={
                "descripcion_original": self.descripcion_original,
                "palabras_clave": self.palabras_clave,
                "confianza_clasificacion": self.confianza,
                "equipo_afectado": self.equipo_afectado
            }
        )

# ========== UTILIDADES ==========

def generate_ticket_number() -> str:
    """Generar número de ticket único con formato ERO-YYYYMMDD-XXXXXXXX"""
    timestamp = datetime.now().strftime("%Y%m%d")
    random_suffix = str(uuid.uuid4())[:8].upper()
    return f"ERO-{timestamp}-{random_suffix}"

def get_prioridad_color(prioridad: PrioridadIncidencia) -> str:
    """Obtener color para mostrar prioridad"""
    colors = {
        PrioridadIncidencia.BAJA: "🟢",
        PrioridadIncidencia.MEDIA: "🟡", 
        PrioridadIncidencia.ALTA: "🟠",
        PrioridadIncidencia.CRITICA: "🔴"
    }
    return colors.get(prioridad, "⚪")

def get_estado_emoji(estado: EstadoIncidencia) -> str:
    """Obtener emoji para estado"""
    emojis = {
        EstadoIncidencia.ABIERTA: "🆕",
        EstadoIncidencia.EN_PROGRESO: "⏳",
        EstadoIncidencia.PENDIENTE_USUARIO: "⏸️",
        EstadoIncidencia.RESUELTA: "✅",
        EstadoIncidencia.CERRADA: "🔒",
        EstadoIncidencia.ESCALADA: "⬆️"
    }
    return emojis.get(estado, "❓")

def validate_ticket_format(ticket: str) -> bool:
    """Validar formato de ticket ERO-YYYYMMDD-XXXXXXXX"""
    import re
    pattern = r'^ERO-\d{8}-[A-Z0-9]{8}$'
    return bool(re.match(pattern, ticket))

def get_incident_types_from_config() -> List[str]:
    """
    Obtener lista de tipos de incidencia válidos desde la configuración JSON.
    
    Returns:
        Lista de IDs de tipos de incidencia
    """
    try:
        from config.incident_config import IncidentConfigLoader
        loader = IncidentConfigLoader()
        return loader.get_incident_ids()
    except Exception:
        # Fallback en caso de error
        return ["general", "hardware", "software", "red"]

def validate_incident_type(tipo: str) -> bool:
    """
    Validar que un tipo de incidencia existe en la configuración JSON.
    
    Args:
        tipo: Tipo a validar
        
    Returns:
        True si el tipo es válido
    """
    valid_types = get_incident_types_from_config()
    return tipo.lower() in [t.lower() for t in valid_types]

def get_incident_urgency_from_config(tipo: str) -> int:
    """
    Obtener el nivel de urgencia de un tipo desde la configuración.
    
    Args:
        tipo: Tipo de incidencia
        
    Returns:
        Nivel de urgencia (1-4), 2 por defecto
    """
    try:
        from config.incident_config import IncidentConfigLoader
        loader = IncidentConfigLoader()
        incident_type = loader.get_incident_type(tipo)
        return incident_type.urgency_level if incident_type else 2
    except Exception:
        return 2

# ========== HELPERS PARA INTEGRACIÓN CON JSON CONFIG ==========

class IncidentTypeValidator:
    """
    Validador que funciona con el sistema de configuración JSON.
    """
    
    def __init__(self):
        self._loader = None
    
    @property
    def loader(self):
        """Lazy loading del configurador"""
        if self._loader is None:
            from config.incident_config import IncidentConfigLoader
            self._loader = IncidentConfigLoader()
        return self._loader
    
    def validate_type(self, tipo: str) -> bool:
        """Validar tipo contra configuración"""
        return self.loader.get_incident_type(tipo) is not None
    
    def get_type_info(self, tipo: str) -> Optional[Dict[str, Any]]:
        """Obtener información completa del tipo"""
        incident_type = self.loader.get_incident_type(tipo)
        if incident_type:
            return {
                "id": incident_type.id,
                "name": incident_type.name,
                "description": incident_type.description,
                "urgency_level": incident_type.urgency_level,
                "category": incident_type.category,
                "requires_technical_support": incident_type.requires_technical_support,
                "estimated_resolution_minutes": incident_type.estimated_resolution_minutes,
                "escalation_contacts": incident_type.escalation_contacts
            }
        return None
    
    def classify_incident(self, text: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Clasificar incidencia basada en texto"""
        return self.loader.search_by_keywords(text, limit)

# ========== EXPORTACIONES ==========

__all__ = [
    # Enums (solo los fijos)
    "PrioridadIncidencia",
    "EstadoIncidencia",
    
    # Modelos principales
    "IncidenciaBase",
    "IncidenciaCreate",
    "IncidenciaUpdate", 
    "IncidenciaDB",
    
    # Modelos de respuesta
    "IncidenciaResponse",
    "IncidenciaListResponse",
    
    # Modelos de extracción
    "IncidenciaExtracted",
    
    # Utilidades
    "generate_ticket_number",
    "get_prioridad_color",
    "get_estado_emoji",
    "validate_ticket_format",
    "get_incident_types_from_config",
    "validate_incident_type",
    "get_incident_urgency_from_config",
    
    # Validador integrado
    "IncidentTypeValidator"
]

# ========== COMPATIBILIDAD HACIA ATRÁS ==========

# Alias para mantener compatibilidad con código existente
TipoIncidencia = str  # Ya no es enum, solo string
CategoriaIncidencia = str  # Ya no es enum, solo string

# Crear instancia global del validador para uso fácil
incident_validator = IncidentTypeValidator()