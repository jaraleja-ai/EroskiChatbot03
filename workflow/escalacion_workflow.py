# =====================================================
# workflows/escalacion_workflow.py - Workflow de escalación
# =====================================================
from langgraph.graph import StateGraph, START, END
from workflow import BaseWorkflow
from models import GraphState
from nodes.escalar_supervisor import escalar_supervisor_node

class EscalacionWorkflow(BaseWorkflow):
    """
    Workflow especializado para casos escalados.
    
    Se ejecuta cuando el workflow principal requiere escalación.
    """
    
    def __init__(self):
        super().__init__("EscalacionWorkflow")
    
    def get_entry_point(self) -> str:
        return "procesar_escalacion"
    
    def get_workflow_description(self) -> str:
        return "Workflow especializado para manejo de escalaciones a supervisores"
    
    def build_graph(self) -> StateGraph:
        """Construir grafo de escalación"""
        
        self.logger.info("🔧 Construyendo grafo de escalación...")
        
        graph = StateGraph(GraphState)
        
        # Por ahora, solo el nodo de escalación
        graph.add_node("procesar_escalacion", escalar_supervisor_node)
        
        # Flujo simple
        graph.add_edge(START, "procesar_escalacion")
        graph.add_edge("procesar_escalacion", END)
        
        self.logger.info("✅ Grafo de escalación construido")
        return graph
