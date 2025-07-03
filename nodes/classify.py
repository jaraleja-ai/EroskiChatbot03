# =====================================================
# nodes/classify.py - Nodo de Clasificación de Consultas
# =====================================================
"""
Nodo para clasificar el tipo de consulta del empleado.

RESPONSABILIDADES:
- Analizar el mensaje del usuario para determinar tipo de consulta
- Clasificar como: INCIDENCIA, CONSULTA, URGENTE, NO_CLARO
- Extraer información técnica relevante
- Asignar nivel de urgencia
- Determinar si requiere escalación inmediata
"""

from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging
import re

from models.eroski_state import EroskiState, ConsultaType, UrgencyLevel
from nodes.base_node import BaseNode
from config.incident_config import get_incident_config

class ClassifyQueryNode(BaseNode):
    """
    Nodo para clasificar consultas de empleados de Eroski.
    
    CARACTERÍSTICAS:
    - Clasificación inteligente usando keywords
    - Detección de urgencia automática
    - Integración con configuración de tipos de incidencia
    - Extracción de información técnica
    """
    
    def __init__(self):
        super().__init__("ClassifyQuery")
        self.incident_config = get_incident_config()
        
        # Palabras clave para clasificación
        self.urgency_keywords = [
            "urgente", "crítico", "emergencia", "parado", "bloqueado",
            "no funciona", "roto", "error crítico", "inmediato", "ya"
        ]
        
        self.consultation_keywords = [
            "consulta", "pregunta", "información", "cómo", "dónde", "cuándo",
            "estado", "revisar", "verificar", "confirmar", "saber"
        ]
        
        self.incident_keywords = [
            "problema", "error", "fallo", "incidencia", "no funciona",
            "roto", "avería", "defecto", "bug", "mal"
        ]
        
    def get_required_fields(self) -> List[str]:
        return ["messages", "authenticated"]
    
    def get_actor_description(self) -> str:
        return "Clasifico consultas de empleados para determinar el tipo de atención requerida"
    
    async def execute(self, state: EroskiState) -> Command:
        """
        Ejecutar clasificación de la consulta.
        
        Args:
            state: Estado actual del workflow
            
        Returns:
            Command con la clasificación realizada
        """
        try:
            # Obtener último mensaje del usuario
            user_message = self.get_last_user_message(state)
            if not user_message:
                return self._request_clarification(state, "No he recibido ningún mensaje para clasificar")
            
            # Realizar clasificación
            classification_result = self._classify_message(user_message)
            
            # Determinar siguiente acción
            if classification_result["confidence"] < 0.5:
                return self._request_clarification(state, 
                    "No estoy seguro del tipo de consulta. ¿Podrías ser más específico?")
            
            # Actualizar estado con clasificación
            return self._update_state_with_classification(state, classification_result)
            
        except Exception as e:
            self.logger.error(f"❌ Error en clasificación: {e}")
            return self._escalate_error(state, str(e))
    
    def _classify_message(self, message: str) -> Dict[str, Any]:
        """
        Clasificar mensaje del usuario.
        
        Args:
            message: Mensaje a clasificar
            
        Returns:
            Diccionario con resultado de clasificación
        """
        message_lower = message.lower()
        
        # Búsqueda en configuración de incidencias
        incident_matches = self.incident_config.search_by_keywords(message, limit=3)
        
        # Calcular puntuaciones
        urgency_score = self._calculate_keyword_score(message_lower, self.urgency_keywords)
        consultation_score = self._calculate_keyword_score(message_lower, self.consultation_keywords)
        incident_score = self._calculate_keyword_score(message_lower, self.incident_keywords)
        
        # Bonus por coincidencias en configuración
        if incident_matches:
            incident_score += incident_matches[0]["score"] / 10
        
        # Determinar clasificación
        query_type = None
        confidence = 0.0
        urgency_level = UrgencyLevel.MEDIA
        
        if urgency_score > 0.3:
            query_type = ConsultaType.URGENTE
            confidence = urgency_score
            urgency_level = UrgencyLevel.ALTA
        elif incident_score > consultation_score and incident_score > 0.2:
            query_type = ConsultaType.INCIDENCIA
            confidence = incident_score
            urgency_level = self._determine_urgency_level(message_lower, incident_matches)
        elif consultation_score > 0.2:
            query_type = ConsultaType.CONSULTA
            confidence = consultation_score
            urgency_level = UrgencyLevel.BAJA
        else:
            query_type = ConsultaType.NO_CLARO
            confidence = 0.1
        
        # Extraer información técnica
        technical_info = self._extract_technical_info(message)
        
        return {
            "query_type": query_type,
            "confidence": confidence,
            "urgency_level": urgency_level,
            "technical_info": technical_info,
            "incident_matches": incident_matches[:2],  # Solo top 2
            "classification_reason": self._get_classification_reason(
                query_type, urgency_score, consultation_score, incident_score
            )
        }
    
    def _calculate_keyword_score(self, text: str, keywords: List[str]) -> float:
        """Calcular puntuación basada en palabras clave"""
        matches = sum(1 for keyword in keywords if keyword in text)
        return min(matches / len(keywords), 1.0)
    
    def _determine_urgency_level(self, message: str, incident_matches: List[Dict]) -> UrgencyLevel:
        """Determinar nivel de urgencia basado en contexto"""
        # Palabras de urgencia crítica
        critical_keywords = ["parado", "bloqueado", "no funciona", "roto", "emergencia"]
        if any(keyword in message for keyword in critical_keywords):
            return UrgencyLevel.CRITICA
        
        # Basado en tipo de incidencia
        if incident_matches and incident_matches[0]["incident_type"].urgency_level >= 3:
            return UrgencyLevel.ALTA
        
        # Hora del día (horario comercial = más urgente)
        current_hour = datetime.now().hour
        if 8 <= current_hour <= 20:
            return UrgencyLevel.MEDIA
        
        return UrgencyLevel.BAJA
    
    def _extract_technical_info(self, message: str) -> Dict[str, Any]:
        """Extraer información técnica del mensaje"""
        technical_info = {}
        
        # Códigos de error
        error_codes = re.findall(r'error\s*[\:\-]?\s*(\w+\d+|\d+)', message.lower())
        if error_codes:
            technical_info["error_codes"] = error_codes
        
        # Números de serie
        serial_numbers = re.findall(r'serie\s*[\:\-]?\s*([A-Z0-9]{6,})', message.upper())
        if serial_numbers:
            technical_info["serial_numbers"] = serial_numbers
        
        # Equipos mencionados
        equipment_keywords = ["tpv", "caja", "terminal", "impresora", "scanner", "ordenador"]
        equipment = [eq for eq in equipment_keywords if eq in message.lower()]
        if equipment:
            technical_info["equipment"] = equipment
        
        # Ubicaciones en tienda
        location_keywords = ["caja", "almacén", "oficina", "entrada", "salida", "parking"]
        locations = [loc for loc in location_keywords if loc in message.lower()]
        if locations:
            technical_info["locations"] = locations
        
        return technical_info
    
    def _get_classification_reason(self, query_type: ConsultaType, 
                                 urgency_score: float, consultation_score: float, 
                                 incident_score: float) -> str:
        """Obtener razón de la clasificación"""
        if query_type == ConsultaType.URGENTE:
            return f"Detectada urgencia (puntuación: {urgency_score:.2f})"
        elif query_type == ConsultaType.INCIDENCIA:
            return f"Detectada incidencia (puntuación: {incident_score:.2f})"
        elif query_type == ConsultaType.CONSULTA:
            return f"Detectada consulta (puntuación: {consultation_score:.2f})"
        else:
            return "Clasificación no clara, requiere clarificación"
    
    def _update_state_with_classification(self, state: EroskiState, 
                                        classification: Dict[str, Any]) -> Command:
        """Actualizar estado con resultado de clasificación"""
        
        # Mensaje de confirmación al usuario
        confirmation_message = self._build_confirmation_message(classification)
        
        return Command(update={
            "query_type": classification["query_type"],
            "confidence_score": classification["confidence"],
            "urgency_level": classification["urgency_level"],
            "technical_info": classification["technical_info"],
            "incident_matches": classification["incident_matches"],
            "classification_reason": classification["classification_reason"],
            "messages": state.get("messages", []) + [AIMessage(content=confirmation_message)],
            "current_node": "classify",
            "last_activity": datetime.now(),
            "awaiting_user_input": False
        })
    
    def _build_confirmation_message(self, classification: Dict[str, Any]) -> str:
        """Construir mensaje de confirmación para el usuario"""
        query_type = classification["query_type"]
        
        if query_type == ConsultaType.URGENTE:
            return """🚨 **CONSULTA URGENTE DETECTADA**

He identificado que tu consulta es **urgente** y requiere atención inmediata.

➡️ **Siguiente paso:** Te conectaré directamente con un supervisor para atención prioritaria.

⏰ **Tiempo estimado:** 2-5 minutos"""
        
        elif query_type == ConsultaType.INCIDENCIA:
            incident_info = ""
            if classification["incident_matches"]:
                top_match = classification["incident_matches"][0]
                incident_info = f"\n📋 **Tipo detectado:** {top_match['incident_type'].name}"
            
            return f"""🔧 **INCIDENCIA TÉCNICA DETECTADA**

He identificado que reportas una **incidencia técnica** que requiere resolución.{incident_info}

➡️ **Siguiente paso:** Voy a recopilar los detalles necesarios para buscar una solución.

⏰ **Tiempo estimado:** 5-15 minutos"""
        
        elif query_type == ConsultaType.CONSULTA:
            return """❓ **CONSULTA GENERAL DETECTADA**

He identificado que tienes una **consulta general** o necesitas información.

➡️ **Siguiente paso:** Te ayudaré a encontrar la información que necesitas.

⏰ **Tiempo estimado:** 2-5 minutos"""
        
        else:
            return """❔ **NECESITO MÁS INFORMACIÓN**

No he podido identificar claramente el tipo de consulta.

➡️ **Siguiente paso:** Te haré algunas preguntas para entender mejor cómo ayudarte."""
    
    def _request_clarification(self, state: EroskiState, reason: str) -> Command:
        """Solicitar clarificación al usuario"""
        attempts = state.get("attempts", 0)
        
        if attempts >= 2:
            return self._escalate_classification_failure(state, reason)
        
        clarification_message = f"""❔ **Necesito que me ayudes a entender tu consulta**

{reason}

**Por favor, cuéntame:**
• ¿Qué tipo de problema o consulta tienes?
• ¿Es algo urgente que necesita atención inmediata?
• ¿Hay algún equipo o sistema involucrado?

**Ejemplos útiles:**
• "El TPV de la caja 3 no funciona y hay cola de clientes"
• "Necesito información sobre el nuevo procedimiento de devoluciones"
• "¿Cómo configuro mi usuario en el sistema?"

¿Podrías darme más detalles? 🙏"""
        
        return Command(update={
            "messages": state.get("messages", []) + [AIMessage(content=clarification_message)],
            "attempts": attempts + 1,
            "awaiting_user_input": True,
            "current_node": "classify",
            "last_activity": datetime.now(),
            "classification_stage": "awaiting_clarification"
        })
    
    def _escalate_classification_failure(self, state: EroskiState, reason: str) -> Command:
        """Escalar por fallo en clasificación"""
        escalation_message = """Lo siento, no he podido entender el tipo de consulta después de varios intentos. 😔

**No te preocupes** - Te he derivado a un supervisor que podrá ayudarte directamente.

📞 **Para consultas urgentes inmediatas:**
• Soporte técnico: +34 946 211 000
• Email: soporte.tecnico@eroski.es

¡Gracias por tu paciencia! 🙏"""
        
        return Command(update={
            "escalation_needed": True,
            "escalation_reason": f"Fallo en clasificación después de múltiples intentos: {reason}",
            "escalation_level": "supervisor",
            "messages": state.get("messages", []) + [AIMessage(content=escalation_message)],
            "current_node": "classify",
            "last_activity": datetime.now(),
            "awaiting_user_input": False
        })
    
    def _escalate_error(self, state: EroskiState, error_message: str) -> Command:
        """Escalar por error técnico"""
        return Command(update={
            "escalation_needed": True,
            "escalation_reason": f"Error técnico en clasificación: {error_message}",
            "escalation_level": "technical",
            "messages": state.get("messages", []) + [
                AIMessage(content="Ha ocurrido un error técnico. Te derivo a soporte técnico.")
            ],
            "current_node": "classify",
            "last_activity": datetime.now(),
            "error_count": state.get("error_count", 0) + 1
        })

# ========== WRAPPER PARA LANGGRAPH ==========

async def classify_query_node(state: EroskiState) -> Command:
    """
    Wrapper function para el nodo de clasificación.
    
    Args:
        state: Estado actual del workflow
        
    Returns:
        Command con la actualización de estado
    """
    node = ClassifyQueryNode()
    return await node.execute(state)