# =====================================================
# nodes/procesar_incidencia.py - CORREGIDO: Returns apropiados
# =====================================================
from typing import Dict, Any, List
from langchain_core.messages import AIMessage
from langgraph.types import Command

from .base_node import BaseNode 
from utils.extractors.incident_extractor import extraer_tipo_incidencia, extraer_detalles_incidencia
from utils.llm.message_generator import generate_natural_message, generate_followup_questions
from models.incidencia import TipoIncidencia, CategoriaIncidencia, PrioridadIncidencia
from utils.database.incidencia_repository import IncidenciaRepository

class ProcesarIncidenciaNode(BaseNode):
    """
    🎭 ACTOR HÍBRIDO: Procesar y categorizar incidencias técnicas
    
    RESPONSABILIDADES:
    - Identificar tipo y categoría de incidencia
    - Extraer detalles relevantes
    - Hacer preguntas de seguimiento
    - Determinar prioridad
    - Crear ticket en BD
    """
    
    def __init__(self):
        super().__init__("procesar_incidencia", timeout_seconds=60)
        self.incidencia_repository = IncidenciaRepository()
    
    def get_required_fields(self) -> List[str]:
        return ["messages", "datos_usuario_completos", "nombre", "email"]
    
    def get_actor_description(self) -> str:
        return (
            "Actor autónomo que procesa y categoriza incidencias técnicas mediante "
            "análisis de NLP, hace preguntas de seguimiento y crea tickets estructurados"
        )

    # =====================================================
    # PUNTO DE SALIDA AL GRAFO - USA Command
    # =====================================================
    
    async def execute(self, state: Dict[str, Any]) -> Command:
        """🎭 PUNTO DE SALIDA PRINCIPAL - Ejecutar procesamiento de incidencia"""
        
        # Verificar si ya tenemos incidencia identificada
        if state.get("tipo_incidencia"):
            return await self._handle_existing_incident(state)
        
        # Procesar nueva incidencia
        return await self._handle_new_incident(state)
    
    # =====================================================
    # MÉTODOS QUE SALEN AL GRAFO - USAN Command
    # =====================================================
    
    async def _handle_new_incident(self, state: Dict[str, Any]) -> Command:
        """🎯 SALE AL GRAFO - Manejar nueva incidencia"""
        ultimo_mensaje = self.get_last_user_message(state)
        intentos = self.increment_attempts(state, "intentos_incidencia")
        
        # Verificar si debe escalar por muchos intentos
        if self._should_escalate_after_attempts(intentos):
            return self.signal_escalation(
                state,
                "identificar y categorizar tu incidencia",
                attempts=intentos
            )
        
        # Extraer información de la incidencia
        try:
            tipo_incidencia = await self._extract_incident_type(ultimo_mensaje)
            detalles = await self._extract_incident_details(ultimo_mensaje, tipo_incidencia)
            
            # ✅ CORREGIDO: Manejar caso TipoIncidencia.OTRO
            if tipo_incidencia == TipoIncidencia.OTRO:
                return self.signal_need_input(
                    state,
                    "No pude identificar específicamente tu problema. ¿Podrías describirlo "
                    "con más detalle? Por ejemplo: ¿es un problema de hardware, software, "
                    "red, acceso o email?",
                    context={
                        "waiting_for": "incident_clarification",
                        "attempts": intentos,
                        "previous_message": ultimo_mensaje
                    }
                )
            
            # Determinar si necesitamos más información
            if self._needs_more_details(detalles):
                return await self._ask_followup_questions_command(state, tipo_incidencia, detalles, intentos)
            
            # Crear incidencia completa
            return await self._create_incident_ticket_command(state, tipo_incidencia, detalles, intentos)
            
        except Exception as e:
            self.logger.error(f"❌ Error procesando incidencia: {e}")
            return await self._request_incident_clarification_command(state, intentos)
    
    async def _handle_existing_incident(self, state: Dict[str, Any]) -> Command:
        """🎯 SALE AL GRAFO - Manejar incidencia existente con más detalles"""
        
        tipo_incidencia = TipoIncidencia(state.get("tipo_incidencia"))
        detalles_parciales = state.get("detalles_parciales", {})
        ultimo_mensaje = self.get_last_user_message(state)
        intentos = state.get("intentos_incidencia", 0)
        
        try:
            # Agregar nueva información a los detalles existentes
            nuevos_detalles = await self._extract_incident_details(ultimo_mensaje, tipo_incidencia)
            detalles_completos = {**detalles_parciales, **nuevos_detalles}
            
            # Verificar si ya tenemos suficiente información
            if self._has_sufficient_details(detalles_completos):
                return await self._create_incident_ticket_command(state, tipo_incidencia, detalles_completos, intentos)
            else:
                return await self._ask_followup_questions_command(state, tipo_incidencia, detalles_completos, intentos)
                
        except Exception as e:
            self.logger.error(f"❌ Error procesando incidencia existente: {e}")
            return await self._request_incident_clarification_command(state, intentos)
    
    async def _ask_followup_questions_command(
        self, 
        state: Dict[str, Any], 
        tipo: TipoIncidencia, 
        detalles: Dict[str, Any],
        intentos: int
    ) -> Command:
        """🎯 SALE AL GRAFO - Hacer preguntas de seguimiento específicas"""
        
        preguntas = await self._generate_followup_questions(tipo, detalles)
        mensaje = f"Para ayudarte mejor con tu problema de **{tipo.value}**, necesito algunos detalles:\n\n"
        mensaje += "\n".join(f"• {pregunta}" for pregunta in preguntas[:3])  # Máximo 3 preguntas
        
        return self.signal_need_input(
            state,
            mensaje,
            context={
                "waiting_for": "incident_details",
                "incident_type": tipo.value,
                "partial_details": detalles,
                "pending_questions": preguntas,
                "attempts": intentos
            }
        )
    
    async def _create_incident_ticket_command(
        self,
        state: Dict[str, Any],
        tipo: TipoIncidencia,
        detalles: Dict[str, Any],
        intentos: int
    ) -> Command:
        """🎯 SALE AL GRAFO - Crear ticket de incidencia en la BD"""
        
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
                
                return self.signal_completion(
                    state,
                    next_actor="finalizar_ticket",
                    completion_message=mensaje,
                    tipo_incidencia=tipo.value,
                    descripcion_incidencia=descripcion,
                    prioridad_incidencia=prioridad.value,
                    incidencia_id=incidencia.id,
                    numero_ticket=incidencia.numero_ticket,
                    incidencia_resuelta=True,
                    flujo_completado=True,
                    intentos_incidencia=intentos
                )
            else:
                raise Exception("No se pudo crear el ticket en BD")
                
        except Exception as e:
            self.logger.error(f"❌ Error creando ticket: {e}")
            return self.signal_escalation(
                state,
                f"crear ticket de incidencia: {str(e)}",
                attempts=intentos
            )
    
    async def _request_incident_clarification_command(self, state: Dict[str, Any], intentos: int) -> Command:
        """🎯 SALE AL GRAFO - Solicitar clarificación de incidencia"""
        
        if intentos >= 3:
            return self.signal_escalation(
                state,
                "entender tu problema después de varios intentos",
                attempts=intentos
            )
        
        mensaje = (
            "No pude entender completamente tu problema. ¿Podrías describirlo de otra manera? "
            "Por ejemplo:\n\n"
            "• ¿Qué estabas haciendo cuando ocurrió el problema?\n"
            "• ¿Qué error o comportamiento específico observaste?\n"
            "• ¿Es un problema de hardware, software o red?"
        )
        
        return self.signal_need_input(
            state,
            mensaje,
            context={
                "waiting_for": "incident_clarification",
                "attempts": intentos,
                "clarification_request": True
            }
        )
    
    # =====================================================
    # MÉTODOS INTERNOS - NO USAN Command
    # =====================================================
    
    async def _extract_incident_type(self, mensaje: str) -> TipoIncidencia:
        """🔧 INTERNO - Extraer tipo de incidencia"""
        return await extraer_tipo_incidencia(mensaje)
    
    async def _extract_incident_details(self, mensaje: str, tipo: TipoIncidencia) -> Dict[str, Any]:
        """🔧 INTERNO - Extraer detalles de incidencia"""
        return await extraer_detalles_incidencia(mensaje, tipo)
    
    def _needs_more_details(self, detalles: Dict[str, Any]) -> bool:
        """🔧 INTERNO - Verificar si necesitamos más detalles"""
        campos_esenciales = ["descripcion_detallada", "impacto", "urgencia"]
        return not all(detalles.get(campo) for campo in campos_esenciales)
    
    def _has_sufficient_details(self, detalles: Dict[str, Any]) -> bool:
        """🔧 INTERNO - Verificar si tenemos suficientes detalles"""
        return not self._needs_more_details(detalles)
    
    async def _generate_followup_questions(self, tipo: TipoIncidencia, detalles: Dict[str, Any]) -> List[str]:
        """🔧 INTERNO - Generar preguntas de seguimiento"""
        return await generate_followup_questions(tipo, detalles)
    
    def _determine_priority(self, tipo: TipoIncidencia, detalles: Dict[str, Any]) -> PrioridadIncidencia:
        """🔧 INTERNO - Determinar prioridad de la incidencia"""
        
        # Lógica básica de priorización
        impacto_alto = any(keyword in str(detalles).lower() 
                          for keyword in ["urgente", "critico", "no puedo trabajar", "sistema caido"])
        
        if impacto_alto:
            return PrioridadIncidencia.CRITICA
        elif tipo in [TipoIncidencia.RED, TipoIncidencia.ACCESO]:
            return PrioridadIncidencia.ALTA
        elif tipo == TipoIncidencia.HARDWARE:
            return PrioridadIncidencia.MEDIA
        else:
            return PrioridadIncidencia.BAJA
    
    def _build_incident_description(self, detalles: Dict[str, Any]) -> str:
        """🔧 INTERNO - Construir descripción estructurada"""
        descripcion_base = detalles.get("descripcion_original", "")
        descripcion_procesada = detalles.get("descripcion_detallada", "")
        
        if descripcion_procesada:
            return f"{descripcion_base}\n\nDetalles adicionales: {descripcion_procesada}"
        return descripcion_base
    
    async def _generate_ticket_created_message(self, incidencia, estado_final: bool = False) -> str:
        """🔧 INTERNO - Generar mensaje de ticket creado"""
        mensaje = f"""
✅ **¡Ticket creado exitosamente!**

📋 **Número de ticket:** {incidencia.numero_ticket}
🎯 **Tipo:** {incidencia.tipo}
⚡ **Prioridad:** {incidencia.prioridad}
📅 **Fecha:** {incidencia.fecha_creacion.strftime('%d/%m/%Y %H:%M')}

Tu incidencia ha sido registrada y será atendida según su prioridad. 
Recibirás actualizaciones sobre el progreso.

¿Hay algo más en lo que pueda ayudarte? 😊
"""
        return mensaje
    
    def _should_escalate_after_attempts(self, intentos: int, max_attempts: int = 3) -> bool:
        """🔧 INTERNO - Determinar si debe escalar por intentos"""
        return intentos >= max_attempts


# =====================================================
# WRAPPER PARA LANGGRAPH - SALE AL GRAFO
# =====================================================
async def procesar_incidencia_node(state: Dict[str, Any]) -> Command:
    """🎯 WRAPPER QUE SALE AL GRAFO - Función para LangGraph"""
    node = ProcesarIncidenciaNode()
    return await node.execute_with_monitoring(state)



