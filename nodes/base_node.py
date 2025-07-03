# =====================================================
# nodes/base_node.py - HÍBRIDO: LangGraph + Actor Pattern
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
    ✨ HÍBRIDO: Nodo base que combina LangGraph con principios de Actor Pattern
    
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
    
    @abstractmethod
    async def execute(self, state: Dict[str, Any]) -> Command:
        """
        Punto de entrada desde LangGraph - DEBE ser implementado.
        
        Este método debe:
        1. Analizar el estado recibido
        2. Tomar decisiones autónomas
        3. Retornar Command con señales claras para el router
        """
        pass
    
    @abstractmethod
    def get_required_fields(self) -> List[str]:
        """Campos requeridos en el estado para que funcione este actor"""
        pass
    
    @abstractmethod
    def get_actor_description(self) -> str:
        """Descripción de las responsabilidades de este actor"""
        pass
   
    def signal_delegation(
        self,
        delegate_to: str,
        delegation_reason: str = None,
        new_state: Optional[Dict[str, Any]] = None,
        **context_data,
    ) -> dict:
        """
        🎯 SEÑAL DE ACTOR: "Delego esta tarea a otro actor"
        
        El actor decide que otro actor debe manejar la situación.
        """
        self._record_decision(ActorDecision.DELEGATE, delegate_to)
        if new_state is None:
            new_state = {}
        new_state.update({
            **context_data,
            "_actor_decision": ActorDecision.DELEGATE,
            "_next_actor": delegate_to,
            "_delegation_reason": delegation_reason
        })
        
        self.logger.info(f"🔄 {self.name} DELEGA → {delegate_to}: {delegation_reason}")
        return new_state


    def signal_completion(
        self, 
        state: Dict[str, Any],
        next_actor: str = None,
        completion_message: str = None,
        **actor_data
    ) -> dict:
        self._record_decision(ActorDecision.COMPLETE, next_actor)
        
        update_data = {
            **actor_data,
            "_completion_message": completion_message
        }
        
        if completion_message:
            update_data["messages"] = [AIMessage(content=completion_message)]
        
        self.logger.info(f"✅ {self.name} COMPLETO → señalando a {next_actor}")
        return update_data

    def signal_need_input(
        self, 
        state: Dict[str, Any],
        request_message: str,
        context: Dict[str, Any] = None
    ) -> dict:
        """🎯 VERSIÓN SIMPLE: Push al stack"""
        
        # Push al stack
        stack = state.get("_routing_stack", [])
        stack.append(self.name)
        update={
            "messages": [AIMessage(content=request_message)],
        }

        return update


    def signal_escalation(
        self, 
        state: Dict[str, Any],
        reason: str,
        attempts: int = None,  # ✅ CORREGIDO: Parámetro opcional
        **escalation_context
    ) -> dict:
        """
        🎯 SEÑAL DE ACTOR: "Necesito escalación"
        
        El actor no puede completar su tarea y solicita ayuda.
        """
        attempts = attempts or state.get("intentos", 0)  # ✅ CORREGIDO: Fallback
        self._record_decision(ActorDecision.ESCALATE, "escalar_supervisor")
        
        escalation_message = (
            f"He intentado {reason} sin éxito después de {attempts} intentos. "
            f"Voy a derivar tu consulta a un supervisor para que pueda ayudarte mejor."
        )
        
        update_data = {
            **escalation_context,
            "escalar_a_supervisor": True,
            "razon_escalacion": reason,
            "messages": [AIMessage(content=escalation_message)]
        }
        
        self.logger.info(f"🔼 {self.name} ESCALA → supervisor: {reason}")
        return update_data


    def _record_decision(self, decision: str, target: str = None):
        """Registrar decisión del actor para debugging"""
        decision_record = {
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
            "target": target,
            "actor": self.name
        }
        self._actor_state["decision_history"].append(decision_record)
        
        # Mantener solo últimas 10 decisiones
        if len(self._actor_state["decision_history"]) > 10:
            self._actor_state["decision_history"] = self._actor_state["decision_history"][-10:]

    def get_last_user_message(self, state: Dict[str, Any]) -> str:
        """✅ CORREGIDO: Obtener el último mensaje del usuario"""
        messages = state.get("messages", [])
        
        for message in reversed(messages):
            # Método 1: Verificar por tipo de clase (más confiable)
            if isinstance(message, HumanMessage):
                return message.content
            
            # Método 2: Verificar por atributo type (backup)
            if hasattr(message, 'type') and message.type == "Human":  # ✅ "Human" con mayúscula
                return message.content
        
        return ""

    def increment_attempts(self, state: Dict[str, Any], field: str = "intentos") -> int:
        """Incrementar contador de intentos"""
        current = state.get(field, 0)
        new_value = current + 1
        return new_value

    async def execute_with_monitoring(self, state: Dict[str, Any]) -> Command:
        """
        Wrapper que ejecuta el nodo con monitoring.
        Agrega logging, métricas y manejo de errores común.
        """
        start_time = datetime.now()
        self._actor_state["is_processing"] = True
        
        try:
            self.logger.info(f"🎭 {self.name} iniciando ejecución #{self._actor_state['execution_count'] + 1}")
            
            # Validar campos requeridos
            if not self._validate_required_fields(state):
                return self.signal_escalation(
                    state, 
                    f"campos requeridos faltantes: {self.get_required_fields()}"
                )
            
            # Ejecutar lógica del actor
            result = await self.execute(state)
            
            # Registrar ejecución exitosa
            execution_time = (datetime.now() - start_time).total_seconds()
            self._actor_state["last_execution_time"] = execution_time
            self._actor_state["execution_count"] += 1
            
            self.logger.info(f"✅ {self.name} completado en {execution_time:.2f}s")
            
            if execution_time > 5.0:
                self.logger.warning(f"⚠️ Ejecución lenta detectada: {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            self._actor_state["error_count"] += 1
            self.logger.error(f"❌ {self.name} error: {e}")
            return await self.handle_error(e, state)
        
        finally:
            self._actor_state["is_processing"] = False

    def _validate_required_fields(self, state: Dict[str, Any]) -> bool:
        """Validar que el estado tenga los campos requeridos"""
        required = self.get_required_fields()
        missing = [field for field in required if field not in state]
        
        if missing:
            self.logger.warning(f"⚠️ Campos faltantes: {missing}")
            return False
        
        return True

    async def handle_error(self, error: Exception, state: Dict[str, Any]) -> Command:
        """Manejo centralizado de errores"""
        error_msg = f"Error en {self.name}: {str(error)}"
        
        # Si hay muchos errores, escalar
        if self._actor_state["error_count"] >= 3:
            return self.signal_escalation(
                state,
                f"múltiples errores en {self.name}",
                attempts=self._actor_state["error_count"]
            )
        
        # Intentar recuperación
        return Command(update={
            **state,
            "error_info": {
                "actor": self.name,
                "error": str(error),
                "timestamp": datetime.now().isoformat()
            },
            "messages": [AIMessage(content="Disculpa, tuve un problema técnico. ¿Podrías intentar de nuevo?")]
        })





    def _record_decision(self, decision: str, target: str = None):
        """Registrar decisión del actor para debugging"""
        decision_record = {
            "timestamp": datetime.now().isoformat(),
            "decision": decision,
            "target": target,
            "actor": self.name
        }
        self._actor_state["decision_history"].append(decision_record)
        
        # Mantener solo últimas 10 decisiones
        if len(self._actor_state["decision_history"]) > 10:
            self._actor_state["decision_history"] = self._actor_state["decision_history"][-10:]
        self.logger.debug(f"💾 {self.name} DECISIONES: {self._actor_state['decision_history'][-10:]}")

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
            
            # Comparar valores
            if old_value != new_value:
                diff[key] = new_value
        
        # Detectar nuevas claves que no existían antes
        for key in new_state:
            if key not in old_state:
                diff[key] = new_state[key]
        
        self.logger.debug(f"🔄 Estado diff calculado: {len(diff)} cambios")
        return diff
   
    def get_actor_state(self) -> Dict[str, Any]:
        """Estado interno del actor (solo lectura)"""
        return self._actor_state.copy()
    
    def should_escalate_after_attempts(self, attempts: int, max_attempts: int = 3) -> bool:
        """Determinar si debe escalar basado en intentos"""
        return attempts >= max_attempts
     
    def _validate_required_fields(self, state: Dict[str, Any]) -> bool:
        """Validar que el estado tenga los campos requeridos"""
        required = self.get_required_fields()
        missing = [field for field in required if field not in state]
        
        if missing:
            self.logger.warning(f"⚠️ Campos faltantes: {missing}")
            return False
        
        self.logger.debug("✅ Estado válido para actor")
        return True
    
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
        
        return Command(update=diff)

