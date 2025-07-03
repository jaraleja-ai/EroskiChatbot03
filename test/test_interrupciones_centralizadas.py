# =====================================================
# test_interrupciones_centralizadas.py - Script de pruebas
# =====================================================
"""
Script para probar las interrupciones centralizadas y optimización del estado.

Para ejecutar:
python test_interrupciones_centralizadas.py
"""

import asyncio
import logging
from typing import Dict, Any
from datetime import datetime

# Configurar logging para las pruebas
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Importar los módulos actualizados
from nodes.base_node import BaseNode
from nodes.identificar_usuario import IdentificarUsuarioNode, identificar_usuario_node
from nodes.interrupcion_procesar_incidencia import InterrupcionIdentificarUsuarioNode, interrupcion_identificar_usuario
from workflow.incidencia_workflow import IncidenciaWorkflow
from models.state import GraphState
from utils.crear_estado_inicial import crear_estado_inicial

class TestInterrupcionesCentralizadas:
    """
    Suite de pruebas para validar:
    1. get_state_diff funciona correctamente
    2. Interrupciones centralizadas en interrupcion_identificar_usuario
    3. Router dirige correctamente según señales
    4. Estado se actualiza apropiadamente
    """
    
    def __init__(self):
        self.logger = logging.getLogger("TestInterrupciones")
        self.test_results = []
    
    async def run_all_tests(self):
        """Ejecutar todas las pruebas"""
        
        self.logger.info("🧪 === INICIANDO SUITE DE PRUEBAS ===")
        
        # Test 1: Función get_state_diff
        await self.test_get_state_diff()
        
        # Test 2: Señalización de necesidad de input
        await self.test_signal_need_input()
        
        # Test 3: Router centraliza interrupciones
        await self.test_router_centralizes_interruptions()
        
        # Test 4: Flujo completo de interrupción
        await self.test_complete_interruption_flow()
        
        # Test 5: Optimización de Command.update
        await self.test_command_optimization()
        
        # Mostrar resultados
        self.show_test_results()
    
    async def test_get_state_diff(self):
        """Test 1: Verificar que get_state_diff funciona correctamente"""
        
        self.logger.info("🧪 Test 1: get_state_diff")
        
        try:
            # Crear instancia de nodo para probar
            node = IdentificarUsuarioNode()
            
            # Estados de prueba
            old_state = {
                "messages": ["mensaje1"],
                "nombre": None,
                "email": None,
                "intentos": 0
            }
            
            new_state = {
                "messages": ["mensaje1", "mensaje2"],
                "nombre": "Juan Pérez", 
                "email": None,
                "intentos": 1,
                "nuevo_campo": "valor_nuevo"
            }
            
            # Calcular diferencias
            diff = node.get_state_diff(old_state, new_state)
            
            # Verificar que solo incluye cambios
            expected_diff = {
                "messages": ["mensaje1", "mensaje2"],
                "nombre": "Juan Pérez",
                "intentos": 1,
                "nuevo_campo": "valor_nuevo"
            }
            
            assert diff == expected_diff, f"Diff incorrecto: {diff} != {expected_diff}"
            
            self.test_results.append(("✅ get_state_diff", "PASSED", "Calcula diferencias correctamente"))
            self.logger.info("✅ Test 1 PASSED: get_state_diff funciona correctamente")
            
        except Exception as e:
            self.test_results.append(("❌ get_state_diff", "FAILED", str(e)))
            self.logger.error(f"❌ Test 1 FAILED: {e}")
    
    async def test_signal_need_input(self):
        """Test 2: Verificar señalización de necesidad de input"""
        
        self.logger.info("🧪 Test 2: signal_need_input")
        
        try:
            node = IdentificarUsuarioNode()
            
            # Estado de prueba
            test_state = {
                "messages": ["Hola"],
                "nombre": None,
                "email": None
            }
            
            # Señalar necesidad de input
            command = node.signal_need_input(
                state=test_state,
                request_message="Necesito tu nombre y email",
                context={"waiting_for": ["nombre", "email"]},
                resume_node="identificar_usuario"
            )
            
            # Verificar que la señal es correcta
            update = command.update
            
            assert update.get("_actor_decision") == "need_input", "No señala need_input"
            assert update.get("_next_actor") == "interrupcion_identificar_usuario", "No dirige a interrupcion_identificar_usuario"
            assert update.get("requires_user_input") == True, "No establece requires_user_input"
            assert update.get("_request_message") == "Necesito tu nombre y email", "Mensaje incorrecto"
            
            self.test_results.append(("✅ signal_need_input", "PASSED", "Señalización correcta"))
            self.logger.info("✅ Test 2 PASSED: signal_need_input funciona correctamente")
            
        except Exception as e:
            self.test_results.append(("❌ signal_need_input", "FAILED", str(e)))
            self.logger.error(f"❌ Test 2 FAILED: {e}")
    
    async def test_router_centralizes_interruptions(self):
        """Test 3: Verificar que el router centraliza interrupciones"""
        
        self.logger.info("🧪 Test 3: Router centraliza interrupciones")
        
        try:
            workflow = IncidenciaWorkflow()
            
            # Estados de prueba que deberían dirigir a interrupcion_identificar_usuario
            test_cases = [
                {
                    "name": "requires_user_input=True",
                    "state": {"requires_user_input": True},
                    "expected": "interrupcion_identificar_usuario"
                },
                {
                    "name": "_actor_decision=need_input", 
                    "state": {"_actor_decision": "need_input"},
                    "expected": "interrupcion_identificar_usuario"
                },
                {
                    "name": "_request_message existe",
                    "state": {"_request_message": "Necesito datos"},
                    "expected": "interrupcion_identificar_usuario"
                },
                {
                    "name": "awaiting_input=True",
                    "state": {"awaiting_input": True},
                    "expected": "interrupcion_identificar_usuario"
                }
            ]
            
            for case in test_cases:
                result = workflow._route_conversation(case["state"])
                assert result == case["expected"], f"{case['name']}: {result} != {case['expected']}"
                self.logger.debug(f"✓ {case['name']}: {result}")
            
            self.test_results.append(("✅ Router centraliza", "PASSED", "Todas las interrupciones van a interrupcion_identificar_usuario"))
            self.logger.info("✅ Test 3 PASSED: Router centraliza interrupciones correctamente")
            
        except Exception as e:
            self.test_results.append(("❌ Router centraliza", "FAILED", str(e)))
            self.logger.error(f"❌ Test 3 FAILED: {e}")
    
    async def test_complete_interruption_flow(self):
        """Test 4: Probar flujo completo de interrupción"""
        
        self.logger.info("🧪 Test 4: Flujo completo de interrupción")
        
        try:
            # Simular flujo completo
            # 1. identificar_usuario necesita input
            identificar_node = IdentificarUsuarioNode()
            
            initial_state = {
                "messages": ["Hola"],
                "nombre": None,
                "email": None,
                "intentos": 0
            }
            
            # Ejecutar identificar_usuario
            result1 = await identificar_node.execute(initial_state)
            
            # Verificar que señala necesidad de input
            assert result1.update.get("_actor_decision") == "need_input", "No señala need_input"
            assert result1.update.get("_next_actor") == "interrupcion_identificar_usuario", "No va a interrupcion_identificar_usuario"
            
            # 2. Simular que router dirige a interrupcion_identificar_usuario
            state_after_identificar = {**initial_state, **result1.update}
            
            # 3. Ejecutar interrupcion_identificar_usuario
            recopilar_node = InterrupcionIdentificarUsuarioNode()
            result2 = await recopilar_node.execute(state_after_identificar)
            
            # Verificar que establece interrupción
            assert result2.update.get("requires_user_input") == True, "No establece requires_user_input"
            assert "workflow_state" in result2.update, "No establece workflow_state"
            assert result2.update["workflow_state"].get("waiting_for_user") == True, "No establece waiting_for_user"
            
            # 4. Verificar que limpia flags temporales
            assert result2.update.get("_actor_decision") is None, "No limpia _actor_decision"
            assert result2.update.get("_request_message") is None, "No limpia _request_message"
            
            self.test_results.append(("✅ Flujo completo", "PASSED", "Identificar → Señal → Recopilar → Interrupción"))
            self.logger.info("✅ Test 4 PASSED: Flujo completo de interrupción funciona")
            
        except Exception as e:
            self.test_results.append(("❌ Flujo completo", "FAILED", str(e)))
            self.logger.error(f"❌ Test 4 FAILED: {e}")
    
    async def test_command_optimization(self):
        """Test 5: Verificar optimización de Command.update"""
        
        self.logger.info("🧪 Test 5: Optimización de Command.update")
        
        try:
            node = IdentificarUsuarioNode()
            
            # Estado grande
            large_state = {
                "messages": ["msg1", "msg2", "msg3"],
                "nombre": "Juan",
                "email": "juan@empresa.com", 
                "intentos": 2,
                "datos_usuario_completos": True,
                "historial": ["step1", "step2", "step3"],
                "configuracion": {"tema": "dark", "idioma": "es"},
                "metricas": {"tiempo": 120, "errores": 0},
                "campo_no_modificado": "valor_constante",
                "otro_campo_constante": [1, 2, 3]
            }
            
            # Solo modificar algunos campos
            small_updates = {
                "intentos": 3,  # Cambio
                "nuevo_campo": "nuevo_valor",  # Nuevo
                "configuracion": {"tema": "light", "idioma": "es"}  # Cambio
            }
            
            # Crear comando optimizado
            command = node.create_optimized_command(large_state, small_updates)
            
            # Verificar que solo incluye los cambios
            expected_keys = {"intentos", "nuevo_campo", "configuracion"}
            actual_keys = set(command.update.keys())
            
            assert actual_keys == expected_keys, f"Keys incorrectas: {actual_keys} != {expected_keys}"
            
            # Verificar que los valores son correctos
            assert command.update["intentos"] == 3, "Valor de intentos incorrecto"
            assert command.update["nuevo_campo"] == "nuevo_valor", "Nuevo campo incorrecto"
            
            # Verificar que no incluye campos no modificados
            assert "campo_no_modificado" not in command.update, "Incluye campo no modificado"
            assert "otro_campo_constante" not in command.update, "Incluye otro campo no modificado"
            
            self.test_results.append(("✅ Command optimización", "PASSED", f"Solo {len(command.update)} de {len(large_state)} campos"))
            self.logger.info(f"✅ Test 5 PASSED: Optimización reduce de {len(large_state)} a {len(command.update)} campos")
            
        except Exception as e:
            self.test_results.append(("❌ Command optimización", "FAILED", str(e)))
            self.logger.error(f"❌ Test 5 FAILED: {e}")
    
    def show_test_results(self):
        """Mostrar resumen de resultados de pruebas"""
        
        self.logger.info("📊 === RESUMEN DE PRUEBAS ===")
        
        passed = sum(1 for result in self.test_results if "PASSED" in result[1])
        total = len(self.test_results)
        
        print(f"\n{'='*60}")
        print(f"RESUMEN DE PRUEBAS: {passed}/{total} PASSED")
        print(f"{'='*60}")
        
        for test_name, status, details in self.test_results:
            print(f"{test_name:<25} {status:<8} {details}")
        
        print(f"{'='*60}")
        
        if passed == total:
            print("🎉 TODAS LAS PRUEBAS PASARON - Los cambios funcionan correctamente!")
        else:
            print(f"⚠️ {total - passed} pruebas fallaron - Revisar implementación")
        
        print(f"{'='*60}\n")
    
    async def test_integration_with_sample_conversation(self):
        """Test bonus: Simulación de conversación completa"""
        
        self.logger.info("🧪 Test Bonus: Conversación completa simulada")
        
        try:
            # Crear estado inicial
            estado = crear_estado_inicial()
            
            # Simular mensajes del usuario
            mensajes_usuario = [
                "Hola, necesito ayuda",
                "Mi nombre es Juan Pérez y mi email es juan@empresa.com",
                "Tengo problemas con mi laptop"
            ]
            
            for i, mensaje in enumerate(mensajes_usuario):
                self.logger.info(f"👤 Usuario dice: {mensaje}")
                
                # Agregar mensaje al estado
                from langchain_core.messages import HumanMessage
                estado["messages"].append(HumanMessage(content=mensaje))
                
                # Ejecutar identificar_usuario
                result = await identificar_usuario_node(estado)
                
                # Aplicar cambios al estado
                estado.update(result.update)
                
                self.logger.info(f"🤖 Estado después del mensaje {i+1}:")
                self.logger.info(f"   - Nombre: {estado.get('nombre')}")
                self.logger.info(f"   - Email: {estado.get('email')}")
                self.logger.info(f"   - Datos completos: {estado.get('datos_usuario_completos')}")
                self.logger.info(f"   - Próxima acción: {estado.get('_next_actor')}")
            
            self.test_results.append(("✅ Conversación simulada", "PASSED", "Flujo natural funciona"))
            self.logger.info("✅ Test Bonus PASSED: Conversación simulada funciona")
            
        except Exception as e:
            self.test_results.append(("❌ Conversación simulada", "FAILED", str(e)))
            self.logger.error(f"❌ Test Bonus FAILED: {e}")


async def main():
    """Función principal para ejecutar las pruebas"""
    
    print("🧪 Iniciando pruebas de interrupciones centralizadas...")
    print("=" * 60)
    
    test_suite = TestInterrupcionesCentralizadas()
    await test_suite.run_all_tests()
    
    # Test bonus
    await test_suite.test_integration_with_sample_conversation()
    
    print("\n🏁 Pruebas completadas.")


if __name__ == "__main__":
    asyncio.run(main())