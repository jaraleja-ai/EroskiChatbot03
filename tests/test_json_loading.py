# =====================================================
# nodes/classify_llm_driven.py - Nodo de Clasificación LLM-Driven
# =====================================================
"""
Nodo de clasificación inteligente dirigido completamente por LLM.

FUNCIONALIDAD:
1. LLM analiza el historial de mensajes para identificar incidencias
2. Identifica tipo de incidencia usando keywords del archivo JSON
3. Hace preguntas específicas para detectar el problema exacto
4. Propone solución cuando identifica el problema
5. Escala a supervisor si no puede identificar la incidencia
6. Mantiene conversación natural durante todo el proceso
"""

from typing import Dict, Any, Optional, List, Union
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging
import json
import re
from pathlib import Path

from models.eroski_state import EroskiState
from nodes.base_node import BaseNode
from utils.llm.providers import get_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from config.incident_config import IncidentConfigLoader


# =============================================================================
# MODELOS DE DATOS
# =============================================================================

class ClassificationDecision(BaseModel):
    """Decisión del LLM sobre la clasificación de incidencia"""
    
    # Estado de la clasificación
    incident_identified: bool = Field(description="Si se ha identificado el tipo de incidencia")
    problem_identified: bool = Field(description="Si se ha identificado el problema específico")
    solution_ready: bool = Field(description="Si se puede proporcionar una solución")
    needs_escalation: bool = Field(description="Si debe escalarse a supervisor")
    wants_to_cancel: bool = Field(description="Si el usuario quiere cancelar")
    
    # Información identificada
    incident_type: Optional[str] = Field(description="Tipo de incidencia identificada", default=None)
    specific_problem: Optional[str] = Field(description="Problema específico identificado", default=None)
    proposed_solution: Optional[str] = Field(description="Solución propuesta", default=None)
    confidence_level: float = Field(description="Confianza en la identificación (0-1)", default=0.0)
    
    # Próxima acción
    next_action: str = Field(description="Próxima acción: ask_questions, provide_solution, escalate, complete")
    message_to_user: str = Field(description="Mensaje natural para el usuario")
    questions_to_ask: List[str] = Field(description="Preguntas específicas si necesita más información", default=[])
    
    # Información extraída del último mensaje
    keywords_detected: List[str] = Field(description="Keywords detectadas en el mensaje", default=[])
    urgency_level: int = Field(description="Nivel de urgencia detectado (1-4)", default=2)
    
    # ✅ NUEVO: Información histórica
    historical_info_found: Optional[str] = Field(description="Información relevante encontrada en el historial", default=None)


# =============================================================================
# NODO PRINCIPAL CLASSIFY LLM-DRIVEN
# =============================================================================

class LLMDrivenClassifyNode(BaseNode):
    """
    Nodo de clasificación completamente dirigido por LLM.
    
    CARACTERÍSTICAS:
    - Análisis inteligente del historial de mensajes
    - Identificación automática usando keywords del JSON
    - Conversación natural para recopilar información faltante
    - Propuesta de soluciones automáticas
    - Escalación inteligente cuando no puede resolver
    """
    
    def __init__(self):
        super().__init__("classify")
        self.max_attempts = 8  # Más intentos para conversación detallada
        self.llm = get_llm()
        
        # Cargar configuración de incidencias
        self.incident_loader = IncidentConfigLoader()
        self.incident_types = self._load_incident_types()
        
        # Parser para decisiones LLM
        self.parser = JsonOutputParser(pydantic_object=ClassificationDecision)
        
        # Sistema principal de conversación
        self.classification_prompt = self._build_classification_prompt()
        
        # ✅ NUEVO: Prompt especializado para análisis histórico
        self.historical_analysis_prompt = self._build_historical_analysis_prompt()
        
    def get_required_fields(self) -> List[str]:
        return ["messages", "authenticated"]
    
    def get_actor_description(self) -> str:
        return "Clasifico incidencias técnicas usando IA conversacional y propongo soluciones"
    
    def _load_incident_types(self) -> Dict[str, Any]:
        """Cargar tipos de incidencia desde el archivo JSON"""
        try:
            # Usar directamente el archivo JSON sin IncidentConfigLoader por ahora
            json_path = Path("config/eroski_incidents.json")
            if not json_path.exists():
                json_path = Path("scripts/eroski_incidents.json")
            
            if json_path.exists():
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Verificar si usa la estructura "tipo_incidente" o "incident_types"
                    if "tipo_incidente" in data:
                        return data["tipo_incidente"]
                    elif "incident_types" in data:
                        return data["incident_types"]
                    else:
                        self.logger.warning("❌ Estructura de JSON no reconocida")
                        return {}
                        
            self.logger.warning("❌ No se pudo cargar archivo de incidencias")
            return {}
            
        except Exception as e:
            self.logger.error(f"❌ Error cargando tipos de incidencia: {e}")
            return {}
    
    def _build_classification_prompt(self) -> PromptTemplate:
        """Construir prompt principal para clasificación LLM-driven"""
        return PromptTemplate(
            template="""Eres un asistente experto en clasificación de incidencias técnicas para Eroski.

Tu misión es analizar los mensajes del usuario para:
1. IDENTIFICAR si describe una incidencia técnica
2. CLASIFICAR el tipo de incidencia usando las categorías disponibles
3. DETECTAR el problema específico dentro de ese tipo
4. PROPONER una solución si la conoces
5. HACER PREGUNTAS inteligentes si necesitas más información
6. ESCALAR a supervisor si no puedes identificar la incidencia

TIPOS DE INCIDENCIAS DISPONIBLES:
{incident_types_info}

HISTORIAL COMPLETO DE MENSAJES DEL USUARIO:
{conversation_history}

DATOS DEL EMPLEADO AUTENTICADO:
- Nombre: {employee_name}
- Tienda: {store_name}
- Sección: {section}

ESTADO ACTUAL DE CLASIFICACIÓN:
- Intentos realizados: {attempt_number}
- Tipo identificado anteriormente: {previous_incident_type}
- Problema identificado: {previous_problem}

ÚLTIMO MENSAJE DEL USUARIO:
"{user_message}"

INSTRUCCIONES PARA TU ANÁLISIS:

1. **ANALIZAR TODO EL HISTORIAL**: No solo el último mensaje, sino toda la conversación
2. **IDENTIFICAR KEYWORDS**: Busca palabras clave que coincidan con los tipos de incidencia
3. **EVALUAR CONTEXTO**: Considera la sección del empleado (ej: si está en "Caja" y habla de problemas, probablemente sea TPV)
4. **SER ESPECÍFICO**: No te conformes con identificar solo el tipo, busca el problema exacto
5. **PROPONER SOLUCIONES**: Si identificas el problema específico, proporciona la solución correspondiente
6. **HACER PREGUNTAS INTELIGENTES**: Si falta información, haz preguntas específicas y útiles
7. **ESCALAR CUANDO SEA NECESARIO**: Si después de varios intentos no puedes clasificar, escala

CRITERIOS DE ESCALACIÓN:
- Han pasado más de 5 intentos sin identificar claramente la incidencia
- El usuario describe algo que no está en ninguna categoría
- El problema parece muy técnico o complejo
- El usuario está frustrado o pide hablar con un supervisor

RESPONDE ÚNICAMENTE CON JSON VÁLIDO incluyendo TODOS los campos:
{{
    "incident_identified": false,
    "problem_identified": false,
    "solution_ready": false,
    "needs_escalation": false,
    "wants_to_cancel": false,
    "incident_type": null,
    "specific_problem": null,
    "proposed_solution": null,
    "confidence_level": 0.0,
    "next_action": "ask_questions",
    "message_to_user": "Mensaje natural aquí",
    "questions_to_ask": [],
    "keywords_detected": [],
    "urgency_level": 2
}}

⚠️ IMPORTANTE: No uses formato Markdown. Solo responde con JSON puro, sin símbolos adicionales.
""",
            input_variables=[
                "incident_types_info", "conversation_history", "employee_name", 
                "store_name", "section"
            ]
        )
    
    def _build_historical_analysis_prompt(self) -> PromptTemplate:
        """Construir prompt especializado para análisis histórico inicial"""
        return PromptTemplate(
            template="""Eres un asistente experto en clasificación de incidencias técnicas para Eroski.

Esta es tu PRIMERA INTERACCIÓN con el usuario en el nodo de clasificación. Tu tarea es analizar TODO EL HISTORIAL de mensajes para:

1. **IDENTIFICAR** si el usuario ya mencionó información sobre una incidencia técnica
2. **EXTRAER** toda la información relevante que ya proporcionó
3. **CLASIFICAR** la incidencia si tienes suficiente información
4. **CONTINUAR** la conversación de forma natural sin repetir preguntas

TIPOS DE INCIDENCIAS DISPONIBLES:
{incident_types_info}

REGLAS ESTRICTAS:
❌ NO inventes soluciones que no estén en el archivo de configuración
❌ NO des consejos genéricos si no tienes la solución específica
✅ SOLO usa las soluciones que aparecen en el archivo para cada problema
✅ Si no encuentras el problema específico en el archivo, pregunta más detalles
✅ Si después de preguntar no puedes clasificar, ESCALA al supervisor

DATOS DEL EMPLEADO AUTENTICADO:
- Nombre: {employee_name}
- Tienda: {store_name}
- Sección: {section}

HISTORIAL COMPLETO DE MENSAJES (ANALIZA TODO):
{conversation_history}

INSTRUCCIONES PARA TU ANÁLISIS:

🔍 **ANÁLISIS HISTÓRICO OBLIGATORIO:**
- Revisa TODOS los mensajes del usuario desde el principio
- Busca cualquier mención de problemas, equipos, errores, fallos
- Identifica keywords que coincidan EXACTAMENTE con los tipos de incidencia
- Considera el contexto de la sección del empleado

🎯 **ESTRATEGIAS DE IDENTIFICACIÓN:**
1. **Keywords directas**: "balanza", "TPV", "impresora", "red", etc.
2. **Problemas descritos**: "no funciona", "error", "no imprime", "no enciende"
3. **Contexto seccional**: Si está en "carnicería" y menciona problemas, probablemente balanza
4. **Urgencia implícita**: Palabras como "urgente", "crítico", "parado"

🧠 **LÓGICA DE DECISIÓN ESTRICTA:**
- Si identificas el tipo Y el problema ESTÁ en el archivo → proponer la solución DEL ARCHIVO
- Si identificas el tipo pero el problema NO ESTÁ en el archivo → hacer preguntas ESPECÍFICAS basadas en los problemas disponibles en el archivo
- Si NO identificas el tipo → hacer preguntas abiertas para clasificar
- Si es confuso o no está catalogado → preparar para escalación

✅ **PREGUNTAS ESPECÍFICAS OBLIGATORIAS:**
Cuando identifiques el tipo pero no el problema específico, debes:
1. Listar los problemas específicos disponibles en el archivo para ese tipo
2. Preguntar directamente cuál de esos problemas coincide
3. No hacer preguntas genéricas como "cuéntame más detalles"

EJEMPLO CORRECTO:
Usuario menciona "balanza no funciona" → 
Respuesta: "Entiendo que hay un problema con la balanza. Según nuestro catálogo, los problemas más comunes con balanzas son:
• La balanza no imprime las etiquetas
• La balanza no se enciende  
• El precio que imprime en la etiqueta no es correcto
• La pantalla no responde
• Error de calibración
• Etiquetas salen en blanco

¿Cuál de estos describe mejor tu problema?"

✅ **EJEMPLO DE ANÁLISIS CORRECTO:**
Usuario menciona "balanza no imprime etiquetas" → 
1. Identifica tipo: "balanza"
2. Busca problema "no imprime etiquetas" en el archivo balanza
3. Si está: propone la solución exacta del archivo
4. Si no está: pregunta más detalles específicos sobre balanzas

RESPONDE ÚNICAMENTE CON JSON VÁLIDO incluyendo TODOS los campos:
{{
    "incident_identified": false,
    "problem_identified": false,
    "solution_ready": false,
    "needs_escalation": false,
    "wants_to_cancel": false,
    "incident_type": null,
    "specific_problem": null,
    "proposed_solution": null,
    "confidence_level": 0.0,
    "next_action": "ask_questions",
    "message_to_user": "Mensaje natural aquí",
    "questions_to_ask": [],
    "keywords_detected": [],
    "urgency_level": 2,
    "historical_info_found": "Descripción de la información encontrada en el historial"
}}

⚠️ IMPORTANTE: No uses formato Markdown. Solo responde con JSON puro, sin símbolos adicionales.
""",
            input_variables=[
                "incident_types_info", "conversation_history", "employee_name", 
                "store_name", "section", "attempt_number", "previous_incident_type",
                "previous_problem", "user_message"
            ]
        )
    
    def _format_incident_types_for_llm(self) -> str:
        """Formatear tipos de incidencia para el LLM"""
        if not self.incident_types:
            return "No hay tipos de incidencia configurados"
        
        formatted = []
        for incident_id, incident_data in self.incident_types.items():
            name = incident_data.get("name", incident_id)
            description = incident_data.get("description", "")
            keywords = incident_data.get("keywords", [])
            
            # Verificar si tiene la estructura "problemas" (nueva) o "common_issues" (antigua)
            problems = []
            if "problemas" in incident_data:
                # Nueva estructura con problemas y soluciones
                problems = list(incident_data["problemas"].keys())[:3]
            elif "common_issues" in incident_data:
                # Estructura antigua
                problems = incident_data["common_issues"][:3]
            
            urgency = incident_data.get("urgency_level", 2)
            
            formatted.append(f"""
**{incident_id.upper()}** - {name}
- Descripción: {description}
- Keywords: {', '.join(keywords)}
- Urgencia: {urgency}/4
- Problemas comunes: {', '.join(problems)}{"..." if len(problems) > 3 else ""}
""")
        
        return "\n".join(formatted)
    
    def _get_specific_solution(self, incident_type: str, problem_description: str) -> Optional[str]:
        """
        Buscar solución específica en el archivo JSON para un problema dado.
        
        Args:
            incident_type: Tipo de incidencia (ej: "balanza")
            problem_description: Descripción del problema
            
        Returns:
            Solución específica o None si no se encuentra
        """
        if incident_type not in self.incident_types:
            return None
        
        incident_data = self.incident_types[incident_type]
        
        # Verificar si tiene la estructura "problemas" (nueva)
        if "problemas" in incident_data:
            problems = incident_data["problemas"]
            
            # Buscar coincidencia exacta o parcial
            problem_lower = problem_description.lower()
            
            for problem_key, solution in problems.items():
                problem_key_lower = problem_key.lower()
                
                # Coincidencia exacta
                if problem_lower == problem_key_lower:
                    return solution
                
                # Coincidencia parcial (palabras clave)
                if any(word in problem_key_lower for word in problem_lower.split() if len(word) > 3):
                    return solution
        
        return None
    
    def _find_best_matching_problem(self, incident_type: str, user_description: str) -> tuple[Optional[str], Optional[str]]:
        """
        Encontrar el problema que mejor coincida con la descripción del usuario.
        
        Args:
            incident_type: Tipo de incidencia
            user_description: Descripción del problema por el usuario
            
        Returns:
            Tupla (problema_identificado, solución) o (None, None)
        """
        if incident_type not in self.incident_types:
            return None, None
        
        incident_data = self.incident_types[incident_type]
        
        if "problemas" not in incident_data:
            return None, None
        
        problems = incident_data["problemas"]
        user_desc_lower = user_description.lower()
        
        best_match = None
        best_solution = None
        best_score = 0
        
        for problem_key, solution in problems.items():
            problem_lower = problem_key.lower()
            
            # Calcular score de coincidencia
            score = 0
            user_words = set(user_desc_lower.split())
            problem_words = set(problem_lower.split())
            
            # Palabras en común
            common_words = user_words.intersection(problem_words)
            if common_words:
                score += len(common_words) * 2
            
            # Substrings en común
            if any(word in problem_lower for word in user_words if len(word) > 3):
                score += 1
            
            if score > best_score:
                best_score = score
                best_match = problem_key
                best_solution = solution
        
        return (best_match, best_solution) if best_score > 0 else (None, None)
    
    def _generate_specific_questions(self, incident_type: str) -> str:
        """
        Generar preguntas específicas basadas en los problemas disponibles en el archivo.
        
        Args:
            incident_type: Tipo de incidencia identificada
            
        Returns:
            Mensaje con preguntas específicas dirigidas
        """
        if incident_type not in self.incident_types:
            return "¿Podrías describir el problema con más detalle?"
        
        incident_data = self.incident_types[incident_type]
        incident_name = incident_data.get("name", incident_type)
        
        # Obtener problemas disponibles
        available_problems = []
        if "problemas" in incident_data:
            available_problems = list(incident_data["problemas"].keys())
        elif "common_issues" in incident_data:
            available_problems = incident_data["common_issues"]
        
        if not available_problems:
            return f"Necesito más información sobre el problema con {incident_name.lower()}. ¿Podrías ser más específico?"
        
        # Crear mensaje con opciones específicas
        message = f"Entiendo que hay un problema con {incident_name.lower()}. "
        
        if len(available_problems) <= 6:
            # Si hay pocas opciones, listarlas todas
            message += "Según nuestro catálogo, los problemas más comunes son:\n\n"
            for i, problem in enumerate(available_problems, 1):
                message += f"• {problem}\n"
            message += f"\n¿Cuál de estos describe mejor tu situación?"
        else:
            # Si hay muchas opciones, mostrar las más relevantes
            message += "Para ayudarte mejor, ¿el problema es que:\n\n"
            # Tomar las primeras 5-6 opciones más comunes
            for i, problem in enumerate(available_problems[:6], 1):
                message += f"• {problem}\n"
            message += f"• Otro problema diferente\n"
            message += f"\n¿Cuál de estas opciones se acerca más a tu situación?"
        
        return message
    
    def _should_generate_specific_questions(self, decision: ClassificationDecision, attempt_number: int) -> bool:
        """
        Determinar si se deben generar preguntas específicas basadas en el archivo.
        
        Args:
            decision: Decisión del LLM
            attempt_number: Número de intento
            
        Returns:
            True si debe generar preguntas específicas
        """
        return (
            decision.incident_identified and 
            decision.incident_type and 
            not decision.problem_identified and
            attempt_number <= 3  # Solo en los primeros intentos
        )
    
    def _generate_targeted_questions(self, state: EroskiState, decision: ClassificationDecision, attempt_number: int) -> Command:
        """
        Generar preguntas dirigidas basadas en los problemas disponibles en el archivo.
        
        Args:
            state: Estado actual
            decision: Decisión del LLM
            attempt_number: Número de intento
            
        Returns:
            Command con preguntas específicas
        """
        
        # Generar mensaje con preguntas específicas
        specific_message = self._generate_specific_questions(decision.incident_type)
        
        # Actualizar datos de clasificación
        classify_data = state.get("classify_data", {})
        classify_data.update({
            "incident_type": decision.incident_type,
            "incident_identified": True,
            "specific_questions_generated": True,
            "questions_source": "archivo_problemas"
        })
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=specific_message)],
                "classify_data": classify_data,
                "classify_attempt_number": attempt_number,
                "current_step": "classify"
            }
        )
    
    def _try_auto_classify_from_file(self, state: EroskiState, decision: ClassificationDecision, attempt_number: int) -> Command:
        """
        Intentar clasificar automáticamente usando el archivo cuando se conoce el tipo pero no el problema.
        
        Args:
            state: Estado actual
            decision: Decisión del LLM
            attempt_number: Número de intento
            
        Returns:
            Command con la acción a tomar
        """
        
        # Obtener historial de mensajes del usuario
        user_messages = []
        for msg in state.get("messages", []):
            if isinstance(msg, HumanMessage):
                user_messages.append(msg.content)
        
        # Combinar todos los mensajes del usuario
        combined_description = " ".join(user_messages)
        
        # Buscar coincidencia en el archivo
        problem_match, solution = self._find_best_matching_problem(
            decision.incident_type, 
            combined_description
        )
        
        if problem_match and solution:
            # ¡Encontramos coincidencia! Proporcionar solución
            solution_message = f"""✅ **Incidencia Identificada: {decision.incident_type}**

📋 **Problema:** {problem_match}

🔧 **Solución:**
{solution}

¿Esta solución resolvió tu problema? Si persiste o necesitas más ayuda, házmelo saber."""
            
            classify_data = state.get("classify_data", {})
            classify_data.update({
                "incident_type": decision.incident_type,
                "specific_problem": problem_match,
                "proposed_solution": solution,
                "solution_source": "archivo_automatico",
                "problem_identified": True,
                "solution_ready": True,
                "completed": True
            })
            
            return Command(
                update={
                    "messages": state["messages"] + [AIMessage(content=solution_message)],
                    "classify_data": classify_data,
                    "current_step": "search_solution",
                    "classification_completed": True
                }
            )
        
        else:
            # No encontramos coincidencia automática, continuar con preguntas
            classify_data = state.get("classify_data", {})
            classify_data.update({
                "incident_type": decision.incident_type,
                "incident_identified": True,
                "auto_classify_attempted": True
            })
            
            return Command(
                update={
                    "messages": state["messages"] + [AIMessage(content=decision.message_to_user)],
                    "classify_data": classify_data,
                    "classify_attempt_number": attempt_number,
                    "current_step": "classify"
                }
            )
    
    def _get_conversation_history(self, state: EroskiState) -> str:
        """Obtener historial de conversación formateado"""
        messages = state.get("messages", [])
        
        # Filtrar solo mensajes del usuario (HumanMessage)
        user_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                user_messages.append(f"Usuario: {msg.content}")
        
        if not user_messages:
            return "No hay mensajes previos del usuario"
        
        return "\n".join(user_messages)
    
    def _get_full_conversation_history(self, state: EroskiState) -> str:
        """Obtener historial completo incluyendo respuestas del bot"""
        messages = state.get("messages", [])
        
        formatted_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                formatted_messages.append(f"👤 Usuario: {msg.content}")
            elif isinstance(msg, AIMessage):
                formatted_messages.append(f"🤖 Bot: {msg.content}")
        
        if not formatted_messages:
            return "No hay historial de conversación"
        
        return "\n".join(formatted_messages)
    
    async def _analyze_historical_messages(self, state: EroskiState) -> Command:
        """
        ✅ NUEVA FUNCIONALIDAD: Analizar mensajes históricos en la primera visita
        
        Esta función se ejecuta solo en el primer intento de clasificación
        para revisar todo el historial y extraer información ya proporcionada.
        """
        
        self.logger.info("🔍 Analizando historial completo para información previa...")
        
        # Preparar datos para el análisis histórico
        auth_data = state.get("auth_data_collected", {})
        
        prompt_input = {
            "incident_types_info": self._format_incident_types_for_llm(),
            "conversation_history": self._get_full_conversation_history(state),
            "employee_name": auth_data.get("name", "No especificado"),
            "store_name": auth_data.get("store_name", "No especificado"),
            "section": auth_data.get("section", "No especificado")
        }
        
        # Ejecutar análisis histórico con LLM
        formatted_prompt = self.historical_analysis_prompt.format(**prompt_input)
        
        self.logger.info("🤖 Ejecutando análisis histórico inicial")
        
        try:
            response = await self.llm.ainvoke(formatted_prompt)
            
            # Parsear respuesta
            decision_data = self.parser.parse(response.content)
            decision = ClassificationDecision(**decision_data)
            
            self.logger.info(f"✅ Análisis histórico completado: {decision.next_action}")
            self.logger.info(f"🔍 Info histórica encontrada: {decision.historical_info_found}")
            
            # Actualizar datos de clasificación con información histórica
            classify_data = {
                "incident_identified": decision.incident_identified,
                "problem_identified": decision.problem_identified,
                "solution_ready": decision.solution_ready,
                "confidence_level": decision.confidence_level,
                "keywords_detected": decision.keywords_detected,
                "urgency_level": decision.urgency_level,
                "historical_info_found": decision.historical_info_found,
                "last_analysis": datetime.now().isoformat()
            }
            
            # Agregar información específica si se identificó
            if decision.incident_type:
                classify_data["incident_type"] = decision.incident_type
            if decision.specific_problem:
                classify_data["specific_problem"] = decision.specific_problem
            if decision.proposed_solution:
                classify_data["proposed_solution"] = decision.proposed_solution
            
            # Procesar según la decisión del análisis histórico
            if decision.next_action == "provide_solution" and decision.solution_ready:
                return self._provide_solution_and_complete(state, decision)
            
            elif decision.needs_escalation:
                return self._escalate_to_supervisor(state)
            
            else:
                # Continuar conversación con información del análisis histórico
                return Command(
                    update={
                        "messages": state["messages"] + [AIMessage(content=decision.message_to_user)],
                        "classify_data": classify_data,
                        "classify_attempt_number": 1,
                        "current_step": "classify"
                    }
                )
                
        except Exception as e:
            self.logger.error(f"❌ Error en análisis histórico: {e}")
            
            # Fallback: continuar con análisis normal
            return Command(
                update={
                    "messages": state["messages"] + [AIMessage(content="Veo que mencionaste un problema. ¿Podrías contarme más detalles sobre qué está ocurriendo exactamente?")],
                    "classify_data": {"last_analysis": datetime.now().isoformat()},
                    "classify_attempt_number": 1,
                    "current_step": "classify"
                }
            )
    
    def _is_classification_complete(self, state: EroskiState) -> bool:
        """Verificar si la clasificación está completa"""
        classify_data = state.get("classify_data", {})
        
        return (
            classify_data.get("incident_identified", False) and
            classify_data.get("problem_identified", False) and
            classify_data.get("solution_ready", False)
        )
    
    def _should_escalate(self, state: EroskiState, attempt_number: int) -> bool:
        """Determinar si se debe escalar a supervisor"""
        classify_data = state.get("classify_data", {})
        
        # Escalación automática por número de intentos
        if attempt_number >= 6:
            return True
        
        # Escalación si el LLM lo indica
        if classify_data.get("needs_escalation", False):
            return True
        
        # Escalación si el usuario lo solicita explícitamente
        last_message = self._get_last_user_message(state)
        escalation_keywords = ["supervisor", "jefe", "responsable", "hablar con alguien mas", "no me ayudas"]
        
        if any(keyword in last_message.lower() for keyword in escalation_keywords):
            return True
        
        return False
    
    def _get_last_user_message(self, state: EroskiState) -> str:
        """Obtener el último mensaje del usuario"""
        messages = state.get("messages", [])
        
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                return msg.content
        
        return ""
    
    async def execute(self, state: EroskiState) -> Command:
        """
        Ejecutar clasificación LLM-driven.
        
        Args:
            state: Estado actual del workflow
            
        Returns:
            Command con la siguiente acción
        """
        
        self.logger.info("🏅" * 50)
        self.logger.info(f"🌄 Entrando en clasificación LLM-driven")
        
        try:
            self.logger.info("🔍 Iniciando clasificación de incidencia")
            
            # 1. Verificar si ya está completo
            if self._is_classification_complete(state):
                return self._proceed_to_next_step(state)
            
            # 2. Preparar datos
            attempt_number = state.get("classify_attempt_number", 0) + 1
            
            # 3. ✅ NUEVA FUNCIONALIDAD: Análisis inicial del historial
            if attempt_number == 1:
                self.logger.info("🔍 Primera visita: analizando historial completo")
                return await self._analyze_historical_messages(state)
            
            # 4. Verificar escalación
            if self._should_escalate(state, attempt_number):
                return self._escalate_to_supervisor(state)
            
            # 5. Verificar cancelación
            if self._wants_to_cancel(state):
                return self._handle_cancellation(state)
            
            # 6. Ejecutar análisis LLM
            decision = await self._analyze_with_llm(state, attempt_number)
            
            # 7. Procesar decisión
            return await self._process_llm_decision(state, decision, attempt_number)
            
        except Exception as e:
            self.logger.error(f"❌ Error en clasificación: {e}")
            return self._handle_error(state, str(e))
    
    async def _analyze_with_llm(self, state: EroskiState, attempt_number: int) -> ClassificationDecision:
        """Analizar con LLM para tomar decisión (para intentos posteriores al primero)"""
        
        # Preparar datos para el prompt
        auth_data = state.get("auth_data_collected", {})
        classify_data = state.get("classify_data", {})
        user_message = self._get_last_user_message(state)
        
        # Crear prompt para análisis continuo (no histórico)
        prompt_input = {
            "incident_types_info": self._format_incident_types_for_llm(),
            "conversation_history": self._get_conversation_history(state),
            "employee_name": auth_data.get("name", "No especificado"),
            "store_name": auth_data.get("store_name", "No especificado"),
            "section": auth_data.get("section", "No especificado"),
            "attempt_number": attempt_number,
            "previous_incident_type": classify_data.get("incident_type"),
            "previous_problem": classify_data.get("specific_problem"),
            "user_message": user_message
        }
        
        # Usar un prompt más simple para intentos continuos
        simple_prompt = PromptTemplate(
            template="""Continúa analizando la consulta del usuario para clasificar la incidencia.

INFORMACIÓN PREVIA IDENTIFICADA:
- Tipo de incidencia: {previous_incident_type}
- Problema específico: {previous_problem}
- Intento número: {attempt_number}

TIPOS DE INCIDENCIAS DISPONIBLES:
{incident_types_info}

ÚLTIMO MENSAJE DEL USUARIO:
"{user_message}"

CONTEXTO DEL EMPLEADO:
- Nombre: {employee_name}
- Sección: {section}

INSTRUCCIONES CRÍTICAS:
1. Si ya identificaste el tipo, enfócate en el problema específico
2. ❌ NO hagas preguntas genéricas como "cuéntame más detalles"
3. ✅ Si no sabes el problema específico, lista los problemas disponibles del archivo para ese tipo y pregunta cuál coincide
4. ✅ Si ya tienes el problema específico, proporciona la solución DEL ARCHIVO
5. Si el usuario confirma o rechaza algo, actúa en consecuencia
6. Si es confuso después de varios intentos, considera escalación

EJEMPLO DE BUENA PREGUNTA ESPECÍFICA:
"Entiendo que hay un problema con la balanza. ¿El problema es que:
• La balanza no imprime las etiquetas
• La balanza no se enciende
• El precio en la etiqueta es incorrecto
• La pantalla no responde
¿Cuál de estos describe tu situación?"

RESPONDE ÚNICAMENTE CON JSON VÁLIDO:
{{
    "incident_identified": false,
    "problem_identified": false,
    "solution_ready": false,
    "needs_escalation": false,
    "wants_to_cancel": false,
    "incident_type": null,
    "specific_problem": null,
    "proposed_solution": null,
    "confidence_level": 0.0,
    "next_action": "ask_questions",
    "message_to_user": "Mensaje natural aquí",
    "questions_to_ask": [],
    "keywords_detected": [],
    "urgency_level": 2
}}""",
            input_variables=[
                "incident_types_info", "employee_name", "section", 
                "attempt_number", "previous_incident_type", "previous_problem", "user_message"
            ]
        )
        
        # Ejecutar LLM
        formatted_prompt = simple_prompt.format(**prompt_input)
        
        self.logger.info(f"🤖 Ejecutando análisis LLM continuo (intento {attempt_number})")
        
        response = await self.llm.ainvoke(formatted_prompt)
        
        # Parsear respuesta
        try:
            decision_data = self.parser.parse(response.content)
            decision = ClassificationDecision(**decision_data)
            
            self.logger.info(f"✅ Decisión LLM: {decision.next_action}")
            return decision
            
        except Exception as e:
            self.logger.error(f"❌ Error parseando respuesta LLM: {e}")
            self.logger.error(f"Respuesta raw: {response.content}")
            
            # Fallback: crear decisión básica
            return ClassificationDecision(
                next_action="ask_questions",
                message_to_user="Disculpa, necesito más información. ¿Podrías describir el problema con más detalle?",
                confidence_level=0.0
            )
    
    async def _process_llm_decision(self, state: EroskiState, decision: ClassificationDecision, attempt_number: int) -> Command:
        """Procesar la decisión del LLM"""
        
        # Actualizar datos de clasificación
        classify_data = state.get("classify_data", {})
        
        # Actualizar con nueva información
        if decision.incident_type:
            classify_data["incident_type"] = decision.incident_type
        if decision.specific_problem:
            classify_data["specific_problem"] = decision.specific_problem
        if decision.proposed_solution:
            classify_data["proposed_solution"] = decision.proposed_solution
        
        classify_data.update({
            "incident_identified": decision.incident_identified,
            "problem_identified": decision.problem_identified,
            "solution_ready": decision.solution_ready,
            "confidence_level": decision.confidence_level,
            "keywords_detected": decision.keywords_detected,
            "urgency_level": decision.urgency_level,
            "last_analysis": datetime.now().isoformat()
        })
        
        # Procesar según la acción
        if decision.next_action == "escalate" or decision.needs_escalation:
            return self._escalate_to_supervisor(state)
        
        elif decision.next_action == "provide_solution" and decision.solution_ready:
            return self._provide_solution_and_complete(state, decision)
        
        elif decision.next_action == "complete" and decision.solution_ready:
            return self._provide_solution_and_complete(state, decision)
        
        # ✅ NUEVO: Si se identifica tipo pero no problema específico, buscar en archivo
        elif decision.incident_identified and decision.incident_type and not decision.problem_identified:
            return self._try_auto_classify_from_file(state, decision, attempt_number)
        
        # ✅ NUEVO: Si necesita más información, generar preguntas específicas del archivo
        elif self._should_generate_specific_questions(decision, attempt_number):
            return self._generate_targeted_questions(state, decision, attempt_number)
        
        else:
            # Continuar conversación
            return Command(
                update={
                    "messages": state["messages"] + [AIMessage(content=decision.message_to_user)],
                    "classify_data": classify_data,
                    "classify_attempt_number": attempt_number,
                    "current_step": "classify"
                }
            )
    
    def _provide_solution_and_complete(self, state: EroskiState, decision: ClassificationDecision) -> Command:
        """Proporcionar solución y completar clasificación"""
        
        classify_data = state.get("classify_data", {})
        incident_type = decision.incident_type or classify_data.get("incident_type")
        
        # ✅ NUEVO: Buscar solución en el archivo JSON
        solution_from_file = None
        if incident_type and decision.specific_problem:
            solution_from_file = self._get_specific_solution(incident_type, decision.specific_problem)
        
        # Usar solución del archivo si existe, sino la del LLM
        final_solution = solution_from_file or decision.proposed_solution
        
        if not final_solution:
            # Si no hay solución específica, escalamos
            return self._escalate_to_supervisor(state)
        
        # Crear mensaje completo con solución
        solution_message = f"""✅ **Incidencia Identificada: {incident_type}**

📋 **Problema:** {decision.specific_problem}

🔧 **Solución:**
{final_solution}

¿Esta solución resolvió tu problema? Si persiste o necesitas más ayuda, házmelo saber."""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=solution_message)],
                "classify_data": {
                    **classify_data, 
                    "completed": True,
                    "solution_provided": final_solution,
                    "solution_source": "archivo" if solution_from_file else "llm"
                },
                "incident_type": incident_type,
                "current_step": "search_solution",  # Pasar al siguiente nodo
                "classification_completed": True
            }
        )
    
    def _escalate_to_supervisor(self, state: EroskiState) -> Command:
        """Escalar a supervisor"""
        
        escalation_message = """🔝 **Escalando a Supervisor**

No he podido identificar completamente tu incidencia o necesitas atención especializada. 

Te estoy conectando con un supervisor que podrá ayudarte mejor. Mientras tanto, ten preparada la siguiente información:
- Descripción detallada del problema
- Qué intentaste hacer cuando ocurrió
- Si hay códigos de error visibles
- Número de serie del equipo (si aplica)

Un supervisor se pondrá en contacto contigo pronto."""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=escalation_message)],
                "current_step": "escalate",
                "escalation_reason": "classification_failed",
                "escalation_data": state.get("classify_data", {})
            }
        )
    
    def _proceed_to_next_step(self, state: EroskiState) -> Command:
        """Proceder al siguiente paso del workflow"""
        
        classify_data = state.get("classify_data", {})
        
        completion_message = f"""✅ **Clasificación Completada**

He identificado tu incidencia como: **{classify_data.get('incident_type', 'N/A')}**

Ahora voy a buscar soluciones específicas para tu problema."""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=completion_message)],
                "current_step": "search_solution",
                "incident_type": classify_data.get("incident_type"),
                "classification_completed": True
            }
        )
    
    def _wants_to_cancel(self, state: EroskiState) -> bool:
        """Verificar si el usuario quiere cancelar"""
        last_message = self._get_last_user_message(state).lower()
        cancel_keywords = ["cancelar", "salir", "terminar", "no quiero", "olvídalo"]
        
        return any(keyword in last_message for keyword in cancel_keywords)
    
    def _handle_cancellation(self, state: EroskiState) -> Command:
        """Manejar cancelación del usuario"""
        
        cancel_message = """❌ **Proceso Cancelado**

Entiendo que no quieres continuar con el reporte de incidencia.

Si cambias de opinión o tienes otro problema, puedes volver a iniciar el proceso en cualquier momento.

¡Que tengas un buen día!"""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=cancel_message)],
                "current_step": "finalize",
                "conversation_ended": True,
                "cancellation_reason": "user_request"
            }
        )
    
    def _handle_error(self, state: EroskiState, error_message: str) -> Command:
        """Manejar errores de manera elegante"""
        
        error_response = """⚠️ **Error Temporal**

Ha ocurrido un problema técnico durante la clasificación de tu incidencia.

Por favor, intenta describir tu problema de nuevo o solicita hablar con un supervisor.

Error técnico registrado para nuestro equipo de sistemas."""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=error_response)],
                "current_step": "escalate",
                "error_occurred": True,
                "error_details": error_message
            }
        )


# =============================================================================
# FUNCIÓN PARA CREAR INSTANCIA
# =============================================================================

async def llm_driven_classify_node(state: EroskiState) -> EroskiState:
    """
    Función wrapper para LangGraph - Nodo Classify LLM-driven
    
    Args:
        state: Estado actual como dict
        
    Returns:
        Estado actualizado como dict
    """
    
    # Crear instancia del nodo
    node = LLMDrivenClassifyNode()
    
    # Ejecutar el nodo (retorna Command)
    command = await node.execute(state)
    
    # Aplicar las actualizaciones al estado
    updated_state = {**state, **command.update}
    
    # Logging para verificar actualizaciones
    logging.getLogger("Node.classify").info("🔍 === CLASIFICACIÓN: ACTUALIZACIONES APLICADAS ===")
    for key, value in command.update.items():
        logging.getLogger("Node.classify").info(f"🔧 {key}: {value}")
    logging.getLogger("Node.classify").info("🔍 === FIN ACTUALIZACIONES CLASIFICACIÓN ===")
    
    return updated_state


__all__ = ["llm_driven_classify_node", "LLMDrivenClassifyNode"]