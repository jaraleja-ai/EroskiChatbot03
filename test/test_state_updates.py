# =====================================================
# test_state_updates.py - Script para probar actualizaciones de estado
# =====================================================
"""
Script simple para verificar que las actualizaciones de Command se aplican correctamente
"""

import asyncio
import logging
from typing import Dict, Any
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StateTest")

async def test_simple_node(state: Dict[str, Any]) -> Command:
    """Nodo de prueba simple que actualiza el estado"""
    
    logger.info(f"🔍 test_simple_node recibió estado:")
    logger.info(f"   intentos: {state.get('intentos', 'NO_DEFINIDO')}")
    logger.info(f"   test_field: {state.get('test_field', 'NO_DEFINIDO')}")
    
    # Incrementar intentos
    current_intentos = state.get('intentos', 0)
    new_intentos = current_intentos + 1
    
    # Crear actualización simple
    updates = {
        'intentos': new_intentos,
        'test_field': f'updated_at_attempt_{new_intentos}',
        'last_update': 'test_simple_node'
    }
    
    logger.info(f"🔧 Creando Command.update: {updates}")
    
    command = Command(update=updates)
    
    logger.info(f"✅ Command creado con {len(command.update)} actualizaciones")
    
    return command

async def test_state_updates():
    """Test para verificar que las actualizaciones funcionan"""
    
    logger.info("🧪 === INICIANDO TEST DE ACTUALIZACIONES DE ESTADO ===")
    
    # Estado inicial
    initial_state = {
        'messages': [HumanMessage(content="test message")],
        'intentos': 0,
        'test_field': 'initial_value'
    }
    
    logger.info(f"📋 Estado inicial: {initial_state}")
    
    # Simular primera ejecución
    logger.info("🔄 Ejecutando nodo (primera vez)...")
    result1 = await test_simple_node(initial_state)
    
    # Simular aplicación de updates (esto lo haría LangGraph)
    updated_state = {**initial_state, **result1.update}
    logger.info(f"📋 Estado después de primera actualización: {updated_state}")
    
    # Simular segunda ejecución
    logger.info("🔄 Ejecutando nodo (segunda vez)...")
    result2 = await test_simple_node(updated_state)
    
    # Aplicar segunda actualización
    final_state = {**updated_state, **result2.update}
    logger.info(f"📋 Estado final: {final_state}")
    
    # Verificar que los cambios se aplicaron
    if final_state['intentos'] == 2:
        logger.info("✅ TEST PASSED: Los intentos se incrementaron correctamente")
    else:
        logger.error(f"❌ TEST FAILED: intentos = {final_state['intentos']}, esperado = 2")
    
    if final_state['test_field'] == 'updated_at_attempt_2':
        logger.info("✅ TEST PASSED: test_field se actualizó correctamente")
    else:
        logger.error(f"❌ TEST FAILED: test_field = {final_state['test_field']}")

async def test_langgraph_simple():
    """Test usando LangGraph real para verificar comportamiento"""
    
    logger.info("🧪 === TEST CON LANGGRAPH REAL ===")
    
    try:
        from langgraph.graph import StateGraph, START, END
        from models.state import GraphState
        
        # Crear grafo simple
        graph = StateGraph(GraphState)
        graph.add_node("test_node", test_simple_node)
        graph.add_edge(START, "test_node")
        graph.add_edge("test_node", END)
        
        # Compilar
        app = graph.compile()
        
        # Estado inicial
        initial_state = GraphState(
            messages=[HumanMessage(content="test")],
            intentos=0
        )
        
        logger.info(f"📋 Estado inicial: intentos={initial_state.get('intentos', 'NO_DEFINIDO')}")
        
        # Ejecutar
        result = app.invoke(initial_state)
        
        logger.info(f"📋 Estado final: intentos={result.get('intentos', 'NO_DEFINIDO')}")
        logger.info(f"📋 Todas las claves finales: {list(result.keys())}")
        
        # Verificar resultado
        if result.get('intentos') == 1:
            logger.info("✅ LANGGRAPH TEST PASSED: Estado se actualizó correctamente")
        else:
            logger.error(f"❌ LANGGRAPH TEST FAILED: intentos = {result.get('intentos')}")
            
    except Exception as e:
        logger.error(f"❌ Error en test de LangGraph: {e}")
        import traceback
        logger.error(traceback.format_exc())

async def main():
    """Ejecutar todos los tests"""
    
    await test_state_updates()
    print("\n" + "="*50 + "\n")
    await test_langgraph_simple()

if __name__ == "__main__":
    asyncio.run(main())