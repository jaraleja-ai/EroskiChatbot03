# =============================================================================
# INTEGRACIÓN DEL NODO LLM-DRIVEN EN EL WORKFLOW
# =============================================================================

# 1. ACTUALIZAR workflow/eroski_main_workflow.py
"""
Reemplazar la importación del nodo de autenticación:

ANTES:
from nodes.authenticate import AuthenticateEmployeeNodeComplete

DESPUÉS:
from nodes.authenticate_llm_driven import LLMDrivenAuthenticateNode

Y en la función _add_nodes:
authenticate_node = LLMDrivenAuthenticateNode()
graph.add_node("authenticate", authenticate_node.execute)
"""

# =============================================================================
# 2. CONFIGURACIÓN DE RUTAS EN EL WORKFLOW
# =============================================================================

def route_authenticate_llm_driven(state: EroskiState) -> str:
    """
    Router mejorado para el nodo LLM-driven.
    
    Args:
        state: Estado actual
        
    Returns:
        Siguiente nodo a ejecutar
    """
    
    # Verificar si necesita input del usuario
    if state.get("awaiting_user_input"):
        return "need_input"  # Termina en END para esperar respuesta
    
    # Verificar cancelación confirmada
    if state.get("user_cancelled"):
        return "cancelled"  # Termina en END
    
    # Verificar escalación por errores
    if state.get("escalation_needed"):
        return "escalate"
    
    # Verificar si la autenticación está completa
    if (state.get("authentication_stage") == "completed" and 
        state.get("datos_usuario_completos")):
        return "continue"  # Ir a classify
    
    # Por defecto, continuar en el mismo nodo
    return "need_input"


# =============================================================================
# 3. PARSER JSON ROBUSTO PARA MANEJO DE ERRORES
# =============================================================================

import json
import re
from typing import Any, Dict

class RobustLLMParser:
    """Parser robusto para respuestas LLM con múltiples estrategias de fallback"""
    
    @staticmethod
    def parse_llm_response(content: str) -> Dict[str, Any]:
        """
        Parsear respuesta LLM con estrategias de fallback.
        
        Args:
            content: Contenido de la respuesta LLM
            
        Returns:
            Diccionario parseado
        """
        
        # Estrategia 1: JSON directo
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # Estrategia 2: JSON en bloques markdown
        json_patterns = [
            r'```json\s*\n(.*?)\n```',  # ```json ... ```
            r'```\s*\n(.*?)\n```',     # ``` ... ```
        ]
        
        for pattern in json_patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                try:
                    return json.loads(match.group(1).strip())
                except json.JSONDecodeError:
                    continue
        
        # Estrategia 3: Buscar JSON en cualquier parte
        try:
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1 and end > start:
                json_str = content[start:end+1]
                return json.loads(json_str)
        except json.JSONDecodeError:
            pass
        
        # Estrategia 4: Crear respuesta de fallback
        return RobustLLMParser._create_emergency_response(content)
    
    @staticmethod
    def _create_emergency_response(content: str) -> Dict[str, Any]:
        """Crear respuesta de emergencia cuando todo falla"""
        
        content_lower = content.lower()
        
        # Detectar intención de cancelar
        cancel_keywords = ["cancelar", "salir", "no quiero", "adiós", "olvídalo"]
        wants_to_cancel = any(keyword in content_lower for keyword in cancel_keywords)
        
        # Detectar email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', content)
        
        # Construir respuesta de emergencia
        return {
            "is_complete": False,
            "should_search_database": bool(email_match),
            "wants_to_cancel": wants_to_cancel,
            "extracted_data": {"email": email_match.group()} if email_match else {},
            "next_action": "cancel" if wants_to_cancel else "collect_data",
            "message_to_user": "Disculpa, ¿podrías repetir la información?",
            "missing_fields": ["información"],
            "confidence_level": 0.3
        }


# =============================================================================
# 4. INTEGRACIÓN EN EL PARSER DEL NODO
# =============================================================================

# Actualizar el método _get_llm_decision en LLMDrivenAuthenticateNode:

async def _get_llm_decision_improved(self, state: EroskiState) -> ConversationDecision:
    """Versión mejorada con parser robusto"""
    
    try:
        # Preparar contexto
        context = self._build_conversation_context(state)
        formatted_prompt = self.conversation_prompt.format(**context)
        
        # Invocar LLM
        response = await self.llm.ainvoke(formatted_prompt)
        
        # Parser robusto
        parsed_data = RobustLLMParser.parse_llm_response(response.content)
        
        # Convertir a ConversationDecision
        decision = ConversationDecision(**parsed_data)
        
        self.logger.info(f"🎯 LLM decidió: {decision.next_action} (confianza: {decision.confidence_level})")
        return decision
        
    except Exception as e:
        self.logger.warning(f"⚠️ Error en decisión LLM: {e}")
        return self._create_fallback_decision(state)


# =============================================================================
# 5. MÉTRICAS Y MONITOREO
# =============================================================================

class AuthenticationMetrics:
    """Clase para recopilar métricas del proceso de autenticación"""
    
    @staticmethod
    def log_authentication_metrics(state: EroskiState, node_logger):
        """Registrar métricas del proceso de autenticación"""
        
        metrics = {
            "total_attempts": state.get("attempts", 0),
            "conversation_efficiency": AuthenticationMetrics._calculate_efficiency(state),
            "data_collection_method": "database" if state.get("found_in_database") else "manual",
            "completion_time": AuthenticationMetrics._calculate_completion_time(state),
            "fallback_used": state.get("fallback_mode", False),
            "llm_decision_count": state.get("llm_decisions_made", 0)
        }
        
        node_logger.info(f"📊 Métricas de autenticación: {metrics}")
        return metrics
    
    @staticmethod
    def _calculate_efficiency(state: EroskiState) -> str:
        """Calcular eficiencia del proceso"""
        
        attempts = state.get("attempts", 0)
        if attempts == 1:
            return "excellent"  # Todo en un intercambio
        elif attempts <= 2:
            return "good"      # 2 intercambios
        elif attempts <= 3:
            return "fair"      # 3 intercambios
        else:
            return "poor"      # Más de 3 intercambios
    
    @staticmethod
    def _calculate_completion_time(state: EroskiState) -> int:
        """Calcular tiempo de completado en minutos"""
        
        start_time = state.get("conversation_started_at")
        end_time = state.get("last_activity")
        
        if start_time and end_time:
            delta = end_time - start_time
            return int(delta.total_seconds() / 60)
        
        return 0


# =============================================================================
# 6. VALIDACIONES Y CHECKS DE CALIDAD
# =============================================================================

class DataQualityValidator:
    """Validador de calidad de datos recopilados"""
    
    @staticmethod
    def validate_collected_data(collected_data: Dict) -> Dict[str, Any]:
        """
        Validar calidad de los datos recopilados.
        
        Args:
            collected_data: Datos recopilados
            
        Returns:
            Reporte de validación
        """
        
        validation_report = {
            "is_valid": True,
            "issues": [],
            "recommendations": [],
            "confidence_score": 1.0
        }
        
        # Validar nombre
        name = collected_data.get("name", "")
        if not DataQualityValidator._is_valid_name(name):
            validation_report["issues"].append("Nombre no parece válido")
            validation_report["confidence_score"] -= 0.2
        
        # Validar email
        email = collected_data.get("email", "")
        if email and not DataQualityValidator._is_valid_email(email):
            validation_report["issues"].append("Formato de email cuestionable")
            validation_report["confidence_score"] -= 0.1
        
        # Validar tienda
        store = collected_data.get("store_name", "")
        if not DataQualityValidator._is_valid_store(store):
            validation_report["issues"].append("Nombre de tienda poco específico")
            validation_report["recommendations"].append("Solicitar ubicación más específica")
            validation_report["confidence_score"] -= 0.1
        
        # Validar sección
        section = collected_data.get("section", "")
        if not DataQualityValidator._is_valid_section(section):
            validation_report["issues"].append("Sección no reconocida")
            validation_report["recommendations"].append("Clarificar sección específica")
            validation_report["confidence_score"] -= 0.1
        
        # Determinar validez general
        validation_report["is_valid"] = validation_report["confidence_score"] >= 0.7
        
        return validation_report
    
    @staticmethod
    def _is_valid_name(name: str) -> bool:
        """Validar que el nombre sea realista"""
        if not name or len(name) < 3:
            return False
        
        # Debe tener al menos nombre y apellido
        parts = name.strip().split()
        return len(parts) >= 2 and all(part.isalpha() or part.replace('-', '').isalpha() for part in parts)
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """Validar formato básico de email"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
    
    @staticmethod
    def _is_valid_store(store: str) -> bool:
        """Validar que el nombre de tienda sea específico"""
        if not store or len(store) < 5:
            return False
        
        # Debe contener "eroski" y alguna ubicación
        store_lower = store.lower()
        return "eroski" in store_lower and any(
            keyword in store_lower for keyword in [
                "madrid", "barcelona", "bilbao", "sevilla", "valencia", 
                "centro", "norte", "sur", "este", "oeste", "mall", "cc"
            ]
        )
    
    @staticmethod
    def _is_valid_section(section: str) -> bool:
        """Validar que la sección sea reconocida"""
        if not section:
            return False
        
        valid_sections = [
            "carnicería", "pescadería", "panadería", "frutería",
            "caja", "cajas", "tpv", "cobro",
            "almacén", "recepción", "stock",
            "oficina", "administración", "gerencia",
            "sala", "descanso", "vestuario",
            "limpieza", "mantenimiento", "seguridad"
        ]
        
        section_lower = section.lower()
        return any(valid in section_lower for valid in valid_sections)


# =============================================================================
# 7. EJEMPLO DE USO E INTEGRACIÓN COMPLETA
# =============================================================================

# En workflows/eroski_main_workflow.py:

"""
def _add_nodes(self, graph):
    try:
        # Importar nodo LLM-driven
        from nodes.authenticate_llm_driven import LLMDrivenAuthenticateNode
        
        # Crear instancia del nodo
        auth_node = LLMDrivenAuthenticateNode()
        
        # Añadir al grafo
        graph.add_node("authenticate", auth_node.execute)
        
        # Configurar router
        graph.add_conditional_edges(
            "authenticate",
            route_authenticate_llm_driven,  # Usar router mejorado
            {
                "continue": "classify",
                "need_input": END,
                "escalate": "escalate",
                "cancelled": END
            }
        )
        
        self.logger.info("✅ Nodo LLM-driven integrado correctamente")
        
    except Exception as e:
        self.logger.error(f"❌ Error integrando nodo LLM: {e}")
        raise
"""

# =============================================================================
# 8. CONFIGURACIÓN DE LOGGING ESPECIALIZADO
# =============================================================================

import logging

def setup_llm_driven_logging():
    """Configurar logging especializado para el nodo LLM-driven"""
    
    # Logger específico para conversaciones LLM
    llm_logger = logging.getLogger("LLMDrivenAuth")
    llm_logger.setLevel(logging.INFO)
    
    # Formato especializado
    formatter = logging.Formatter(
        '%(asctime)s | LLM-AUTH | %(levelname)s | %(message)s'
    )
    
    # Handler para archivo específico
    handler = logging.FileHandler('logs/llm_authentication.log')
    handler.setFormatter(formatter)
    llm_logger.addHandler(handler)
    
    return llm_logger

# =============================================================================
# 9. TESTS UNITARIOS PARA EL NODO LLM-DRIVEN
# =============================================================================

"""
# En tests/test_llm_authenticate_node.py

import pytest
from nodes.authenticate_llm_driven import LLMDrivenAuthenticateNode, ConversationDecision

@pytest.mark.asyncio
async def test_complete_data_in_one_message():
    '''Test: Usuario da toda la información en un mensaje'''
    
    node = LLMDrivenAuthenticateNode()
    
    state = {
        "messages": [
            HumanMessage(content="Hola, soy Juan Pérez, mi email es juan@eroski.es, trabajo en Eroski Madrid Centro en carnicería")
        ],
        "auth_data_collected": {}
    }
    
    # Mock LLM response
    mock_decision = ConversationDecision(
        is_complete=True,
        extracted_data={
            "name": "Juan Pérez",
            "email": "juan@eroski.es",
            "store_name": "Eroski Madrid Centro",
            "section": "carnicería"
        },
        next_action="complete",
        message_to_user="¡Perfecto Juan! Ya tengo toda tu información..."
    )
    
    with patch.object(node, '_get_llm_decision', return_value=mock_decision):
        result = await node.execute(state)
    
    # Verificar que se completa en un intercambio
    assert result.update["authentication_stage"] == "completed"
    assert result.update["datos_usuario_completos"] is True

@pytest.mark.asyncio
async def test_database_search_integration():
    '''Test: Integración con búsqueda en base de datos'''
    
    node = LLMDrivenAuthenticateNode()
    
    # Simular usuario encontrado en BD
    mock_employee = {
        "name": "Juan Pérez",
        "email": "juan@eroski.es",
        "store_name": "Eroski Madrid Centro",
        "id": 123
    }
    
    with patch.object(node, '_search_employee_database', return_value={"found": True, "employee": mock_employee}):
        decision = ConversationDecision(
            should_search_database=True,
            extracted_data={"email": "juan@eroski.es"},
            next_action="search_db"
        )
        
        result = await node._execute_llm_decision({}, decision)
    
    # Verificar integración con BD
    assert result.update["authenticated"] is True
    assert result.update["found_in_database"] is True
"""

# =============================================================================
# RESUMEN DE BENEFICIOS DE LA NUEVA IMPLEMENTACIÓN
# =============================================================================

"""
🎯 BENEFICIOS CLAVE:

1. **EFICIENCIA MÁXIMA**:
   - 1 intercambio vs 4+ del sistema anterior
   - Recopilación inteligente de múltiples datos por mensaje
   - Adaptación contextual automática

2. **SIMPLICIDAD DE CÓDIGO**:
   - ~300 líneas vs 800+ del anterior
   - Lógica centralizada en el LLM
   - Mantenimiento simplificado

3. **EXPERIENCIA SUPERIOR**:
   - Conversación natural vs interrogatorio
   - Mensajes personalizados y contextuales
   - Detección inteligente de intenciones

4. **ROBUSTEZ**:
   - Parser múltiple con fallbacks
   - Validación de calidad de datos
   - Métricas de rendimiento

5. **ESCALABILIDAD**:
   - Fácil añadir nuevos campos
   - Modificaciones solo en prompt
   - Integración simple con otros sistemas

6. **MONITOREO**:
   - Métricas detalladas de eficiencia
   - Logging especializado
   - Validación de calidad automática
"""