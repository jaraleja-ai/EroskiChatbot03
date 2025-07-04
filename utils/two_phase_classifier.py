# =====================================================
# CLASIFICACIÓN EN DOS FASES CON ESTADO EroskiState
# =====================================================

from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging
from pydantic import BaseModel, Field

from models.eroski_state import EroskiState
from utils.llm.providers import get_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# =============================================================================
# MODELOS PARA LAS DOS FASES
# =============================================================================

class IncidentTypeDecision(BaseModel):
    """Decisión de la FASE 1: Identificación del tipo de incidencia"""
    
    incident_type_identified: bool = Field(description="Si se identificó el tipo de incidencia")
    incident_type: Optional[str] = Field(description="Tipo identificado (balanza, tpv, impresora, etc.)")
    confidence_level: float = Field(description="Confianza en la identificación (0-1)")
    keywords_detected: List[str] = Field(description="Palabras clave que llevaron a la identificación", default=[])
    additional_info: Optional[str] = Field(description="Información adicional relevante detectada", default=None)
    reasoning: str = Field(description="Razonamiento de por qué se identificó este tipo")
    needs_clarification: bool = Field(description="Si necesita más información para identificar", default=False)

class SpecificProblemDecision(BaseModel):
    """Decisión de la FASE 2: Identificación del problema específico"""
    
    problem_identified: bool = Field(description="Si se identificó el problema específico")
    specific_problem: Optional[str] = Field(description="Problema específico del catálogo")
    problem_description: Optional[str] = Field(
        description="Descripción del problema (puede ser 'otros')", 
        default="No especificado"
    )
    solution_available: bool = Field(description="Si hay solución disponible para este problema")
    proposed_solution: Optional[str] = Field(description="Solución propuesta si está disponible")
    additional_info: Optional[str] = Field(description="Información adicional sobre el problema", default=None)
    confidence_level: float = Field(description="Confianza en la identificación del problema (0-1)")
    next_action: str = Field(description="Próxima acción: provide_solution, ask_details, escalate")

# =============================================================================
# PROMPTS PARA LAS DOS FASES
# =============================================================================

def build_phase_1_prompt() -> PromptTemplate:
    """
    FASE 1: Identificar TIPO de incidencia
    
    Objetivo: Determinar si es balanza, TPV, impresora, red, etc.
    Actualiza: state.incident_type + state.additional_info
    """
    return PromptTemplate(
        template="""Eres un especialista en identificación de TIPOS de incidencias técnicas en Eroski.

🎯 **MISIÓN FASE 1:** Identificar ÚNICAMENTE el TIPO de equipo/sistema con problemas.

EMPLEADO: {employee_name} - Sección: {section} - Tienda: {store_name}

TIPOS DE EQUIPOS DISPONIBLES:
{equipment_types}

HISTORIAL COMPLETO DE MENSAJES:
{conversation_history}

ÚLTIMO MENSAJE: "{user_message}"

🔍 **ANÁLISIS REQUERIDO:**

1️⃣ **Identificar el EQUIPO/SISTEMA:**
   - ¿Menciona directamente un equipo? (balanza, TPV, impresora, ordenador...)
   - ¿Se puede inferir por la sección? (carnicería → probable balanza)
   - ¿Hay palabras clave técnicas? (etiquetas, pantalla, peso, conexión...)

2️⃣ **Evaluar CONFIANZA:**
   - Alta (>0.8): Mención directa o contexto muy claro
   - Media (0.5-0.8): Se puede inferir razonablemente
   - Baja (<0.5): Muy vago o ambiguo

3️⃣ **Capturar INFORMACIÓN ADICIONAL:**
   - Síntomas mencionados
   - Detalles técnicos
   - Contexto temporal (desde cuándo, frecuencia...)

✅ **EJEMPLOS DE IDENTIFICACIÓN CORRECTA:**

**Ejemplo A - Mención directa:**
Usuario: "la balanza no funciona bien"
→ incident_type: "balanza", confidence: 0.95

**Ejemplo B - Inferencia por contexto:**
Usuario: "problema con las etiquetas" + Sección: "carnicería"
→ incident_type: "balanza", confidence: 0.85

**Ejemplo C - Síntoma técnico:**
Usuario: "no puedo cobrar" + Sección: "caja"
→ incident_type: "tpv", confidence: 0.8

**Ejemplo D - Información insuficiente:**
Usuario: "no funciona"
→ incident_type_identified: false, needs_clarification: true

RESPONDE ÚNICAMENTE CON JSON:
{{
  "incident_type_identified": true/false,
  "incident_type": "balanza|tpv|impresora|red|ordenador|telefono|otros",
  "confidence_level": 0.0-1.0,
  "keywords_detected": ["palabra1", "palabra2"],
  "additional_info": "Información relevante detectada",
  "reasoning": "Razón por la que identifiqué este tipo",
  "needs_clarification": true/false
}}""",
        input_variables=[
            "employee_name", "section", "store_name", "equipment_types",
            "conversation_history", "user_message"
        ]
    )

def build_phase_2_prompt() -> PromptTemplate:
    """
    FASE 2: Identificar PROBLEMA ESPECÍFICO - PROMPT MEJORADO
    """
    return PromptTemplate(
        template="""🎯 **MISIÓN FASE 2:** Identificar el PROBLEMA ESPECÍFICO dentro de {incident_type}.

INFORMACIÓN DE FASE 1:
- Tipo identificado: {incident_type}
- Información adicional: {phase1_additional_info}
- Confianza Fase 1: {phase1_confidence}

PROBLEMAS ESPECÍFICOS DISPONIBLES PARA {incident_type}:
{specific_problems_catalog}

HISTORIAL COMPLETO:
{conversation_history}

ÚLTIMO MENSAJE: "{user_message}"

🔍 **ANÁLISIS DE PROBLEMA ESPECÍFICO:**

1️⃣ **Buscar COINCIDENCIA EXACTA:**
   - ¿El usuario describe exactamente uno de los problemas del catálogo?
   - ¿Usa palabras clave que coinciden directamente?

2️⃣ **Buscar COINCIDENCIA PARCIAL:**
   - ¿Los síntomas coinciden con algún problema conocido?
   - ¿Se puede inferir cuál es el problema más probable?

3️⃣ **Evaluar si es PROBLEMA NO CATALOGADO:**
   - Si no coincide con ninguno → problem_description: "otros"
   - Capturar descripción del usuario en additional_info

RESPONDE ÚNICAMENTE CON JSON VÁLIDO:
{{
  "problem_identified": true/false,
  "specific_problem": "Problema exacto del catálogo o null",
  "problem_description": "Descripción del problema o 'otros' - NUNCA null",
  "solution_available": true/false,
  "proposed_solution": "Solución paso a paso o null",
  "additional_info": "Información adicional capturada o null",
  "confidence_level": 0.0-1.0,
  "next_action": "provide_solution|ask_details|escalate"
}}

⚠️ **IMPORTANTE:** 
- problem_description NUNCA debe ser null, siempre un string
- Si no hay descripción clara, usar "Problema no especificado"
- Si es problema no catalogado, usar "otros"
""",
        input_variables=[
            "incident_type", "phase1_additional_info", "phase1_confidence",
            "specific_problems_catalog", "conversation_history", "user_message"
        ]
    )
# =============================================================================
# LÓGICA PRINCIPAL DE CLASIFICACIÓN EN DOS FASES
# =============================================================================

class TwoPhaseClassifier:
    """
    Clasificador en dos fases que usa EroskiState como canal de comunicación
    """
    
    def __init__(self):
        self.llm = get_llm()
        self.logger = logging.getLogger("TwoPhaseClassifier")
        
        # Parsers para cada fase
        self.phase1_parser = JsonOutputParser(pydantic_object=IncidentTypeDecision)
        self.phase2_parser = JsonOutputParser(pydantic_object=SpecificProblemDecision)
        
        # Prompts para cada fase
        self.phase1_prompt = build_phase_1_prompt()
        self.phase2_prompt = build_phase_2_prompt()
    
    async def classify_incident(self, state: EroskiState) -> Command:
        """
        Ejecutar clasificación en dos fases usando EroskiState
        
        Args:
            state: Estado actual con mensajes e información del empleado
            
        Returns:
            Command con estado actualizado
        """
        
        # ✅ FASE 1: Identificar TIPO de incidencia
        if not state.get("incident_type"):
            self.logger.info("🔍 FASE 1: Identificando tipo de incidencia...")
            
            phase1_result = await self._execute_phase_1(state)
            
            if phase1_result.incident_type_identified and phase1_result.confidence_level >= 0.7:
                # Actualizar estado con tipo identificado
                updated_state = self._update_state_after_phase1(state, phase1_result)
                
                self.logger.info(f"✅ FASE 1 COMPLETADA: {phase1_result.incident_type} (confianza: {phase1_result.confidence_level})")
                
                # Continuar inmediatamente a FASE 2
                return await self._execute_phase_2_with_state(updated_state)
            
            elif phase1_result.needs_clarification:
                # Necesita más información para identificar tipo
                return self._ask_for_type_clarification(state, phase1_result)
            
            else:
                # Confianza baja, pedir más información
                return self._ask_general_clarification(state)
        
        # ✅ FASE 2: Identificar PROBLEMA ESPECÍFICO
        else:
            self.logger.info(f"🔍 FASE 2: Identificando problema específico para {state.get('incident_type')}...")
            return await self._execute_phase_2_with_state(state)
    
    async def _execute_phase_1(self, state: EroskiState) -> IncidentTypeDecision:
        """Ejecutar FASE 1: Identificación del tipo"""
        
        auth_data = state.get("auth_data_collected", {})
        
        # Preparar datos para el prompt
        prompt_data = {
            "employee_name": auth_data.get("name", "No especificado"),
            "section": auth_data.get("section", "No especificado"),
            "store_name": auth_data.get("store_name", "No especificado"),
            "equipment_types": self._get_equipment_types_list(),
            "conversation_history": self._format_conversation_history(state),
            "user_message": self._get_last_user_message(state)
        }
        
        # Ejecutar LLM Fase 1
        formatted_prompt = self.phase1_prompt.format(**prompt_data)
        response = await self.llm.ainvoke(formatted_prompt)
        
        # Parsear respuesta
        decision_data = self.phase1_parser.parse(response.content)
        return IncidentTypeDecision(**decision_data)
    
    async def _execute_phase_2_with_state(self, state: EroskiState) -> Command:
        """Ejecutar FASE 2 con validación mejorada"""
        
        try:
            # Ejecutar Fase 2
            phase2_result = await self._execute_phase_2(state)
            
            # ✅ VALIDACIÓN ADICIONAL: Verificar que problem_description no sea None
            if phase2_result.problem_description is None:
                self.logger.warning("⚠️ problem_description es None, aplicando fallback")
                
                # Crear una nueva instancia con valores por defecto
                phase2_result = SpecificProblemDecision(
                    problem_identified=phase2_result.problem_identified,
                    specific_problem=phase2_result.specific_problem,
                    problem_description="Problema no especificado",  # ✅ Valor por defecto
                    solution_available=phase2_result.solution_available,
                    proposed_solution=phase2_result.proposed_solution,
                    additional_info=phase2_result.additional_info,
                    confidence_level=phase2_result.confidence_level,
                    next_action=phase2_result.next_action
                )
            
            # Procesar resultado según el next_action
            if phase2_result.next_action == "provide_solution" and phase2_result.solution_available:
                return self._provide_solution_response(state, phase2_result)
            
            elif phase2_result.next_action == "ask_details":
                return self._ask_for_more_details(state, phase2_result)
            
            elif phase2_result.next_action == "escalate":
                return self._escalate_incident(state, phase2_result)
            
            else:
                # Fallback por defecto
                return self._ask_for_more_details(state, phase2_result)
                
        except Exception as e:
            self.logger.error(f"❌ Error en Fase 2: {e}")
            
            # ✅ MANEJO ROBUSTO DE ERRORES
            return Command(
                update={
                    **state,
                    "last_error": f"Error en clasificación: {str(e)}",
                    "needs_escalation": True
                },
                graph=self._create_error_response_with_escalation(state, str(e))
            )

    
    def _create_error_response_with_escalation(self, state: EroskiState, error_message: str) -> EroskiState:
        """Crear respuesta de error con escalación automática"""
        
        error_response = (
            "⚠️ **Error Temporal**\n\n"
            "Ha ocurrido un problema técnico durante la clasificación de tu incidencia.\n\n"
            "Por favor, intenta describir tu problema de nuevo o solicita hablar con un supervisor.\n\n"
            "Error técnico registrado para nuestro equipo de sistemas."
        )
        
        updated_state = {
            **state,
            "messages": state["messages"] + [AIMessage(content=error_response)],
            "needs_escalation": True,
            "escalation_reason": f"Error técnico: {error_message}",
            "current_node": "escalate"
        }
        
        return updated_state
    
    def _update_state_after_phase1(self, state: EroskiState, phase1_result: IncidentTypeDecision) -> EroskiState:
        """Actualizar estado después de FASE 1"""
        
        updated_state = dict(state)
        
        # Actualizar campos del estado
        updated_state.update({
            "incident_type": phase1_result.incident_type,
            "additional_info": phase1_result.additional_info,
            "confidence_score": phase1_result.confidence_level,
            "last_activity": datetime.now()
        })
        
        return EroskiState(updated_state)
    
    def _process_phase2_result(self, state: EroskiState, phase2_result: SpecificProblemDecision) -> Command:
        """Procesar resultado de FASE 2 y generar respuesta"""
        
        # Actualizar estado con resultado de FASE 2
        updated_state = dict(state)
        updated_state.update({
            "incident_description": phase2_result.problem_description,
            "solution_found": phase2_result.solution_available,
            "solution_content": phase2_result.proposed_solution,
            "last_activity": datetime.now()
        })
        
        # Combinar información adicional de ambas fases
        existing_additional_info = updated_state.get("additional_info", "")
        new_additional_info = phase2_result.additional_info or ""
        
        if new_additional_info and existing_additional_info:
            combined_info = f"{existing_additional_info} | {new_additional_info}"
        else:
            combined_info = new_additional_info or existing_additional_info
        
        updated_state["additional_info"] = combined_info
        
        # Decidir próxima acción basada en el resultado
        if phase2_result.next_action == "provide_solution" and phase2_result.solution_available:
            return self._provide_solution(updated_state, phase2_result)
        
        elif phase2_result.next_action == "ask_details":
            return self._ask_for_problem_details(updated_state, phase2_result)
        
        elif phase2_result.next_action == "escalate":
            return self._escalate_complex_problem(updated_state, phase2_result)
        
        else:
            # Fallback: pedir más detalles
            return self._ask_for_problem_details(updated_state, phase2_result)
    
    def _provide_solution(self, state: EroskiState, phase2_result: SpecificProblemDecision) -> Command:
        """Proporcionar solución identificada"""
        
        incident_code = state.get("incident_code", "N/A")
        
        solution_message = f"""✅ **Problema identificado: {state.get('incident_type', '').title()}**

📋 **Problema específico:** {phase2_result.specific_problem}

🔧 **Solución paso a paso:**
{phase2_result.proposed_solution}

🤔 **¿Quieres intentar esta solución?**
• Responde **'sí'** para que te guíe paso a paso
• Responde **'no entiendo'** si necesitas más explicación
• Responde **'ya lo intenté'** si ya probaste esto

📋 *Código de incidencia: {incident_code}*"""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=solution_message)],
                "current_step": "verify_solution",
                "awaiting_user_input": True,
                "solution_provided": True
            }
        )
    
    def _ask_for_problem_details(self, state: EroskiState, phase2_result: SpecificProblemDecision) -> Command:
        """Pedir más detalles sobre el problema"""
        
        incident_type = state.get("incident_type", "equipo")
        
        if phase2_result.problem_description == "otros":
            # Problema no catalogado
            message = f"""🔍 **Problema con {incident_type.title()} - Información adicional necesaria**

He identificado que tienes un problema con **{incident_type}**, pero necesito más detalles específicos para ayudarte mejor.

📋 **Por favor, describe:**
• ¿Qué síntomas observas exactamente?
• ¿Cuándo empezó el problema?
• ¿Has intentado algo para solucionarlo?
• ¿Aparece algún mensaje de error?

💡 *Cuanto más específico seas, mejor podré ayudarte*"""
        
        else:
            # Información insuficiente para identificar problema específico
            available_problems = self._get_specific_problems_for_type(incident_type)
            
            message = f"""🔍 **Problema con {incident_type.title()} - ¿Cuál es tu caso específico?**

He identificado que el problema es con **{incident_type}**. Para darte la solución exacta, ¿cuál de estos describe mejor tu situación?

{available_problems}

📝 **O describe tu problema con más detalle si no coincide con ninguno de estos.**"""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=message)],
                "current_step": "collect_details",
                "awaiting_user_input": True
            }
        )
    
    # ========== MÉTODOS AUXILIARES ==========
    
    def _get_equipment_types_list(self) -> str:
        """Obtener lista formateada de tipos de equipos"""
        return """
• **Balanza** - Equipos de pesado y etiquetado
• **TPV** - Terminales de punto de venta (cajas)
• **Impresora** - Impresoras de tickets, etiquetas, códigos de barras
• **Ordenador** - PCs, terminales, tablets
• **Red** - Problemas de conectividad, WiFi, internet
• **Teléfono** - Teléfonos fijos, intercomunicadores
• **Otros** - Otros equipos técnicos
"""
    
    def _get_specific_problems_for_type(self, incident_type: str) -> str:
        """Obtener problemas específicos para un tipo de equipo"""
        
        problems_catalog = {
            "balanza": """
• **La balanza no imprime etiquetas**
• **La balanza no se enciende**
• **El peso mostrado es incorrecto**
• **Error de calibración**
• **La pantalla no responde**
• **Las etiquetas salen en blanco**
• **Problemas con el teclado de la balanza**
""",
            "tpv": """
• **El TPV no enciende**
• **No lee tarjetas de crédito**
• **Error en el cajón de efectivo**
• **Problemas con el lector de códigos de barras**
• **La pantalla táctil no responde**
• **No imprime tickets**
• **Error de comunicación con el servidor**
""",
            "impresora": """
• **No imprime documentos**
• **Impresión borrosa o con líneas**
• **Atasco de papel**
• **Error de tinta o tóner**
• **No reconoce el formato de papel**
• **Problemas de conectividad**
""",
            "red": """
• **Sin conexión a internet**
• **WiFi muy lento**
• **No puede acceder a aplicaciones corporativas**
• **Error de conexión intermitente**
• **Problemas con VPN**
""",
            "ordenador": """
• **El ordenador no enciende**
• **Pantalla azul o error del sistema**
• **Muy lento al trabajar**
• **No reconoce dispositivos USB**
• **Problemas con aplicaciones específicas**
""",
            "telefono": """
• **No hay línea telefónica**
• **No se escucha al otro lado**
• **Problemas con extensiones internas**
• **Error en el sistema de intercomunicación**
"""
        }
        
        return problems_catalog.get(incident_type, "• Problemas técnicos diversos")
    
    def _format_conversation_history(self, state: EroskiState) -> str:
        """Formatear historial de conversación"""
        messages = state.get("messages", [])
        formatted = []
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted.append(f"👤 Usuario: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted.append(f"🤖 Asistente: {msg.content}")
        
        return "\n".join(formatted) if formatted else "Sin historial previo"
    
    def _get_last_user_message(self, state: EroskiState) -> str:
        """Obtener último mensaje del usuario"""
        messages = state.get("messages", [])
        
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return msg.content
        
        return ""

# =============================================================================
# INTEGRACIÓN CON EL NODO CLASSIFY
# =============================================================================

async def execute_two_phase_classification(state: EroskiState) -> Command:
    """
    Función principal para ejecutar clasificación en dos fases
    
    Args:
        state: Estado actual con EroskiState
        
    Returns:
        Command con estado actualizado
    """
    
    classifier = TwoPhaseClassifier()
    return await classifier.classify_incident(state)
