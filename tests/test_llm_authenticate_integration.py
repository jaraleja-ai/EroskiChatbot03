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
        
        with patch.object