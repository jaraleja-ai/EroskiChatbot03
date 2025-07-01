
# =====================================================
# nodes/node_utils.py - Utilidades comunes para nodos
# =====================================================
from typing import Callable, Any, Dict
from langgraph.types import Command
import functools

def node_wrapper(func: Callable) -> Callable:
    """
    Decorator para convertir funciones async en nodos de LangGraph.
    
    Usage:
        @node_wrapper
        async def mi_nodo_func(state):
            # lógica del nodo
            return Command(update={...})
    """
    @functools.wraps(func)
    async def wrapper(state: Dict[str, Any]) -> Command:
        # Aquí podrías agregar lógica común para todos los nodos
        return await func(state)
    
    return wrapper

def validate_email_format(email: str) -> bool:
    """Validar formato básico de email"""
    import re
    if not email or not isinstance(email, str):
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))

def validate_name_format(name: str) -> bool:
    """Validar formato básico de nombre"""
    import re
    if not name or not isinstance(name, str):
        return False
    
    name = name.strip()
    if len(name) < 2:
        return False
    
    # Permitir letras, espacios, acentos y caracteres especiales de nombres
    pattern = r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\-\'\.]+$'
    return bool(re.match(pattern, name))

def names_are_similar(name1: str, name2: str) -> bool:
    """Comparar si dos nombres son similares"""
    if not name1 or not name2:
        return False
    
    # Normalizar nombres
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()
    
    # Comparación exacta
    if n1 == n2:
        return True
    
    # Comparación por palabras
    words1 = set(n1.split())
    words2 = set(n2.split())
    
    # Si hay intersección significativa
    return bool(words1 & words2)