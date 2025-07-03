# =====================================================
# nodes/nodes_utils.py - Utilidades comunes para nodos
# =====================================================
"""
Utilidades comunes para todos los nodos del workflow.

FUNCIONES:
- Decorators para nodos
- Validaciones comunes
- Formateo de texto
- Extracción de información
"""

import re
import logging
import functools
from typing import Callable, Any, Dict, List, Optional
from langchain_core.messages import AIMessage
from langgraph.types import Command
from datetime import datetime

def node_wrapper(func: Callable) -> Callable:
    """
    Decorator para convertir funciones async en nodos de LangGraph con manejo de errores.
    
    Args:
        func: Función del nodo a decorar
        
    Returns:
        Función decorada con manejo de errores
    
    Usage:
        @node_wrapper
        async def mi_nodo_func(state):
            # lógica del nodo
            return Command(update={...})
    """
    @functools.wraps(func)
    async def wrapper(state: Dict[str, Any]) -> Command:
        logger = logging.getLogger(f"NodeWrapper.{func.__name__}")
        
        try:
            # Ejecutar función original
            result = await func(state)
            
            # Verificar que devuelve Command
            if not isinstance(result, Command):
                logger.warning(f"⚠️ {func.__name__} no devolvió Command")
                return Command(update={
                    "error": True,
                    "error_message": f"Error interno en {func.__name__}",
                    "current_node": func.__name__,
                    "last_activity": datetime.now()
                })
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Error en {func.__name__}: {e}")
            
            error_response = {
                "error": True,
                "error_message": str(e),
                "current_node": func.__name__,
                "last_activity": datetime.now(),
                "escalation_needed": True,
                "escalation_reason": f"Error técnico en {func.__name__}: {str(e)}",
                "messages": [AIMessage(content="Ha ocurrido un error técnico. Te derivo a soporte.")]
            }
            
            return Command(update=error_response)
    
    return wrapper

def validate_email_format(email: str) -> bool:
    """
    Validar formato básico de email.
    
    Args:
        email: Email a validar
        
    Returns:
        True si el formato es válido
    """
    if not email or not isinstance(email, str):
        return False
    
    email = email.strip()
    
    # Patrón básico de email
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_eroski_email(email: str) -> bool:
    """
    Validar email corporativo de Eroski.
    
    Args:
        email: Email a validar
        
    Returns:
        True si es un email válido de Eroski
    """
    if not validate_email_format(email):
        return False
    
    # Verificar dominio Eroski
    return email.strip().lower().endswith('@eroski.es')

def validate_name_format(name: str) -> bool:
    """
    Validar formato básico de nombre.
    
    Args:
        name: Nombre a validar
        
    Returns:
        True si el formato es válido
    """
    if not name or not isinstance(name, str):
        return False
    
    name = name.strip()
    
    # Longitud mínima
    if len(name) < 2:
        return False
    
    # Permitir letras, espacios, acentos y caracteres especiales de nombres
    pattern = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\-\'\.]+$'
    return bool(re.match(pattern, name))

def names_are_similar(name1: str, name2: str, threshold: float = 0.6) -> bool:
    """
    Comparar si dos nombres son similares.
    
    Args:
        name1: Primer nombre
        name2: Segundo nombre
        threshold: Umbral de similitud (0.0 a 1.0)
        
    Returns:
        True si los nombres son similares
    """
    if not name1 or not name2:
        return False
    
    # Normalizar nombres
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)
    
    # Comparación exacta
    if n1 == n2:
        return True
    
    # Comparación por palabras
    words1 = set(n1.split())
    words2 = set(n2.split())
    
    if not words1 or not words2:
        return False
    
    # Calcular similitud Jaccard
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    similarity = intersection / union if union > 0 else 0
    return similarity >= threshold

def normalize_name(name: str) -> str:
    """
    Normalizar nombre para comparación.
    
    Args:
        name: Nombre a normalizar
        
    Returns:
        Nombre normalizado
    """
    if not name:
        return ""
    
    # Convertir a minúsculas y quitar espacios extra
    normalized = re.sub(r'\s+', ' ', name.strip().lower())
    
    # Quitar acentos básicos
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'ñ': 'n', 'ü': 'u'
    }
    
    for accented, plain in replacements.items():
        normalized = normalized.replace(accented, plain)
    
    return normalized

def extract_serial_number(text: str) -> Optional[str]:
    """
    Extraer número de serie del texto.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Número de serie si se encuentra
    """
    if not text:
        return None
    
    patterns = [
        r'serie[:\s]+([A-Z0-9]{6,})',
        r'número[:\s]+([A-Z0-9]{6,})',
        r'sn[:\s]+([A-Z0-9]{6,})',
        r'serial[:\s]+([A-Z0-9]{6,})',
        r'ns[:\s]+([A-Z0-9]{6,})',
        r'#[:\s]*([A-Z0-9]{6,})'
    ]
    
    text_upper = text.upper()
    
    for pattern in patterns:
        match = re.search(pattern, text_upper)
        if match:
            return match.group(1)
    
    return None

def extract_error_codes(text: str) -> List[str]:
    """
    Extraer códigos de error del texto.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Lista de códigos de error encontrados
    """
    if not text:
        return []
    
    patterns = [
        r'error[:\s]+([A-Z0-9]{3,})',
        r'código[:\s]+([A-Z0-9]{3,})',
        r'code[:\s]+([A-Z0-9]{3,})',
        r'err[:\s]+([A-Z0-9]{3,})'
    ]
    
    text_upper = text.upper()
    error_codes = []
    
    for pattern in patterns:
        matches = re.findall(pattern, text_upper)
        error_codes.extend(matches)
    
    return list(set(error_codes))  # Eliminar duplicados

def extract_equipment_info(text: str) -> Dict[str, Any]:
    """
    Extraer información de equipos del texto.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Diccionario con información de equipos
    """
    equipment_info = {}
    
    # Tipos de equipos comunes
    equipment_types = [
        'tpv', 'terminal', 'impresora', 'scanner', 'báscula', 'ordenador',
        'caja registradora', 'dataphone', 'código de barras', 'etiquetadora'
    ]
    
    text_lower = text.lower()
    
    # Buscar tipos de equipos
    for equipment in equipment_types:
        if equipment in text_lower:
            equipment_info['type'] = equipment
            break
    
    # Buscar números de serie
    serial = extract_serial_number(text)
    if serial:
        equipment_info['serial'] = serial
    
    # Buscar códigos de error
    error_codes = extract_error_codes(text)
    if error_codes:
        equipment_info['error_codes'] = error_codes
    
    return equipment_info

def extract_location_info(text: str) -> Optional[str]:
    """
    Extraer información de ubicación del texto.
    
    Args:
        text: Texto a analizar
        
    Returns:
        Ubicación si se encuentra
    """
    # Secciones típicas de Eroski
    sections = [
        'cajas', 'carnicería', 'pescadería', 'charcutería', 'panadería',
        'frutería', 'perfumería', 'electrodomésticos', 'textil', 'librería',
        'cafetería', 'gasolinera', 'parking', 'almacén', 'oficina', 'seguridad'
    ]
    
    text_lower = text.lower()
    
    for section in sections:
        if section in text_lower:
            return section.title()
    
    return None

def format_time_elapsed(start_time: datetime) -> str:
    """
    Formatear tiempo transcurrido desde una fecha.
    
    Args:
        start_time: Fecha de inicio
        
    Returns:
        Tiempo formateado
    """
    if not start_time:
        return "N/A"
    
    elapsed = datetime.now() - start_time
    total_seconds = elapsed.total_seconds()
    
    if total_seconds < 60:
        return f"{int(total_seconds)} segundos"
    elif total_seconds < 3600:
        minutes = int(total_seconds / 60)
        return f"{minutes} minutos"
    else:
        hours = int(total_seconds / 3600)
        minutes = int((total_seconds % 3600) / 60)
        return f"{hours}h {minutes}m"

def clean_text(text: str) -> str:
    """
    Limpiar texto de caracteres especiales.
    
    Args:
        text: Texto a limpiar
        
    Returns:
        Texto limpio
    """
    if not text:
        return ""
    
    # Quitar múltiples espacios
    text = re.sub(r'\s+', ' ', text.strip())
    
    # Quitar caracteres especiales problemáticos
    text = re.sub(r'[^\w\s\-\.,:;!?¿¡áéíóúÁÉÍÓÚñÑüÜ]', '', text)
    
    return text

def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncar texto a longitud máxima.
    
    Args:
        text: Texto a truncar
        max_length: Longitud máxima
        
    Returns:
        Texto truncado
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    return text[:max_length-3] + "..."

def validate_store_code(store_code: str) -> bool:
    """
    Validar código de tienda.
    
    Args:
        store_code: Código a validar
        
    Returns:
        True si es válido
    """
    if not store_code or not isinstance(store_code, str):
        return False
    
    # Formato típico: 3 dígitos
    pattern = r'^\d{3}$'
    return bool(re.match(pattern, store_code.strip()))

def generate_ticket_number(store_code: str = "000") -> str:
    """
    Generar número de ticket único.
    
    Args:
        store_code: Código de tienda
        
    Returns:
        Número de ticket
    """
    import uuid
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = str(uuid.uuid4())[:4].upper()
    
    return f"ERK-{store_code}-{timestamp}-{random_suffix}"