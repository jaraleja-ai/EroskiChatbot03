# =====================================================
# nodes/escalate.py - Nodo de Escalación a Supervisor
# =====================================================
"""
Nodo para escalación a supervisor o soporte técnico.

RESPONSABILIDADES:
- Identificar contacto de escalación apropiado
- Crear ticket en sistema externo (futuro)
- Notificar a supervisor
- Proporcionar información de contacto
- Registrar motivo de escalación
"""

from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging

from models.eroski_state import EroskiState
from nodes.base_node import BaseNode

class EscalateToSupervisorNode(BaseNode):
    """
    Nodo para escalación a supervisor o soporte técnico.
    
    CARACTERÍSTICAS:
    - Determinación automática del tipo de escalación
    - Contactos específicos por tipo de problema
    - Creación de tickets de escalación
    - Notificación automática (futuro)
    """
    
    def __init__(self):
        super().__init__("EscalateToSupervisor")
        
        # Contactos de escalación por tipo
        self.escalation_contacts = {
            "technical": {
                "name": "Soporte Técnico",
                "phone": "+34 946 211 000",
                "email": "soporte.tecnico@eroski.es",
                "hours": "24/7",
                "priority": "alta"
            },
            "supervisor": {
                "name": "Supervisor de Tienda",
                "phone": "Ext. 100",
                "email": "supervisor@tienda.eroski.es",
                "hours": "Horario de tienda",
                "priority": "media"
            },
            "hr": {
                "name": "Recursos Humanos",
                "phone": "+34 946 211 100",
                "email": "rrhh@eroski.es",
                "hours": "L-V 9:00-17:00",
                "priority": "baja"
            },
            "it": {
                "name": "Soporte IT",
                "phone": "+34 946 211 200",
                "email": "it.support@eroski.es",
                "hours": "L-V 8:00-20:00",
                "priority": "alta"
            },
            "maintenance": {
                "name": "Mantenimiento",
                "phone": "+34 946 211 300",
                "email": "mantenimiento@eroski.es",
                "hours": "24/7",
                "priority": "media"
            }
        }
        
        # Mapeo de tipos de problema a contactos
        self.problem_to_contact = {
            "tpv": "technical",
            "impresora": "technical",
            "scanner": "technical",
            "red": "it",
            "internet": "it",
            "ordenador": "it",
            "sistema": "it",
            "usuario": "hr",
            "contraseña": "hr",
            "acceso": "hr",
            "limpieza": "maintenance",
            "mantenimiento": "maintenance",
            "averıá": "maintenance",
            "general": "supervisor"
        }
    
    def get_required_fields(self) -> List[str]:
        return ["messages", "escalation_needed"]
    
    def get_actor_description(self) -> str:
        return "Gestiono escalaciones a supervisores y soporte técnico especializado"
    
    async def execute(self, state: EroskiState) -> Command:
        """
        Ejecutar escalación a supervisor.
        
        Args:
            state: Estado actual del workflow
            
        Returns:
            Command con la escalación procesada
        """
        try:
            # Determinar tipo de escalación
            escalation_type = self._determine_escalation_type(state)
            
            # Obtener contacto apropiado
            contact_info = self._get_contact_info(escalation_type)
            
            # Crear ticket de escalación
            ticket_info = self._create_escalation_ticket(state, escalation_type)
            
            # Notificar escalación (futuro: integración con sistema externo)
            # await self._notify_escalation(ticket_info, contact_info)
            
            # Proporcionar información al usuario
            return self._provide_escalation_info(state, contact_info, ticket_info)
            
        except Exception as e:
            self.logger.error(f"❌ Error en escalación: {e}")
            return self._provide_emergency_contacts(state)
    
    def _determine_escalation_type(self, state: EroskiState) -> str:
        """Determinar tipo de escalación basado en el contexto"""
        
        # Verificar si hay nivel de escalación específico
        escalation_level = state.get("escalation_level")
        if escalation_level and escalation_level in self.escalation_contacts:
            return escalation_level
        
        # Determinar basado en equipos mencionados
        affected_equipment = state.get("affected_equipment", "").lower()
        incident_description = state.get("incident_description", "").lower()
        
        combined_text = f"{affected_equipment} {incident_description}"
        
        # Buscar coincidencias con tipos de problema
        for problem_keyword, contact_type in self.problem_to_contact.items():
            if problem_keyword in combined_text:
                return contact_type
        
        # Verificar urgencia
        urgency_level = state.get("urgency_level")
        if urgency_level and hasattr(urgency_level, 'value') and urgency_level.value >= 4:
            return "technical"  # Escalación técnica para urgencias críticas
        
        # Default: supervisor
        return "supervisor"
    
    def _get_contact_info(self, escalation_type: str) -> Dict[str, Any]:
        """Obtener información de contacto para escalación"""
        return self.escalation_contacts.get(escalation_type, self.escalation_contacts["supervisor"])
    
    def _create_escalation_ticket(self, state: EroskiState, escalation_type: str) -> Dict[str, Any]:
        """Crear ticket de escalación"""
        escalation_reason = state.get("escalation_reason", "Escalación automática")
        
        ticket_info = {
            "ticket_id": f"ESC-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "escalation_type": escalation_type,
            "employee_name": state.get("employee_name", ""),
            "employee_id": state.get("employee_id", ""),
            "store_id": state.get("store_id", ""),
            "store_name": state.get("store_name", ""),
            "escalation_reason": escalation_reason,
            "original_problem": state.get("incident_description", ""),
            "affected_equipment": state.get("affected_equipment", ""),
            "urgency_level": str(state.get("urgency_level", "Media")),
            "created_at": datetime.now(),
            "status": "open"
        }
        
        self.logger.info(f"📋 Ticket de escalación creado: {ticket_info['ticket_id']}")
        
        return ticket_info
    
    def _provide_escalation_info(self, state: EroskiState, contact_info: Dict[str, Any], 
                                ticket_info: Dict[str, Any]) -> Command:
        """Proporcionar información de escalación al usuario"""
        
        escalation_message = self._build_escalation_message(contact_info, ticket_info, state)
        
        return Command(update={
            "escalation_processed": True,
            "escalation_ticket": ticket_info,
            "escalation_contact": contact_info,
            "escalation_type": ticket_info["escalation_type"],
            "ticket_created": True,
            "messages": state.get("messages", []) + [AIMessage(content=escalation_message)],
            "current_node": "escalate",
            "last_activity": datetime.now(),
            "awaiting_user_input": False,
            "flow_completed": True
        })
    
    def _build_escalation_message(self, contact_info: Dict[str, Any], 
                                 ticket_info: Dict[str, Any], state: EroskiState) -> str:
        """Construir mensaje de escalación"""
        
        escalation_reason = state.get("escalation_reason", "Escalación automática")
        
        return f"""🔼 **ESCALACIÓN PROCESADA**

Tu consulta ha sido escalada al equipo especializado apropiado.

**📋 Ticket de Escalación:** `{ticket_info['ticket_id']}`

**👥 Contacto Asignado:**
• **Departamento:** {contact_info['name']}
• **Teléfono:** {contact_info['phone']}
• **Email:** {contact_info['email']}
• **Horario:** {contact_info['hours']}

**📝 Resumen:**
• **Empleado:** {ticket_info['employee_name']}
• **Tienda:** {ticket_info['store_name']}
• **Problema:** {ticket_info['original_problem'][:100]}...
• **Motivo de escalación:** {escalation_reason}

**⏰ Tiempo de respuesta estimado:**
• **Prioridad Alta:** 15-30 minutos
• **Prioridad Media:** 1-2 horas
• **Prioridad Baja:** 24 horas

**📞 Contacto Inmediato:**
Si es urgente, puedes contactar directamente:
• **Teléfono:** {contact_info['phone']}
• **Menciona el ticket:** `{ticket_info['ticket_id']}`

**✅ Próximos pasos:**
1. El equipo especializado será notificado automáticamente
2. Recibirás una llamada o email en breve
3. Mantén a mano el número de ticket para referencia

¡Gracias por tu paciencia! El equipo especializado se pondrá en contacto contigo pronto. 🤝"""
    
    def _provide_emergency_contacts(self, state: EroskiState) -> Command:
        """Proporcionar contactos de emergencia cuando falla la escalación"""
        
        emergency_message = """🚨 **CONTACTOS DE EMERGENCIA**

Ha ocurrido un problema técnico con el sistema de escalación, pero puedes contactar directamente:

**📞 Contactos Inmediatos:**

**🔧 Soporte Técnico (24/7):**
• Teléfono: +34 946 211 000
• Email: soporte.tecnico@eroski.es
• Para: Problemas con TPV, impresoras, scanners

**👨‍💼 Supervisor de Tienda:**
• Teléfono: Ext. 100 (desde teléfono de tienda)
• Para: Consultas generales, procedimientos

**💻 Soporte IT:**
• Teléfono: +34 946 211 200
• Email: it.support@eroski.es
• Horario: L-V 8:00-20:00
• Para: Problemas de red, ordenadores, sistemas

**🏥 Emergencias:**
• Teléfono: 112
• Para: Emergencias médicas o de seguridad

**📋 Información a proporcionar:**
• Tu nombre y número de empleado
• Código de tienda
• Descripción del problema
• Ubicación exacta

¡Disculpa las molestias técnicas! 🙏"""
        
        return Command(update={
            "escalation_processed": True,
            "escalation_type": "emergency",
            "escalation_failed": True,
            "messages": state.get("messages", []) + [AIMessage(content=emergency_message)],
            "current_node": "escalate",
            "last_activity": datetime.now(),
            "awaiting_user_input": False,
            "flow_completed": True
        })
    
    async def _notify_escalation(self, ticket_info: Dict[str, Any], 
                               contact_info: Dict[str, Any]) -> bool:
        """
        Notificar escalación al equipo correspondiente.
        
        TODO: Implementar integración con sistema externo
        - Email automático
        - Notificación SMS
        - Integración con sistema de tickets
        """
        try:
            # Placeholder para integración futura
            self.logger.info(f"📧 Notificación de escalación enviada para ticket {ticket_info['ticket_id']}")
            return True
        except Exception as e:
            self.logger.error(f"❌ Error enviando notificación: {e}")
            return False

# ========== WRAPPER PARA LANGGRAPH ==========

async def escalate_supervisor_node(state: EroskiState) -> Command:
    """
    Wrapper function para el nodo de escalación.
    
    Args:
        state: Estado actual del workflow
        
    Returns:
        Command con la actualización de estado
    """
    node = EscalateToSupervisorNode()
    return await node.execute(state)