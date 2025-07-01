# =====================================================
# ARQUITECTURA ESCALABLE PARA MÚLTIPLES NODOS
# =====================================================

# 1. ESTADO CENTRALIZADO Y ESCALABLE
class ConversationState(TypedDict):
    """Estado unificado que escala con nuevos nodos"""
    
    # === CONTROL DE FLUJO ===
    current_step: str           # Estado actual (ej: "identifying_user", "categorizing_issue")  
    awaiting_input: bool        # Si está esperando input del usuario
    next_action: str           # Qué hacer con el próximo input
    flow_history: list[str]    # Historial de pasos para debugging
    
    # === DATOS DE CONVERSACIÓN ===
    messages: list[BaseMessage]
    session_id: str
    user_intent: Optional[str]  # Intención detectada
    
    # === DATOS DE USUARIO ===
    nombre: Optional[str]
    email: Optional[str]
    numero_empleado: Optional[str]
    usuario_confirmado: bool
    
    # === DATOS DE INCIDENCIA ===
    categoria_incidencia: Optional[str]     # Hardware, Software, Red, etc.
    subcategoria: Optional[str]             # Específico dentro de categoría
    urgencia: Optional[str]                 # Baja, Media, Alta, Crítica
    descripcion: Optional[str]              # Descripción del problema
    pasos_reproducir: Optional[list[str]]   # Pasos para reproducir
    
    # === DATOS DE RESOLUCIÓN ===
    solucion_intentada: Optional[str]       # Qué ha intentado el usuario
    solucion_propuesta: Optional[str]       # Nuestra propuesta
    incidencia_resuelta: bool
    ticket_id: Optional[str]
    
    # === ESCALACIÓN ===
    escalar_a_supervisor: bool
    razon_escalacion: Optional[str]
    supervisor_asignado: Optional[str]

# =====================================================
# 2. SISTEMA DE PASOS ESCALABLE
# =====================================================

class ConversationSteps:
    """Definición centralizada de todos los pasos posibles"""
    
    # Identificación
    START = "start"
    IDENTIFYING_USER = "identifying_user"
    WAITING_USER_DATA = "waiting_user_data"
    WAITING_USER_CONFIRMATION = "waiting_user_confirmation"
    
    # Categorización
    CATEGORIZING_ISSUE = "categorizing_issue" 
    WAITING_CATEGORY_SELECTION = "waiting_category_selection"
    WAITING_SUBCATEGORY = "waiting_subcategory"
    
    # Detalles de incidencia
    GATHERING_DETAILS = "gathering_details"
    WAITING_DESCRIPTION = "waiting_description"
    WAITING_STEPS = "waiting_steps"
    WAITING_URGENCY = "waiting_urgency"
    
    # Resolución
    ANALYZING_ISSUE = "analyzing_issue"
    PROPOSING_SOLUTION = "proposing_solution"
    WAITING_SOLUTION_FEEDBACK = "waiting_solution_feedback"
    
    # Finalización
    CREATING_TICKET = "creating_ticket"
    ESCALATING = "escalating"
    COMPLETED = "completed"

# =====================================================
# 3. ROUTER CENTRALIZADO Y SIMPLE
# =====================================================

def route_conversation(state: ConversationState) -> str:
    """Router universal que escala con nuevos nodos"""
    
    # Si está esperando input, PARAR
    if state.get("awaiting_input", False):
        return "__interrupt__"
    
    # Si necesita escalación, escalar
    if state.get("escalar_a_supervisor", False):
        return "escalar_supervisor"
    
    # Si está completado, terminar
    if state.get("current_step") == ConversationSteps.COMPLETED:
        return "__end__"
    
    # Mapeo de pasos a nodos (fácil de extender)
    step_to_node = {
        ConversationSteps.START: "identificar_usuario",
        ConversationSteps.IDENTIFYING_USER: "identificar_usuario", 
        ConversationSteps.CATEGORIZING_ISSUE: "categorizar_incidencia",
        ConversationSteps.GATHERING_DETAILS: "recopilar_detalles",
        ConversationSteps.ANALYZING_ISSUE: "analizar_incidencia",
        ConversationSteps.PROPOSING_SOLUTION: "proponer_solucion",
        ConversationSteps.CREATING_TICKET: "crear_ticket",
        ConversationSteps.ESCALATING: "escalar_supervisor"
    }
    
    current_step = state.get("current_step", ConversationSteps.START)
    next_node = step_to_node.get(current_step, "identificar_usuario")
    
    # Log para debugging
    logger.info(f"🔄 Routing: {current_step} → {next_node}")
    
    return next_node

# =====================================================
# 4. CLASE BASE PARA NODOS ESCALABLES
# =====================================================

class ScalableBaseNode(BaseNode):
    """Clase base que facilita crear nuevos nodos"""
    
    def __init__(self, node_name: str, default_next_step: str):
        super().__init__(node_name)
        self.default_next_step = default_next_step
    
    def transition_to(self, next_step: str, awaiting_input: bool = False, **updates):
        """Helper para transiciones limpias"""
        update_data = {
            "current_step": next_step,
            "awaiting_input": awaiting_input,
            "flow_history": self._get_updated_history(next_step),
            **updates
        }
        
        self.logger.info(f"🔄 Transición: {self.node_name} → {next_step}")
        return Command(update=update_data)
    
    def wait_for_input(self, next_step: str, message: str, next_action: str = None):
        """Helper para esperar input del usuario"""
        return self.transition_to(
            next_step=next_step,
            awaiting_input=True,
            messages=[AIMessage(content=message)],
            next_action=next_action or f"process_{next_step}"
        )
    
    def _get_updated_history(self, step: str):
        """Actualizar historial de flujo"""
        # Implementar tracking de pasos para debugging
        pass

# =====================================================
# 5. EJEMPLO DE NUEVO NODO USANDO EL PATRÓN
# =====================================================

class CategorizarIncidenciaNode(ScalableBaseNode):
    """Nodo para categorizar el tipo de incidencia"""
    
    def __init__(self):
        super().__init__("categorizar_incidencia", ConversationSteps.GATHERING_DETAILS)
    
    async def execute(self, state: ConversationState):
        # Verificar si estamos procesando una respuesta
        if self._is_processing_response(state):
            return await self._handle_category_response(state)
        
        # Lógica normal: categorizar automáticamente o preguntar
        categoria = await self._detect_category(state)
        
        if categoria:
            return self.transition_to(
                next_step=ConversationSteps.GATHERING_DETAILS,
                categoria_incidencia=categoria
            )
        else:
            return self.wait_for_input(
                next_step=ConversationSteps.WAITING_CATEGORY_SELECTION,
                message="¿Tu problema es de Hardware, Software o Red?",
                next_action="process_category_selection"
            )
    
    async def _handle_category_response(self, state):
        """Procesar respuesta del usuario sobre categoría"""
        # Implementar lógica específica
        pass

# =====================================================
# 6. CONSTRUCTOR DE WORKFLOW ESCALABLE  
# =====================================================

def build_scalable_workflow():
    """Workflow que crece fácilmente con nuevos nodos"""
    
    workflow = StateGraph(ConversationState)
    
    # === NODOS ACTUALES ===
    workflow.add_node("identificar_usuario", IdentificarUsuarioNode())
    workflow.add_node("escalar_supervisor", EscalarSupervisorNode())
    
    # === NODOS NUEVOS (fácil de agregar) ===
    workflow.add_node("categorizar_incidencia", CategorizarIncidenciaNode())
    workflow.add_node("recopilar_detalles", RecopilarDetallesNode())
    workflow.add_node("analizar_incidencia", AnalizarIncidenciaNode())
    workflow.add_node("proponer_solucion", ProponerSolucionNode())
    workflow.add_node("crear_ticket", CrearTicketNode())
    
    # === ROUTING UNIVERSAL ===
    # Un solo router maneja todos los nodos
    for node_name in workflow.nodes:
        workflow.add_conditional_edges(node_name, route_conversation)
    
    workflow.set_entry_point("identificar_usuario")
    
    return workflow.compile(
        checkpointer=MemorySaver(),
        interrupt_before=["__interrupt__"]
    )

# =====================================================
# 7. TESTING ESCALABLE
# =====================================================

class ConversationTester:
    """Testing framework para el workflow escalable"""
    
    @staticmethod
    def test_node_transition(from_step: str, to_step: str, input_data: dict):
        """Test específico de transición entre nodos"""
        pass
    
    @staticmethod 
    def test_interruption_flow(step: str, user_input: str):
        """Test de flujo con interrupciones"""
        pass