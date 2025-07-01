# =====================================================
# workflows/consulta_workflow.py - Workflow de consultas
# =====================================================
from workflow import BaseWorkflow
from typing import Dict, Any
from models import GraphState
from nodes import identificar_usuario
from langgraph.graph import StateGraph, START, END

class ConsultaWorkflow(BaseWorkflow):
    """
    Workflow para consultas simples que no requieren crear tickets.
    
    Casos de uso:
    - Preguntas sobre procedimientos
    - Consultas de estado de tickets existentes
    - Información general
    """
    
    def __init__(self):
        super().__init__("ConsultaWorkflow")
    
    def get_entry_point(self) -> str:
        return "identificar_usuario"
    
    def get_workflow_description(self) -> str:
        return "Workflow para consultas simples que no requieren crear tickets de incidencia"
    
    def build_graph(self) -> StateGraph:
        """Construir grafo de consultas (placeholder)"""
        
        # Por ahora, usar el mismo flujo que incidencias
        # En el futuro, agregar nodos específicos para consultas
        graph = StateGraph(GraphState)
        
        graph.add_node("identificar_usuario", identificar_usuario)
        graph.add_node("procesar_consulta", self._placeholder_consulta_node)
        graph.add_node("responder_consulta", self._placeholder_respuesta_node)
        
        graph.add_edge(START, "identificar_usuario")
        graph.add_edge("identificar_usuario", "procesar_consulta")
        graph.add_edge("procesar_consulta", "responder_consulta")
        graph.add_edge("responder_consulta", END)
        
        return graph
    
    async def _placeholder_consulta_node(self, state: Dict[str, Any]):
        """Nodo placeholder para procesar consultas"""
        from langgraph.types import Command
        from langchain_core.messages import AIMessage
        
        # TODO: Implementar lógica real de consultas
        mensaje = "Gracias por tu consulta. Este flujo está en desarrollo."
        
        return Command(update={
            "messages": [AIMessage(content=mensaje)],
            "flujo_completado": True
        })
    
    async def _placeholder_respuesta_node(self, state: Dict[str, Any]):
        """Nodo placeholder para responder consultas"""
        from langgraph.types import Command
        from langchain_core.messages import AIMessage
        
        mensaje = "Tu consulta ha sido procesada. ¿Hay algo más en lo que pueda ayudarte?"
        
        return Command(update={
            "messages": [AIMessage(content=mensaje)],
            "flujo_completado": True
        })