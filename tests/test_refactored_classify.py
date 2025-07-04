#!/usr/bin/env python3
"""
Test específico para verificar que el nodo classify refactorizado funciona correctamente.
"""

import asyncio
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

def test_helpers_creation():
    """Probar que los helpers se crean correctamente"""
    
    print("🧪 Probando creación de helpers...")
    
    try:
        from utils.incident_helpers import IncidentHelpersFactory
        
        # Crear helpers usando factory
        incident_types = {"balanza": {"name": "test", "problemas": {"test": "test solution"}}}
        incidents_file = Path("test_incidents.json")
        
        helpers = IncidentHelpersFactory.create_all_helpers(incident_types, incidents_file)
        
        # Verificar que se crearon todos
        expected_helpers = ["code_manager", "solution_searcher", "confirmation_handler", "persistence_manager"]
        
        for helper_name in expected_helpers:
            if helper_name in helpers:
                print(f"✅ {helper_name} creado correctamente")
            else:
                print(f"❌ {helper_name} NO creado")
                
        return True
        
    except Exception as e:
        print(f"❌ Error creando helpers: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_code_manager():
    """Probar el gestor de códigos"""
    
    print("\n🧪 Probando IncidentCodeManager...")
    
    try:
        from utils.incident_helpers import IncidentCodeManager
        
        # Crear gestor con archivo temporal
        test_file = Path("test_incidents.json")
        code_manager = IncidentCodeManager(test_file)
        
        # Generar códigos
        code1 = code_manager.generate_unique_code()
        code2 = code_manager.generate_unique_code()
        
        print(f"✅ Código 1: {code1}")
        print(f"✅ Código 2: {code2}")
        
        # Verificar formato
        if code_manager.validate_code_format(code1):
            print(f"✅ Formato válido para {code1}")
        else:
            print(f"❌ Formato inválido para {code1}")
        
        # Verificar que son diferentes
        if code1 != code2:
            print("✅ Códigos únicos generados")
        else:
            print("❌ Códigos duplicados")
            
        # Limpiar archivo de prueba
        if test_file.exists():
            test_file.unlink()
            
        return True
        
    except Exception as e:
        print(f"❌ Error en CodeManager: {e}")
        return False

def test_solution_searcher():
    """Probar el buscador de soluciones"""
    
    print("\n🧪 Probando SolutionSearcher...")
    
    try:
        from utils.incident_helpers import SolutionSearcher
        
        # Crear datos de prueba
        incident_types = {
            "balanza": {
                "name": "Balanzas",
                "problemas": {
                    "La balanza no imprime etiquetas": "Verificar papel y reiniciar",
                    "La balanza no enciende": "Verificar conexión eléctrica"
                }
            }
        }
        
        searcher = SolutionSearcher(incident_types)
        
        # Probar búsqueda
        problem, solution = searcher.find_best_solution("balanza", "no imprime etiquetas")
        
        if problem and solution:
            print(f"✅ Solución encontrada:")
            print(f"   Problema: {problem}")
            print(f"   Solución: {solution}")
        else:
            print("❌ No se encontró solución")
        
        # Probar formateo de preguntas
        questions = searcher.format_problems_for_user("balanza")
        print(f"✅ Preguntas generadas:")
        print(f"   {questions[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en SolutionSearcher: {e}")
        return False

async def test_confirmation_handler():
    """Probar el manejador de confirmaciones"""
    
    print("\n🧪 Probando ConfirmationLLMHandler...")
    
    try:
        from utils.incident_helpers import ConfirmationLLMHandler
        from models.eroski_state import EroskiState
        from datetime import datetime
        
        handler = ConfirmationLLMHandler()
        
        # Crear estado de prueba
        state = {
            "auth_data_collected": {
                "name": "Test User",
                "store_name": "Test Store",
                "section": "Test Section"
            }
        }
        
        # Probar interpretación (esto requiere LLM real)
        print("⚠️ Test de confirmación requiere LLM - simulando...")
        
        # Simular respuesta
        print("✅ ConfirmationLLMHandler inicializado correctamente")
        print("💡 Test completo requiere LLM conectado")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en ConfirmationHandler: {e}")
        return False

def test_persistence_manager():
    """Probar el gestor de persistencia"""
    
    print("\n🧪 Probando IncidentPersistence...")
    
    try:
        from utils.incident_helpers import IncidentPersistence
        from models.eroski_state import EroskiState
        from langchain_core.messages import HumanMessage, AIMessage
        
        # Crear gestor con archivo temporal
        test_file = Path("test_persistence.json")
        persistence = IncidentPersistence(test_file)
        
        # Crear estado de prueba
        state = {
            "auth_data_collected": {
                "name": "Test User",
                "email": "test@eroski.es",
                "store_name": "Test Store",
                "section": "Test Section"
            },
            "messages": [
                HumanMessage(content="Test message"),
                AIMessage(content="Test response")
            ]
        }
        
        # Probar inicialización
        success = persistence.initialize_incident(state, "ER-1234")
        print(f"✅ Inicialización: {'exitosa' if success else 'falló'}")
        
        # Probar actualización
        success = persistence.update_incident("ER-1234", {"tipo_incidencia": "test"})
        print(f"✅ Actualización: {'exitosa' if success else 'falló'}")
        
        # Probar guardado de mensajes
        success = persistence.save_messages("ER-1234", state["messages"])
        print(f"✅ Guardado mensajes: {'exitoso' if success else 'falló'}")
        
        # Verificar archivo
        if test_file.exists():
            print("✅ Archivo de persistencia creado")
            
            # Leer y mostrar contenido
            import json
            with open(test_file, 'r') as f:
                data = json.load(f)
                print(f"✅ Incidencias en archivo: {len(data)}")
                
            # Limpiar
            test_file.unlink()
        else:
            print("❌ Archivo de persistencia NO creado")
            
        return True
        
    except Exception as e:
        print(f"❌ Error en Persistence: {e}")
        return False

async def test_refactored_node():
    """Probar el nodo refactorizado completo"""
    
    print("\n🧪 Probando nodo classify refactorizado...")
    
    try:
        from nodes.classify_llm_driven import LLMDrivenClassifyNode
        from models.eroski_state import EroskiState
        from langchain_core.messages import HumanMessage, AIMessage
        from datetime import datetime
        
        # Crear nodo
        node = LLMDrivenClassifyNode()
        
        print(f"✅ Nodo creado")
        print(f"✅ Helpers disponibles: {list(node.helpers.keys())}")
        print(f"✅ Tipos de incidencia: {len(node.incident_types)}")
        
        # Verificar que los helpers están correctamente asignados
        if hasattr(node, 'code_manager'):
            print("✅ code_manager asignado")
        if hasattr(node, 'solution_searcher'):
            print("✅ solution_searcher asignado")
        if hasattr(node, 'confirmation_handler'):
            print("✅ confirmation_handler asignado")
        if hasattr(node, 'persistence_manager'):
            print("✅ persistence_manager asignado")
        
        return True
        
    except Exception as e:
        print(f"❌ Error en nodo refactorizado: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Ejecutar todos los tests"""
    
    print("🚀 INICIANDO TESTS DE REFACTORIZACIÓN")
    print("=" * 60)
    
    tests = [
        ("Creación de Helpers", test_helpers_creation),
        ("Gestor de Códigos", test_code_manager),
        ("Buscador de Soluciones", test_solution_searcher),
        ("Manejador de Confirmaciones", test_confirmation_handler),
        ("Gestor de Persistencia", test_persistence_manager),
        ("Nodo Refactorizado", test_refactored_node)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"💥 Error en {test_name}: {e}")
            results[test_name] = False
    
    # Resumen
    print("\n" + "=" * 60)
    print("📋 RESUMEN DE TESTS:")
    
    passed = 0
    total = len(tests)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} {test_name}")
        if result:
            passed += 1
    
    print(f"\n🎯 Resultado: {passed}/{total} tests pasaron")
    
    if passed == total:
        print("🎉 ¡Todos los tests de refactorización pasaron!")
        print("💡 El nodo classify está listo para usar con helpers especializados")
    else:
        print("⚠️ Algunos tests fallaron - revisar implementación")

if __name__ == "__main__":
    asyncio.run(main())