# =====================================================
# Estrategia para detectar primera visita a un nodo
# =====================================================

from typing import Dict, Any, List
from models.eroski_state import EroskiState
from langgraph.types import Command
import logging
from datetime import datetime
from langchain_core.messages import AIMessage

class NodeVisitManager:
    """Gestor para manejar lógica de primera visita vs revisita"""
    
    @staticmethod
    def is_first_visit(state: EroskiState, node_name: str) -> bool:
        """
        Verificar si es la primera vez que se visita un nodo.
        
        Args:
            state: Estado actual
            node_name: Nombre del nodo a verificar
            
        Returns:
            True si es primera visita, False si es revisita
        """
        execution_path = state.get("execution_path", [])
        return node_name not in execution_path
    
    @staticmethod
    def get_visit_count(state: EroskiState, node_name: str) -> int:
        """
        Contar cuántas veces se ha visitado un nodo.
        
        Args:
            state: Estado actual
            node_name: Nombre del nodo
            
        Returns:
            Número de veces visitado
        """
        execution_path = state.get("execution_path", [])
        return execution_path.count(node_name)
    
    @staticmethod
    def update_execution_path(state: EroskiState, node_name: str) -> Dict[str, Any]:
        """
        Actualizar execution_path con la visita actual.
        
        Args:
            state: Estado actual
            node_name: Nodo que se está visitando
            
        Returns:
            Diccionario con execution_path actualizado
        """
        current_path = state.get("execution_path", [])
        return {
            "execution_path": current_path + [node_name],
            "last_activity": datetime.now()
        }

# =====================================================
# Ejemplo de implementación en un nodo
# =====================================================

class ExampleNode:
    """Ejemplo de nodo con lógica de primera visita vs revisita"""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Node.{name}")
    
    async def execute(self, state: EroskiState) -> Command:
        """Ejecutar nodo con lógica de primera visita"""
        
        # 🔍 DETECTAR TIPO DE VISITA
        is_first_time = NodeVisitManager.is_first_visit(state, self.name)
        visit_count = NodeVisitManager.get_visit_count(state, self.name)
        
        self.logger.info(f"🔄 Nodo {self.name} - Primera vez: {is_first_time}, Visitas: {visit_count}")
        
        # 🎯 LÓGICA DIFERENCIADA
        if is_first_time:
            return await self._handle_first_visit(state)
        else:
            return await self._handle_revisit(state, visit_count)
    
    async def _handle_first_visit(self, state: EroskiState) -> Command:
        """Manejar primera visita al nodo"""
        self.logger.info(f"🆕 Primera visita a {self.name}")
        
        # Lógica específica para primera vez
        message = f"¡Bienvenido al {self.name}! Esta es tu primera visita."
        
        # Actualizar estado con visita
        update_data = NodeVisitManager.update_execution_path(state, self.name)
        update_data.update({
            "current_node": self.name,
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "attempts": 0  # Reset intentos en primera visita
        })
        
        return Command(update=update_data)
    
    async def _handle_revisit(self, state: EroskiState, visit_count: int) -> Command:
        """Manejar revisita al nodo"""
        self.logger.info(f"🔄 Revisita #{visit_count} a {self.name}")
        
        # Lógica específica para revisitas
        if visit_count == 2:
            message = f"Veo que has vuelto a {self.name}. ¿Necesitas aclarar algo?"
        elif visit_count >= 3:
            message = f"Has visitado {self.name} {visit_count} veces. ¿Te ayudo de otra manera?"
        else:
            message = f"Has regresado a {self.name}."
        
        # Actualizar estado con revisita
        update_data = NodeVisitManager.update_execution_path(state, self.name)
        update_data.update({
            "current_node": self.name,
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "attempts": state.get("attempts", 0) + 1  # Incrementar intentos en revisita
        })
        
        return Command(update=update_data)

# =====================================================
# Implementación específica para nodo de autenticación
# =====================================================

class AuthenticateNodeWithVisitLogic:
    """Nodo de autenticación con lógica de primera visita"""
    
    def __init__(self):
        self.name = "authenticate"
        self.logger = logging.getLogger(f"Node.{self.name}")
    
    async def execute(self, state: EroskiState) -> Command:
        """Ejecutar autenticación con lógica de visita"""
        
        # Verificar si ya está autenticado
        if self._is_already_authenticated(state):
            return self._continue_authenticated_user(state)
        
        # Detectar tipo de visita
        is_first_time = NodeVisitManager.is_first_visit(state, self.name)
        
        if is_first_time:
            return await self._handle_first_authentication_attempt(state)
        else:
            return await self._handle_retry_authentication(state)
    
    async def _handle_first_authentication_attempt(self, state: EroskiState) -> Command:
        """Primera vez pidiendo autenticación"""
        self.logger.info("🆕 Primera solicitud de autenticación")
        
        welcome_message = """¡Hola! Soy el asistente de incidencias de Eroski 🤖

Para ayudarte, necesito identificarte.

Por favor, proporciona:
📧 **Tu email corporativo** (debe terminar en @eroski.es)
🏪 **Nombre de tu tienda** (ej: "Eroski Bilbao Centro")

**Ejemplo:** "Mi email es juan.perez@eroski.es y trabajo en Eroski Madrid Sur"
"""
        
        update_data = NodeVisitManager.update_execution_path(state, self.name)
        update_data.update({
            "current_node": self.name,
            "messages": state.get("messages", []) + [AIMessage(content=welcome_message)],
            "awaiting_user_input": True,
            "attempts": 1,
            "authentication_stage": "initial_request"
        })
        
        return Command(update=update_data)
    
    async def _handle_retry_authentication(self, state: EroskiState) -> Command:
        """Reintentar autenticación después de error"""
        visit_count = NodeVisitManager.get_visit_count(state, self.name)
        attempts = state.get("attempts", 0)
        
        self.logger.info(f"🔄 Reintento de autenticación - Visita #{visit_count}, Intento #{attempts + 1}")
        
        # Verificar límite de intentos
        if attempts >= 3:
            return self._escalate_authentication_failure(state)
        
        retry_message = f"""No he podido verificar tu identidad (intento {attempts + 1}/3).

Por favor, verifica que incluyes:
📧 **Email corporativo completo** (debe terminar en @eroski.es)
🏪 **Nombre exacto de tu tienda**

¿Puedes intentar de nuevo?"""
        
        update_data = NodeVisitManager.update_execution_path(state, self.name)
        update_data.update({
            "current_node": self.name,
            "messages": state.get("messages", []) + [AIMessage(content=retry_message)],
            "awaiting_user_input": True,
            "attempts": attempts + 1,
            "authentication_stage": "retry"
        })
        
        return Command(update=update_data)
    
    def _is_already_authenticated(self, state: EroskiState) -> bool:
        """Verificar si ya está autenticado"""
        return bool(
            state.get("employee_email") and 
            state.get("store_id") and 
            state.get("authenticated")
        )
    
    def _continue_authenticated_user(self, state: EroskiState) -> Command:
        """Continuar con usuario autenticado"""
        employee_name = state.get("employee_name", "")
        self.logger.info(f"✅ Usuario ya autenticado: {employee_name}")
        
        # No actualizar execution_path si ya está autenticado
        return Command(update={
            "current_node": self.name,
            "last_activity": datetime.now()
        })
    
    def _escalate_authentication_failure(self, state: EroskiState) -> Command:
        """Escalar por fallos repetidos de autenticación"""
        escalation_message = """🔼 **Derivando a soporte**

No he podido verificar tu identidad después de varios intentos.

📞 **Contacta directamente:**
• Soporte técnico: +34 946 211 000
• Email: soporte.tecnico@eroski.es

¡Gracias por tu paciencia! 🙏"""
        
        update_data = NodeVisitManager.update_execution_path(state, self.name)
        update_data.update({
            "escalation_needed": True,
            "escalation_reason": "Fallos repetidos de autenticación",
            "current_node": self.name,
            "messages": state.get("messages", []) + [AIMessage(content=escalation_message)],
            "awaiting_user_input": False,
            "authentication_stage": "escalated"
        })
        
        return Command(update=update_data)

# =====================================================
# Utilidades adicionales
# =====================================================

def get_node_visit_stats(state: EroskiState) -> Dict[str, int]:
    """
    Obtener estadísticas de visitas por nodo.
    
    Args:
        state: Estado actual
        
    Returns:
        Diccionario con conteo de visitas por nodo
    """
    execution_path = state.get("execution_path", [])
    stats = {}
    
    for node in execution_path:
        stats[node] = stats.get(node, 0) + 1
    
    return stats

def has_been_to_node_recently(state: EroskiState, node_name: str, last_n_steps: int = 3) -> bool:
    """
    Verificar si se ha visitado un nodo recientemente.
    
    Args:
        state: Estado actual
        node_name: Nodo a verificar
        last_n_steps: Últimos N pasos a considerar
        
    Returns:
        True si se visitó recientemente
    """
    execution_path = state.get("execution_path", [])
    recent_path = execution_path[-last_n_steps:] if len(execution_path) >= last_n_steps else execution_path
    return node_name in recent_path