# =====================================================
# utils/extractors/__init__.py - Exportaciones
# =====================================================
from .user_extractor import extraer_datos_usuario, UsuarioExtraido
from .incident_extractor import extraer_tipo_incidencia, extraer_detalles_incidencia, IncidenciaExtraida

__all__ = [
    "extraer_datos_usuario",
    "UsuarioExtraido", 
    "extraer_tipo_incidencia",
    "extraer_detalles_incidencia",
    "IncidenciaExtraida"
]