# =====================================================
# utils/extractors/user_extractor.py - Extractor de datos de usuario CORREGIDO
# =====================================================
from pydantic import BaseModel, Field
from langchain.output_parsers import PydanticOutputParser
from langchain.prompts import PromptTemplate
from typing import Optional, Dict, Any
import logging

from utils.llm.providers import get_llm
from models.user import UsuarioExtracted

logger = logging.getLogger("Extractor.User")

class UsuarioExtraido(BaseModel):
    """Modelo para datos de usuario extraídos"""
    nombre: Optional[str] = Field(None, description="Nombre completo del usuario si se puede identificar")
    email: Optional[str] = Field(None, description="Correo electrónico del usuario si se menciona")
    numero_empleado: Optional[str] = Field(None, description="Número de empleado si se menciona")
    confianza_nombre: float = Field(0.0, description="Confianza en la extracción del nombre (0-1)")
    confianza_email: float = Field(0.0, description="Confianza en la extracción del email (0-1)")
    
    # ✅ MÉTODO .get() AGREGADO PARA COMPATIBILIDAD
    def get(self, key: str, default=None):
        """
        Método para acceso tipo diccionario.
        Permite usar objeto.get('campo', default) como un dict.
        
        Args:
            key: Nombre del atributo
            default: Valor por defecto si no existe
            
        Returns:
            Valor del atributo o default
        """
        try:
            return getattr(self, key, default)
        except AttributeError:
            return default
    
    # ✅ MÉTODO PARA CONVERSIÓN A DICT
    def to_dict(self) -> Dict[str, Any]:
        """Convertir a diccionario para facilitar acceso."""
        return {
            'nombre': self.nombre,
            'email': self.email,
            'numero_empleado': self.numero_empleado,
            'confianza_nombre': self.confianza_nombre,
            'confianza_email': self.confianza_email
        }
    
    # ✅ MÉTODO PARA VERIFICAR SI TIENE DATOS VÁLIDOS
    def has_valid_data(self, min_confidence: float = 0.5) -> bool:
        """
        Verificar si tiene datos válidos con confianza mínima.
        
        Args:
            min_confidence: Confianza mínima requerida
            
        Returns:
            True si tiene al menos un campo con confianza suficiente
        """
        return (
            (self.nombre and self.confianza_nombre >= min_confidence) or
            (self.email and self.confianza_email >= min_confidence)
        )
    
    # ✅ MÉTODO PARA OBTENER MEJOR DATO DISPONIBLE
    def get_best_identifier(self) -> Optional[str]:
        """
        Obtener el mejor identificador disponible.
        
        Returns:
            Email si existe, sino nombre, sino None
        """
        if self.email and self.confianza_email > 0.3:
            return self.email
        elif self.nombre and self.confianza_nombre > 0.3:
            return self.nombre
        else:
            return None

# Parser para convertir respuesta LLM a objeto Pydantic
parser = PydanticOutputParser(pydantic_object=UsuarioExtraido)

# Template del prompt para extracción
extraction_prompt = PromptTemplate(
    template="""
Analiza el siguiente mensaje del usuario y extrae la información personal si está presente.

Instrucciones:
- Extrae SOLO información explícitamente mencionada
- NO inventes o asumas información que no esté clara
- Asigna confianza alta (0.8-1.0) solo si la información es muy clara
- Asigna confianza media (0.5-0.7) si hay alguna ambigüedad  
- Asigna confianza baja (0.1-0.4) si la información es poco clara

Ejemplos de extracción:
- "Hola, soy Juan Pérez" → nombre: "Juan Pérez", confianza_nombre: 0.9
- "Mi email es juan@empresa.com" → email: "juan@empresa.com", confianza_email: 0.95
- "Creo que soy Juan" → nombre: "Juan", confianza_nombre: 0.3
- "juan en empresa punto com" → email: "juan@empresa.com", confianza_email: 0.6

Mensaje del usuario: {mensaje}

{format_instructions}
""",
    input_variables=["mensaje"],
    partial_variables={"format_instructions": parser.get_format_instructions()}
)

async def extraer_datos_usuario(mensaje: str) -> UsuarioExtraido:
    """
    Extraer datos de usuario de un mensaje usando LLM.
    
    Args:
        mensaje: Mensaje del usuario del cual extraer datos
        
    Returns:
        UsuarioExtraido con los datos encontrados y niveles de confianza
    """
    try:
        logger.debug(f"🔍 Extrayendo datos de: {mensaje[:50]}...")
        
        # Obtener LLM
        llm = get_llm()
        
        # Formatear prompt
        formatted_prompt = extraction_prompt.format(mensaje=mensaje)
        
        # Ejecutar extracción
        response = await llm.ainvoke(formatted_prompt)
        
        # Parsear respuesta
        extracted_data = parser.parse(response.content)
        
        logger.info(f"✅ Extracción completada - Nombre: {extracted_data.nombre} (conf: {extracted_data.confianza_nombre}), Email: {extracted_data.email} (conf: {extracted_data.confianza_email})")
        
        return extracted_data
        
    except Exception as e:
        logger.error(f"❌ Error en extracción de usuario: {e}")
        # Retornar objeto vacío en caso de error
        return UsuarioExtraido()