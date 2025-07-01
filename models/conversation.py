from pydantic import BaseModel, Field, EmailStr
from typing import Optional
from datetime import datetime
from enum import Enum


# =====================================================
# models/conversation.py - Modelos de conversación
# =====================================================
class ConversationContext(BaseModel):
    """Contexto de la conversación"""
    sesion_id: str = Field(..., description="ID único de la sesión")
    usuario_id: Optional[int] = None
    incidencia_id: Optional[int] = None
    
    # Estado de la conversación
    etapa_actual: str = Field("identificacion_usuario", description="Etapa actual del flujo")
    intentos_realizados: int = Field(default=0)
    timestamp_inicio: datetime = Field(default_factory=datetime.now)
    timestamp_ultima_actividad: datetime = Field(default_factory=datetime.now)
    
    # Flags de estado
    usuario_identificado: bool = Field(default=False)
    incidencia_identificada: bool = Field(default=False)
    requiere_escalacion: bool = Field(default=False)
    
    # Metadatos adicionales
    canal_origen: str = Field(default="chainlit", description="Canal por donde llegó el usuario")
    idioma_preferido: str = Field(default="es", description="Idioma preferido del usuario")
    
    def actualizar_actividad(self):
        """Actualizar timestamp de última actividad"""
        self.timestamp_ultima_actividad = datetime.now()
    
    def tiempo_transcurrido_minutos(self) -> int:
        """Calcular tiempo transcurrido en minutos"""
        delta = datetime.now() - self.timestamp_inicio
        return int(delta.total_seconds() / 60)