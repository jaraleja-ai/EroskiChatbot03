# =====================================================
# nodes/procesar_incidencia.py - Nodo de procesamiento de incidencias
# =====================================================
from typing import Dict, Any, List
from langchain_core.messages import AIMessage
from langgraph.types import Command


from .base_node import BaseNode, NodeExecutionResult
from utils.extractors.incident_extractor import extraer_tipo_incidencia, extraer_detalles_incidencia
from utils.llm.message_generator import generate_natural_message, generate_followup_questions
from models.incidencia import TipoIncidencia, CategoriaIncidencia, PrioridadIncidencia
from utils.database.incidencia_repository import IncidenciaRepository

class ProcesarIncidenciaNode(BaseNode):
    """
    Nodo para procesar y categorizar incidencias técnicas.
    
    Funcionalidades:
    - Identificar tipo y categoría de incidencia
    - Extraer detalles relevantes
    - Hacer preguntas de seguimiento
    - Determinar prioridad
    - Crear ticket en BD
    """
    
    def __init__(self):
        super().__init__("ProcesarIncidencia", timeout_seconds=60)
        self.incidencia_repository = IncidenciaRepository()
    
    def get_required_fields(self) -> List[str]:
        return ["messages", "datos_usuario_completos", "nombre", "email"]
    
    def get_node_description(self) -> str:
        return (
            "Procesa y categoriza incidencias técnicas mediante análisis de NLP, "
            "hace preguntas de seguimiento y crea tickets estructurados"
        )
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """Ejecutar procesamiento de incidencia"""
        
        # Verificar si ya tenemos incidencia identificada
        if state.get("tipo_incidencia"):
            return await self._handle_existing_incident(state)
        
        # Procesar nueva incidencia
        return await self._handle_new_incident(state)
    
    async def _handle_new_incident(self, state: Dict[str, Any]) -> Command:
        """Manejar nueva incidencia"""
        ultimo_mensaje = self.get_last_user_message(state)
        intentos = self.increment_attempts(state, "intentos_incidencia")
        
        if self.should_escalate(state, "intentos_incidencia"):
            return self.create_escalation_command(
                state,
                "identificar y categorizar tu incidencia",
                intentos
            )
        
        # Extraer información de la incidencia
        try:
            tipo_incidencia = await extraer_tipo_incidencia(ultimo_mensaje)
            detalles = await extraer_detalles_incidencia(ultimo_mensaje, tipo_incidencia)
            
            if tipo_incidencia == TipoIncidencia.OTRO:
                return await self._request_incident_clarification(state, intentos)
            
            # Determinar si necesitamos más información
            if self._needs_more_details(detalles):
                return await self._ask_followup_questions(state, tipo_incidencia, detalles, intentos)
            
            # Crear incidencia completa
            return await self._create_incident_ticket(state, tipo_incidencia, detalles, intentos)
            
        except Exception as e:
            self.logger.error(f"Error procesando incidencia: {e}")
            return await self._request_incident_clarification(state, intentos)
    
    async def _ask_followup_questions(
        self, 
        state: Dict[str, Any], 
        tipo: TipoIncidencia, 
        detalles: Dict[str, Any],
        intentos: int
    ) -> Command:
        """Hacer preguntas de seguimiento específicas"""
        
        preguntas = await generate_followup_questions(tipo, detalles)
        mensaje = f"Para ayudarte mejor con tu problema de **{tipo.value}**, necesito algunos detalles:\n\n"
        mensaje += "\n".join(f"• {pregunta}" for pregunta in preguntas[:3])  # Máximo 3 preguntas
        
        return Command(update=self.create_message_update(mensaje, {
            "tipo_incidencia": tipo.value,
            "detalles_parciales": detalles,
            "intentos_incidencia": intentos,
            "preguntas_pendientes": preguntas,
            "escalar_a_supervisor": False
        }))
    
    async def _create_incident_ticket(
        self,
        state: Dict[str, Any],
        tipo: TipoIncidencia,
        detalles: Dict[str, Any],
        intentos: int
    ) -> Command:
        """Crear ticket de incidencia en la BD"""
        
        try:
            # Determinar prioridad automáticamente
            prioridad = self._determine_priority(tipo, detalles)
            
            # Crear descripción estructurada
            descripcion = self._build_incident_description(detalles)
            
            # Buscar usuario para obtener ID (simplificado por ahora)
            usuario_id = 1  # TODO: Obtener del repositorio de usuarios
            
            # Crear incidencia en BD
            incidencia = await self.incidencia_repository.crear_incidencia(
                usuario_id=usuario_id,
                tipo=tipo,
                descripcion=descripcion,
                prioridad=prioridad.value
            )
            
            if incidencia:
                mensaje = await self._generate_ticket_created_message(incidencia, estado_final=True)
                
                return Command(update=self.create_message_update(mensaje, {
                    "tipo_incidencia": tipo.value,
                    "descripcion_incidencia": descripcion,
                    "prioridad_incidencia": prioridad.value,
                    "incidencia_id": incidencia.id,
                    "numero_ticket": incidencia.numero_ticket,
                    "incidencia_resuelta": True,
                    "flujo_completado": True,
                    "intentos_incidencia": intentos,
                    "escalar_a_supervisor": False
                }))
            else:
                raise Exception("No se pudo crear el ticket en BD")
                
        except Exception as e:
            self.logger.error(f"Error creando ticket: {e}")
            return await self.handle_error(e, state)



# =====================================================
# Funciones wrapper para LangGraph
# =====================================================
async def procesar_incidencia_node(state: Dict[str, Any]) -> Command:
    """Wrapper para nodo de procesamiento de incidencias"""
    node = ProcesarIncidenciaNode()
    return await node.execute_with_monitoring(state)

