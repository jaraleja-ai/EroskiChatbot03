# =====================================================
# utils/eroski_systems.py - Integración con Sistemas Eroski
# =====================================================
"""
Utilidades para integración con sistemas internos de Eroski.

SISTEMAS INTEGRADOS:
- Active Directory (validación de empleados)
- SAP (creación de tickets)
- Base de datos de tiendas
- Sistema de inventario
- Contactos de escalación

NOTA: Este módulo contiene implementaciones mock para desarrollo.
En producción debe conectar con los sistemas reales de Eroski.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
import re

logger = logging.getLogger("EroskiSystems")

class EroskiEmployeeValidator:
    """
    Validador de empleados contra sistemas de Eroski.
    
    IMPLEMENTACIÓN:
    - Versión actual: Mock para desarrollo
    - Versión producción: Integración con Active Directory
    
    RESPONSABILIDADES:
    - Validar credenciales de empleados
    - Obtener información de tiendas
    - Verificar permisos y roles
    """
    
    def __init__(self):
        self.logger = logging.getLogger("EmployeeValidator")
        
        # Base de datos mock de empleados para desarrollo
        self.mock_employees = {
            "juan.perez@eroski.es": {
                "id": "E001",
                "name": "Juan Pérez",
                "email": "juan.perez@eroski.es",
                "store_id": "ERO001",
                "store_name": "Eroski Bilbao Centro",
                "store_type": "hipermercado",
                "department": "Tecnología",
                "level": 2,
                "shift": "mañana",
                "active": True
            },
            "maria.garcia@eroski.es": {
                "id": "E002", 
                "name": "María García",
                "email": "maria.garcia@eroski.es",
                "store_id": "ERO002",
                "store_name": "Eroski Madrid Salamanca",
                "store_type": "supermercado",
                "department": "Caja",
                "level": 1,
                "shift": "tarde",
                "active": True
            },
            "admin.test@eroski.es": {
                "id": "E999",
                "name": "Admin Test",
                "email": "admin.test@eroski.es", 
                "store_id": "ERO999",
                "store_name": "Eroski Test Store",
                "store_type": "test",
                "department": "IT",
                "level": 3,
                "shift": "completa",
                "active": True
            },
            "supervisor.bilbao@eroski.es": {
                "id": "S001",
                "name": "Ana Supervisor",
                "email": "supervisor.bilbao@eroski.es",
                "store_id": "ERO001", 
                "store_name": "Eroski Bilbao Centro",
                "store_type": "hipermercado",
                "department": "Supervisión",
                "level": 3,
                "shift": "completa",
                "active": True
            },
            "tecnico.madrid@eroski.es": {
                "id": "T001",
                "name": "Carlos Técnico",
                "email": "tecnico.madrid@eroski.es",
                "store_id": "ERO002",
                "store_name": "Eroski Madrid Salamanca", 
                "store_type": "supermercado",
                "department": "IT",
                "level": 2,
                "shift": "mañana",
                "active": True
            }
        }
        
        # Base de datos de tiendas
        self.mock_stores = {
            "ERO001": {
                "id": "ERO001",
                "name": "Eroski Bilbao Centro",
                "type": "hipermercado",
                "address": "Gran Vía 1, Bilbao",
                "phone": "+34 944 123 456",
                "region": "País Vasco",
                "manager": "supervisor.bilbao@eroski.es"
            },
            "ERO002": {
                "id": "ERO002", 
                "name": "Eroski Madrid Salamanca",
                "type": "supermercado",
                "address": "Calle Salamanca 100, Madrid",
                "phone": "+34 91 123 456", 
                "region": "Madrid",
                "manager": "gerente.madrid@eroski.es"
            },
            "ERO999": {
                "id": "ERO999",
                "name": "Eroski Test Store", 
                "type": "test",
                "address": "Test Address",
                "phone": "+34 900 000 000",
                "region": "Test",
                "manager": "admin.test@eroski.es"
            }
        }
    
    async def validate_employee(
        self, 
        email: str, 
        store_hint: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Validar empleado contra sistemas Eroski.
        
        Args:
            email: Email del empleado
            store_hint: Pista sobre la tienda (opcional)
            
        Returns:
            Datos del empleado si es válido, None en caso contrario
        """
        try:
            self.logger.info(f"🔍 Validando empleado: {email}")
            
            # Simular latencia de red con Active Directory
            await asyncio.sleep(0.3)
            
            # Normalizar email
            email = email.lower().strip()
            
            # Validar formato de email de Eroski
            if not self._is_valid_eroski_email(email):
                self.logger.warning(f"❌ Email no válido para Eroski: {email}")
                return None
            
            # Buscar en base de datos mock
            employee = self.mock_employees.get(email)
            
            if not employee:
                self.logger.warning(f"❌ Empleado no encontrado: {email}")
                return None
            
            # Verificar que esté activo
            if not employee.get("active", True):
                self.logger.warning(f"❌ Empleado inactivo: {email}")
                return None
            
            # Enriquecer con información de tienda si es necesario
            enriched_employee = await self._enrich_employee_data(employee, store_hint)
            
            self.logger.info(f"✅ Empleado validado: {enriched_employee['name']}")
            return enriched_employee
            
        except Exception as e:
            self.logger.error(f"❌ Error validando empleado {email}: {e}")
            return None
    
    def _is_valid_eroski_email(self, email: str) -> bool:
        """Validar que el email sea del dominio Eroski"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@eroski\.es$'
        return bool(re.match(email_pattern, email))
    
    async def _enrich_employee_data(
        self, 
        employee: Dict[str, Any], 
        store_hint: Optional[str]
    ) -> Dict[str, Any]:
        """Enriquecer datos del empleado con información adicional"""
        enriched = employee.copy()
        
        # Agregar información de tienda
        store_id = employee.get("store_id")
        if store_id and store_id in self.mock_stores:
            store_info = self.mock_stores[store_id]
            enriched.update({
                "store_address": store_info["address"],
                "store_phone": store_info["phone"],
                "store_region": store_info["region"],
                "store_manager": store_info["manager"]
            })
        
        # Validar store_hint si se proporciona
        if store_hint:
            if not self._validate_store_hint(employee, store_hint):
                self.logger.warning(f"⚠️ Store hint '{store_hint}' no coincide con tienda del empleado")
        
        return enriched
    
    def _validate_store_hint(self, employee: Dict[str, Any], store_hint: str) -> bool:
        """Validar que la pista de tienda coincida con el empleado"""
        store_name = employee.get("store_name", "").lower()
        store_hint_lower = store_hint.lower()
        
        # Buscar coincidencias parciales
        return any(word in store_name for word in store_hint_lower.split())
    
    async def get_employee_by_id(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Obtener empleado por ID"""
        for employee in self.mock_employees.values():
            if employee.get("id") == employee_id:
                return employee.copy()
        return None
    
    async def get_store_employees(self, store_id: str) -> List[Dict[str, Any]]:
        """Obtener todos los empleados de una tienda"""
        employees = []
        for employee in self.mock_employees.values():
            if employee.get("store_id") == store_id and employee.get("active", True):
                employees.append(employee.copy())
        return employees
    
    async def get_supervisors_for_store(self, store_id: str) -> List[Dict[str, Any]]:
        """Obtener supervisores de una tienda específica"""
        supervisors = []
        for employee in self.mock_employees.values():
            if (employee.get("store_id") == store_id and 
                employee.get("level", 1) >= 3 and 
                employee.get("active", True)):
                supervisors.append(employee.copy())
        return supervisors

class EroskiSAPIntegration:
    """
    Integración con el sistema SAP de Eroski para tickets.
    
    NOTA: Implementación mock para desarrollo.
    En producción debe usar la API real de SAP.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("SAPIntegration")
        self.mock_tickets = {}
        self.ticket_counter = 1000
    
    async def create_ticket(
        self,
        incident_data: Dict[str, Any],
        employee_data: Dict[str, Any]
    ) -> str:
        """
        Crear ticket en SAP.
        
        Args:
            incident_data: Datos de la incidencia
            employee_data: Datos del empleado
            
        Returns:
            ID del ticket creado
        """
        try:
            self.logger.info("🎫 Creando ticket en SAP...")
            
            # Simular latencia de SAP
            await asyncio.sleep(0.5)
            
            # Generar ID de ticket
            self.ticket_counter += 1
            ticket_id = f"ERO{self.ticket_counter:06d}"
            
            # Crear ticket mock
            ticket = {
                "id": ticket_id,
                "type": incident_data.get("incident_type", "general"),
                "description": incident_data.get("incident_description", ""),
                "urgency": incident_data.get("urgency_level", 2),
                "store_id": employee_data.get("store_id"),
                "employee_id": employee_data.get("id"),
                "employee_email": employee_data.get("email"),
                "created_at": datetime.now().isoformat(),
                "status": "open",
                "assigned_to": None
            }
            
            # Guardar en mock database
            self.mock_tickets[ticket_id] = ticket
            
            self.logger.info(f"✅ Ticket creado: {ticket_id}")
            return ticket_id
            
        except Exception as e:
            self.logger.error(f"❌ Error creando ticket SAP: {e}")
            raise
    
    async def get_ticket_status(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Obtener estado de un ticket"""
        return self.mock_tickets.get(ticket_id)
    
    async def update_ticket_status(self, ticket_id: str, new_status: str) -> bool:
        """Actualizar estado de un ticket"""
        if ticket_id in self.mock_tickets:
            self.mock_tickets[ticket_id]["status"] = new_status
            self.mock_tickets[ticket_id]["updated_at"] = datetime.now().isoformat()
            return True
        return False

class EroskiEscalationManager:
    """
    Gestor de escalaciones específico para Eroski.
    
    Maneja la lógica de escalación según el tipo de incidencia,
    tienda y disponibilidad de personal.
    """
    
    def __init__(self):
        self.logger = logging.getLogger("EscalationManager")
        self.employee_validator = EroskiEmployeeValidator()
        
        # Contactos de escalación por categoría
        self.escalation_contacts = {
            "hardware": ["soporte.hardware@eroski.es", "tecnico.tienda@eroski.es"],
            "software": ["soporte.software@eroski.es", "sap.support@eroski.es"],
            "network": ["soporte.red@eroski.es", "infraestructura@eroski.es"],
            "critical": ["urgencias@eroski.es", "supervisor.tecnico@eroski.es"],
            "security": ["seguridad@eroski.es", "supervisor.seguridad@eroski.es"],
            "facilities": ["mantenimiento@eroski.es", "supervisor.mantenimiento@eroski.es"]
        }
    
    async def get_escalation_contacts(
        self,
        incident_type: str,
        store_id: str,
        urgency_level: int = 2
    ) -> List[str]:
        """
        Obtener contactos de escalación apropiados.
        
        Args:
            incident_type: Tipo de incidencia
            store_id: ID de la tienda
            urgency_level: Nivel de urgencia (1-4)
            
        Returns:
            Lista de contactos de escalación
        """
        try:
            contacts = []
            
            # Obtener supervisores de la tienda
            store_supervisors = await self.employee_validator.get_supervisors_for_store(store_id)
            for supervisor in store_supervisors:
                contacts.append(supervisor["email"])
            
            # Agregar contactos específicos por categoría
            # (Esto vendría de la configuración de incident_types.json)
            category_contacts = self.escalation_contacts.get("hardware", [])
            contacts.extend(category_contacts)
            
            # Para urgencias críticas, agregar contactos adicionales
            if urgency_level >= 4:
                critical_contacts = self.escalation_contacts.get("critical", [])
                contacts.extend(critical_contacts)
            
            # Remover duplicados manteniendo orden
            unique_contacts = []
            for contact in contacts:
                if contact not in unique_contacts:
                    unique_contacts.append(contact)
            
            self.logger.info(f"📧 Contactos de escalación: {len(unique_contacts)}")
            return unique_contacts
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo contactos de escalación: {e}")
            return ["soporte.general@eroski.es"]  # Fallback
    
    async def send_escalation_notification(
        self,
        contacts: List[str],
        incident_summary: Dict[str, Any]
    ) -> bool:
        """
        Enviar notificación de escalación.
        
        NOTA: Implementación mock. En producción usar sistema real de email.
        """
        try:
            self.logger.info(f"📧 Enviando notificación de escalación a {len(contacts)} contactos")
            
            # Simular envío de email
            await asyncio.sleep(0.2)
            
            # En producción, integrar con sistema de email de Eroski
            for contact in contacts:
                self.logger.info(f"📧 Email enviado a: {contact}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error enviando notificaciones: {e}")
            return False

# ========== INSTANCIAS GLOBALES ==========

_global_employee_validator: Optional[EroskiEmployeeValidator] = None
_global_sap_integration: Optional[EroskiSAPIntegration] = None
_global_escalation_manager: Optional[EroskiEscalationManager] = None

def get_employee_validator() -> EroskiEmployeeValidator:
    """Obtener instancia global del validador de empleados"""
    global _global_employee_validator
    if _global_employee_validator is None:
        _global_employee_validator = EroskiEmployeeValidator()
    return _global_employee_validator

def get_sap_integration() -> EroskiSAPIntegration:
    """Obtener instancia global de integración SAP"""
    global _global_sap_integration
    if _global_sap_integration is None:
        _global_sap_integration = EroskiSAPIntegration()
    return _global_sap_integration

def get_escalation_manager() -> EroskiEscalationManager:
    """Obtener instancia global del gestor de escalaciones"""
    global _global_escalation_manager
    if _global_escalation_manager is None:
        _global_escalation_manager = EroskiEscalationManager()
    return _global_escalation_manager

# ========== FUNCIONES DE CONVENIENCIA ==========

async def validate_eroski_employee(email: str, store_hint: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Función de conveniencia para validar empleado"""
    validator = get_employee_validator()
    return await validator.validate_employee(email, store_hint)

async def create_eroski_ticket(incident_data: Dict[str, Any], employee_data: Dict[str, Any]) -> str:
    """Función de conveniencia para crear ticket"""
    sap = get_sap_integration()
    return await sap.create_ticket(incident_data, employee_data)

async def escalate_to_supervisor(
    incident_type: str,
    store_id: str,
    incident_summary: Dict[str, Any],
    urgency_level: int = 2
) -> bool:
    """Función de conveniencia para escalar incidencia"""
    escalation_manager = get_escalation_manager()
    
    # Obtener contactos
    contacts = await escalation_manager.get_escalation_contacts(
        incident_type, store_id, urgency_level
    )
    
    # Enviar notificación
    return await escalation_manager.send_escalation_notification(contacts, incident_summary)