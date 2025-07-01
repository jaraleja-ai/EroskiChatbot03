# =====================================================
# models/conversation_step.py - Estados de conversación
# =====================================================
"""
Definición de estados para el flujo conversacional del chatbot.

Este módulo centraliza todos los posibles estados/pasos de la conversación,
permitiendo un control de flujo consistente y fácil mantenimiento.
"""

from enum import Enum
from typing import Dict, List, Optional


class ConversationSteps:
    """
    Constantes para los diferentes pasos/estados de la conversación.
    
    Organizado por categorías para facilitar el mantenimiento:
    - Estados de identificación de usuario
    - Estados de descripción del problema
    - Estados de procesamiento
    - Estados de finalización
    """
    
    # ===== ESTADOS DE IDENTIFICACIÓN DE USUARIO =====
    EXTRACTING_USER_DATA = "extracting_user_data"
    WAITING_USER_DATA = "waiting_user_data"
    WAITING_USER_CONFIRMATION = "waiting_user_confirmation"
    PROCESSING_USER_CONFIRMATION = "processing_user_confirmation"
    RESOLVING_USER_CONFLICT = "resolving_user_conflict"
    USER_IDENTIFIED = "user_identified"
    
    # ===== ESTADOS DE DESCRIPCIÓN DEL PROBLEMA =====
    DESCRIBING_PROBLEM = "describing_problem"
    WAITING_PROBLEM_DETAILS = "waiting_problem_details"
    CLARIFYING_PROBLEM = "clarifying_problem"
    CATEGORIZING_PROBLEM = "categorizing_problem"
    
    # ===== ESTADOS DE PROCESAMIENTO =====
    ANALYZING_PROBLEM = "analyzing_problem"
    SEARCHING_SOLUTIONS = "searching_solutions"
    PROCESSING_INCIDENT = "processing_incident"
    CREATING_TICKET = "creating_ticket"
    
    # ===== ESTADOS DE CONFIRMACIÓN =====
    WAITING_SOLUTION_CONFIRMATION = "waiting_solution_confirmation"
    WAITING_TICKET_CONFIRMATION = "waiting_ticket_confirmation"
    CONFIRMING_RESOLUTION = "confirming_resolution"
    
    # ===== ESTADOS DE ESCALACIÓN =====
    PREPARING_ESCALATION = "preparing_escalation"
    ESCALATING = "escalating"
    ESCALATED = "escalated"
    
    # ===== ESTADOS FINALES =====
    COMPLETED = "completed"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    ESCALATING = "escalating"
    ESCALATED = "escalated"
    ERROR = "error"
    
    # ===== ESTADOS ESPECIALES =====
    WAITING_INPUT = "waiting_input"  # Estado genérico para input del usuario
    PROCESSING_INPUT = "processing_input"  # Procesando input recibido
    INTERRUPTED = "interrupted"  # Flujo interrumpido


class ConversationStepsMeta:
    """
    Metadatos y utilidades para los estados de conversación.
    """
    
    @staticmethod
    def get_all_steps() -> List[str]:
        """Obtener lista de todos los pasos disponibles."""
        return [
            value for key, value in vars(ConversationSteps).items() 
            if not key.startswith('_') and isinstance(value, str)
        ]
    
    @staticmethod
    def get_user_identification_steps() -> List[str]:
        """Obtener pasos relacionados con identificación de usuario."""
        return [
            ConversationSteps.EXTRACTING_USER_DATA,
            ConversationSteps.WAITING_USER_DATA,
            ConversationSteps.WAITING_USER_CONFIRMATION,
            ConversationSteps.PROCESSING_USER_CONFIRMATION,
            ConversationSteps.RESOLVING_USER_CONFLICT,
            ConversationSteps.USER_IDENTIFIED,
        ]
    
    @staticmethod
    def get_problem_description_steps() -> List[str]:
        """Obtener pasos relacionados con descripción del problema."""
        return [
            ConversationSteps.DESCRIBING_PROBLEM,
            ConversationSteps.WAITING_PROBLEM_DETAILS,
            ConversationSteps.CLARIFYING_PROBLEM,
            ConversationSteps.CATEGORIZING_PROBLEM,
        ]
    
    @staticmethod
    def get_processing_steps() -> List[str]:
        """Obtener pasos relacionados con procesamiento."""
        return [
            ConversationSteps.ANALYZING_PROBLEM,
            ConversationSteps.SEARCHING_SOLUTIONS,
            ConversationSteps.PROCESSING_INCIDENT,
            ConversationSteps.CREATING_TICKET,
        ]
    
    @staticmethod
    def get_waiting_steps() -> List[str]:
        """Obtener pasos que esperan input del usuario."""
        return [
            ConversationSteps.WAITING_USER_DATA,
            ConversationSteps.WAITING_USER_CONFIRMATION,
            ConversationSteps.WAITING_PROBLEM_DETAILS,
            ConversationSteps.WAITING_SOLUTION_CONFIRMATION,
            ConversationSteps.WAITING_TICKET_CONFIRMATION,
            ConversationSteps.WAITING_INPUT,
        ]
    
    @staticmethod
    def get_final_steps() -> List[str]:
        """Obtener pasos finales (terminales)."""
        return [
            ConversationSteps.COMPLETED,
            ConversationSteps.RESOLVED,
            ConversationSteps.CANCELLED,
            ConversationSteps.ERROR,
            ConversationSteps.ESCALATED,
        ]
    
    @staticmethod
    def is_waiting_step(step: str) -> bool:
        """Verificar si un paso está esperando input del usuario."""
        return step in ConversationStepsMeta.get_waiting_steps()
    
    @staticmethod
    def is_final_step(step: str) -> bool:
        """Verificar si un paso es terminal."""
        return step in ConversationStepsMeta.get_final_steps()
    
    @staticmethod
    def get_next_logical_step(current_step: str) -> Optional[str]:
        """
        Obtener el siguiente paso lógico basado en el actual.
        
        Esta es una función helper que sugiere transiciones comunes,
        pero cada nodo puede decidir su propio flujo.
        """
        step_transitions = {
            # Flujo de identificación
            ConversationSteps.EXTRACTING_USER_DATA: ConversationSteps.WAITING_USER_CONFIRMATION,
            ConversationSteps.WAITING_USER_DATA: ConversationSteps.PROCESSING_USER_CONFIRMATION,
            ConversationSteps.WAITING_USER_CONFIRMATION: ConversationSteps.PROCESSING_USER_CONFIRMATION,
            ConversationSteps.PROCESSING_USER_CONFIRMATION: ConversationSteps.USER_IDENTIFIED,
            ConversationSteps.USER_IDENTIFIED: ConversationSteps.DESCRIBING_PROBLEM,
            
            # Flujo de problema
            ConversationSteps.DESCRIBING_PROBLEM: ConversationSteps.CATEGORIZING_PROBLEM,
            ConversationSteps.WAITING_PROBLEM_DETAILS: ConversationSteps.ANALYZING_PROBLEM,
            ConversationSteps.CATEGORIZING_PROBLEM: ConversationSteps.ANALYZING_PROBLEM,
            ConversationSteps.ANALYZING_PROBLEM: ConversationSteps.PROCESSING_INCIDENT,
            
            # Flujo de procesamiento
            ConversationSteps.PROCESSING_INCIDENT: ConversationSteps.CREATING_TICKET,
            ConversationSteps.CREATING_TICKET: ConversationSteps.WAITING_TICKET_CONFIRMATION,
            ConversationSteps.WAITING_TICKET_CONFIRMATION: ConversationSteps.COMPLETED,
            
            # Flujos especiales
            ConversationSteps.PREPARING_ESCALATION: ConversationSteps.ESCALATING,
            ConversationSteps.ESCALATING: ConversationSteps.ESCALATED,
        }
        
        return step_transitions.get(current_step)
    
    @staticmethod
    def get_step_description(step: str) -> str:
        """Obtener descripción human-readable del paso."""
        descriptions = {
            # Identificación
            ConversationSteps.EXTRACTING_USER_DATA: "Extrayendo datos del usuario",
            ConversationSteps.WAITING_USER_DATA: "Esperando datos del usuario",
            ConversationSteps.WAITING_USER_CONFIRMATION: "Esperando confirmación del usuario",
            ConversationSteps.PROCESSING_USER_CONFIRMATION: "Procesando confirmación del usuario",
            ConversationSteps.RESOLVING_USER_CONFLICT: "Resolviendo conflicto de datos de usuario",
            ConversationSteps.USER_IDENTIFIED: "Usuario identificado exitosamente",
            
            # Problema
            ConversationSteps.DESCRIBING_PROBLEM: "Describiendo el problema",
            ConversationSteps.WAITING_PROBLEM_DETAILS: "Esperando detalles del problema",
            ConversationSteps.CLARIFYING_PROBLEM: "Clarificando el problema",
            ConversationSteps.CATEGORIZING_PROBLEM: "Categorizando el problema",
            
            # Procesamiento
            ConversationSteps.ANALYZING_PROBLEM: "Analizando el problema",
            ConversationSteps.SEARCHING_SOLUTIONS: "Buscando soluciones",
            ConversationSteps.PROCESSING_INCIDENT: "Procesando incidencia",
            ConversationSteps.CREATING_TICKET: "Creando ticket",
            
            # Confirmaciones
            ConversationSteps.WAITING_SOLUTION_CONFIRMATION: "Esperando confirmación de solución",
            ConversationSteps.WAITING_TICKET_CONFIRMATION: "Esperando confirmación de ticket",
            ConversationSteps.CONFIRMING_RESOLUTION: "Confirmando resolución",
            
            # Escalación
            ConversationSteps.PREPARING_ESCALATION: "Preparando escalación",
            ConversationSteps.ESCALATING: "Escalando a supervisor",
            ConversationSteps.ESCALATED: "Escalado exitosamente",
            
            # Finales
            ConversationSteps.COMPLETED: "Conversación completada",
            ConversationSteps.RESOLVED: "Problema resuelto",
            ConversationSteps.CANCELLED: "Conversación cancelada",
            ConversationSteps.ERROR: "Error en el proceso",
            
            # Especiales
            ConversationSteps.WAITING_INPUT: "Esperando input del usuario",
            ConversationSteps.PROCESSING_INPUT: "Procesando input del usuario",
            ConversationSteps.INTERRUPTED: "Flujo interrumpido",
        }
        
        return descriptions.get(step, f"Paso desconocido: {step}")


class ConversationStepValidator:
    """
    Validador para transiciones de pasos de conversación.
    """
    
    @staticmethod
    def is_valid_transition(from_step: str, to_step: str) -> bool:
        """
        Validar si una transición entre pasos es válida.
        
        Args:
            from_step: Paso actual
            to_step: Paso destino
            
        Returns:
            True si la transición es válida
        """
        
        # Transiciones siempre válidas
        always_valid_destinations = [
            ConversationSteps.ERROR,
            ConversationSteps.ESCALATING,
            ConversationSteps.CANCELLED,
            ConversationSteps.INTERRUPTED,
        ]
        
        if to_step in always_valid_destinations:
            return True
        
        # Desde estados finales no se puede transicionar (excepto a los siempre válidos)
        if ConversationStepsMeta.is_final_step(from_step):
            return False
        
        # Transiciones específicas válidas
        valid_transitions = {
            ConversationSteps.EXTRACTING_USER_DATA: [
                ConversationSteps.WAITING_USER_DATA,
                ConversationSteps.WAITING_USER_CONFIRMATION,
                ConversationSteps.USER_IDENTIFIED,
            ],
            ConversationSteps.WAITING_USER_CONFIRMATION: [
                ConversationSteps.PROCESSING_USER_CONFIRMATION,
                ConversationSteps.RESOLVING_USER_CONFLICT,
                ConversationSteps.WAITING_USER_DATA,
            ],
            ConversationSteps.USER_IDENTIFIED: [
                ConversationSteps.DESCRIBING_PROBLEM,
                ConversationSteps.PROCESSING_INCIDENT,
            ],
            # Agregar más según sea necesario...
        }
        
        allowed_destinations = valid_transitions.get(from_step, [])
        return to_step in allowed_destinations
    
    @staticmethod
    def validate_step_sequence(steps: List[str]) -> List[str]:
        """
        Validar una secuencia completa de pasos.
        
        Args:
            steps: Lista de pasos en orden
            
        Returns:
            Lista de errores encontrados (vacía si es válida)
        """
        errors = []
        
        for i in range(len(steps) - 1):
            current_step = steps[i]
            next_step = steps[i + 1]
            
            if not ConversationStepValidator.is_valid_transition(current_step, next_step):
                errors.append(
                    f"Transición inválida: {current_step} → {next_step}"
                )
        
        return errors