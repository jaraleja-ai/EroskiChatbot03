# =====================================================
# nodes/base_node.py - HÍBRIDO ACTUALIZADO: LangGraph + Actor Pattern
# =====================================================
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
import logging
from datetime import datetime
import asyncio

from config.settings import get_settings

class ActorDecision:
    """Decisiones que puede tomar un actor"""
    CONTINUE = "continue"
    COMPLETE = "complete" 
    NEED_INPUT = "need_input"
    ESCALATE = "escalate"
    DELEGATE = "delegate"

class BaseNode(ABC):
    """
    ✨ HÍBRIDO ACTUALIZADO: Nodo base que combina LangGraph con principios de Actor Pattern
    
    NUEVAS FUNCIONALIDADES:
    - ✅ get_state_diff para optimizar Command.update
    - ✅ create_optimized_command para usar solo diferencias
    - ✅ Interrupciones centralizadas en recopilar_input_usuario
    
    PRINCIPIOS ACTOR:
    - ✅ Autonomía: Cada nodo toma sus propias decisiones
    - ✅ Encapsulación: Estado interno del nodo protegido
    - ✅ Señalización: Comunica intenciones claramente al router
    - ✅ Responsabilidad única: Cada nodo tiene una función específica
    
    COMPATIBILIDAD LANGGRAPH:
    - ✅ Usa Command para actualizaciones de estado
    - ✅ Compatible con el sistema de routing existente
    - ✅ Mantiene el flujo de ejecución de LangGraph
    """
    
    def __init__(self, name: str, timeout_seconds: Optional[int] = None):
        self.name = name
        self.logger = logging.getLogger(f"Actor.{name}")
        self.settings = get_settings()
        self.timeout_seconds = timeout_seconds or 30
        
        # 🎭 ESTADO INTERNO DEL ACTOR (encapsulado)
        self._actor_state = {
            "execution_count": 0,
            "error_count": 0,
            "last_execution_time": None,
            "is_processing": False,
            "decision_history": []
        }
        
        self.logger.debug(f"🎭 Actor {name} inicializado")
    
    # =====================================================
    # NUEVOS MÉTODOS PARA OPTIMIZACIÓN DEL ESTADO
    # =====================================================
    
    def get_state_diff(self, old_state: Dict[str, Any], new_state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calcular diferencias entre estados para optimizar Command.update
        
        Args:
            old_state: Estado anterior
            new_state: Estado nuevo
            
        Returns:
            Diccionario con solo las claves que cambiaron
        """
        diff = {}
        
        # Detectar cambios en valores existentes
        for key, new_value in new_state.items():
            old_value = old_state.get(key)
            
            # Comparación especial para listas (como messages)
            if isinstance(new_value, list) and isinstance(old_value, list):
                if len(new_value) != len(old_value) or new_value != old_value:
                    diff[key] = new_value
            # Comparación especial para diccionarios anidados
            elif isinstance(new_value, dict) and isinstance(old_value, dict):
                if new_value != old_value:
                    diff[key] = new_value
            # Comparación normal para otros tipos
            elif old_value != new_value:
                diff[key] = new_value
        
        # Detectar nuevas claves que no existían antes
        for key in new_state:
            if key not in old_state:
                diff[key] = new_state[key]
        
        self.logger.debug(f"🔄 Estado diff calculado: {len(diff)} cambios de {len(new_state)} campos totales")
        if len(diff) < 10:  # Solo mostrar diffs pequeños para evitar spam
            self.logger.debug(f"🔄 Cambios: {list(diff.keys())}")
        
        return diff

    def create_optimized_command(self, old_state: Dict[str, Any], new_updates: Dict[str, Any]) -> Command:
        """
        Crear Command optimizado usando solo diferencias del estado
        
        Args:
            old_state: Estado anterior
            new_updates: Nuevas actualizaciones a aplicar
            
        Returns:
            Command con actualizaciones optimizadas
        """
        # Crear estado temporal con las actualizaciones
        temp_state = {**old_state, **new_updates}
        
        # Calcular solo las diferencias
        diff = self.get_state_diff(old_state, temp_state)
        
        self.logger.debug(f"⚡ Command optimizado: {len(diff)} campos vs {len(temp_state)} totales")
        
        return Command(update=diff)

    def create_message_update(self, message_content: str, additional_updates: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Helper para crear actualizaciones que incluyen mensajes
        
        Args:
            message_content: Contenido del mensaje a agregar
            additional_updates: Actualizaciones adicionales del estado
            
        Returns:
            Diccionario con las actualizaciones
        """
        updates = {
            "messages": [AIMessage(content=message_content)]
        }
        
        if additional_updates:
            updates.update(additional_updates)
        
        return updates
    
    # =====================================================
    # INTERFAZ LANGGRAPH (obligatoria)
    # =====================================================
    
    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> Command:
        """
        Punto de entrada desde LangGraph - DEBE ser implementado.
        
        Este método debe:
        1. Analizar el estado recibido
        2. Tomar decisiones autónomas
        3. Usar create_optimized_command para optimizar actualizaciones
        4. Señalar intenciones al router (NO interrumpir directamente)
        
        Returns:
            Command con actualizaciones optimizadas del estado
        """
        pass
    
    async def execute_with_monitoring(self, state: Dict[str, Any]) -> Command:
        """
        ⚡ WRAPPER: Ejecutar con monitoreo y métricas del actor
        """
        start_time = datetime.now()
        self._actor_state["is_processing"] = True
        self._actor_state["execution_count"] += 1
        
        try:
            self.logger.info(f"🎭 {self.name} iniciando ejecución #{self._actor_state['execution_count']}")
            
            # Ejecutar lógica del actor
            result = await asyncio.wait_for(self.execute(state), timeout=self.timeout_seconds)
            
            # Registrar decisión
            if hasattr(result, 'update') and result.update:
                decision = result.update.get("_actor_decision", "continue")
                self._actor_state["decision_history"].append({
                    "timestamp": start_time.isoformat(),
                    "decision": decision,
                    "execution_time_ms": (datetime.now() - start_time).total_seconds() * 1000
                })
            
            self.logger.info(f"✅ {self.name} completado en {(datetime.now() - start_time).total_seconds():.2f}s")
            return result
            
        except asyncio.TimeoutError:
            self.logger.error(f"⏰ {self.name} timeout después de {self.timeout_seconds}s")
            self._actor_state["error_count"] += 1
            return await self.handle_timeout(state)
            
        except Exception as e:
            self.logger.error(f"❌ {self.name} error: {e}")
            self._actor_state["error_count"] += 1
            return await self.handle_error(e, state)
            
        finally:
            self._actor_state["is_processing"] = False
            self._actor_state["last_execution_time"] = start_time.isoformat()
    
    # =====================================================
    # SEÑALIZACIÓN HÍBRIDA ACTUALIZADA
    # =====================================================
    
    def signal_need_input(
        self,
        state: Dict[str, Any], 
        request_message: str, 
        context: Dict[str, Any] = None,
        resume_node: str = None
    ) -> Command:
        """
        ✅ HÍBRIDO ACTUALIZADO: Señalar que se necesita input del usuario
        
        YA NO interrumpe directamente, solo señala al router que dirija 
        a recopilar_input_usuario donde se manejará la interrupción.
        """
        
        context = context or {}
        resume_node = resume_node or self.name
        
        old_state = state.copy()
        new_updates = {
            "_actor_decision": "need_input",
            "_request_message": request_message,
            "_input_context": {
                **context,
                "requesting_node": self.name,
                "resume_node": resume_node,
                "timestamp": datetime.now().isoformat()
            },
            "requires_user_input": True,
            "_next_actor": "recopilar_input_usuario"  # Señal explícita al router
        }
        
        self.logger.info(f"📥 {self.name} solicita input del usuario → router → recopilar_input_usuario")
        
        # Usar get_state_diff para optimizar
        return self.create_optimized_command(old_state, new_updates)
    
    def signal_completion(
        self,
        state: Dict[str, Any],
        next_actor: str,
        completion_message: str = None,
        **additional_updates
    ) -> Command:
        """
        ✅ HÍBRIDO: Señalar que el actor ha completado su trabajo
        """
        
        old_state = state.copy()
        new_updates = {
            "_actor_decision": "complete",
            "_next_actor": next_actor,
            **additional_updates
        }
        
        if completion_message:
            new_updates["messages"] = [AIMessage(content=completion_message)]
        
        self.logger.info(f"✅ {self.name} completado → {next_actor}")
        
        return self.create_optimized_command(old_state, new_updates)
    
    def signal_escalation(
        self,
        state: Dict[str, Any],
        reason: str,
        **additional_context
    ) -> Command:
        """
        ✅ HÍBRIDO: Señalar escalación a supervisor
        """
        
        old_state = state.copy()
        new_updates = {
            "_actor_decision": "escalate",
            "_next_actor": "escalar_supervisor",
            "escalar_a_supervisor": True,
            "motivo_escalacion": reason,
            "contexto_escalacion": {
                "actor_origen": self.name,
                "timestamp": datetime.now().isoformat(),
                **additional_context
            }
        }
        
        self.logger.warning(f"🔼 {self.name} escalando: {reason}")
        
        return self.create_optimized_command(old_state, new_updates)
    
    # =====================================================
    # UTILIDADES PARA NODOS
    # =====================================================
    
    def get_last_user_message(self, state: Dict[str, Any]) -> str:
        """Obtener el último mensaje del usuario"""
        messages = state.get("messages", [])
        for message in reversed(messages):
            if isinstance(message, HumanMessage):
                return message.content
        return ""
    
    def increment_attempts(self, state: Dict[str, Any], field_name: str) -> int:
        """Incrementar contador de intentos de forma segura"""
        current = state.get(field_name, 0)
        return current + 1
    
    def is_retry_limit_exceeded(self, state: Dict[str, Any], field_name: str, max_attempts: int = 3) -> bool:
        """Verificar si se excedió el límite de reintentos"""
        attempts = state.get(field_name, 0)
        return attempts >= max_attempts
    
    # =====================================================
    # MANEJO DE ERRORES
    # =====================================================
    
    async def handle_timeout(self, state: Dict[str, Any]) -> Command:
        """Manejar timeout del actor"""
        error_message = f"⏰ {self.name} necesita más tiempo. ¿Podrías esperar un momento?"
        
        old_state = state.copy()
        new_updates = self.create_message_update(error_message, {
            "_actor_decision": "escalate",
            "_next_actor": "escalar_supervisor",
            "escalar_a_supervisor": True,
            "motivo_escalacion": f"timeout_en_{self.name}"
        })
        
        return self.create_optimized_command(old_state, new_updates)
    
    async def handle_error(self, error: Exception, state: Dict[str, Any]) -> Command:
        """Manejar errores del actor"""
        error_message = f"❌ Ocurrió un problema en {self.name}. Escalando a supervisor."
        
        old_state = state.copy()
        new_updates = self.create_message_update(error_message, {
            "_actor_decision": "escalate",
            "_next_actor": "escalar_supervisor",
            "escalar_a_supervisor": True,
            "motivo_escalacion": f"error_en_{self.name}",
            "detalle_error": str(error)
        })
        
        return self.create_optimized_command(old_state, new_updates)
    
    # =====================================================
    # MÉTRICAS Y DEBUGGING
    # =====================================================
    
    def get_execution_metrics(self) -> Dict[str, Any]:
        """Obtener métricas de ejecución del actor"""
        return {
            "actor_name": self.name,
            "execution_count": self._actor_state["execution_count"],
            "error_count": self._actor_state["error_count"],
            "last_execution_time": self._actor_state["last_execution_time"],
            "is_processing": self._actor_state["is_processing"],
            "recent_decisions": self._actor_state["decision_history"][-5:]  # Últimas 5 decisiones
        }
    
    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """Campos requeridos en el estado para este actor"""
        pass
    
    @abstractmethod  
    def get_node_description(self) -> str:
        """Descripción de la funcionalidad del nodo"""
        pass