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
    
    # =====================================================
    # MÉTODOS ACTOR PATTERN (mejores prácticas)
    # =====================================================
    
    def signal_completion(
        self, 
        state: Dict[str, Any],
        next_actor: str = None,
        completion_message: str = None,
        **actor_data
    ) -> Command:
        """
        🎯 SEÑAL DE ACTOR: "He completado mi trabajo"
        
        El actor señala explícitamente que terminó y sugiere el próximo paso.
        """
        self._record_decision(ActorDecision.COMPLETE, next_actor)
        
        update_data = {
            **state
            **actor_data,
            "_actor_decision": ActorDecision.COMPLETE,
            "_next_actor": next_actor,  # Señal explícita al router
            "_completion_message": completion_message
        }
        
        if completion_message:
            update_data["messages"] = [AIMessage(content=completion_message)]
        
        self.logger.info(f"✅ {self.name} COMPLETO → señalando a {next_actor}")
        return Command(update=update_data)
    
    def signal_need_input(
        self, 
        state: Dict[str, Any],
        request_message: str,
        context: Dict[str, Any] = None
    ) -> Command:
        """
        🎯 SEÑAL DE ACTOR: "Necesito información del usuario"
        
        El actor solicita específicamente datos del usuario.
        """
        self._record_decision(ActorDecision.NEED_INPUT, "user")
        
        update_data = {
            **state,
            "_actor_decision": ActorDecision.NEED_INPUT,
            "_request_message": request_message,
            "_input_context": context or {},
            "messages": [AIMessage(content=request_message)]
        }
        print(f'🛑🛑 signal_need_input, actor_decision: {update_data["_actor_decision"]}')
        self.logger.info(f"📥 {self.name} SOLICITA INPUT: {request_message[:50]}...")
        return Command(update=update_data)
    
    def signal_delegation(
        self, 
        state: Dict[str, Any],
        delegate_to: str,
        delegation_reason: str = None,
        **context_data
    ) -> Command:
        """
        🎯 SEÑAL DE ACTOR: "Delego esta tarea a otro actor"
        
        El actor decide que otro actor debe manejar la situación.
        """
        self._record_decision(ActorDecision.DELEGATE, delegate_to)
        
        update_data = {
            **state,
            **context_data,
            "_actor_decision": ActorDecision.DELEGATE,
            "_next_actor": delegate_to,
            "_delegation_reason": delegation_reason
        }
        
        self.logger.info(f"🔄 {self.name} DELEGA → {delegate_to}: {delegation_reason}")
        return Command(update=update_data)
    
    def signal_escalation(
        self, 
        state: Dict[str, Any],
        reason: str,
        **escalation_context
    ) -> Command:
        """
        🎯 SEÑAL DE ACTOR: "Necesito escalación"
        
        El actor no puede completar su tarea y solicita ayuda.
        """
        attempts = state["intentos"]
        self._record_decision(ActorDecision.ESCALATE, "supervisor")
        
        escalation_message = (
            f"He intentado {reason} sin éxito después de {attempts} intentos. "
            f"Voy a derivar tu consulta a un supervisor para que pueda ayudarte mejor."
        )

        
        
        update_data = {
            **state,
            "intentos": attempts + 1,
            "_actor_decision": ActorDecision.ESCALATE,
            "_next_actor": "escalar_supervisor",
            "escalar_a_supervisor": True,
            "razon_escalacion": reason,
            "messages": [AIMessage(content=escalation_message)],
            **escalation_context
        }
        
        self.logger.warning(f"🔼 {self.name} ESCALA: {reason}")
        return Command(update=update_data)
    
    # =====================================================
    # UTILIDADES DE ACTOR (helpers)
    # =====================================================
    
    def get_actor_state(self) -> Dict[str, Any]:
        """Estado interno del actor (solo lectura)"""
        return self._actor_state.copy()
    
    def increment_attempts(self, state: Dict[str, Any], attempt_key: str = "intentos") -> int:
        """Incrementar intentos de manera consistente"""
        current = state.get(attempt_key, 0)
        new_attempts = current + 1
        
        self._actor_state["execution_count"] += 1
        self.logger.debug(f"🔄 Intento {new_attempts} para {attempt_key}")
        return new_attempts
    
    def should_escalate_after_attempts(self, attempts: int, max_attempts: int = 3) -> bool:
        """Determinar si debe escalar basado en intentos"""
        return attempts >= max_attempts
    
    def get_last_user_message(self, state: Dict[str, Any]) -> str:
        """Obtener último mensaje del usuario de forma segura"""
        messages = state.get("messages", [])
        for msg in reversed(messages):
            if hasattr(msg, 'type') and msg.type == "human":
                return msg.content
            elif isinstance(msg, HumanMessage):
                return msg.content
        return ""
    
    def _record_decision(self, decision: str, target: str = None):
        """Registrar decisión para debugging"""
        decision_record = {
            "decision": decision,
            "target": target,
            "timestamp": datetime.now().isoformat()
        }
        self._actor_state["decision_history"].append(decision_record)
        
        # Mantener solo las últimas 10 decisiones
        if len(self._actor_state["decision_history"]) > 10:
            self._actor_state["decision_history"] = self._actor_state["decision_history"][-10:]
    
    async def execute_with_monitoring(self, state: Dict[str, Any]) -> Command:
        """
        Wrapper que ejecuta el actor con monitoreo.
        
        Agrega logging, métricas y manejo de errores común.
        """
        start_time = datetime.now()
        self._actor_state["is_processing"] = True
        
        try:
            self.logger.info(f"🔍 === INICIANDO {self.name.upper()} ===")
            
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
            
            self.logger.info(f"✅ {self.name} completado - Resultado: success ({execution_time:.2f}s)")
            
            if execution_time > 5.0:
                self.logger.warning(f"⚠️ Ejecución lenta detectada: {execution_time:.2f}s")
            
            return result
            
        except Exception as e:
            self._actor_state["error_count"] += 1
            self.logger.error(f"❌ Error en {self.name}: {e}")
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
        
        self.logger.debug("✅ Estado válido para actor")
        return True
    
    async def handle_error(self, error: Exception, state: Dict[str, Any], intentos: int =0,) -> Command:
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
            "intentos":0,
            "error_info": {
                "actor": self.name,
                "error": str(error),
                "timestamp": datetime.now().isoformat()
            },
            "messages": [AIMessage(content="Disculpa, tuve un problema técnico. ¿Podrías intentar de nuevo?")]
        })