# =====================================================
# utils/incident_helpers.py - Clases Helper Especializadas
# =====================================================
"""
Clases helper especializadas para el manejo de incidencias.

RESPONSABILIDADES:
- IncidentCodeManager: Generación y gestión de códigos únicos
- SolutionSearcher: Búsqueda de soluciones en archivo JSON
- ConfirmationLLMHandler: Interpretación inteligente de confirmaciones
- IncidentPersistence: Persistencia y gestión del archivo JSON
"""

import json
import random
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from abc import ABC, abstractmethod

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

from models.eroski_state import EroskiState
from utils.llm.providers import get_llm


# =============================================================================
# MODELOS DE DATOS COMPARTIDOS
# =============================================================================

class ConfirmationDecision(BaseModel):
    """Decisión del LLM sobre confirmación del usuario"""
    user_intent: str = Field(description="Intención: solution_worked, solution_failed, new_incident, needs_clarification")
    confidence_level: float = Field(description="Confianza (0-1)", default=0.0)
    
    # Para soluciones
    solution_successful: bool = Field(description="Si la solución funcionó", default=False)
    additional_details: Optional[str] = Field(description="Detalles adicionales", default=None)
    
    # Para nueva incidencia
    wants_new_incident: bool = Field(description="Si quiere nueva incidencia", default=False)
    same_location: Optional[bool] = Field(description="Si es misma ubicación", default=None)
    new_store: Optional[str] = Field(description="Nueva tienda", default=None)
    new_section: Optional[str] = Field(description="Nueva sección", default=None)
    
    # Respuesta
    message_to_user: str = Field(description="Mensaje para el usuario")
    needs_location_update: bool = Field(description="Si necesita actualizar ubicación", default=False)


# =============================================================================
# 1. GESTOR DE CÓDIGOS DE INCIDENCIA
# =============================================================================

class IncidentCodeManager:
    """
    Gestiona la generación y validación de códigos únicos de incidencia.
    
    RESPONSABILIDADES:
    - Generar códigos únicos formato ER-NNNN
    - Validar que no existan duplicados
    - Proporcionar códigos para consulta
    """
    
    def __init__(self, incidents_file: Path):
        self.incidents_file = incidents_file
        self.logger = logging.getLogger("IncidentCodeManager")
    
    def generate_unique_code(self) -> str:
        """
        Generar código único de incidencia.
        
        Returns:
            Código único en formato ER-NNNN
        """
        existing_codes = self._get_existing_codes()
        
        # Generar código único
        max_attempts = 1000
        for _ in range(max_attempts):
            code = f"ER-{random.randint(1000, 9999)}"
            if code not in existing_codes:
                self.logger.info(f"✅ Código generado: {code}")
                return code
        
        # Fallback si no encuentra único
        fallback_code = f"ER-{random.randint(10000, 99999)}"
        self.logger.warning(f"⚠️ Usando código fallback: {fallback_code}")
        return fallback_code
    
    def _get_existing_codes(self) -> set:
        """Obtener códigos existentes del archivo"""
        if not self.incidents_file.exists():
            return set()
        
        try:
            with open(self.incidents_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return set(data.keys())
        except Exception as e:
            self.logger.warning(f"⚠️ Error leyendo códigos existentes: {e}")
            return set()
    
    def validate_code_format(self, code: str) -> bool:
        """Validar formato de código ER-NNNN"""
        import re
        pattern = r'^ER-\d{4,5}$'
        return bool(re.match(pattern, code))
    
    def is_code_available(self, code: str) -> bool:
        """Verificar si un código está disponible"""
        existing_codes = self._get_existing_codes()
        return code not in existing_codes


# =============================================================================
# 2. BUSCADOR DE SOLUCIONES
# =============================================================================

class SolutionSearcher:
    """
    Busca soluciones específicas en el archivo de configuración JSON.
    
    RESPONSABILIDADES:
    - Buscar soluciones por tipo de incidencia y problema
    - Matching inteligente con múltiples estrategias
    - Formatear soluciones para presentación
    """
    
    def __init__(self, incident_types: Dict[str, Any]):
        self.incident_types = incident_types
        self.logger = logging.getLogger("SolutionSearcher")
    
    def find_best_solution(self, incident_type: str, problem_description: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Encontrar la mejor solución para un problema específico.
        
        Args:
            incident_type: Tipo de incidencia (ej: "balanza")
            problem_description: Descripción del problema
            
        Returns:
            Tupla (problema_encontrado, solución) o (None, None)
        """
        if incident_type not in self.incident_types:
            self.logger.warning(f"⚠️ Tipo de incidencia no encontrado: {incident_type}")
            return None, None
        
        incident_data = self.incident_types[incident_type]
        
        # Estrategia 1: Estructura "problemas" con soluciones específicas
        if "problemas" in incident_data:
            return self._search_in_problems_structure(incident_data["problemas"], problem_description)
        
        # Estrategia 2: Estructura "common_issues" con problemas comunes
        elif "common_issues" in incident_data:
            return self._search_in_common_issues(incident_data["common_issues"], problem_description)
        
        self.logger.warning(f"⚠️ No se encontró estructura de problemas para {incident_type}")
        return None, None
    
    def _search_in_problems_structure(self, problems: Dict[str, str], description: str) -> Tuple[Optional[str], Optional[str]]:
        """Buscar en estructura problemas -> soluciones"""
        description_lower = description.lower()
        
        best_match = None
        best_solution = None
        best_score = 0
        
        for problem_key, solution in problems.items():
            score = self._calculate_match_score(problem_key, description_lower)
            
            if score > best_score:
                best_score = score
                best_match = problem_key
                best_solution = solution
        
        if best_score > 0:
            self.logger.info(f"✅ Solución encontrada: {best_match} (score: {best_score})")
            return best_match, best_solution
        
        return None, None
    
    def _search_in_common_issues(self, issues: List[str], description: str) -> Tuple[Optional[str], Optional[str]]:
        """Buscar en lista de problemas comunes"""
        description_lower = description.lower()
        
        best_match = None
        best_score = 0
        
        for issue in issues:
            score = self._calculate_match_score(issue, description_lower)
            
            if score > best_score:
                best_score = score
                best_match = issue
        
        if best_match:
            # Generar solución genérica para common_issues
            generic_solution = f"Para resolver '{best_match}', consulta el manual técnico o contacta con soporte especializado para este tipo de problema."
            return best_match, generic_solution
        
        return None, None
    
    def _calculate_match_score(self, problem_text: str, user_description: str) -> int:
        """Calcular puntuación de coincidencia entre problema y descripción"""
        problem_lower = problem_text.lower()
        
        # Palabras del usuario
        user_words = set(word for word in user_description.split() if len(word) > 2)
        problem_words = set(word for word in problem_lower.split() if len(word) > 2)
        
        score = 0
        
        # Coincidencias exactas de palabras
        common_words = user_words.intersection(problem_words)
        score += len(common_words) * 3
        
        # Subcadenas importantes
        important_words = ['imprime', 'enciende', 'funciona', 'error', 'problema', 'etiqueta']
        for word in important_words:
            if word in user_description and word in problem_lower:
                score += 2
        
        # Substrings de palabras largas
        for user_word in user_words:
            if len(user_word) > 4:
                for problem_word in problem_words:
                    if user_word in problem_word or problem_word in user_word:
                        score += 1
        
        return score
    
    def get_available_problems(self, incident_type: str) -> List[str]:
        """Obtener lista de problemas disponibles para un tipo"""
        if incident_type not in self.incident_types:
            return []
        
        incident_data = self.incident_types[incident_type]
        
        if "problemas" in incident_data:
            return list(incident_data["problemas"].keys())
        elif "common_issues" in incident_data:
            return incident_data["common_issues"]
        
        return []
    
    def format_problems_for_user(self, incident_type: str, max_problems: int = 6) -> str:
        """Formatear problemas disponibles para mostrar al usuario"""
        problems = self.get_available_problems(incident_type)
        
        if not problems:
            return f"No hay problemas catalogados para {incident_type}"
        
        # Limitar número de problemas mostrados
        display_problems = problems[:max_problems]
        
        incident_name = self.incident_types.get(incident_type, {}).get("name", incident_type)
        
        message = f"Para ayudarte con {incident_name.lower()}, ¿el problema es que:\n\n"
        
        for i, problem in enumerate(display_problems, 1):
            message += f"• {problem}\n"
        
        if len(problems) > max_problems:
            message += f"• Otro problema diferente\n"
        
        message += f"\n¿Cuál describe mejor tu situación?"
        
        return message


# =============================================================================
# 3. MANEJADOR DE CONFIRMACIONES LLM
# =============================================================================

class ConfirmationLLMHandler:
    """
    Maneja la interpretación inteligente de confirmaciones del usuario usando LLM.
    
    RESPONSABILIDADES:
    - Interpretar respuestas del usuario sobre soluciones
    - Detectar intenciones (funcionó, falló, nueva incidencia)
    - Generar respuestas apropiadas
    """
    
    def __init__(self):
        self.llm = get_llm()
        self.parser = JsonOutputParser(pydantic_object=ConfirmationDecision)
        self.prompt = self._build_confirmation_prompt()
        self.logger = logging.getLogger("ConfirmationLLMHandler")
    
    def _build_confirmation_prompt(self) -> PromptTemplate:
        """Construir prompt para interpretación de confirmaciones"""
        return PromptTemplate(
            template="""Eres un especialista en interpretar respuestas de empleados de Eroski.

CONTEXTO:
Se proporcionó una solución al usuario. Necesitas interpretar su respuesta para entender:

MENSAJE DEL USUARIO:
"{user_message}"

SOLUCIÓN PROPORCIONADA:
"{previous_solution}"

INFORMACIÓN DEL EMPLEADO:
- Nombre: {employee_name}
- Tienda: {store_name}  
- Sección: {section}

PATRONES A DETECTAR:

🟢 **SOLUCIÓN EXITOSA:**
- "sí", "funcionó", "perfecto", "resuelto", "ya está", "gracias"
- "lo arreglé", "ya funciona", "todo bien", "listo"

🔴 **SOLUCIÓN FALLÓ:**
- "no", "sigue igual", "no funciona", "persiste", "aún no"
- "intenté pero...", "hice lo que dijiste pero...", "no sirvió"

🆕 **NUEVA INCIDENCIA:**
- "ahora tengo otro problema", "nueva incidencia", "otro tema"
- "además", "también", "por cierto", "diferente problema"
- "en otra sección", "en otra tienda"

❓ **NECESITA CLARIFICACIÓN:**
- "no entendí", "cómo hago", "qué significa", "dónde está"
- "puedes explicar", "más detalles", "paso a paso"

RESPONDE CON JSON VÁLIDO:
{{
    "user_intent": "solution_worked|solution_failed|new_incident|needs_clarification",
    "confidence_level": 0.0,
    "solution_successful": false,
    "additional_details": null,
    "wants_new_incident": false,
    "same_location": null,
    "new_store": null,
    "new_section": null,
    "message_to_user": "Respuesta natural",
    "needs_location_update": false
}}""",
            input_variables=["user_message", "previous_solution", "employee_name", "store_name", "section"]
        )
    
    async def interpret_confirmation(self, state: EroskiState, user_message: str, previous_solution: str) -> ConfirmationDecision:
        """
        Interpretar confirmación del usuario usando LLM.
        
        Args:
            state: Estado actual
            user_message: Mensaje del usuario
            previous_solution: Solución proporcionada anteriormente
            
        Returns:
            Decisión interpretada por el LLM
        """
        auth_data = state.get("auth_data_collected", {})
        
        prompt_input = {
            "user_message": user_message,
            "previous_solution": previous_solution,
            "employee_name": auth_data.get("name", ""),
            "store_name": auth_data.get("store_name", ""),
            "section": auth_data.get("section", "")
        }
        
        try:
            formatted_prompt = self.prompt.format(**prompt_input)
            response = await self.llm.ainvoke(formatted_prompt)
            
            decision_data = self.parser.parse(response.content)
            decision = ConfirmationDecision(**decision_data)
            
            self.logger.info(f"🤖 Interpretación: {decision.user_intent} (confianza: {decision.confidence_level:.2f})")
            
            return decision
            
        except Exception as e:
            self.logger.error(f"❌ Error en interpretación LLM: {e}")
            # Fallback: interpretación básica
            return self._fallback_interpretation(user_message)
    
    def _fallback_interpretation(self, user_message: str) -> ConfirmationDecision:
        """Interpretación fallback sin LLM"""
        message_lower = user_message.lower()
        
        # Patrones básicos
        success_keywords = ["sí", "si", "funcionó", "resuelto", "perfecto", "gracias"]
        failure_keywords = ["no", "sigue", "persiste", "falló"]
        
        if any(keyword in message_lower for keyword in success_keywords):
            return ConfirmationDecision(
                user_intent="solution_worked",
                solution_successful=True,
                confidence_level=0.7,
                message_to_user="Entendido que la solución funcionó"
            )
        elif any(keyword in message_lower for keyword in failure_keywords):
            return ConfirmationDecision(
                user_intent="solution_failed",
                solution_successful=False,
                confidence_level=0.7,
                message_to_user="Entendido que la solución no funcionó"
            )
        else:
            return ConfirmationDecision(
                user_intent="needs_clarification",
                confidence_level=0.3,
                message_to_user="Necesito que confirmes si la solución funcionó o no"
            )


# =============================================================================
# 4. GESTOR DE PERSISTENCIA
# =============================================================================

class IncidentPersistence:
    """
    Maneja la persistencia de incidencias en archivo JSON.
    
    RESPONSABILIDADES:
    - Inicializar registros de incidencia
    - Actualizar información progresivamente
    - Guardar mensajes de conversación
    - Gestionar estados de incidencia
    """
    
    def __init__(self, incidents_file: Path):
        self.incidents_file = incidents_file
        self.logger = logging.getLogger("IncidentPersistence")
    
    def initialize_incident(self, state: EroskiState, incident_code: str) -> bool:
        """
        Inicializar nuevo registro de incidencia.
        
        Args:
            state: Estado actual
            incident_code: Código de la incidencia
            
        Returns:
            True si se inicializó correctamente
        """
        auth_data = state.get("auth_data_collected", {})
        
        incident_record = {
            "codigo_incidencia": incident_code,
            "timestamp_creacion": datetime.now().isoformat(),
            "estado": "abierta",
            
            # Datos obligatorios del empleado
            "nombre_empleado": auth_data.get("name", ""),
            "email_empleado": auth_data.get("email", ""),
            "nombre_tienda": auth_data.get("store_name", ""),
            "seccion": auth_data.get("section", ""),
            
            # Datos de la incidencia (se completarán progresivamente)
            "tipo_incidencia": None,
            "problema_especifico": None,
            "solucion_aplicada": None,
            "estado_solucion": None,
            
            # Conversación
            "mensajes": []
        }
        
        return self._save_incident_record(incident_code, incident_record)
    
    def update_incident(self, incident_code: str, updates: Dict[str, Any]) -> bool:
        """
        Actualizar registro de incidencia.
        
        Args:
            incident_code: Código de la incidencia
            updates: Datos a actualizar
            
        Returns:
            True si se actualizó correctamente
        """
        try:
            incidents_data = self._load_incidents_data()
            
            if incident_code in incidents_data:
                incidents_data[incident_code].update(updates)
                incidents_data[incident_code]["timestamp_actualizacion"] = datetime.now().isoformat()
                
                return self._save_incidents_data(incidents_data)
            else:
                self.logger.warning(f"⚠️ Incidencia {incident_code} no encontrada para actualizar")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error actualizando incidencia {incident_code}: {e}")
            return False
    
    def save_messages(self, incident_code: str, messages: List[Any]) -> bool:
        """
        Guardar mensajes de conversación.
        
        Args:
            incident_code: Código de la incidencia
            messages: Lista de mensajes de LangChain
            
        Returns:
            True si se guardaron correctamente
        """
        # Convertir mensajes a formato serializable
        serialized_messages = []
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                serialized_messages.append({
                    "tipo": "usuario",
                    "contenido": msg.content,
                    "timestamp": datetime.now().isoformat()
                })
            elif isinstance(msg, AIMessage):
                serialized_messages.append({
                    "tipo": "bot",
                    "contenido": msg.content,
                    "timestamp": datetime.now().isoformat()
                })
        
        return self.update_incident(incident_code, {"mensajes": serialized_messages})
    
    def close_incident(self, incident_code: str, closure_reason: str, additional_data: Optional[Dict] = None) -> bool:
        """
        Cerrar incidencia.
        
        Args:
            incident_code: Código de la incidencia
            closure_reason: Razón de cierre
            additional_data: Datos adicionales
            
        Returns:
            True si se cerró correctamente
        """
        closure_data = {
            "estado": "cerrada",
            "timestamp_cierre": datetime.now().isoformat(),
            "razon_cierre": closure_reason
        }
        
        if additional_data:
            closure_data.update(additional_data)
        
        return self.update_incident(incident_code, closure_data)
    
    def get_incident(self, incident_code: str) -> Optional[Dict[str, Any]]:
        """Obtener registro de incidencia específica"""
        try:
            incidents_data = self._load_incidents_data()
            return incidents_data.get(incident_code)
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo incidencia {incident_code}: {e}")
            return None
    
    def get_all_incidents(self) -> Dict[str, Any]:
        """Obtener todas las incidencias"""
        return self._load_incidents_data()
    
    def _load_incidents_data(self) -> Dict[str, Any]:
        """Cargar datos del archivo de incidencias"""
        if not self.incidents_file.exists():
            return {}
        
        try:
            with open(self.incidents_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"❌ Error leyendo archivo de incidencias: {e}")
            return {}
    
    def _save_incidents_data(self, data: Dict[str, Any]) -> bool:
        """Guardar datos en archivo de incidencias"""
        try:
            with open(self.incidents_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"❌ Error guardando archivo de incidencias: {e}")
            return False
    
    def _save_incident_record(self, incident_code: str, record: Dict[str, Any]) -> bool:
        """Guardar registro individual de incidencia"""
        try:
            incidents_data = self._load_incidents_data()
            incidents_data[incident_code] = record
            return self._save_incidents_data(incidents_data)
        except Exception as e:
            self.logger.error(f"❌ Error guardando incidencia {incident_code}: {e}")
            return False


# =============================================================================
# INTERFAZ BASE PARA EXTENSIBILIDAD
# =============================================================================

class IncidentHandler(ABC):
    """Interfaz base para manejadores de incidencia"""
    
    @abstractmethod
    async def handle(self, state: EroskiState) -> Dict[str, Any]:
        """Manejar incidencia específica"""
        pass
    
    @abstractmethod
    def can_handle(self, incident_type: str) -> bool:
        """Verificar si puede manejar el tipo de incidencia"""
        pass


# =============================================================================
# FACTORY PARA CREAR HELPERS
# =============================================================================

class IncidentHelpersFactory:
    """Factory para crear instancias de helpers especializados"""
    
    @staticmethod
    def create_code_manager(incidents_file: Path) -> IncidentCodeManager:
        """Crear gestor de códigos"""
        return IncidentCodeManager(incidents_file)
    
    @staticmethod
    def create_solution_searcher(incident_types: Dict[str, Any]) -> SolutionSearcher:
        """Crear buscador de soluciones"""
        return SolutionSearcher(incident_types)
    
    @staticmethod
    def create_confirmation_handler() -> ConfirmationLLMHandler:
        """Crear manejador de confirmaciones"""
        return ConfirmationLLMHandler()
    
    @staticmethod
    def create_persistence_manager(incidents_file: Path) -> IncidentPersistence:
        """Crear gestor de persistencia"""
        return IncidentPersistence(incidents_file)
    
    @staticmethod
    def create_all_helpers(incident_types: Dict[str, Any], incidents_file: Path) -> Dict[str, Any]:
        """Crear todos los helpers de una vez"""
        return {
            "code_manager": IncidentHelpersFactory.create_code_manager(incidents_file),
            "solution_searcher": IncidentHelpersFactory.create_solution_searcher(incident_types),
            "confirmation_handler": IncidentHelpersFactory.create_confirmation_handler(),
            "persistence_manager": IncidentHelpersFactory.create_persistence_manager(incidents_file)
        }