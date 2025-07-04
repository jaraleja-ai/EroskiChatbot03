# =====================================================
# nodes/classify_llm_driven.py - Nodo de Clasificación LLM-Driven Refactorizado
# =====================================================
"""
Nodo de clasificación inteligente dirigido completamente por LLM.

REFACTORIZACIÓN:
- Uso de clases helper especializadas
- Separación clara de responsabilidades
- Código más mantenible y testeable
- Orquestación centralizada en el nodo principal

HELPERS UTILIZADOS:
- IncidentCodeManager: Gestión de códigos únicos
- SolutionSearcher: Búsqueda de soluciones en archivo
- ConfirmationLLMHandler: Interpretación inteligente de confirmaciones
- IncidentPersistence: Persistencia en archivo JSON
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
from utils.two_phase_classifier import execute_two_phase_classification
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from config.incident_config import IncidentConfigLoader


# ✅ NUEVO: Importar helpers especializados
from utils.incident_helpers import (
    IncidentCodeManager,
    SolutionSearcher, 
    ConfirmationLLMHandler,
    IncidentPersistence,
    IncidentHelpersFactory,
    ConfirmationDecision
)

# Eliminar todos los handlers del root logger
logging.basicConfig(level=logging.WARNING)  # Solo muestra warning, error y critical

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
    
    # ✅ NUEVO: Análisis de progreso
    progress_assessment: str = Field(description="Evaluación del progreso hacia la solución", default="unknown")
    new_information_provided: bool = Field(description="Si el usuario proporcionó información nueva", default=False)
    questions_already_asked: List[str] = Field(description="Preguntas que ya se han hecho anteriormente", default=[])
    stuck_in_loop: bool = Field(description="Si está atascado en un bucle sin progreso", default=False)
class ClassifyConfirmationDecision(BaseModel):
    """DEPRECATED - Usar ConfirmationDecision de utils.incident_helpers"""
    pass


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
        
    # ✅ NUEVO: Archivo de incidencias ANTES de inicializar helpers
        self.incidents_file = Path("incidents_database.json")

        # ✅ ORDEN CORRECTO: PRIMERO inicializar helpers
        self.helpers = {}
        self._initialize_helpers()

        # ✅ CREAR REFERENCIAS DIRECTAS A HELPERS
        self.code_manager = self.helpers.get("code_manager")
        self.solution_searcher = self.helpers.get("solution_searcher") 
        self.confirmation_handler = self.helpers.get("confirmation_handler")
        self.persistence_manager = self.helpers.get("persistence_manager")
        
        # Parser para decisiones LLM
        self.parser = JsonOutputParser(pydantic_object=ClassificationDecision)
        self.confirmation_parser = JsonOutputParser(pydantic_object=ClassifyConfirmationDecision)
        
        # Sistema principal de conversación
        self.classification_prompt = self._build_classification_prompt()
        
        # ✅ NUEVO: Prompt especializado para análisis histórico
        self.historical_analysis_prompt = self._build_historical_analysis_prompt()
        
        # ✅ NUEVO: Prompt para confirmaciones inteligentes
        self.confirmation_prompt = self._build_confirmation_prompt()
        
        # ✅ NUEVO: Archivo de incidencias
        self.incidents_file = Path("incidents_database.json")

        
    def _initialize_helpers(self):
        """
        ✅ NUEVO MÉTODO: Inicializar todos los helpers usando la factory
        """
        try:
            # Crear helpers usando factory
            self.helpers = IncidentHelpersFactory.create_all_helpers(
                incident_types=self.incident_types,
                incidents_file=self.incidents_file
            )
            
            self.logger.info(f"✅ Helpers inicializados: {list(self.helpers.keys())}")
            
        except Exception as e:
            self.logger.error(f"❌ Error inicializando helpers: {e}")
            # Crear helpers individuales como fallback
            self._create_fallback_helpers()

    def _create_fallback_helpers(self):
        """
        ✅ NUEVO MÉTODO: Crear helpers individuales si falla la factory
        """
        try:
            self.helpers = {
                "code_manager": IncidentCodeManager(self.incidents_file),
                "solution_searcher": SolutionSearcher(self.incident_types),
                "confirmation_handler": ConfirmationLLMHandler(),
                "persistence_manager": IncidentPersistence(self.incidents_file)
            }
            
            self.logger.info("✅ Helpers fallback creados")
            
        except Exception as e:
            self.logger.error(f"❌ Error en helpers fallback: {e}")
            # Crear helpers mínimos para evitar errores
            self.helpers = {
                "code_manager": None,
                "solution_searcher": None,
                "confirmation_handler": None,
                "persistence_manager": None
            }



    def get_required_fields(self) -> List[str]:
        return ["messages", "authenticated"]
    
    def get_actor_description(self) -> str:
        return "Clasifico incidencias técnicas usando IA conversacional y propongo soluciones"
    
    def _load_incident_types(self) -> Dict[str, Any]:
        """Cargar tipos de incidencia desde el archivo JSON"""
        try:
            # Usar directamente el archivo JSON
            json_paths = [
                Path("config/eroski_incidents.json"),
                Path("scripts/eroski_incidents.json")
            ]
            
            for json_path in json_paths:
                if json_path.exists():
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # Verificar estructura
                        if "tipo_incidente" in data:
                            return data["tipo_incidente"]
                        elif "incident_types" in data:
                            return data["incident_types"]
                        
            self.logger.warning("❌ No se pudo cargar archivo de incidencias")
            return {}
            
        except Exception as e:
            self.logger.error(f"❌ Error cargando tipos de incidencia: {e}")
            return {}
    
    def _build_classification_prompt(self) -> PromptTemplate:
        """
        ✅ PROMPT CORREGIDO: Elimina bucles y fuerza soluciones directas
        """
        return PromptTemplate(
            template="""Eres un experto en clasificación de incidencias técnicas para Eroski.

    🎯 MISIÓN: RESOLVER problemas técnicos de forma DIRECTA y EFICIENTE.

    🚨 REGLAS CRÍTICAS - CUMPLIR OBLIGATORIAMENTE:

    1️⃣ **SI IDENTIFICASTE TIPO + PROBLEMA → PROPORCIONA SOLUCIÓN INMEDIATAMENTE**
    - NO digas "vamos a verificar" 
    - NO digas "procederemos a buscar"
    - NO digas "estamos verificando"
    - DI LA SOLUCIÓN PASO A PASO del catálogo

    2️⃣ **USA LAS SOLUCIONES EXACTAS DEL CATÁLOGO**
    - Si usuario dice "etiquetas" y trabajas en carnicería → "balanza no imprime etiquetas" → DAR SOLUCIÓN
    - Si usuario dice "calibración" → "error de calibración" → DAR SOLUCIÓN  
    - Si usuario dice "no enciende" → buscar en el tipo → DAR SOLUCIÓN

    3️⃣ **MÁXIMO 2 INTERCAMBIOS PARA RESOLVER**
    - Intercambio 1: Identificar problema específico
    - Intercambio 2: Dar solución completa
    - NO más vueltas innecesarias

    TIPOS DE INCIDENCIAS DISPONIBLES:
    {incident_types_info}

    DATOS DEL EMPLEADO AUTENTICADO:
    - Nombre: {employee_name}
    - Tienda: {store_name}
    - Sección: {section}

    HISTORIAL COMPLETO DE MENSAJES:
    {conversation_history}

    ESTADO ACTUAL:
    - Intentos realizados: {attempt_number}
    - Tipo identificado: {previous_incident_type}
    - Problema identificado: {previous_problem}

    ÚLTIMO MENSAJE DEL USUARIO:
    "{user_message}"

    🔍 ANÁLISIS OBLIGATORIO:

    **PASO 1: ¿Ya tienes tipo + problema específico?**
    - SI → next_action: "provide_solution" + dar solución completa del catálogo
    - NO → continuar al paso 2

    **PASO 2: ¿Tienes el tipo pero problema vago?**
    - SI → next_action: "ask_specific_questions" + listar problemas específicos del catálogo
    - NO → continuar al paso 3

    **PASO 3: ¿No tienes ni el tipo?**
    - SI → next_action: "ask_general_questions" + preguntar qué equipo
    - Escalación solo después de 6+ intentos fallidos

    ✅ **EJEMPLOS DE RESPUESTAS CORRECTAS:**

    **Ejemplo A - Usuario dice "lo de las etiquetas" (PROBLEMA IDENTIFICADO):**
    ```json
    {{
    "incident_identified": true,
    "problem_identified": true,
    "solution_ready": true,
    "incident_type": "balanza",
    "specific_problem": "La balanza no imprime etiquetas",
    "proposed_solution": "1. Verificar que hay papel en el compartimento\n2. Abrir la tapa y revisar que el papel esté bien colocado\n3. Limpiar el cabezal de impresión con alcohol\n4. Reiniciar la balanza\n5. Probar imprimiendo una etiqueta de prueba",
    "confidence_level": 0.95,
    "next_action": "provide_solution",
    "message_to_user": "✅ **Problema identificado: Balanza no imprime etiquetas**\n\n🔧 **Solución paso a paso:**\n1. Verificar que hay papel en el compartimento\n2. Abrir la tapa y revisar que el papel esté bien colocado\n3. Limpiar el cabezal de impresión con alcohol\n4. Reiniciar la balanza\n5. Probar imprimiendo una etiqueta de prueba\n\n🤔 **¿Quieres intentar esta solución?**\n• Responde 'sí' para que te guíe paso a paso\n• Responde 'no entiendo' si necesitas más explicación",
    "keywords_detected": ["etiquetas", "balanza"]
    }}
    ```

    **Ejemplo B - Usuario dice "balanza va mal" (TIPO IDENTIFICADO, PROBLEMA VAGO):**
    ```json
    {{
    "incident_identified": true,
    "problem_identified": false,
    "solution_ready": false,
    "incident_type": "balanza",
    "confidence_level": 0.8,
    "next_action": "ask_specific_questions",
    "message_to_user": "He identificado que el problema es con la BALANZA. Para darte la solución exacta, ¿cuál de estos problemas tienes?\n\n1️⃣ **No imprime etiquetas**\n2️⃣ **El peso mostrado es incorrecto**\n3️⃣ **Error de calibración**\n4️⃣ **La balanza no enciende**\n5️⃣ **La pantalla no responde**\n6️⃣ **Las etiquetas salen en blanco**\n\nResponde el número o describe tu problema específico:",
    "keywords_detected": ["balanza"]
    }}
    ```

    ❌ **PROHIBIDO HACER (EJEMPLOS DE LO QUE NO DEBES DECIR):**
    - "Vamos a verificar cómo podemos solucionarlo" → MUY VAGO
    - "Procederemos a buscar una solución" → DAR LA SOLUCIÓN YA
    - "Estamos verificando cómo resolverlo" → NO VERIFICAR, RESOLVER
    - "Entendido, parece que..." → SER DIRECTO
    - "Hemos identificado que..." → DAR LA SOLUCIÓN INMEDIATAMENTE

    ✅ **EN SU LUGAR DI:**
    - "✅ **Problema identificado: [PROBLEMA]**\n\n🔧 **Solución paso a paso:**\n1. [PASO]\n2. [PASO]..."
    - "He identificado que el problema es con [EQUIPO]. Para darte la solución exacta, ¿cuál de estos problemas tienes? 1️⃣ [OPCIÓN] 2️⃣ [OPCIÓN]..."

    🚨 CRITERIOS DE ESCALACIÓN (SOLO en estos casos):
    - Han pasado más de 6 intentos sin identificar claramente la incidencia
    - El usuario describe algo que NO está en ninguna categoría del catálogo
    - El usuario EXPLÍCITAMENTE pide hablar con un supervisor
    - Tu confianza es menor a 0.3 después de múltiples intentos

    ✅ NO ESCALES SI:
    - Tienes alta confianza (>= 0.7)
    - Ya identificaste el problema
    - Tienes la solución del catálogo
    - El usuario está cooperando

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

    ⚠️ IMPORTANTE: No uses formato Markdown en JSON. Solo responde con JSON puro.""",
            input_variables=[
                "incident_types_info", "conversation_history", "employee_name", 
                "store_name", "section", "attempt_number", "previous_incident_type",
                "previous_problem", "user_message"
            ]
        )
    
    def _build_confirmation_prompt(self) -> PromptTemplate:
        """Construir prompt para interpretación inteligente de confirmaciones"""
        return PromptTemplate(
            template="""Eres un asistente especializado en interpretar las respuestas de empleados de Eroski.

CONTEXTO:
Se le proporcionó una solución al usuario y ahora necesitas interpretar su respuesta para entender:
1. Si la solución funcionó o no
2. Si quiere abrir una nueva incidencia  
3. Si necesita más ayuda con la misma incidencia

MENSAJE DEL USUARIO:
"{user_message}"

SOLUCIÓN PROPORCIONADA ANTERIORMENTE:
"{previous_solution}"

INFORMACIÓN DEL EMPLEADO:
- Nombre: {employee_name}
- Tienda: {store_name}
- Sección: {section}

INSTRUCCIONES PARA INTERPRETAR:

🎯 **DETECCIÓN DE INTENCIONES:**

**Solución exitosa** - Palabras/frases como:
- "sí", "funcionó", "perfecto", "resuelto", "ya está", "gracias"
- "lo arreglé", "ya funciona", "problem solved", "todo bien"

**Solución fallida** - Palabras/frases como:
- "no", "sigue igual", "no funciona", "persiste", "aún no", "todavía"
- "intenté pero...", "hice lo que dijiste pero...", "no sirvió"

**Nueva incidencia** - Palabras/frases como:
- "ahora tengo otro problema", "nueva incidencia", "otro tema"
- "además", "también", "por cierto", "mientras tanto"
- "en otra sección", "en otra tienda", "diferente problema"

**Necesita clarificación** - Palabras/frases como:
- "no entendí", "cómo hago", "qué significa", "dónde está"
- "puedes explicar", "más detalles", "paso a paso"

RESPONDE ÚNICAMENTE CON JSON VÁLIDO:
{{
    "user_intent": "solution_worked|solution_failed|new_incident|needs_clarification",
    "confidence_level": 0.0,
    "solution_successful": false,
    "additional_details": null,
    "wants_new_incident": false,
    "same_location": null,
    "new_store": null,
    "new_section": null,
    "message_to_user": "Respuesta natural aquí",
    "needs_location_update": false
}}""",
            input_variables=[
                "user_message", "previous_solution", "employee_name", "store_name", "section"
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
        user_desc_lower = user_description.lower()
        
        # ✅ MEJORADO: Verificar múltiples estructuras posibles
        
        # Estructura 1: "problemas" con diccionario problema -> solución
        if "problemas" in incident_data:
            problems = incident_data["problemas"]
            
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
        
        # Estructura 2: "common_issues" con lista de problemas (sin soluciones específicas)
        elif "common_issues" in incident_data:
            common_issues = incident_data["common_issues"]
            
            best_match = None
            best_score = 0
            
            for issue in common_issues:
                issue_lower = issue.lower()
                
                # Buscar coincidencia
                score = 0
                user_words = set(user_desc_lower.split())
                issue_words = set(issue_lower.split())
                
                common_words = user_words.intersection(issue_words)
                if common_words:
                    score += len(common_words) * 2
                
                if any(word in issue_lower for word in user_words if len(word) > 3):
                    score += 1
                
                if score > best_score:
                    best_score = score
                    best_match = issue
            
            # Para common_issues, generar solución genérica
            if best_match:
                generic_solution = f"Para el problema '{best_match}', consulta el manual técnico o contacta con soporte especializado."
                return (best_match, generic_solution)
        
        return None, None
    
    def _generate_specific_questions(self, incident_type: str) -> str:
        """
        ✅ REFACTORIZADO: Generar preguntas específicas usando helper.
        
        Args:
            incident_type: Tipo de incidencia identificada
            
        Returns:
            Mensaje con preguntas específicas dirigidas
        """
        return self.solution_searcher.format_problems_for_user(incident_type)
    
    def _handle_confirmation_fallback(self, state: EroskiState) -> Command:
        """Fallback para confirmación sin LLM"""
        
        user_message = self._get_last_user_message(state).lower()
        
        # Interpretación básica
        if any(word in user_message for word in ["sí", "si", "funcionó", "resuelto"]):
            return Command(
                update={
                    "messages": state["messages"] + [AIMessage(content="Perfecto, problema resuelto.")],
                    "current_step": "finalize",
                    "conversation_ended": True
                }
            )
        else:
            return Command(
                update={
                    "messages": state["messages"] + [AIMessage(content="Escalando a supervisor.")],
                    "current_step": "escalate"
                }
            )
    
    def _try_auto_classify_from_file(self, state: EroskiState, decision: ClassificationDecision, attempt_number: int) -> Command:
        """
        ✅ REFACTORIZADO: Intentar clasificar automáticamente usando helper.
        
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
        
        # ✅ REFACTORIZADO: Buscar coincidencia usando helper
        problem_match, solution = self._find_solution_with_helpers(
            decision.incident_type, 
            combined_description
        )
        
        if problem_match and solution:
            # ¡Encontramos coincidencia! Proporcionar solución
            incident_code = state.get("incident_code", "N/A")
            solution_message = f"""✅ **Incidencia Identificada: {decision.incident_type}**

📋 **Problema:** {problem_match}

🔧 **Solución:**
{solution}

¿Esta solución resolvió tu problema? Si persiste o necesitas más ayuda, házmelo saber.

📋 *Código de incidencia: {incident_code}*"""
            
            classify_data = state.get("classify_data", {})
            classify_data.update({
                "incident_type": decision.incident_type,
                "specific_problem": problem_match,
                "proposed_solution": solution,
                "solution_source": "archivo_automatico",
                "problem_identified": True,
                "solution_ready": True,
                "completed": False,
                "awaiting_confirmation": True
            })
            
            # ✅ REFACTORIZADO: Actualizar incidencia usando helper
            self._update_incident_with_helpers(state, {
                "tipo_incidencia": decision.incident_type,
                "problema_especifico": problem_match,
                "solucion_aplicada": solution,
                "estado_solucion": "automatica"
            })
            
            return Command(
                update={
                    "messages": state["messages"] + [AIMessage(content=solution_message)],
                    "classify_data": classify_data,
                    "current_step": "classify",
                    "classification_completed": False  # Esperando confirmación
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
        
        # ✅ NUEVO: Escalación por falta de progreso
        if self._is_stuck_without_progress(state, attempt_number):
            self.logger.info(f"🔴 Escalando por falta de progreso después de {attempt_number} intentos")
            return True
        
        # Escalación automática por número de intentos
        if attempt_number >= 5:  # Reducido de 6 a 5
            self.logger.info(f"🔴 Escalando por máximo número de intentos: {attempt_number}")
            return True
        
        # Escalación si el LLM lo indica
        if classify_data.get("needs_escalation", False):
            self.logger.info("🔴 Escalando por decisión del LLM")
            return True
        
        # Escalación si el usuario lo solicita explícitamente
        last_message = self._get_last_user_message(state)
        escalation_keywords = ["supervisor", "jefe", "responsable", "hablar con alguien mas", "no me ayudas"]
        
        if any(keyword in last_message.lower() for keyword in escalation_keywords):
            self.logger.info("🔴 Escalando por solicitud explícita del usuario")
            return True
        
        return False
    
    def _is_stuck_without_progress(self, state: EroskiState, attempt_number: int) -> bool:
        """
        ✅ NUEVO: Evaluar si está atascado sin hacer progreso hacia una solución.
        
        Args:
            state: Estado actual
            attempt_number: Número de intento actual
            
        Returns:
            True si está atascado sin progreso
        """
        
        if attempt_number < 3:
            return False  # Dar al menos 3 oportunidades
        
        classify_data = state.get("classify_data", {})
        
        # Obtener historial de confianza
        confidence_history = classify_data.get("confidence_history", [])
        
        # Si no hay progreso en confianza en los últimos 2-3 intentos
        if len(confidence_history) >= 3:
            recent_confidence = confidence_history[-3:]
            
            # Si la confianza no ha mejorado en absoluto
            if all(conf <= 0.3 for conf in recent_confidence):
                self.logger.info(f"🔴 Confianza consistentemente baja: {recent_confidence}")
                return True
            
            # Si la confianza está estancada (no mejora)
            if len(set(recent_confidence)) == 1:  # Todos los valores iguales
                self.logger.info(f"🔴 Confianza estancada: {recent_confidence}")
                return True
        
        # Si se detectó bucle en el LLM
        if classify_data.get("stuck_in_loop", False):
            self.logger.info("🔴 LLM detectó bucle sin progreso")
            return True
        
        # Si no se ha identificado ni siquiera el tipo después de varios intentos
        if attempt_number >= 4 and not classify_data.get("incident_identified", False):
            self.logger.info("🔴 Sin identificar tipo después de 4 intentos")
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
        Ejecutar clasificación usando el sistema de dos fases
        """
        
        self.logger.info("🚀 Iniciando clasificación en dos fases")
        
        try:
            # Generar código de incidencia si no existe
            if not state.get("incident_code"):
                incident_code = self.code_manager.generate_unique_code()
                state = {**state, "incident_code": incident_code}
                self._initialize_incident_with_helpers(state, incident_code)
            
            # Ejecutar clasificación en dos fases
            return await execute_two_phase_classification(state)
            
        except Exception as e:
            self.logger.error(f"❌ Error en clasificación dos fases: {e}")
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
            "user_message": user_message,
                "previous_confidence": classify_data.get("confidence_level", 0.0) 
        }
        
        # Usar un prompt más avanzado para intentos continuos
        continuous_prompt = PromptTemplate(
            template="""Continúa analizando la consulta del usuario para clasificar la incidencia.

INFORMACIÓN PREVIA IDENTIFICADA:
- Tipo de incidencia: {previous_incident_type}
- Problema específico: {previous_problem}
- Intento número: {attempt_number}
- Confianza anterior: {previous_confidence}

HISTORIAL COMPLETO DE MENSAJES DEL USUARIO (ANALIZA TODO):
{conversation_history}

TIPOS DE INCIDENCIAS DISPONIBLES:
{incident_types_info}

ÚLTIMO MENSAJE DEL USUARIO:
"{user_message}"

CONTEXTO DEL EMPLEADO:
- Nombre: {employee_name}
- Sección: {section}

INSTRUCCIONES CRÍTICAS PARA EVITAR BUCLES:

🔍 **ANÁLISIS OBLIGATORIO DEL PROGRESO:**
1. Analiza TODO el historial de mensajes del usuario para extraer TODA la información acumulada
2. Evalúa si has hecho progreso desde el intento anterior (¿ha subido la confianza?)
3. Identifica qué preguntas ya has hecho para NO repetirlas
4. Si el usuario da información nueva, combínala con la anterior

🎯 **ESTRATEGIAS PARA EVITAR BUCLES:**
- Si ya preguntaste sobre algo de forma similar, NO lo vuelvas a preguntar
- Si no has hecho progreso en 2-3 intentos, considera escalación
- Si la información del usuario es limitada y no coincide con problemas del archivo, escalar
- Si ya tienes el tipo pero no puedes identificar problema específico después de preguntar, escalar

🧠 **LÓGICA DE DECISIÓN MEJORADA:**
1. Si identificaste el tipo Y el problema ESTÁ en el archivo → proponer la solución DEL ARCHIVO
2. Si identificas el tipo pero el problema NO ESTÁ en el archivo → hacer UNA pregunta específica con opciones del archivo
3. Si ya hiciste preguntas específicas y el usuario no puede elegir → ESCALAR
4. Si NO identificas el tipo después de {attempt_number} intentos → ESCALAR
5. Si detectas que estás en bucle preguntando lo mismo → ESCALAR

✅ **EJEMPLO DE ANÁLISIS CORRECTO:**
"He preguntado sobre conexión y reinicio. El usuario mencionó pantalla borrosa. En el archivo no hay 'pantalla borrosa' como problema específico para balanzas. Los problemas disponibles son: no imprime, no enciende, precio incorrecto, etc. Como no coincide → ESCALAR"

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
    "urgency_level": 2,
    "progress_assessment": "improving/stagnant/declining",
    "new_information_provided": false,
    "questions_already_asked": [],
    "stuck_in_loop": false
}}""",
            input_variables=[
                "incident_types_info", "employee_name", "section", 
                "attempt_number", "previous_incident_type", "previous_problem", 
                "user_message", "conversation_history", "previous_confidence"
            ]
        )
        
        # Ejecutar LLM
        formatted_prompt = continuous_prompt.format(**prompt_input)
        
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
        
        # ✅ NUEVO: Seguimiento de progreso y confianza
        confidence_history = classify_data.get("confidence_history", [])
        confidence_history.append(decision.confidence_level)
        
        # Mantener solo las últimas 5 mediciones
        if len(confidence_history) > 5:
            confidence_history = confidence_history[-5:]
        
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
            "confidence_history": confidence_history,  # ✅ NUEVO
            "keywords_detected": decision.keywords_detected,
            "urgency_level": decision.urgency_level,
            "last_analysis": datetime.now().isoformat(),
            "progress_assessment": decision.progress_assessment,  # ✅ NUEVO
            "new_information_provided": decision.new_information_provided,  # ✅ NUEVO
            "stuck_in_loop": decision.stuck_in_loop  # ✅ NUEVO
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
    
    def _generate_targeted_questions(self, state: EroskiState, decision: ClassificationDecision, attempt_number: int) -> Command:
        """
        ✅ REFACTORIZADO: Generar preguntas dirigidas usando helper.
        
        Args:
            state: Estado actual
            decision: Decisión del LLM
            attempt_number: Número de intento
            
        Returns:
            Command con preguntas específicas
        """
        
        # Generar mensaje con preguntas específicas usando helper
        specific_message = self.solution_searcher.format_problems_for_user(decision.incident_type)
        
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
    
    def _should_generate_specific_questions(self, decision: ClassificationDecision, attempt_number: int) -> bool:
        """Determinar si se deben generar preguntas específicas"""
        return (
            decision.incident_identified and 
            decision.incident_type and 
            not decision.problem_identified and
            attempt_number <= 3
        )
    
    def _provide_solution_and_complete(self, state: EroskiState, decision: ClassificationDecision) -> Command:
        """Proporcionar solución y completar clasificación"""
        
        classify_data = state.get("classify_data", {})
        incident_type = decision.incident_type or classify_data.get("incident_type")
        
        # ✅ REFACTORIZADO: Buscar solución usando helper
        solution_from_file = None
        problem_key_found = None
        
        if incident_type and decision.specific_problem:
            problem_key_found, solution_from_file = self._find_solution_with_helpers(
                incident_type, decision.specific_problem
            )
        
        # Si no encontramos, buscar por descripción general del usuario
        if not solution_from_file and incident_type:
            user_messages = []
            for msg in state.get("messages", []):
                if isinstance(msg, HumanMessage):
                    user_messages.append(msg.content)
            
            combined_description = " ".join(user_messages)
            problem_key_found, solution_from_file = self._find_solution_with_helpers(
                incident_type, combined_description
            )
        
        # Usar solución del archivo si existe, sino la del LLM
        final_solution = solution_from_file or decision.proposed_solution
        solution_source = "archivo" if solution_from_file else "llm"
        
        if not final_solution:
            # Si no hay solución específica, escalamos
            return self._escalate_to_supervisor(state)
        
        # ✅ MEJORADO: Mensaje que solicita confirmación con código de incidencia
        incident_code = state.get("incident_code", "N/A")
        solution_message = f"""✅ **Incidencia Identificada: {incident_type}**

📋 **Problema:** {problem_key_found or decision.specific_problem}

🔧 **Solución:**
{final_solution}

¿Esta solución resolvió tu problema? 
• Escribe "sí" o "resuelto" si funcionó
• Escribe "no" o "persiste" si continúa el problema  
• O cuéntame qué pasó al intentar la solución

📋 *Código de incidencia: {incident_code}*"""
        
        # ✅ REFACTORIZADO: Actualizar registro usando helper
        self._update_incident_with_helpers(state, {
            "tipo_incidencia": incident_type,
            "problema_especifico": problem_key_found or decision.specific_problem,
            "solucion_aplicada": final_solution,
            "estado_solucion": "proporcionada"
        })
        
        # ✅ CORREGIDO: Actualizar estado correctamente
        updated_classify_data = {
            **classify_data, 
            "incident_identified": True,
            "problem_identified": True,
            "solution_ready": True,
            "incident_type": incident_type,
            "specific_problem": problem_key_found or decision.specific_problem,
            "proposed_solution": final_solution,
            "solution_provided": final_solution,
            "solution_source": solution_source,
            "confidence_level": decision.confidence_level,
            "completed": False,  # No marcar como completo hasta confirmación
            "awaiting_confirmation": True  # Esperando confirmación
        }
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=solution_message)],
                "classify_data": updated_classify_data,
                "incident_type": incident_type,
                "current_step": "classify",  # Mantener en classify para confirmación
                "classification_completed": False  # No completar hasta confirmación
            }
        )
    
    def _escalate_to_supervisor(self, state: EroskiState) -> Command:
        """Escalar a supervisor con información detallada"""
        
        classify_data = state.get("classify_data", {})
        
        # ✅ NUEVO: Mensaje de escalación más informativo
        escalation_reason = self._determine_escalation_reason(state)
        
        escalation_message = f"""🔝 **Escalando a Supervisor**

{escalation_reason}

**Información recopilada:**
- Empleado: {state.get('auth_data_collected', {}).get('name', 'N/A')}
- Sección: {state.get('auth_data_collected', {}).get('section', 'N/A')}
- Tipo identificado: {classify_data.get('incident_type', 'No identificado')}
- Intentos realizados: {state.get('classify_attempt_number', 0)}
- Nivel de confianza: {classify_data.get('confidence_level', 0.0):.2f}

Un supervisor especializado te contactará pronto para resolver tu consulta.

Por favor, ten preparada la siguiente información:
- Descripción detallada del problema
- Pasos que ya has intentado
- Número de serie del equipo (si aplica)"""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=escalation_message)],
                "current_step": "escalate",
                "escalation_reason": escalation_reason,
                "escalation_data": classify_data,
                "escalation_timestamp": datetime.now().isoformat()
            }
        )
    
    def _determine_escalation_reason(self, state: EroskiState) -> str:
        """
        ✅ NUEVO: Determinar la razón específica de escalación.
        
        Args:
            state: Estado actual
            
        Returns:
            Mensaje explicando por qué se escala
        """
        classify_data = state.get("classify_data", {})
        attempt_number = state.get("classify_attempt_number", 0)
        
        if classify_data.get("stuck_in_loop", False):
            return "No he podido identificar tu problema específico después de varios intentos. La situación requiere atención especializada."
        
        elif self._is_stuck_without_progress(state, attempt_number):
            confidence_history = classify_data.get("confidence_history", [])
            return f"Después de {attempt_number} intentos, no he logrado suficiente certeza para resolver tu consulta (confianza: {confidence_history})."
        
        elif attempt_number >= 5:
            return f"He alcanzado el máximo de intentos de clasificación ({attempt_number}) sin poder resolver completamente tu consulta."
        
        elif not classify_data.get("incident_identified", False):
            return "No he podido identificar el tipo de incidencia que describes en nuestro catálogo de problemas."
        
        else:
            return "Tu consulta requiere atención especializada que está fuera de mi capacidad de resolución automática."
    
    def _initialize_incident_with_helpers(self, state: EroskiState, incident_code: str) -> None:
        """
        ✅ REFACTORIZADO: Inicializar incidencia usando helper de persistencia.
        
        Args:
            state: Estado actual
            incident_code: Código de la incidencia
        """
        success = self.persistence_manager.initialize_incident(state, incident_code)
        if success:
            self.logger.info(f"✅ Incidencia {incident_code} inicializada")
        else:
            self.logger.error(f"❌ Error inicializando incidencia {incident_code}")
    
    def _update_incident_with_helpers(self, state: EroskiState, updates: dict) -> None:
        """
        ✅ REFACTORIZADO: Actualizar incidencia usando helper de persistencia.
        
        Args:
            state: Estado actual
            updates: Datos a actualizar
        """
        incident_code = state.get("incident_code")
        if incident_code:
            success = self.persistence_manager.update_incident(incident_code, updates)
            if not success:
                self.logger.error(f"❌ Error actualizando incidencia {incident_code}")
    
    def _save_messages_with_helpers(self, state: EroskiState) -> None:
        """
        ✅ REFACTORIZADO: Guardar mensajes usando helper de persistencia.
        
        Args:
            state: Estado actual
        """
        incident_code = state.get("incident_code")
        if incident_code:
            messages = state.get("messages", [])
            success = self.persistence_manager.save_messages(incident_code, messages)
            if not success:
                self.logger.error(f"❌ Error guardando mensajes para {incident_code}")
    
    def _find_solution_with_helpers(self, incident_type: str, problem_description: str) -> tuple[Optional[str], Optional[str]]:
        """
        ✅ REFACTORIZADO: Buscar solución usando helper especializado.
        
        Args:
            incident_type: Tipo de incidencia
            problem_description: Descripción del problema
            
        Returns:
            Tupla (problema_encontrado, solución)
        """
        return self.solution_searcher.find_best_solution(incident_type, problem_description)
    
    def _is_awaiting_confirmation(self, state: EroskiState) -> bool:
        """
        ✅ NUEVO: Verificar si está esperando confirmación de una solución proporcionada.
        
        Args:
            state: Estado actual
            
        Returns:
            True si está esperando confirmación
        """
        classify_data = state.get("classify_data", {})
        return classify_data.get("awaiting_confirmation", False)
    
    async def _handle_solution_confirmation(self, state: EroskiState) -> Command:
        """
        ✅ REFACTORIZADO: Manejar confirmación usando helper especializado.
        
        Args:
            state: Estado actual
            
        Returns:
            Command con la acción apropiada
        """
        
        user_message = self._get_last_user_message(state)
        classify_data = state.get("classify_data", {})
        
        # ✅ REFACTORIZADO: Usar helper para interpretación
        try:
            decision = await self.confirmation_handler.interpret_confirmation(
                state=state,
                user_message=user_message,
                previous_solution=classify_data.get("solution_provided", "")
            )
            
            self.logger.info(f"🤖 Interpretación: {decision.user_intent}")
            
            # Actualizar mensajes en archivo
            self._save_messages_with_helpers(state)
            
            # Procesar según la intención detectada
            if decision.user_intent == "solution_worked" or decision.solution_successful:
                return await self._handle_successful_resolution_with_helpers(state, decision)
            
            elif decision.user_intent == "solution_failed":
                return await self._handle_failed_solution_with_helpers(state, decision)
            
            elif decision.user_intent == "new_incident" or decision.wants_new_incident:
                return await self._handle_new_incident_with_helpers(state, decision)
            
            elif decision.user_intent == "needs_clarification":
                return self._ask_for_clarification_with_helpers(state, decision)
            
            else:
                return self._ask_for_clarification_with_helpers(state, decision)
                
        except Exception as e:
            self.logger.error(f"❌ Error en confirmación: {e}")
            return self._handle_confirmation_fallback(state)
    
    async def _handle_successful_resolution_with_helpers(self, state: EroskiState, decision: ConfirmationDecision) -> Command:
        """✅ REFACTORIZADO: Manejar resolución exitosa con helpers"""
        
        incident_code = state.get("incident_code", "N/A")
        
        # Actualizar incidencia
        self._update_incident_with_helpers(state, {
            "estado": "cerrada",
            "estado_solucion": "exitosa",
            "timestamp_cierre": datetime.now().isoformat(),
            "detalles_cierre": decision.additional_details
        })
        
        success_message = f"""✅ **¡Perfecto!** 

Me alegra saber que la solución funcionó. La incidencia **{incident_code}** ha sido resuelta exitosamente.

Si en el futuro tienes otra incidencia, no dudes en contactarme. ¡Que tengas un buen día!

📋 *Código de incidencia: {incident_code}*"""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=success_message)],
                "classify_data": {
                    **state.get("classify_data", {}), 
                    "completed": True,
                    "solution_successful": True,
                    "awaiting_confirmation": False
                },
                "current_step": "finalize",
                "classification_completed": True,
                "conversation_ended": True,
                "resolved": True
            }
        )
    
    async def _handle_failed_solution_with_helpers(self, state: EroskiState, decision: ConfirmationDecision) -> Command:
        """✅ REFACTORIZADO: Manejar solución fallida con helpers"""
        
        incident_code = state.get("incident_code", "N/A")
        classify_data = state.get("classify_data", {})
        
        # Actualizar incidencia
        self._update_incident_with_helpers(state, {
            "estado_solucion": "fallida",
            "detalles_fallo": decision.additional_details,
            "escalado_por": "solucion_fallida"
        })
        
        escalation_message = f"""🔝 **Escalando a Supervisor**

Entiendo que la solución proporcionada no resolvió el problema completamente.

**Información del caso {incident_code}:**
- Empleado: {state.get('auth_data_collected', {}).get('name', 'N/A')}
- Problema: {classify_data.get('specific_problem', 'N/A')}
- Solución intentada: {classify_data.get('solution_provided', 'N/A')}

Un supervisor técnico te contactará pronto para resolver este caso específico.

📋 *Código de incidencia: {incident_code}*"""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=escalation_message)],
                "current_step": "escalate",
                "escalation_reason": "solution_failed",
                "escalation_data": classify_data
            }
        )
    
    async def _handle_new_incident_with_helpers(self, state: EroskiState, decision: ConfirmationDecision) -> Command:
        """✅ REFACTORIZADO: Manejar nueva incidencia con helpers"""
        
        # Cerrar incidencia actual
        current_incident_code = state.get("incident_code", "N/A")
        self._update_incident_with_helpers(state, {
            "estado": "cerrada",
            "estado_solucion": "nueva_incidencia_solicitada",
            "timestamp_cierre": datetime.now().isoformat()
        })
        
        if decision.needs_location_update:
            # Pedir confirmación de ubicación
            location_message = f"""📋 **Nueva Incidencia**

Perfecto, voy a abrir una nueva incidencia para ti.

¿La nueva incidencia es en la misma ubicación?
- Tienda: {state.get('auth_data_collected', {}).get('store_name', 'N/A')}
- Sección: {state.get('auth_data_collected', {}).get('section', 'N/A')}

Responde "sí" si es la misma ubicación, o indícame la nueva tienda/sección.

📋 *Incidencia anterior: {current_incident_code} (cerrada)*"""
            
            return Command(
                update={
                    "messages": state["messages"] + [AIMessage(content=location_message)],
                    "classify_data": {"awaiting_location_confirmation": True},
                    "current_step": "classify"
                }
            )
        else:
            # Crear nueva incidencia directamente
            return await self._create_new_incident_with_helpers(state)
    
    async def _create_new_incident_with_helpers(self, state: EroskiState) -> Command:
        """✅ REFACTORIZADO: Crear nueva incidencia con helpers"""
        
        # Guardar mensajes finales de incidencia actual
        self._save_messages_with_helpers(state)
        
        # Generar nuevo código
        new_incident_code = self.code_manager.generate_unique_code()
        
        # Inicializar nueva incidencia
        self._initialize_incident_with_helpers(state, new_incident_code)
        
        new_incident_message = f"""🆕 **Nueva Incidencia Creada**

He abierto una nueva incidencia para ti.

📋 **Código de incidencia: {new_incident_code}**

Por favor, describe el nuevo problema que necesitas reportar.

💡 *Recuerda que tu código anterior era {state.get('incident_code', 'N/A')} por si necesitas consultarlo*"""
        
        # Resetear estado para nueva incidencia
        return Command(
            update={
                "incident_code": new_incident_code,
                "messages": [AIMessage(content=new_incident_message)],  # Resetear mensajes
                "classify_data": {},
                "classify_attempt_number": 0,
                "classification_completed": False,
                "current_step": "classify",
                "conversation_ended": False,
                "resolved": False
            }
        )
    
    def _ask_for_clarification_with_helpers(self, state: EroskiState, decision: ConfirmationDecision) -> Command:
        """✅ REFACTORIZADO: Pedir clarificación con helpers"""
        
        clarification_message = f"""🤔 **Necesito Clarificación**

{decision.message_to_user}

Para ayudarte mejor, ¿podrías confirmar claramente?
• ¿La solución funcionó y el problema se resolvió?
• ¿El problema persiste y necesitas más ayuda?
• ¿Quieres reportar un problema diferente?

📋 *Código de incidencia: {state.get('incident_code', 'N/A')}*"""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=clarification_message)],
                "classify_data": state.get("classify_data", {}),
                "current_step": "classify"
            }
        )
    
    async def _handle_new_incident_request(self, state: EroskiState, decision: ClassifyConfirmationDecision) -> Command:
        """Manejar solicitud de nueva incidencia"""
        
        # Cerrar incidencia actual
        current_incident_code = state.get("incident_code", "N/A")
        self._update_incident_record(state, {
            "estado": "cerrada",
            "estado_solucion": "nueva_incidencia_solicitada",
            "timestamp_cierre": datetime.now().isoformat()
        })
        
        if decision.needs_location_update:
            # Pedir confirmación de ubicación
            location_message = f"""📋 **Nueva Incidencia**

Perfecto, voy a abrir una nueva incidencia para ti.

¿La nueva incidencia es en la misma ubicación?
- Tienda: {state.get('auth_data_collected', {}).get('store_name', 'N/A')}
- Sección: {state.get('auth_data_collected', {}).get('section', 'N/A')}

Responde "sí" si es la misma ubicación, o indícame la nueva tienda/sección.

📋 *Incidencia anterior: {current_incident_code} (cerrada)*"""
            
            return Command(
                update={
                    "messages": state["messages"] + [AIMessage(content=location_message)],
                    "classify_data": {"awaiting_location_confirmation": True},
                    "current_step": "classify"
                }
            )
        else:
            # Crear nueva incidencia directamente
            return await self._create_new_incident(state)
    
    async def _create_new_incident(self, state: EroskiState) -> Command:
        """Crear nueva incidencia"""
        
        # Guardar mensajes en incidencia actual
        self._save_messages_to_incident(state)
        
        # Generar nuevo código
        new_incident_code = self._generate_incident_code()
        
        # Limpiar estado pero mantener datos de empleado
        auth_data = state.get("auth_data_collected", {})
        
        # Inicializar nueva incidencia
        self._initialize_incident_record(state, new_incident_code)
        
        new_incident_message = f"""🆕 **Nueva Incidencia Creada**

He abierto una nueva incidencia para ti.

📋 **Código de incidencia: {new_incident_code}**

Por favor, describe el nuevo problema que necesitas reportar.

💡 *Recuerda que tu código anterior era {state.get('incident_code', 'N/A')} por si necesitas consultarlo*"""
        
        # Resetear estado para nueva incidencia
        return Command(
            update={
                "incident_code": new_incident_code,
                "messages": [AIMessage(content=new_incident_message)],  # ✅ RESETEAR mensajes
                "classify_data": {},
                "classify_attempt_number": 0,
                "classification_completed": False,
                "current_step": "classify",
                "conversation_ended": False,
                "resolved": False
            }
        )
    
    def _ask_for_clarification(self, state: EroskiState, decision: ClassifyConfirmationDecision) -> Command:
        """Pedir clarificación cuando no está claro"""
        
        clarification_message = f"""🤔 **Necesito Clarificación**

{decision.message_to_user}

Para ayudarte mejor, ¿podrías confirmar claramente?
• ¿La solución funcionó y el problema se resolvió?
• ¿El problema persiste y necesitas más ayuda?
• ¿Quieres reportar un problema diferente?

📋 *Código de incidencia: {state.get('incident_code', 'N/A')}*"""
        
        return Command(
            update={
                "messages": state["messages"] + [AIMessage(content=clarification_message)],
                "classify_data": state.get("classify_data", {}),
                "current_step": "classify"
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