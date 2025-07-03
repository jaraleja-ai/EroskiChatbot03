# =====================================================
# PASO 4: Test de Integración y Verificación
# =====================================================

# Crear este archivo: tests/test_llm_authenticate_integration.py

import pytest
import asyncio
from unittest.mock import patch, Mock, AsyncMock
from langchain_core.messages import HumanMessage, AIMessage

# Importar componentes a testear
from nodes.authenticate_llm_driven import LLMDrivenAuthenticateNode, ConversationDecision
from workflows.eroski_main_workflow import EroskiFinalWorkflow
from models.eroski_state import EroskiState


class TestLLMAuthenticateIntegration:
    """Tests de integración para el nodo LLM-driven"""
    
    @pytest.fixture
    def auth_node(self):
        """Fixture para crear instancia del nodo"""
        return LLMDrivenAuthenticateNode()
    
    @pytest.fixture
    def workflow(self):
        """Fixture para crear instancia del workflow"""
        return EroskiFinalWorkflow()
    
    @pytest.fixture
    def initial_state(self):
        """Estado inicial básico para tests"""
        return {
            "messages": [],
            "session_id": "test_session_123",
            "last_activity": None,
            "attempts": 0
        }
    
    @pytest.fixture
    def complete_user_data_state(self):
        """Estado con datos completos del usuario"""
        return {
            "messages": [
                HumanMessage(content="Hola, soy Juan Pérez, mi email es juan@eroski.es, trabajo en Eroski Madrid Centro en carnicería")
            ],
            "session_id": "test_complete_123",
            "auth_data_collected": {},
            "attempts": 0
        }
    
    # =========================================================================
    # TESTS DEL NODO INDIVIDUAL
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_first_visit_creates_welcome_message(self, auth_node, initial_state):
        """Test: Primera visita crea mensaje de bienvenida"""
        
        result = await auth_node.execute(initial_state)
        
        # Verificar estructura de respuesta
        assert "update" in result.__dict__
        update = result.update
        
        # Verificar campos esperados
        assert update["current_node"] == "authenticate"
        assert update["awaiting_user_input"] is True
        assert update["attempts"] == 1
        assert update["auth_conversation_started"] is True
        assert "auth_data_collected" in update
        
        # Verificar mensaje de bienvenida
        messages = update["messages"]
        assert len(messages) == 1
        assert isinstance(messages[0], AIMessage)
        assert "nombre completo" in messages[0].content.lower()
        assert "email" in messages[0].content.lower()
        assert "tienda" in messages[0].content.lower()
        assert "sección" in messages[0].content.lower()
    
    @pytest.mark.asyncio
    async def test_complete_data_extraction(self, auth_node, complete_user_data_state):
        """Test: Extracción completa de datos en un mensaje"""
        
        # Mock de la respuesta del LLM
        mock_decision = ConversationDecision(
            is_complete=True,
            should_search_database=True,
            wants_to_cancel=False,
            extracted_data={
                "name": "Juan Pérez",
                "email": "juan@eroski.es",
                "store_name": "Eroski Madrid Centro",
                "section": "carnicería"
            },
            next_action="search_db",
            message_to_user="Perfecto Juan, déjame buscar tu información...",
            confidence_level=0.95
        )
        
        # Mock de búsqueda en BD exitosa
        mock_employee = {
            "id": 123,
            "name": "Juan Pérez",
            "email": "juan@eroski.es",
            "store_name": "Eroski Madrid Centro",
            "department": "Alimentación"
        }
        
        with patch.object(auth_node, '_get_llm_decision', return_value=mock_decision) as mock_llm, \
             patch.object(auth_node, '_search_employee_database', return_value={"found": True, "employee": mock_employee}) as mock_db:
            
            result = await auth_node.execute(complete_user_data_state)
        
        # Verificar que se completó la autenticación
        update = result.update
        assert update["authentication_stage"] == "completed"
        assert update["datos_usuario_completos"] is True
        assert update["ready_for_classification"] is True
        
        # Verificar datos extraídos
        assert update["employee_name"] == "Juan Pérez"
        assert update["employee_email"] == "juan@eroski.es"
        assert update["incident_store_name"] == "Eroski Madrid Centro"
        assert update["incident_section"] == "carnicería"
        assert update["authenticated"] is True
        
        # Verificar que se llamaron los métodos correctos
        mock_llm.assert_called_once()
        mock_db.assert_called_once_with("juan@eroski.es")
    
    @pytest.mark.asyncio
    async def test_partial_data_extraction(self, auth_node):
        """Test: Extracción parcial de datos - continúa conversación"""
        
        partial_state = {
            "messages": [
                HumanMessage(content="Trabajo en Eroski Madrid en caja")
            ],
            "session_id": "test_partial",
            "auth_data_collected": {},
            "auth_conversation_started": True,
            "attempts": 1
        }
        
        # Mock de respuesta LLM para datos parciales
        mock_decision = ConversationDecision(
            is_complete=False,
            should_search_database=False,
            wants_to_cancel=False,
            extracted_data={
                "store_name": "Eroski Madrid",
                "section": "caja"
            },
            next_action="collect_data",
            message_to_user="Gracias. ¿Podrías decirme tu nombre completo y email?",
            missing_fields=["name", "email"],
            confidence_level=0.8
        )
        
        with patch.object(auth_node, '_get_llm_decision', return_value=mock_decision):
            result = await auth_node.execute(partial_state)
        
        # Verificar que continúa la conversación
        update = result.update
        assert update["awaiting_user_input"] is True
        assert update["attempts"] == 2
        
        # Verificar que guardó los datos parciales
        collected_data = update["auth_data_collected"]
        assert collected_data["store_name"] == "Eroski Madrid"
        assert collected_data["section"] == "caja"
        
        # Verificar que no está completo
        assert update.get("authentication_stage") != "completed"
    
    @pytest.mark.asyncio
    async def test_cancellation_handling(self, auth_node):
        """Test: Manejo de cancelación del usuario"""
        
        cancel_state = {
            "messages": [
                HumanMessage(content="cancelar")
            ],
            "session_id": "test_cancel",
            "auth_data_collected": {},
            "auth_conversation_started": True,
            "attempts": 1
        }
        
        # Mock de respuesta LLM para cancelación
        mock_decision = ConversationDecision(
            is_complete=False,
            should_search_database=False,
            wants_to_cancel=True,
            extracted_data={},
            next_action="cancel",
            message_to_user="Entiendo que quieres cancelar. ¿Estás seguro?",
            confidence_level=0.9
        )
        
        with patch.object(auth_node, '_get_llm_decision', return_value=mock_decision):
            result = await auth_node.execute(cancel_state)
        
        # Verificar manejo de cancelación
        update = result.update
        assert update["awaiting_cancellation_confirmation"] is True
        assert update["awaiting_user_input"] is True
        assert "cancelar" in update["messages"][-1].content.lower()
    
    @pytest.mark.asyncio
    async def test_fallback_mode_activation(self, auth_node):
        """Test: Activación del modo fallback cuando LLM falla"""
        
        error_state = {
            "messages": [
                HumanMessage(content="Información compleja que podría fallar")
            ],
            "session_id": "test_fallback",
            "auth_data_collected": {},
            "auth_conversation_started": True,
            "attempts": 1
        }
        
        # Simular error en LLM
        with patch.object(auth_node, '_get_llm_decision', side_effect=Exception("LLM Error")):
            result = await auth_node.execute(error_state)
        
        # Verificar activación de fallback
        update = result.update
        assert update["fallback_mode"] is True
        assert update["fallback_stage"] == "requesting_name"
        assert update["awaiting_user_input"] is True
        assert "problema técnico" in update["messages"][-1].content.lower()
    
    # =========================================================================
    # TESTS DE INTEGRACIÓN CON WORKFLOW
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_workflow_integration(self, workflow):
        """Test: Integración completa con el workflow"""
        
        # Verificar que el workflow se puede compilar
        try:
            compiled_graph = workflow.compile()
            assert compiled_graph is not None
        except Exception as e:
            pytest.fail(f"Error compilando workflow con nodo LLM: {e}")
    
    @pytest.mark.asyncio
    async def test_routing_logic(self, workflow):
        """Test: Lógica de routing del nodo LLM-driven"""
        
        # Test routing - necesita input
        state_need_input = {
            "awaiting_user_input": True,
            "authentication_stage": "in_progress"
        }
        result = workflow.route_authenticate_llm_driven_with_validation(state_need_input)
        assert result == "need_input"
        
        # Test routing - autenticación completa
        state_complete = {
            "authentication_stage": "completed",
            "datos_usuario_completos": True,
            "ready_for_classification": True,
            "employee_name": "Juan Pérez",
            "incident_store_name": "Eroski Madrid",
            "incident_section": "caja",
            "awaiting_user_input": False
        }
        result = workflow.route_authenticate_llm_driven_with_validation(state_complete)
        assert result == "continue"
        
        # Test routing - escalación por límite de intentos
        state_escalate = {
            "attempts": 6,  # Más del límite de 5
            "awaiting_user_input": False
        }
        result = workflow.route_authenticate_llm_driven_with_validation(state_escalate)
        assert result == "escalate"
        
        # Test routing - cancelación
        state_cancelled = {
            "user_cancelled": True,
            "awaiting_user_input": False
        }
        result = workflow.route_authenticate_llm_driven_with_validation(state_cancelled)
        assert result == "cancelled"
    
    @pytest.mark.asyncio
    async def test_end_to_end_flow(self, workflow):
        """Test: Flujo completo end-to-end"""
        
        # Mock del LLM para respuesta completa
        mock_llm_response = Mock()
        mock_llm_response.content = '''
        {
            "is_complete": true,
            "should_search_database": true,
            "wants_to_cancel": false,
            "extracted_data": {
                "name": "María García",
                "email": "maria@eroski.es",
                "store_name": "Eroski Bilbao Centro",
                "section": "panadería"
            },
            "next_action": "complete",
            "message_to_user": "¡Perfecto María! Ya tengo toda tu información...",
            "confidence_level": 0.95
        }
        '''
        
        # Mock de la búsqueda en BD
        mock_employee = {
            "id": 456,
            "name": "María García",
            "email": "maria@eroski.es",
            "store_name": "Eroski Bilbao Centro"
        }
        
        initial_state = {
            "messages": [
                HumanMessage(content="Hola, soy María García, maria@eroski.es, Eroski Bilbao Centro, panadería")
            ],
            "session_id": "test_e2e"
        }
        
        # Compilar workflow
        compiled_graph = workflow.compile()
        
        with patch('utils.llm_client.get_llm') as mock_get_llm:
            mock_llm = AsyncMock()
            mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)
            mock_get_llm.return_value = mock_llm
            
            with patch('utils.eroski_database_auth.EroskiEmployeeDatabaseAuth') as mock_db_auth:
                mock_db_instance = AsyncMock()
                mock_db_instance.get_employee_by_email = AsyncMock(return_value=mock_employee)
                mock_db_auth.return_value = mock_db_instance
                
                # Ejecutar workflow
                result = await compiled_graph.ainvoke(initial_state)
        
        # Verificar resultado final
        assert result.get("authentication_stage") == "completed"
        assert result.get("employee_name") == "María García"
        assert result.get("ready_for_classification") is True
    
    # =========================================================================
    # TESTS DE PERFORMANCE Y EFICIENCIA
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_authentication_efficiency_metrics(self, workflow):
        """Test: Métricas de eficiencia de autenticación"""
        
        # Test eficiencia excelente (1 intento)
        state_excellent = {"attempts": 1}
        efficiency = workflow._calculate_auth_efficiency(state_excellent)
        assert efficiency == "excellent"
        
        # Test eficiencia buena (2 intentos)
        state_good = {"attempts": 2}
        efficiency = workflow._calculate_auth_efficiency(state_good)
        assert efficiency == "good"
        
        # Test eficiencia regular (3 intentos)
        state_fair = {"attempts": 3}
        efficiency = workflow._calculate_auth_efficiency(state_fair)
        assert efficiency == "fair"
        
        # Test eficiencia pobre (4+ intentos)
        state_poor = {"attempts": 5}
        efficiency = workflow._calculate_auth_efficiency(state_poor)
        assert efficiency == "poor"
    
    @pytest.mark.asyncio
    async def test_state_validation(self, workflow):
        """Test: Validación de estado antes del routing"""
        
        # Estado válido
        valid_state = {
            "messages": [],
            "session_id": "test_valid",
            "attempts": 2
        }
        assert workflow.validate_auth_state_before_routing(valid_state) is True
        
        # Estado inválido - sin session_id
        invalid_state = {
            "messages": []
        }
        assert workflow.validate_auth_state_before_routing(invalid_state) is False
        
        # Estado con inconsistencia que se puede corregir
        inconsistent_state = {
            "messages": [],
            "session_id": "test_inconsistent",
            "authentication_stage": "completed",
            "datos_usuario_completos": False,
            "attempts": -1  # Intento negativo
        }
        
        # La validación debe corregir las inconsistencias
        result = workflow.validate_auth_state_before_routing(inconsistent_state)
        assert result is True
        assert inconsistent_state["datos_usuario_completos"] is True
        assert inconsistent_state["attempts"] == 0
    
    # =========================================================================
    # TESTS DE ROBUSTEZ Y MANEJO DE ERRORES
    # =========================================================================
    
    @pytest.mark.asyncio
    async def test_robust_json_parsing(self, auth_node):
        """Test: Parser JSON robusto con diferentes formatos"""
        
        from nodes.authenticate_llm_driven import RobustJsonParser
        
        # Test JSON directo
        json_direct = '{"test": "value"}'
        result = RobustJsonParser.parse_llm_response(json_direct)
        assert result["test"] == "value"
        
        # Test JSON en markdown
        json_markdown = '''```json
        {"test": "markdown"}
        ```'''
        result = RobustJsonParser.parse_llm_response(json_markdown)
        assert result["test"] == "markdown"
        
        # Test JSON malformado - debe usar fallback
        json_malformed = "Texto sin JSON válido"
        result = RobustJsonParser.parse_llm_response(json_malformed)
        assert "next_action" in result
        assert "message_to_user" in result
        
        # Test con email en texto malformado
        text_with_email = "Mi email es test@eroski.es pero no es JSON"
        result = RobustJsonParser.parse_llm_response(text_with_email)
        assert result["extracted_data"]["email"] == "test@eroski.es"
    
    @pytest.mark.asyncio
    async def test_database_connection_failure(self, auth_node):
        """Test: Manejo de fallo en conexión a base de datos"""
        
        state_with_email = {
            "messages": [HumanMessage(content="juan@eroski.es")],
            "auth_data_collected": {"email": "juan@eroski.es"},
            "auth_conversation_started": True,
            "attempts": 1
        }
        
        # Mock de decisión LLM que requiere búsqueda en BD
        mock_decision = ConversationDecision(
            is_complete=False,
            should_search_database=True,
            extracted_data={"email": "juan@eroski.es"},
            next_action="search_db",
            message_to_user="Déjame buscar tu información..."
        )
        
        # Simular error en base de datos
        with patch.object(auth_node, '_get_llm_decision', return_value=mock_decision), \
             patch.object(auth_node, '_search_employee_database', return_value={"found": False, "error": "Connection failed"}):
            
            result = await auth_node.execute(state_with_email)
        
        # Verificar que continúa funcionando a pesar del error
        update = result.update
        assert update["auth_data_collected"]["found_in_database"] is False
        assert update["awaiting_user_input"] is True


# =========================================================================
# SCRIPT DE EJECUCIÓN MANUAL PARA TESTING
# =========================================================================

async def run_manual_test():
    """Script para ejecutar test manual del nodo LLM-driven"""
    
    print("🧪 Ejecutando test manual del nodo LLM-driven...")
    
    # Crear instancia del nodo
    auth_node = LLMDrivenAuthenticateNode()
    
    # Test 1: Primera visita
    print("\n1️⃣ Test: Primera visita")
    state1 = {
        "messages": [],
        "session_id": "manual_test_1"
    }
    
    try:
        result1 = await auth_node.execute(state1)
        print(f"✅ Primera visita: {result1.update['awaiting_user_input']}")
        print(f"📝 Mensaje: {result1.update['messages'][0].content[:100]}...")
    except Exception as e:
        print(f"❌ Error en primera visita: {e}")
    
    # Test 2: Datos completos
    print("\n2️⃣ Test: Datos completos")
    state2 = {
        "messages": [
            HumanMessage(content="Hola, soy Ana López, ana@eroski.es, Eroski Sevilla Norte, caja")
        ],
        "session_id": "manual_test_2",
        "auth_data_collected": {},
        "auth_conversation_started": True,
        "attempts": 1
    }
    
    try:
        # Mock del LLM para este test
        with patch.object(auth_node, '_get_llm_decision') as mock_llm:
            mock_llm.return_value = ConversationDecision(
                is_complete=True,
                extracted_data={
                    "name": "Ana López",
                    "email": "ana@eroski.es",
                    "store_name": "Eroski Sevilla Norte",
                    "section": "caja"
                },
                next_action="complete",
                message_to_user="¡Perfecto Ana! Ya tengo toda tu información."
            )
            
            result2 = await auth_node.execute(state2)
            print(f"✅ Datos completos: {result2.update.get('authentication_stage')}")
            print(f"👤 Empleado: {result2.update.get('employee_name')}")
    except Exception as e:
        print(f"❌ Error con datos completos: {e}")
    
    print("\n✅ Tests manuales completados")


if __name__ == "__main__":
    # Ejecutar tests manuales
    asyncio.run(run_manual_test())