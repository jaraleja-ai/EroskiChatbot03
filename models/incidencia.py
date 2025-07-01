# =====================================================
# models/incidencia.py - Modelos de incidencia
# =====================================================
from enum import Enum
from typing import List, Dict
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TipoIncidencia(str, Enum):
    """Tipos de incidencia técnica"""
    HARDWARE = "hardware"
    SOFTWARE = "software"
    RED = "red"
    ACCESO = "acceso"
    EMAIL = "email"
    IMPRESORA = "impresora"
    TELEFONIA = "telefonia"
    OTRO = "otro"

class PrioridadIncidencia(str, Enum):
    """Prioridades de incidencia"""
    BAJA = "baja"
    MEDIA = "media"
    ALTA = "alta"
    CRITICA = "critica"

class EstadoIncidencia(str, Enum):
    """Estados de incidencia"""
    ABIERTA = "abierta"
    EN_PROGRESO = "en_progreso"
    PENDIENTE_USUARIO = "pendiente_usuario"
    RESUELTA = "resuelta"
    CERRADA = "cerrada"
    ESCALADA = "escalada"

class CategoriaIncidencia(str, Enum):
    """Categorías más específicas de incidencia"""
    # Hardware
    COMPUTADORA_LENTA = "computadora_lenta"
    PANTALLA_PROBLEMAS = "pantalla_problemas"
    TECLADO_MOUSE = "teclado_mouse"
    
    # Software
    APLICACION_NO_ABRE = "aplicacion_no_abre"
    APLICACION_LENTA = "aplicacion_lenta"
    ERROR_SISTEMA = "error_sistema"
    
    # Red
    INTERNET_LENTO = "internet_lento"
    SIN_CONEXION = "sin_conexion"
    VPN_PROBLEMAS = "vpn_problemas"
    
    # Acceso
    OLVIDE_PASSWORD = "olvide_password"
    CUENTA_BLOQUEADA = "cuenta_bloqueada"
    PERMISOS_INSUFICIENTES = "permisos_insuficientes"

class IncidenciaBase(BaseModel):
    """Modelo base de incidencia"""
    tipo: TipoIncidencia = Field(..., description="Tipo principal de incidencia")
    categoria: Optional[CategoriaIncidencia] = Field(None, description="Categoría específica")
    descripcion: str = Field(..., min_length=10, max_length=1000, description="Descripción del problema")
    prioridad: PrioridadIncidencia = PrioridadIncidencia.MEDIA
    
    def get_preguntas_followup(self) -> List[str]:
        """Obtener preguntas de seguimiento según el tipo"""
        preguntas_por_tipo = {
            TipoIncidencia.HARDWARE: [
                "¿Hace cuánto tiempo empezó el problema?",
                "¿Escuchas algún ruido extraño en la computadora?",
                "¿Has instalado algo nuevo recientemente?"
            ],
            TipoIncidencia.SOFTWARE: [
                "¿Qué aplicación específica está causando problemas?",
                "¿Aparece algún mensaje de error? Si es así, ¿cuál?",
                "¿Has reiniciado la aplicación?"
            ],
            TipoIncidencia.RED: [
                "¿Puedes acceder a algunos sitios web pero no a otros?",
                "¿Otros dispositivos en tu ubicación tienen el mismo problema?",
                "¿Estás usando WiFi o conexión por cable?"
            ]
        }
        return preguntas_por_tipo.get(self.tipo, [
            "¿Puedes proporcionar más detalles sobre el problema?",
            "¿Cuándo ocurrió por primera vez?",
            "¿Has intentado alguna solución?"
        ])

class IncidenciaCreate(IncidenciaBase):
    """Modelo para crear nueva incidencia"""
    usuario_id: int = Field(..., description="ID del usuario que reporta")

class IncidenciaUpdate(BaseModel):
    """Modelo para actualizar incidencia"""
    estado: Optional[EstadoIncidencia] = None
    prioridad: Optional[PrioridadIncidencia] = None
    categoria: Optional[CategoriaIncidencia] = None
    notas_actualizacion: Optional[str] = Field(None, max_length=500)

class IncidenciaDB(IncidenciaBase):
    """Modelo de incidencia en base de datos"""
    id: int = Field(..., description="ID único de la incidencia")
    usuario_id: int = Field(..., description="ID del usuario")
    numero_ticket: str = Field(..., description="Número de ticket único")
    estado: EstadoIncidencia = EstadoIncidencia.ABIERTA
    fecha_creacion: datetime = Field(default_factory=datetime.now)
    fecha_actualizacion: Optional[datetime] = None
    fecha_resolucion: Optional[datetime] = None
    tiempo_resolucion_minutos: Optional[int] = None
    
    # Información adicional
    preguntas_realizadas: List[str] = Field(default_factory=list)
    respuestas_usuario: Dict[str, str] = Field(default_factory=dict)
    intentos_resolucion: int = Field(default=0)
    escalado_a: Optional[str] = Field(None, description="A quién se escaló")
    
    class Config:
        from_attributes = True
