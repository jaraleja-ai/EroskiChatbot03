# =====================================================
# tests/test_eroski_workflow.py - Tests de Validación del Workflow
# =====================================================
"""
Suite completa de tests para validar el workflow optimizado de Eroski.

COBERTURA DE TESTS:
- Flujo completo de autenticación
- Clasificación de consultas
- Manejo de incidencias
- Escalación automática
- Manejo de errores
- Estado persistente
- Integración con interfaz

TIPOS DE TESTS:
- Unit tests: Nodos individuales
- Integration tests: Flujo completo
- End-to-end tests: Interfaz + workflow
- Performance tests: Rendimiento
- Error handling tests: Casos de error
"""

import pytest
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage

# Importar componentes a testear
from workflows.eroski_main_workflow import EroskiFinalWorkflow, create_eroski_workflow
from interfaces.eroski_chat_interface import EroskiChatInterface, create_eroski_chat_interface
from models.eroski_state import EroskiState, create_initial_eroski_state, ConsultaType
from nodes.eroski.authenticate import AuthenticateEmployeeNodeComplete, EroskiEmployeeValidator

# ========== FIXTURES ==========

@pytest.fixture
def sample_employee_data():
    """Datos de empleado de prueba"""
    return {
        "id": "E001",
        "name": "Juan Pérez Test",
        "email": "juan.test@eroski.es",
        "store_id": "TEST001",
        "store_name": "Eroski Test Store",
        "store_type": "supermercado",
        "department": "IT Testing",
        "level": 2
    }

@pytest.fixture
def initial_state():
    """Estado inicial para tests"""
    return create_initial_eroski_state("test_session_001")

@pytest.fixture
def authenticated_state(sample_employee_data):
    """Estado con usuario autenticado"""
    state = create_initial_eroski_state("test_session_002")
    state.update({
        "employee_email": sample_employee_data["email"],
        "employee_name": sample_employee_data["name"],
        "employee_id": sample_employee_data["id"],
        "store_id": sample_employee_data["store_id"],
        "store_name": sample_employee_data["store_name"],
        "authenticated": True
    })
    return state

@pytest.fixture
def workflow():
    """Instancia del workflow para tests"""
    return create_eroski_workflow()

@pytest.fixture
def chat_interface():
    """Instancia de la interfaz de chat para tests"""
    return create_eroski_chat_interface()

# ========== TESTS UNITARIOS - NODOS ==========

class TestAuthenticateNode:
    """Tests para el nodo de autenticación"""
    
    @pytest.fixture
    def auth_node(self):
        return AuthenticateEmployeeNodeComplete()
    
    @pytest.mark.asyncio
    async def test_first_execution_requests_credentials(self, auth_node, initial_state):
        """Test: Primera ejecución solicita credenciales"""
        result = await auth_node.execute(initial_state)
        
        # Verificar que solicita credenciales
        assert result.update["awaiting_user_input"] is True
        assert result.update["attempts"] == 1
        assert "email corporativo" in result.update["messages"][-1].content.lower()
        assert "tienda" in result.update["messages"][-1].content.lower()
    
    @pytest.mark.asyncio
    async def test_already_authenticated_continues(self, auth_node, authenticated_state):
        """Test: Usuario ya autenticado continúa"""
        result = await auth_node.execute(authenticated_state)
        
        # Verificar que continúa sin solicitar credenciales
        assert result.update.get("awaiting_user_input") != True
        assert result.update["current_node"] == "authenticate"
        assert result.update["attempts"] == 0
    
    @pytest.mark.asyncio
    async def test_valid_credentials_authentication(self, auth_node, initial_state, sample_employee_data):
        """Test: Credenciales válidas autentican correctamente"""
        # Preparar estado con mensaje del usuario
        user_message = f"Mi email es {sample_employee_data['email']} y trabajo en Test Store"
        initial_state["messages"] = [HumanMessage(content=user_message)]
        
        # Mock del validador
        with patch.object(auth_node.employee_validator, 'validate_employee', 
                         return_value=sample_employee_data):
            result = await auth_node.execute(initial_state)
        
        # Verificar autenticación exitosa
        assert result.update["authenticated"] is True
        assert result.update["employee_email"] == sample_employee_data["email"]
        assert result.update["employee_name"] == sample_employee_data["name"]
        assert result.update["awaiting_user_input"] is False
    
    @pytest.mark.asyncio
    async def test_invalid_email_retry(self, auth_node, initial_state):
        """Test: Email inválido solicita reintento"""
        # Email sin dominio eroski.es
        user_message = "Mi email es juan@gmail.com y trabajo en Test Store"
        initial_state["messages"] = [HumanMessage(content=user_message)]
        
        result = await auth_node.execute(initial_state)
        
        # Verificar que solicita reintento
        assert result.update["awaiting_user_input"] is True
        assert result.update["attempts"] == 2
        assert "no se encontró email corporativo" in result.update["messages"][-1].content.lower()
    
    @pytest.mark.asyncio
    async def test_max_attempts_escalation(self, auth_node, initial_state):
        """Test: Máximo de intentos causa escalación"""
        # Configurar estado con máximo de intentos
        initial_state["attempts"] = 3
        initial_state["messages"] = [HumanMessage(content="email inválido")]
        
        result = await auth_node.execute(initial_state)
        
        # Verificar escalación
        assert result.update["escalation_needed"] is True
        assert "supervisor" in result.update["messages"][-1].content.lower()

class TestEmployeeValidator:
    """Tests para el validador de empleados"""
    
    @pytest.fixture
    def validator(self):
        return EroskiEmployeeValidator()
    
    @pytest.mark.asyncio
    async def test_valid_employee_found(self, validator):
        """Test: Empleado válido es encontrado"""
        result = await validator.validate_employee("juan.perez@eroski.es")
        
        assert result is not None
        assert result["email"] == "juan.perez@eroski.es"
        assert result["name"] == "Juan Pérez"
        assert "store_id" in result
    
    @pytest.mark.asyncio
    async def test_invalid_employee_not_found(self, validator):
        """Test: Empleado inválido no es encontrado"""
        result = await validator.validate_employee("noexiste@eroski.es")
        
        assert result is None

# ========== TESTS DE INTEGRACIÓN - WORKFLOW ==========

class TestEroskiWorkflow:
    """Tests de integración del workflow completo"""
    
    @pytest.mark.asyncio
    async def test_workflow_compilation(self, workflow):
        """Test: Workflow se compila correctamente"""
        compiled_graph = workflow.compile_with_checkpointer()
        
        assert compiled_graph is not None
        # Verificar que tiene los nodos esperados
        node_names = list(compiled_graph.nodes.keys())
        expected_nodes = ["authenticate", "classify", "collect_incident", 
                         "search_solution", "escalate", "finalize"]
        
        for node in expected_nodes:
            assert node in node_names
    
    @pytest.mark.asyncio
    async def test_authentication_flow(self, workflow):
        """Test: Flujo completo de autenticación"""
        compiled_graph = workflow.compile_with_checkpointer()
        config = {"configurable": {"thread_id": "test_auth_flow"}}
        
        # Mensaje inicial
        initial_input = {
            "messages": [HumanMessage(content="Hola")],
            "session_id": "test_auth_flow"
        }
        
        result = await compiled_graph.ainvoke(initial_input, config)
        
        # Verificar que solicita autenticación
        last_message = result["messages"][-1]
        assert isinstance(last_message, AIMessage)
        assert "email" in last_message.content.lower()
        
        # Enviar credenciales válidas
        auth_input = {
            "messages": result["messages"] + [
                HumanMessage(content="Mi email es admin.test@eroski.es y trabajo en Test Store")
            ]
        }
        
        # Mock del validador para este test
        with patch('nodes.eroski.authenticate.EroskiEmployeeValidator.validate_employee',
                   return_value={
                       "id": "E999", "name": "Admin Test", "email": "admin.test@eroski.es",
                       "store_id": "TEST999", "store_name": "Test Store"
                   }):
            result2 = await compiled_graph.ainvoke(auth_input, config)
        
        # Verificar autenticación exitosa
        assert result2.get("authenticated") is True
        assert result2.get("employee_email") == "admin.test@eroski.es"
    
    @pytest.mark.asyncio  
    async def test_routing_functions(self, workflow):
        """Test: Funciones de routing funcionan correctamente"""
        
        # Test routing de autenticación
        authenticated_state = {
            "employee_email": "test@eroski.es",
            "store_name": "Test Store",
            "authenticated": True
        }
        assert workflow.route_authenticate(authenticated_state) == "continue"
        
        unauthenticated_state = {"attempts": 1}
        assert workflow.route_authenticate(unauthenticated_state) == "need_input"
        
        max_attempts_state = {"attempts": 3}
        assert workflow.route_authenticate(max_attempts_state) == "escalate"
        
        # Test routing de clasificación
        incident_state = {
            "query_type": ConsultaType.INCIDENCIA,
            "confidence_score": 0.8
        }
        assert workflow.route_classify(incident_state) == "incident"
        
        urgent_state = {
            "query_type": ConsultaType.URGENTE,
            "confidence_score": 0.9
        }
        assert workflow.route_classify(urgent_state) == "urgent"

# ========== TESTS END-TO-END - INTERFAZ ==========

class TestChatInterface:
    """Tests end-to-end de la interfaz de chat"""
    
    @pytest.mark.asyncio
    async def test_interface_initialization(self, chat_interface):
        """Test: Interfaz se inicializa correctamente"""
        assert chat_interface.workflow is not None
        assert chat_interface.graph is not None
        assert chat_interface.active_sessions == {}
    
    @pytest.mark.asyncio
    async def test_process_message_first_time(self, chat_interface):
        """Test: Procesar primer mensaje"""
        result = await chat_interface.process_message(
            user_message="Hola, necesito ayuda",
            session_id="test_first_msg"
        )
        
        assert result["success"] is True
        assert result["session_id"] == "test_first_msg"
        assert "email" in result["response"].lower() or "credenciales" in result["response"].lower()
        assert result["awaiting_input"] is True
    
    @pytest.mark.asyncio
    async def test_authentication_conversation(self, chat_interface):
        """Test: Conversación completa de autenticación"""
        session_id = "test_auth_conversation"
        
        # Primer mensaje
        result1 = await chat_interface.process_message(
            user_message="Hola",
            session_id=session_id
        )
        assert result1["success"] is True
        
        # Enviar credenciales con mock
        with patch('nodes.eroski.authenticate.EroskiEmployeeValidator.validate_employee',
                   return_value={
                       "id": "E001", "name": "Test User", "email": "test@eroski.es",
                       "store_id": "TEST001", "store_name": "Test Store"
                   }):
            result2 = await chat_interface.process_message(
                user_message="Mi email es test@eroski.es y trabajo en Test Store",
                session_id=session_id
            )
        
        assert result2["success"] is True
        assert result2["metadata"]["employee_name"] == "Test User"
        assert result2["metadata"]["store_name"] == "Test Store"
    
    @pytest.mark.asyncio
    async def test_error_handling(self, chat_interface):
        """Test: Manejo de errores"""
        # Simular error en el workflow
        with patch.object(chat_interface.graph, 'ainvoke', side_effect=Exception("Test error")):
            result = await chat_interface.process_message(
                user_message="Test message",
                session_id="test_error"
            )
        
        assert result["success"] is False
        assert "error" in result["response"].lower()
        assert result["status"] == "error"
    
    def test_session_management(self, chat_interface):
        """Test: Gestión de sesiones"""
        # Verificar sesiones vacías inicialmente
        assert chat_interface.get_active_sessions_count() == 0
        
        # Agregar sesión mock
        chat_interface.active_sessions["test_session"] = {
            "last_activity": datetime.now(),
            "status": "in_progress",
            "employee_id": "E001",
            "store_id": "TEST001"
        }
        
        assert chat_interface.get_active_sessions_count() == 1
        assert chat_interface.get_session_info("test_session") is not None
        
        # Test filtro por tienda
        store_sessions = chat_interface.get_sessions_by_store("TEST001")
        assert len(store_sessions) == 1
        assert store_sessions[0]["employee_id"] == "E001"

# ========== TESTS DE RENDIMIENTO ==========

class TestPerformance:
    """Tests de rendimiento y carga"""
    
    @pytest.mark.asyncio
    async def test_concurrent_sessions(self, chat_interface):
        """Test: Múltiples sesiones concurrentes"""
        async def process_session(session_id: str):
            return await chat_interface.process_message(
                user_message="Test concurrent message",
                session_id=session_id
            )
        
        # Crear 10 sesiones concurrentes
        tasks = []
        for i in range(10):
            task = process_session(f"concurrent_session_{i}")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        # Verificar que todas las sesiones se procesaron
        assert len(results) == 10
        for result in results:
            assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_message_processing_time(self, chat_interface):
        """Test: Tiempo de procesamiento de mensajes"""
        start_time = datetime.now()
        
        result = await chat_interface.process_message(
            user_message="Test performance message",
            session_id="performance_test"
        )
        
        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()
        
        # Verificar que se procesa en menos de 5 segundos
        assert processing_time < 5.0
        assert result["success"] is True

# ========== TESTS DE CASOS EDGE ==========

class TestEdgeCases:
    """Tests para casos extremos y edge cases"""
    
    @pytest.mark.asyncio
    async def test_empty_message(self, chat_interface):
        """Test: Mensaje vacío"""
        result = await chat_interface.process_message(
            user_message="",
            session_id="empty_message_test"
        )
        
        # Debería manejar gracefully el mensaje vacío
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_very_long_message(self, chat_interface):
        """Test: Mensaje muy largo"""
        long_message = "a" * 10000  # 10k caracteres
        
        result = await chat_interface.process_message(
            user_message=long_message,
            session_id="long_message_test"
        )
        
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_special_characters(self, chat_interface):
        """Test: Caracteres especiales"""
        special_message = "Test ñáéíóú 🤖 @#$%^&*()_+ <script>alert('test')</script>"
        
        result = await chat_interface.process_message(
            user_message=special_message,
            session_id="special_chars_test"
        )
        
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_session_cleanup(self, chat_interface):
        """Test: Limpieza de sesiones antiguas"""
        # Agregar sesión antigua
        old_time = datetime.now().timestamp() - (25 * 3600)  # 25 horas atrás
        chat_interface.active_sessions["old_session"] = {
            "last_activity": datetime.fromtimestamp(old_time)
        }
        
        # Agregar sesión reciente
        chat_interface.active_sessions["recent_session"] = {
            "last_activity": datetime.now()
        }
        
        # Ejecutar limpieza
        chat_interface._cleanup_old_sessions()
        
        # Verificar que solo queda la sesión reciente
        assert "old_session" not in chat_interface.active_sessions
        assert "recent_session" in chat_interface.active_sessions

# ========== CONFIGURACIÓN DE PYTEST ==========

@pytest.fixture(scope="session")
def event_loop():
    """Crear event loop para tests async"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

# ========== HELPERS PARA TESTS ==========

def create_test_state(**kwargs) -> EroskiState:
    """Helper para crear estados de test"""
    base_state = create_initial_eroski_state("test_session")
    base_state.update(kwargs)
    return base_state

def assert_message_contains(messages: List, content: str, message_type=AIMessage):
    """Helper para verificar contenido en mensajes"""
    found = False
    for msg in messages:
        if isinstance(msg, message_type) and content.lower() in msg.content.lower():
            found = True
            break
    assert found, f"No se encontró '{content}' en mensajes de tipo {message_type.__name__}"

# ========== SUITE DE TESTS PRINCIPALES ==========

if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--cov=workflows",
        "--cov=interfaces", 
        "--cov=nodes",
        "--cov-report=html",
        "--cov-report=term-missing"
    ])