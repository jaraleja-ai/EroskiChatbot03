# =====================================================
# nodes/__init__.py - Exportaciones del módulo
# =====================================================
from .base_node import BaseNode, NodeExecutionResult
from .nodes_utils import (node_wrapper, 
                          validate_email_format, 
                          validate_name_format, 
                          names_are_similar)

__all__ = [
    "BaseNode",
    "NodeExecutionResult", 
    "node_wrapper",
    "validate_email_format",
    "validate_name_format",
    "names_are_similar"
]