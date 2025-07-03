# =====================================================
# nodes/classify_enhanced.py - Nodo de Clasificación Mejorado
# =====================================================
"""
Nodo para clasificar consultas con lógica de primera visita y análisis LLM.

FUNCIONALIDAD:
1. Primera visita: Analiza histórico de mensajes con LLM
2. Usa archivo de tipologías de incidencias
3. Si encuentra información de incidencia -> siguiente nodo
4. Si no encuentra información -> pide explicación cordial
"""

from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging

from models.eroski_state import EroskiState, ConsultaType
from nodes.base_node import BaseNode
from config.incident_config import get_incident_config
from utils.llm import get_llm
from utils.node_visit_manager import NodeVisitManager
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field

class IncidentAnalysisResult(BaseModel):
    """Resultado del análisis de incidencia por LLM"""
    incident_detected: bool = Field(description="Si se detectó información de incidencia")
    incident_type: Optional[str] = Field(description="Tipo de incidencia identificado")
    incident_description: Optional[str] = Field(description="Descripción extraída de la incidencia")
    confidence: float = Field(description="Confianza del análisis (0.0 a 1.0)")
    reasoning: str = Field(description="Razonamiento del análisis")
    missing_info: List[str] = Field(description="Información que falta para completar")

class ClassifyQueryNodeEnhanced(BaseNode):
    """
    Nodo de clasificación mejorado con análisis LLM y primera visita.
    """
    
    def __init__(self):
        super().__init__("ClassifyQuery")
        self.incident_config = get_incident_config()
        self.llm = get_llm()
        
        # Parser para respuesta del LLM
        self.parser = JsonOutputParser(pydantic_object=IncidentAnalysisResult)
        
        # Prompt para análisis de incidencias
        self.analysis_prompt = PromptTemplate(
            template="""Eres un experto en análisis de incidencias técnicas de Eroski.

Tu tarea es analizar el historial de mensajes del usuario para identificar si hay información sobre una incidencia técnica.

TIPOS DE INCIDENCIAS DISPONIBLES:
{incident_types}

HISTORIAL DE MENSAJES DEL USUARIO:
{message_history}

INSTRUCCIONES:
1. Analiza TODOS los mensajes del usuario (no solo el último)
2. Busca información sobre problemas técnicos, equipos, errores, etc.
3. Si encuentras información de incidencia, identifica el tipo más probable
4. Evalúa qué información falta para resolver el problema
5. Asigna una confianza alta (>0.7) solo si tienes información clara

CRITERIOS PARA DETECTAR INCIDENCIA:
- Menciona problemas con equipos (TPV, impresoras, tablets, etc.)
- Describe errores o fallos
- Indica que algo "no funciona"
- Menciona códigos de error
- Habla de interrupciones en el trabajo

{format_instructions}
""",
            input_variables=["incident_types", "message_history"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
    
    def get_required_fields(self) -> List[str]:
        return ["messages", "authenticated"]
    
    def get_actor_description(self) -> str:
        return "Clasifico consultas y analizo mensajes para identificar incidencias técnicas"
    
    async def execute(self, state: EroskiState) -> Command:
        """
        Ejecutar clasificación con lógica de primera visita.
        """
        print("🎗️" * 50)
        print(f"Entra en el nodo: {self.__class__.__name__}")
        
        try:
            # Verificar si es primera visita
            is_first_visit = NodeVisitManager.is_first_visit(state, self.name)
            
            if is_first_visit:
                return await self._handle_first_visit(state)
            else:
                return await self._handle_revisit(state)
                
        except Exception as e:
            self.logger.error(f"❌ Error en clasificación: {e}")
            return self._handle_error(state, str(e))
    
    async def _handle_first_visit(self, state: EroskiState) -> Command:
        """
        Manejar primera visita - Analizar histórico con LLM.
        """
        self.logger.info("🆕 Primera visita a ClassifyQuery - Analizando histórico con LLM")
        
        # Extraer mensajes del usuario
        user_messages = self._extract_user_messages(state)
        
        if not user_messages:
            return self._request_initial_explanation(state)
        
        # Analizar con LLM
        analysis_result = await self._analyze_messages_with_llm(user_messages)
        
        # Actualizar execution_path
        update_data = NodeVisitManager.update_execution_path(state, self.name)
        
        if analysis_result.incident_detected and analysis_result.confidence > 0.6:
            # Se detectó incidencia - continuar al siguiente nodo
            return self._proceed_to_collect_details(state, analysis_result, update_data)
        else:
            # No se detectó incidencia clara - pedir explicación
            return self._request_incident_explanation(state, analysis_result, update_data)
    
    async def _handle_revisit(self, state: EroskiState) -> Command:
        """
        Manejar revisita - El usuario ha proporcionado más información.
        """
        visit_count = NodeVisitManager.get_visit_count(state, self.name)
        self.logger.info(f"🔄 Revisita #{visit_count} a ClassifyQuery")
        
        # Obtener último mensaje del usuario
        last_message = self.get_last_user_message(state)
        
        if not last_message:
            return self._handle_no_response(state)
        
        # Analizar el nuevo mensaje
        analysis_result = await self._analyze_messages_with_llm([last_message])
        
        # Actualizar execution_path
        update_data = NodeVisitManager.update_execution_path(state, self.name)
        
        if analysis_result.incident_detected and analysis_result.confidence > 0.5:
            # Ahora sí tenemos información de incidencia
            return self._proceed_to_collect_details(state, analysis_result, update_data)
        else:
            # Aún no está claro - intentar clarificar o escalar
            if visit_count >= 3:
                return self._escalate_classification_failure(state, update_data)
            else:
                return self._request_more_specific_info(state, update_data)
    
    def _extract_user_messages(self, state: EroskiState) -> List[str]:
        """
        Extraer solo los mensajes del usuario del historial.
        """
        messages = state.get("messages", [])
        user_messages = []
        
        for msg in messages:
            if isinstance(msg, HumanMessage):
                user_messages.append(msg.content)
        
        return user_messages
    
    async def _analyze_messages_with_llm(self, user_messages: List[str]) -> IncidentAnalysisResult:
        """
        Analizar mensajes del usuario con LLM para detectar incidencias.
        """
        try:
            # Preparar tipos de incidencias disponibles
            incident_types_text = self._format_incident_types()
            
            # Preparar historial de mensajes
            message_history = "\n".join([f"- {msg}" for msg in user_messages])
            
            # Crear prompt
            formatted_prompt = self.analysis_prompt.format(
                incident_types=incident_types_text,
                message_history=message_history
            )
            
            # Invocar LLM
            self.logger.debug("🤖 Invocando LLM para análisis de incidencias")
            response = await self.llm.ainvoke(formatted_prompt)
            
            # Parsear respuesta
            result = self.parser.parse(response.content)
            
            self.logger.info(f"🔍 Análisis LLM - Incidencia detectada: {result.incident_detected}, Confianza: {result.confidence}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"❌ Error en análisis LLM: {e}")
            # Retornar resultado por defecto en caso de error
            return IncidentAnalysisResult(
                incident_detected=False,
                confidence=0.0,
                reasoning=f"Error en análisis: {str(e)}",
                missing_info=["Información técnica del problema"]
            )
    
    def _format_incident_types(self) -> str:
        """
        Formatear tipos de incidencias para el prompt del LLM.
        """
        try:
            all_types = self.incident_config.get_all_incident_types()
            
            formatted_types = []
            for incident_id, incident_type in all_types.items():
                formatted_types.append(
                    f"- {incident_type.name}: {incident_type.description}\n"
                    f"  Palabras clave: {', '.join(incident_type.keywords)}"
                )
            
            return "\n".join(formatted_types)
            
        except Exception as e:
            self.logger.error(f"❌ Error formateando tipos de incidencia: {e}")
            return "No se pudieron cargar los tipos de incidencia"
    
    def _request_initial_explanation(self, state: EroskiState) -> Command:
        """
        Solicitar explicación inicial cuando no hay mensajes del usuario.
        """
        message = """👋 ¡Hola! Soy tu asistente para incidencias técnicas de Eroski.

🔧 **¿Qué problema técnico estás experimentando?**

Puedes contarme sobre:
• 💻 **Problemas con equipos** (TPV, impresoras, tablets, ordenadores)
• 🌐 **Problemas de red o internet**
• 📱 **Aplicaciones que no funcionan**
• ⚡ **Errores o fallos en general**

**Por favor, describe tu problema con el máximo detalle posible.**"""
        
        update_data = NodeVisitManager.update_execution_path(state, self.name)
        update_data.update({
            "current_node": self.name,
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "classification_stage": "requesting_initial_info"
        })
        
        return Command(update=update_data)
    
#**Mi análisis:** {analysis.reasoning}
    def _request_incident_explanation(self, state: EroskiState, analysis: IncidentAnalysisResult, update_data: Dict[str, Any]) -> Command:
        """
        Solicitar explicación de incidencia cuando no se detectó información clara.
        """
        message = """Podrías proporcionarme información sobre la incidencia para ayudarte mejor?.
🔧 **¿Podrías explicarme específicamente:**
• ¿Qué equipo o sistema tiene el problema?
• ¿Qué error aparece exactamente?
• ¿Cuándo comenzó el problema?
• ¿Puedes describir qué no funciona como debería?

**Ejemplo:** "El TPV de la caja 3 muestra error 'CONEXIÓN PERDIDA' desde esta mañana y no puedo cobrar"

¡Con esta información podré ayudarte mucho mejor! 😊"""
        
        update_data.update({
            "current_node": self.name,
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "classification_stage": "requesting_details",
            "llm_analysis": analysis.dict()
        })
        
        return Command(update=update_data)
    
    def _proceed_to_collect_details(self, state: EroskiState, analysis: IncidentAnalysisResult, update_data: Dict[str, Any]) -> Command:
        """
        Proceder al siguiente nodo cuando se detectó incidencia.
        """
        self.logger.info(f"✅ Incidencia detectada: {analysis.incident_type} - Procediendo a recopilar detalles")
        
        update_data.update({
            "current_node": self.name,
            "query_type": ConsultaType.INCIDENCIA,
            "incident_type": analysis.incident_type,
            "incident_description": analysis.incident_description,
            "confidence_score": analysis.confidence,
            "awaiting_user_input": False,
            "classification_stage": "completed",
            "llm_analysis": analysis.dict()
        })
        
        return Command(update=update_data)
    
    def _request_more_specific_info(self, state: EroskiState, update_data: Dict[str, Any]) -> Command:
        """
        Solicitar información más específica en revisitas.
        """
        visit_count = NodeVisitManager.get_visit_count(state, self.name)
        
        message = f"""🔍 Intento #{visit_count} - Necesito información más específica para ayudarte.

Por favor, incluye **todos** estos detalles:

🖥️ **Equipo específico:** (ej: "TPV caja 2", "impresora de etiquetas", "tablet inventario")
❌ **Error exacto:** (ej: mensaje que aparece, código de error)
⏰ **Cuándo ocurre:** (ej: "desde esta mañana", "al imprimir tickets")
🔄 **Frecuencia:** (ej: "siempre", "a veces", "solo al hacer X")

**Ejemplo completo:** "La impresora de la caja 1 no imprime tickets desde las 9:00. Aparece luz roja parpadeando y en pantalla dice 'Error 502 - Papel atascado'. He revisado y no hay papel atascado visible."

¡Así podré diagnosticar el problema correctamente! 🔧"""
        
        update_data.update({
            "current_node": self.name,
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "classification_stage": "requesting_specific_details"
        })
        
        return Command(update=update_data)
    
    def _escalate_classification_failure(self, state: EroskiState, update_data: Dict[str, Any]) -> Command:
        """
        Escalar cuando no se puede clasificar después de varios intentos.
        """
        message = """🔼 **Derivando a especialista técnico**

No he podido identificar claramente tu problema después de varios intentos.

📞 **Te conectaré directamente con soporte técnico:**
• **Teléfono:** +34 946 211 000 (ext. 123)
• **Email:** soporte.tecnico@eroski.es
• **Interno:** Extensión 123

**Ellos podrán:**
✅ Diagnóstico presencial si es necesario
✅ Acceso remoto a equipos
✅ Escalación a proveedores externos

**Datos que puedes mencionar:**
🆔 Sesión: {session_id}
📅 Hora: {timestamp}

¡Gracias por tu paciencia! 🙏"""
        
        session_id = state.get("session_id", "N/A")
        timestamp = datetime.now().strftime("%d/%m/%Y %H:%M")
        
        formatted_message = message.format(session_id=session_id, timestamp=timestamp)
        
        update_data.update({
            "escalation_needed": True,
            "escalation_reason": "No se pudo clasificar la consulta después de múltiples intentos",
            "escalation_level": "technical_support",
            "current_node": self.name,
            "messages": state.get("messages", []) + [AIMessage(content=formatted_message)],
            "awaiting_user_input": False,
            "classification_stage": "escalated"
        })
        
        return Command(update=update_data)
    
    def _handle_no_response(self, state: EroskiState) -> Command:
        """
        Manejar caso donde el usuario no responde.
        """
        message = """⏰ No he recibido tu respuesta.

🔄 **¿Sigues ahí?** Si necesitas tiempo para revisar el problema, no hay problema.

**Cuando estés listo, describe:**
• Qué equipo tiene el problema
• Qué error aparece
• Desde cuándo ocurre

Si prefieres hablar directamente con alguien:
📞 **Soporte:** +34 946 211 000 (ext. 123)"""
        
        update_data = NodeVisitManager.update_execution_path(state, self.name)
        update_data.update({
            "current_node": self.name,
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": True,
            "classification_stage": "waiting_response"
        })
        
        return Command(update=update_data)
    
    def _handle_error(self, state: EroskiState, error_message: str) -> Command:
        """
        Manejar errores en la clasificación.
        """
        self.logger.error(f"❌ Error en ClassifyQuery: {error_message}")
        
        message = """❌ **Error técnico temporal**

Ha ocurrido un problema al procesar tu consulta.

📞 **Por favor, contacta directamente:**
• **Soporte técnico:** +34 946 211 000 (ext. 123)
• **Email:** soporte.tecnico@eroski.es

**Proporciona este código de error:** CLASSIFY_ERROR

¡Disculpa las molestias! 🙏"""
        
        update_data = {
            "error_count": state.get("error_count", 0) + 1,
            "last_error": error_message,
            "escalation_needed": True,
            "escalation_reason": f"Error técnico en clasificación: {error_message}",
            "current_node": self.name,
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "awaiting_user_input": False
        }
        
        return Command(update=update_data)

# =====================================================
# Utilidad: NodeVisitManager
# =====================================================

class NodeVisitManager:
    """Gestor para manejar lógica de primera visita vs revisita"""
    
    @staticmethod
    def is_first_visit(state: EroskiState, node_name: str) -> bool:
        """Verificar si es la primera vez que se visita un nodo"""
        execution_path = state.get("execution_path", [])
        return node_name not in execution_path
    
    @staticmethod
    def get_visit_count(state: EroskiState, node_name: str) -> int:
        """Contar cuántas veces se ha visitado un nodo"""
        execution_path = state.get("execution_path", [])
        return execution_path.count(node_name)
    
    @staticmethod
    def update_execution_path(state: EroskiState, node_name: str) -> Dict[str, Any]:
        """Actualizar execution_path con la visita actual"""
        current_path = state.get("execution_path", [])
        return {
            "execution_path": current_path + [node_name],
            "last_activity": datetime.now()
        }

# =====================================================
# Archivo de configuración de incidencias requerido
# =====================================================

# Crear archivo: config/incident_types.json
SAMPLE_INCIDENT_CONFIG = {
    "incident_types": {
        "tpv": {
            "name": "TPV (Terminal Punto de Venta)",
            "description": "Problemas con cajas registradoras y sistemas de cobro",
            "keywords": ["tpv", "caja", "terminal", "cobro", "ticket", "registradora"],
            "urgency_level": 3,
            "category": "hardware",
            "requires_technical_support": True
        },
        "impresora": {
            "name": "Impresoras",
            "description": "Problemas con impresoras de tickets, etiquetas o documentos",
            "keywords": ["impresora", "imprimir", "papel", "tinta", "atasco", "ticket"],
            "urgency_level": 2,
            "category": "hardware",
            "requires_technical_support": False
        },
        "red": {
            "name": "Conectividad de Red",
            "description": "Problemas de internet, WiFi o conexiones de red",
            "keywords": ["internet", "wifi", "red", "conexión", "lento", "desconectado"],
            "urgency_level": 3,
            "category": "network",
            "requires_technical_support": True
        },
        "software": {
            "name": "Software y Aplicaciones",
            "description": "Problemas con programas, aplicaciones o sistemas informáticos",
            "keywords": ["programa", "aplicación", "software", "sistema", "error", "pantalla"],
            "urgency_level": 2,
            "category": "software",
            "requires_technical_support": False
        }
    }
}