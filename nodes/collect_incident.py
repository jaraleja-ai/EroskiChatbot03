# =====================================================
# nodes/collect_incident.py - Nodo de Recopilación de Incidencias
# =====================================================
"""
Nodo para recopilar información detallada de incidencias técnicas.

RESPONSABILIDADES:
- Recopilar información faltante para registrar la incidencia
- Validar datos según reglas de negocio de Eroski
- Estructurar información para insertar en PostgreSQL
- Generar número de ticket único
- Determinar si la información es suficiente para proceder

DATOS REQUERIDOS PARA INCIDENCIA:
- Nombre y Apellidos de la persona que reporta
- Código de la Tienda
- Nombre de la Tienda
- Nombre Sección donde se genera la incidencia
- Número de Serie del equipo
- Explicación del Problema
- Solución dada (si la hay)
- Estado de la incidencia (Abierta/Cerrada)
"""

from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging
import uuid
import re

from models.eroski_state import EroskiState
from nodes.base_node import BaseNode

class CollectIncidentDetailsNode(BaseNode):
    """
    Nodo para recopilar detalles completos de incidencias.
    
    CARACTERÍSTICAS:
    - Recopilación inteligente de información faltante
    - Validación de datos según reglas de Eroski
    - Generación de tickets únicos
    - Manejo de información parcial
    """
    
    def __init__(self):
        super().__init__("CollectIncidentDetails")
        
        # Secciones típicas de Eroski
        self.eroski_sections = [
            "Cajas", "Carnicería", "Pescadería", "Charcutería", "Panadería",
            "Frutería", "Perfumería", "Electrodomésticos", "Textil", "Librería",
            "Cafetería", "Gasolinera", "Parking", "Almacén", "Oficina", "Seguridad"
        ]
        
        # Tipos de equipos comunes
        self.equipment_types = [
            "TPV", "Terminal", "Impresora", "Scanner", "Báscula", "Ordenador",
            "Caja registradora", "Dataphone", "Código de barras", "Etiquetadora"
        ]
        
    def get_required_fields(self) -> List[str]:
        return ["messages", "authenticated", "employee_name", "store_id", "store_name"]
    
    def get_actor_description(self) -> str:
        return "Recopilo información detallada de incidencias técnicas para su resolución"
    
    async def execute(self, state: EroskiState) -> Command:
        """
        Ejecutar recopilación de detalles de incidencia.
        
        Args:
            state: Estado actual del workflow
            
        Returns:
            Command con la información recopilada
        """
        try:
            # Verificar si ya tenemos información completa
            if self._has_complete_incident_info(state):
                return self._finalize_incident_collection(state)
            
            # Obtener último mensaje del usuario
            user_message = self.get_last_user_message(state)
            
            # Procesar información del mensaje
            if user_message:
                extracted_info = self._extract_incident_info(user_message)
                updated_state = self._merge_incident_info(state, extracted_info)
            else:
                updated_state = state
            
            # Determinar qué información falta
            missing_fields = self._get_missing_fields(updated_state)
            
            if not missing_fields:
                return self._finalize_incident_collection(updated_state)
            
            # Solicitar información faltante
            return self._request_missing_info(updated_state, missing_fields)
            
        except Exception as e:
            self.logger.error(f"❌ Error recopilando detalles: {e}")
            return self._escalate_error(state, str(e))
    
    def _has_complete_incident_info(self, state: EroskiState) -> bool:
        """Verificar si tenemos información completa"""
        required_fields = [
            "incident_description", "incident_location", "affected_equipment"
        ]
        
        for field in required_fields:
            value = state.get(field)
            if not value or (isinstance(value, str) and len(value.strip()) < 5):
                return False
        
        return True
    
    def _extract_incident_info(self, message: str) -> Dict[str, Any]:
        """Extraer información de incidencia del mensaje"""
        info = {}
        message_lower = message.lower()
        
        # Extraer sección/ubicación
        section_found = None
        for section in self.eroski_sections:
            if section.lower() in message_lower:
                section_found = section
                break
        
        if section_found:
            info["incident_location"] = section_found
        
        # Extraer equipo afectado
        equipment_found = None
        for equipment in self.equipment_types:
            if equipment.lower() in message_lower:
                equipment_found = equipment
                break
        
        if equipment_found:
            info["affected_equipment"] = equipment_found
        
        # Extraer número de serie
        serial_patterns = [
            r'serie[:\s]+([A-Z0-9]{6,})',
            r'número[:\s]+([A-Z0-9]{6,})',
            r'sn[:\s]+([A-Z0-9]{6,})'
        ]
        
        for pattern in serial_patterns:
            match = re.search(pattern, message.upper())
            if match:
                info["equipment_serial"] = match.group(1)
                break
        
        # Extraer códigos de error
        error_patterns = [
            r'error[:\s]+([A-Z0-9]{3,})',
            r'código[:\s]+([A-Z0-9]{3,})'
        ]
        
        error_codes = []
        for pattern in error_patterns:
            matches = re.findall(pattern, message.upper())
            error_codes.extend(matches)
        
        if error_codes:
            info["error_codes"] = error_codes
        
        # La descripción es el mensaje completo si no tenemos una específica
        if not info.get("incident_description"):
            info["incident_description"] = message
        
        return info
    
    def _merge_incident_info(self, state: EroskiState, new_info: Dict[str, Any]) -> EroskiState:
        """Fusionar nueva información con el estado existente"""
        merged = dict(state)
        
        # Fusionar información de incidencia
        current_details = merged.get("incident_details", {})
        current_details.update(new_info)
        merged["incident_details"] = current_details
        
        # Actualizar campos principales
        for key, value in new_info.items():
            if key not in merged or not merged[key]:
                merged[key] = value
        
        return EroskiState(merged)
    
    def _get_missing_fields(self, state: EroskiState) -> List[str]:
        """Obtener lista de campos faltantes"""
        missing = []
        
        # Verificar descripción del problema
        description = state.get("incident_description", "")
        if not description or len(description.strip()) < 10:
            missing.append("incident_description")
        
        # Verificar ubicación/sección
        location = state.get("incident_location", "")
        if not location:
            missing.append("incident_location")
        
        # Verificar equipo afectado
        equipment = state.get("affected_equipment", "")
        if not equipment:
            missing.append("affected_equipment")
        
        return missing
    
    def _request_missing_info(self, state: EroskiState, missing_fields: List[str]) -> Command:
        """Solicitar información faltante al usuario"""
        attempts = state.get("attempts", 0)
        
        if attempts >= 3:
            return self._escalate_incomplete_info(state, missing_fields)
        
        # Construir mensaje personalizado según lo que falte
        message = self._build_missing_info_message(missing_fields, state)
        
        return Command(update={
            "messages": state.get("messages", []) + [AIMessage(content=message)],
            "attempts": attempts + 1,
            "awaiting_user_input": True,
            "current_node": "collect_incident",
            "last_activity": datetime.now(),
            "collection_stage": "awaiting_details"
        })
    
    def _build_missing_info_message(self, missing_fields: List[str], state: EroskiState) -> str:
        """Construir mensaje personalizado para solicitar información faltante"""
        
        if "incident_description" in missing_fields:
            return """📝 **Necesito que me expliques el problema con más detalle**

Para poder ayudarte mejor, necesito que me cuentes:

🔍 **Descripción del problema:**
• ¿Qué exactamente no funciona o qué error estás viendo?
• ¿Cuándo empezó el problema?
• ¿Habías usado este equipo antes sin problemas?

**Ejemplo:** "El TPV de la caja 3 se queda congelado cuando intento procesar pagos con tarjeta. Lleva así desde esta mañana y los clientes tienen que esperar."

Por favor, cuéntame qué está pasando con el mayor detalle posible. 🙏"""
        
        if "incident_location" in missing_fields:
            sections_list = ", ".join(self.eroski_sections[:8]) + "..."
            return f"""📍 **¿En qué sección de la tienda ocurre el problema?**

Para registrar correctamente la incidencia, necesito saber dónde está ubicado el problema.

**Secciones comunes:**
{sections_list}

**Ejemplos válidos:**
• "En las cajas de la entrada principal"
• "En la sección de Carnicería"
• "En la oficina de administración"
• "En el almacén de la planta baja"

¿Podrías indicarme la ubicación exacta? 📍"""
        
        if "affected_equipment" in missing_fields:
            equipment_list = ", ".join(self.equipment_types[:6]) + "..."
            return f"""🔧 **¿Qué equipo o sistema está fallando?**

Para buscar la solución adecuada, necesito saber qué tipo de equipo tiene el problema.

**Equipos comunes:**
{equipment_list}

**Ejemplos válidos:**
• "TPV número 3"
• "Impresora de etiquetas de pescadería"
• "Scanner de códigos de barras"
• "Báscula de la frutería"

¿Qué equipo específico está dando problemas? 🔧"""
        
        # Mensaje genérico para múltiples campos
        return """📋 **Necesito algunos detalles más para ayudarte**

Para resolver tu incidencia de manera efectiva, necesito:

• **Descripción detallada del problema**
• **Ubicación exacta en la tienda**
• **Equipo o sistema afectado**

Por favor, proporciona esta información para continuar. 🙏"""
    
    def _finalize_incident_collection(self, state: EroskiState) -> Command:
        """Finalizar recopilación con información completa"""
        
        # Generar número de ticket único
        ticket_number = self._generate_ticket_number(state)
        
        # Estructurar datos para BD
        incident_data = self._structure_incident_data(state, ticket_number)
        
        # Mensaje de confirmación
        confirmation_message = self._build_confirmation_message(incident_data)
        
        return Command(update={
            "incident_complete": True,
            "ticket_number": ticket_number,
            "incident_data": incident_data,
            "incident_status": "Abierta",
            "messages": state.get("messages", []) + [AIMessage(content=confirmation_message)],
            "awaiting_user_input": False,
            "current_node": "collect_incident",
            "last_activity": datetime.now(),
            "collection_stage": "completed"
        })
    
    def _generate_ticket_number(self, state: EroskiState) -> str:
        """Generar número de ticket único"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        store_id = state.get("store_id", "000")
        random_suffix = str(uuid.uuid4())[:4].upper()
        
        return f"ERK-{store_id}-{timestamp}-{random_suffix}"
    
    def _structure_incident_data(self, state: EroskiState, ticket_number: str) -> Dict[str, Any]:
        """Estructurar datos para insertar en BD"""
        return {
            "ticket_number": ticket_number,
            "employee_name": state.get("employee_name", ""),
            "employee_id": state.get("employee_id", ""),
            "store_code": state.get("store_id", ""),
            "store_name": state.get("store_name", ""),
            "incident_section": state.get("incident_location", ""),
            "equipment_serial": state.get("equipment_serial", ""),
            "problem_description": state.get("incident_description", ""),
            "solution_provided": state.get("solution_provided", ""),
            "incident_status": "Abierta",
            "created_at": datetime.now(),
            "urgency_level": state.get("urgency_level", "Media"),
            "affected_equipment": state.get("affected_equipment", ""),
            "error_codes": state.get("error_codes", []),
            "additional_details": state.get("incident_details", {})
        }
    
    def _build_confirmation_message(self, incident_data: Dict[str, Any]) -> str:
        """Construir mensaje de confirmación"""
        return f"""✅ **INCIDENCIA REGISTRADA CORRECTAMENTE**

📋 **Número de Ticket:** `{incident_data['ticket_number']}`

**Resumen de la incidencia:**
• **Empleado:** {incident_data['employee_name']}
• **Tienda:** {incident_data['store_name']}
• **Sección:** {incident_data['incident_section']}
• **Equipo:** {incident_data['affected_equipment']}
• **Problema:** {incident_data['problem_description'][:100]}...

➡️ **Siguiente paso:** Voy a buscar soluciones disponibles en nuestra base de conocimiento.

⏰ **Tiempo estimado:** 3-5 minutos

📞 **Si es urgente:** Puedes contactar con soporte al +34 946 211 000 mencionando el ticket `{incident_data['ticket_number']}`"""
    
    def _escalate_incomplete_info(self, state: EroskiState, missing_fields: List[str]) -> Command:
        """Escalar por información incompleta"""
        escalation_message = f"""Lo siento, no he podido recopilar toda la información necesaria después de varios intentos. 😔

**Te he derivado a un supervisor** que podrá ayudarte a completar el registro de la incidencia.

**Información faltante:** {', '.join(missing_fields)}

📞 **Para continuar inmediatamente:**
• Soporte técnico: +34 946 211 000
• Menciona que necesitas registrar una incidencia técnica

¡Gracias por tu paciencia! 🙏"""
        
        return Command(update={
            "escalation_needed": True,
            "escalation_reason": f"Información incompleta después de múltiples intentos. Falta: {', '.join(missing_fields)}",
            "escalation_level": "supervisor",
            "messages": state.get("messages", []) + [AIMessage(content=escalation_message)],
            "current_node": "collect_incident",
            "last_activity": datetime.now(),
            "awaiting_user_input": False
        })
    
    def _escalate_error(self, state: EroskiState, error_message: str) -> Command:
        """Escalar por error técnico"""
        return Command(update={
            "escalation_needed": True,
            "escalation_reason": f"Error técnico recopilando información: {error_message}",
            "escalation_level": "technical",
            "messages": state.get("messages", []) + [
                AIMessage(content="Ha ocurrido un error técnico. Te derivo a soporte técnico.")
            ],
            "current_node": "collect_incident",
            "last_activity": datetime.now(),
            "error_count": state.get("error_count", 0) + 1
        })

# ========== WRAPPER PARA LANGGRAPH ==========

async def collect_incident_details_node(state: EroskiState) -> Command:
    """
    Wrapper function para el nodo de recopilación de detalles.
    
    Args:
        state: Estado actual del workflow
        
    Returns:
        Command con la actualización de estado
    """
    node = CollectIncidentDetailsNode()
    return await node.execute(state)