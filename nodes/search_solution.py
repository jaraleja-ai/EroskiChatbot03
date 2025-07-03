# =====================================================
# nodes/search_solution.py - Nodo de Búsqueda de Soluciones
# =====================================================
"""
Nodo para buscar soluciones automáticas a incidencias técnicas.

RESPONSABILIDADES:
- Buscar en base de conocimiento de soluciones
- Aplicar soluciones automáticas cuando sea posible
- Proporcionar guías paso a paso
- Determinar si la solución es aplicable
- Registrar intentos de solución
"""

from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging
import json

from models.eroski_state import EroskiState, SolutionType
from nodes.base_node import BaseNode
from config.incident_config import get_incident_config

class SearchSolutionNode(BaseNode):
    """
    Nodo para buscar y aplicar soluciones automáticas.
    
    CARACTERÍSTICAS:
    - Búsqueda inteligente en base de conocimiento
    - Matching por tipo de equipo y error
    - Soluciones paso a paso
    - Registro de efectividad
    """
    
    def __init__(self):
        super().__init__("SearchSolution")
        self.incident_config = get_incident_config()
        
        # Base de conocimiento de soluciones comunes
        self.knowledge_base = {
            "tpv_frozen": {
                "title": "TPV Congelado/Bloqueado",
                "keywords": ["tpv", "congelado", "bloqueado", "no responde"],
                "solutions": [
                    {
                        "type": "restart",
                        "title": "Reinicio del TPV",
                        "steps": [
                            "Mantén presionado el botón de encendido durante 10 segundos",
                            "Espera 30 segundos antes de encender nuevamente",
                            "Presiona el botón de encendido y espera que cargue completamente",
                            "Verifica que aparezca la pantalla de inicio de sesión"
                        ],
                        "estimated_time": "2-3 minutos",
                        "success_rate": 85
                    },
                    {
                        "type": "cable_check",
                        "title": "Verificación de Cables",
                        "steps": [
                            "Revisa que el cable de alimentación esté bien conectado",
                            "Verifica que el cable de red esté conectado correctamente",
                            "Asegúrate de que no haya cables sueltos en la parte trasera",
                            "Reinicia el equipo después de verificar las conexiones"
                        ],
                        "estimated_time": "1-2 minutos",
                        "success_rate": 70
                    }
                ]
            },
            "printer_error": {
                "title": "Error de Impresora",
                "keywords": ["impresora", "no imprime", "papel", "tinta"],
                "solutions": [
                    {
                        "type": "paper_jam",
                        "title": "Problema de Papel",
                        "steps": [
                            "Apaga la impresora",
                            "Abre la bandeja de papel y retira cualquier papel atascado",
                            "Verifica que el papel esté correctamente alineado",
                            "Cierra la bandeja y enciende la impresora",
                            "Realiza una impresión de prueba"
                        ],
                        "estimated_time": "2-3 minutos",
                        "success_rate": 80
                    },
                    {
                        "type": "driver_reset",
                        "title": "Reinicio de Controladores",
                        "steps": [
                            "Ve a Panel de Control > Dispositivos e impresoras",
                            "Clic derecho en la impresora problemática",
                            "Selecciona 'Eliminar dispositivo'",
                            "Desconecta y vuelve a conectar el cable USB",
                            "Permite que Windows reinstale automáticamente el controlador"
                        ],
                        "estimated_time": "5-7 minutos",
                        "success_rate": 75
                    }
                ]
            },
            "scanner_error": {
                "title": "Error de Scanner",
                "keywords": ["scanner", "código barras", "no lee", "no funciona"],
                "solutions": [
                    {
                        "type": "cleaning",
                        "title": "Limpieza del Scanner",
                        "steps": [
                            "Apaga el scanner",
                            "Limpia el cristal con alcohol isopropílico y un paño suave",
                            "Deja secar completamente",
                            "Enciende el scanner y verifica el LED indicador",
                            "Prueba escaneando un código de barras conocido"
                        ],
                        "estimated_time": "3-4 minutos",
                        "success_rate": 85
                    }
                ]
            },
            "network_error": {
                "title": "Error de Red/Conectividad",
                "keywords": ["red", "internet", "conexión", "no conecta"],
                "solutions": [
                    {
                        "type": "network_reset",
                        "title": "Reinicio de Red",
                        "steps": [
                            "Desconecta el cable de red del equipo",
                            "Espera 30 segundos",
                            "Vuelve a conectar el cable de red",
                            "Verifica que el LED de red esté encendido",
                            "Prueba la conexión abriendo una página web"
                        ],
                        "estimated_time": "2-3 minutos",
                        "success_rate": 70
                    }
                ]
            }
        }
    
    def get_required_fields(self) -> List[str]:
        return ["incident_description", "affected_equipment", "incident_complete"]
    
    def get_actor_description(self) -> str:
        return "Busco soluciones automáticas para incidencias técnicas comunes"
    
    async def execute(self, state: EroskiState) -> Command:
        """
        Ejecutar búsqueda de soluciones.
        
        Args:
            state: Estado actual del workflow
            
        Returns:
            Command con las soluciones encontradas
        """
        print("🎗️"*50)
        print(f"entra en el nodo: {self.__class__.__name__}")
        try:
            # Buscar soluciones aplicables
            solutions = self._search_applicable_solutions(state)
            
            if not solutions:
                return self._no_solution_found(state)
            
            # Seleccionar mejor solución
            best_solution = self._select_best_solution(solutions)
            
            # Proporcionar solución al usuario
            return self._provide_solution(state, best_solution)
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando soluciones: {e}")
            return self._escalate_error(state, str(e))
    
    def _search_applicable_solutions(self, state: EroskiState) -> List[Dict[str, Any]]:
        """Buscar soluciones aplicables al problema"""
        description = state.get("incident_description", "").lower()
        equipment = state.get("affected_equipment", "").lower()
        error_codes = state.get("error_codes", [])
        
        applicable_solutions = []
        
        # Buscar en base de conocimiento local
        for solution_id, solution_data in self.knowledge_base.items():
            score = self._calculate_solution_score(
                description, equipment, error_codes, solution_data
            )
            
            if score > 0.3:  # Umbral mínimo de relevancia
                for solution in solution_data["solutions"]:
                    applicable_solutions.append({
                        "solution_id": solution_id,
                        "solution_data": solution,
                        "category": solution_data["title"],
                        "score": score,
                        "source": "knowledge_base"
                    })
        
        # Buscar en configuración de incidencias
        incident_matches = self.incident_config.search_by_keywords(description, limit=3)
        for match in incident_matches:
            incident_type = match["incident_type"]
            if hasattr(incident_type, 'common_issues') and incident_type.common_issues:
                for issue in incident_type.common_issues:
                    applicable_solutions.append({
                        "solution_id": f"config_{incident_type.id}",
                        "solution_data": {
                            "type": "configuration",
                            "title": f"Solución para {incident_type.name}",
                            "steps": [issue],
                            "estimated_time": "5-10 minutos",
                            "success_rate": 60
                        },
                        "category": incident_type.name,
                        "score": match["score"] / 10,
                        "source": "incident_config"
                    })
        
        # Ordenar por puntuación
        applicable_solutions.sort(key=lambda x: x["score"], reverse=True)
        
        return applicable_solutions[:3]  # Top 3 soluciones
    
    def _calculate_solution_score(self, description: str, equipment: str, 
                                error_codes: List[str], solution_data: Dict[str, Any]) -> float:
        """Calcular puntuación de relevancia de una solución"""
        score = 0.0
        
        # Puntuación por keywords
        keywords = solution_data.get("keywords", [])
        for keyword in keywords:
            if keyword in description:
                score += 0.3
            if keyword in equipment:
                score += 0.4
        
        # Puntuación por códigos de error específicos
        if error_codes:
            # Aquí se podrían agregar mappings específicos de códigos de error
            score += 0.2
        
        # Limitar puntuación máxima
        return min(score, 1.0)
    
    def _select_best_solution(self, solutions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Seleccionar la mejor solución basada en puntuación y tasa de éxito"""
        if not solutions:
            return None
        
        # Ordenar por puntuación y tasa de éxito
        solutions.sort(key=lambda x: (
            x["score"], 
            x["solution_data"].get("success_rate", 50)
        ), reverse=True)
        
        return solutions[0]
    
    def _provide_solution(self, state: EroskiState, solution: Dict[str, Any]) -> Command:
        """Proporcionar solución al usuario"""
        solution_data = solution["solution_data"]
        
        # Construir mensaje con la solución
        solution_message = self._build_solution_message(solution_data, solution["category"])
        
        return Command(update={
            "solution_found": True,
            "solution_type": SolutionType.GUIA_MANUAL,
            "solution_content": solution_data,
            "solution_category": solution["category"],
            "solution_score": solution["score"],
            "resolution_steps": solution_data.get("steps", []),
            "estimated_resolution_time": solution_data.get("estimated_time", "5-10 minutos"),
            "messages": state.get("messages", []) + [AIMessage(content=solution_message)],
            "current_node": "search_solution",
            "last_activity": datetime.now(),
            "awaiting_user_input": False
        })
    
    def _build_solution_message(self, solution_data: Dict[str, Any], category: str) -> str:
        """Construir mensaje con la solución"""
        steps = solution_data.get("steps", [])
        estimated_time = solution_data.get("estimated_time", "5-10 minutos")
        success_rate = solution_data.get("success_rate", 70)
        
        steps_text = "\n".join([f"{i+1}. {step}" for i, step in enumerate(steps)])
        
        return f"""🔧 **SOLUCIÓN ENCONTRADA**

**Categoría:** {category}
**Solución:** {solution_data.get('title', 'Solución Recomendada')}

**Pasos a seguir:**
{steps_text}

⏰ **Tiempo estimado:** {estimated_time}
📊 **Tasa de éxito:** {success_rate}%

**Instrucciones:**
1. **Sigue cada paso** en el orden indicado
2. **No te saltes pasos** aunque parezcan obvios
3. **Verifica** que cada paso se complete correctamente

➡️ **Después de seguir estos pasos,** por favor confirma si el problema se ha resuelto o si necesitas más ayuda.

**¿Has podido seguir estos pasos? ¿Se ha solucionado el problema?** 🤔"""
    
    def _no_solution_found(self, state: EroskiState) -> Command:
        """Manejar caso donde no se encuentra solución"""
        no_solution_message = """🔍 **No he encontrado una solución automática específica**

Aunque no tengo una solución automática para tu problema específico, puedo ayudarte de otras formas:

**Opciones disponibles:**
• **Escalación a soporte técnico** - Te conectaré con un especialista
• **Búsqueda en documentación** - Revisaré manuales y guías adicionales
• **Contacto directo** - Te proporcionaré números de soporte especializado

**Información del problema:**
• **Equipo:** {equipment}
• **Descripción:** {description}

¿Qué prefieres que haga para ayudarte? 🤝""".format(
            equipment=state.get("affected_equipment", "No especificado"),
            description=state.get("incident_description", "No especificado")[:100]
        )
        
        return Command(update={
            "solution_found": False,
            "solution_type": None,
            "escalation_reason": "No se encontró solución automática aplicable",
            "messages": state.get("messages", []) + [AIMessage(content=no_solution_message)],
            "current_node": "search_solution",
            "last_activity": datetime.now(),
            "awaiting_user_input": False
        })
    
    def _escalate_error(self, state: EroskiState, error_message: str) -> Command:
        """Escalar por error técnico"""
        return Command(update={
            "escalation_needed": True,
            "escalation_reason": f"Error técnico buscando soluciones: {error_message}",
            "escalation_level": "technical",
            "messages": state.get("messages", []) + [
                AIMessage(content="Ha ocurrido un error técnico. Te derivo a soporte técnico.")
            ],
            "current_node": "search_solution",
            "last_activity": datetime.now(),
            "error_count": state.get("error_count", 0) + 1
        })

# ========== WRAPPER PARA LANGGRAPH ==========

async def search_solution_node(state: EroskiState) -> Command:
    """
    Wrapper function para el nodo de búsqueda de soluciones.
    
    Args:
        state: Estado actual del workflow
        
    Returns:
        Command con la actualización de estado
    """
    node = SearchSolutionNode()
    return await node.execute(state)