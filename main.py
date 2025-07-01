# =====================================================
# main.py - Entry point principal actualizado
# =====================================================
"""
Entry point principal de la aplicación de chatbot con LangGraph.

Este archivo centraliza el inicio de la aplicación y permite ejecutar
diferentes interfaces según la configuración, con la nueva arquitectura
completamente integrada.
"""

import asyncio
import os
import sys
from pathlib import Path
import subprocess

# Agregar el directorio raíz al path para imports
ROOT_DIR = Path(__file__).parent
sys.path.insert(0, str(ROOT_DIR))

from config.settings import get_settings, validate_environment
from config.logging_config import setup_logging

async def main():
    """
    Entry point principal de la aplicación.
    
    Configura el entorno, inicializa logging y ejecuta la interfaz seleccionada.
    """
    try:
        # Configurar logging antes que nada
        setup_logging()
        
        # Obtener logger
        import logging
        logger = logging.getLogger("Main")
        
        logger.info("🚀 Iniciando Chatbot de Incidencias con LangGraph")
        
        # Cargar y validar configuración
        settings = get_settings()
        logger.info(f"📋 Configuración cargada - Debug: {settings.app.debug_mode}")
        
        # Validar entorno
        if not validate_environment():
            logger.error("❌ Configuración del entorno inválida")
            sys.exit(1)
        
        # Determinar interfaz a ejecutar
        interface = os.getenv("INTERFACE", "chainlit").lower()
        
        logger.info(f"🔧 Iniciando interfaz: {interface}")
        
        if interface == "chainlit":
            await run_chainlit_interface(settings, logger)
        elif interface == "fastapi":
            await run_fastapi_interface(settings, logger)
        elif interface == "test":
            await run_test_mode(settings, logger)
        elif interface == "setup":
            await run_setup_mode(settings, logger)
        else:
            logger.error(f"❌ Interfaz no soportada: {interface}")
            print_usage()
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Aplicación detenida por el usuario")
    except Exception as e:
        print(f"❌ Error crítico al iniciar aplicación: {e}")
        sys.exit(1)

async def run_chainlit_interface(settings, logger):
    """Ejecutar interfaz de Chainlit"""
    logger.info("🔗 Iniciando aplicación Chainlit...")
    
    try:
        # Verificar que chainlit esté instalado
        try:
            import chainlit
        except ImportError:
            logger.error("❌ Chainlit no está instalado. Ejecuta: pip install chainlit")
            return
        
        # 🔥 SOLUCIÓN: No usar variables de entorno que no funcionan
        # Chainlit ignora CHAINLIT_HOST y CHAINLIT_PORT
        
        # Configurar ruta del archivo de la aplicación
        app_file = ROOT_DIR / "interfaces" / "chainlit_app.py"
        
        if not app_file.exists():
            logger.error(f"❌ Archivo de aplicación no encontrado: {app_file}")
            return
        
        # 🔥 IMPORTANTE: Usar localhost explícitamente en el comando
        host = "localhost"  # Forzar localhost independientemente de la config
        port = settings.chainlit.port
        
        logger.info(f"✅ Iniciando Chainlit en {host}:{port}")
        logger.info(f"🌐 Abre tu navegador en: http://localhost:{port}")
        
        # 🔥 SOLUCIÓN: Comando con parámetros explícitos
        cmd = [
            sys.executable, "-m", "chainlit", "run", 
            str(app_file),
            "--host", host,  # 🔥 Forzar localhost aquí
            "--port", str(port)
        ]
        
        if settings.chainlit.debug:
            cmd.append("--debug")
        
        # 🔥 DEBUG: Mostrar comando exacto que se ejecuta
        logger.info(f"🔧 Ejecutando comando: {' '.join(cmd)}")
        
        # Ejecutar comando
        process = subprocess.Popen(cmd)
        
        try:
            # Esperar a que termine el proceso
            process.wait()
        except KeyboardInterrupt:
            logger.info("🛑 Deteniendo Chainlit...")
            process.terminate()
            process.wait()
            
    except Exception as e:
        logger.error(f"❌ Error en interfaz Chainlit: {e}")
        raise

async def run_fastapi_interface(settings, logger):
    """Ejecutar interfaz de FastAPI (futuro)"""
    logger.info("🚀 Iniciando aplicación FastAPI...")
    
    try:
        # TODO: Implementar interfaz FastAPI
        logger.warning("⚠️ Interfaz FastAPI aún no implementada")
        
        # Placeholder para futura implementación
        from interfaces.fastapi_app import create_fastapi_app
        
        app = create_fastapi_app()
        
        import uvicorn
        
        uvicorn.run(
            app,
            host=settings.chainlit.host,
            port=settings.chainlit.port + 1,  # Puerto diferente
            log_level=settings.logging.level.lower()
        )
        
    except ImportError:
        logger.error("❌ FastAPI no está implementado aún")
        logger.info("💡 Usa 'chainlit' como interfaz por ahora")
    except Exception as e:
        logger.error(f"❌ Error en interfaz FastAPI: {e}")
        raise

async def run_test_mode(settings, logger):
    """Ejecutar en modo de test"""
    logger.info("🧪 Iniciando modo de test...")
    
    try:
        # Configurar para testing
        logger.info("⚙️ Configurando entorno de test...")
        
        # Ejecutar tests básicos
        await run_comprehensive_tests(logger)
        
        logger.info("✅ Tests completados exitosamente")
        
    except Exception as e:
        logger.error(f"❌ Error en modo test: {e}")
        raise

async def run_setup_mode(settings, logger):
    """Ejecutar modo de setup inicial"""
    logger.info("🔧 Iniciando modo de setup...")
    
    try:
        from scripts.setup_db import setup_database
        from scripts.verify_config import verify_configuration
        
        # 1. Verificar configuración
        logger.info("1️⃣ Verificando configuración...")
        await verify_configuration()
        
        # 2. Setup de base de datos
        logger.info("2️⃣ Configurando base de datos...")
        await setup_database()
        
        # 3. Verificar workflows
        logger.info("3️⃣ Verificando workflows...")
        await verify_workflows()
        
        logger.info("✅ Setup completado exitosamente")
        logger.info("🚀 Puedes ejecutar la aplicación con: python main.py")
        
    except Exception as e:
        logger.error(f"❌ Error en setup: {e}")
        raise

async def run_comprehensive_tests(logger):
    """Ejecutar tests comprensivos del sistema"""
    
    logger.info("🧪 Ejecutando tests del sistema...")
    
    # Test 1: Configuración
    logger.info("📋 Test 1: Configuración...")
    settings = get_settings()
    assert settings is not None
    logger.info("✅ Configuración OK")
    
    # Test 2: Importaciones críticas
    logger.info("📦 Test 2: Importaciones...")
    try:
        from nodes.base_node import BaseNode
        from workflows.workflow_manager import get_workflow_manager
        from graph import build_default_graph
        from models.state import GraphState
        logger.info("✅ Importaciones OK")
    except ImportError as e:
        logger.error(f"❌ Error en importaciones: {e}")
        raise
    
    # Test 3: Workflows
    logger.info("🔧 Test 3: Workflows...")
    try:
        workflow_manager = get_workflow_manager()
        workflows = workflow_manager.list_workflows()
        assert len(workflows) > 0
        logger.info(f"✅ Workflows OK: {workflows}")
    except Exception as e:
        logger.error(f"❌ Error en workflows: {e}")
        raise
    
    # Test 4: Grafo principal
    logger.info("🕸️ Test 4: Construcción de grafo...")
    try:
        graph = build_default_graph()
        assert graph is not None
        logger.info("✅ Grafo OK")
    except Exception as e:
        logger.error(f"❌ Error en grafo: {e}")
        raise
    
    # Test 5: Estado inicial
    logger.info("📊 Test 5: Estado inicial...")
    try:
        from utils.crear_estado_inicial import crear_estado_inicial
        estado = crear_estado_inicial()
        assert estado is not None
        assert "messages" in estado
        logger.info("✅ Estado inicial OK")
    except Exception as e:
        logger.error(f"❌ Error en estado inicial: {e}")
        raise
    
    logger.info("🎉 Todos los tests pasaron exitosamente")

async def verify_workflows():
    """Verificar que todos los workflows funcionen correctamente"""
    from workflows.workflow_manager import get_workflow_manager
    from graph import get_graph_metrics
    
    workflow_manager = get_workflow_manager()
    
    # Listar workflows
    workflows = workflow_manager.list_workflows()
    print(f"📋 Workflows disponibles: {workflows}")
    
    # Compilar cada workflow
    for workflow_name in workflows:
        try:
            workflow = workflow_manager.get_workflow(workflow_name)
            compiled = workflow.compile()
            print(f"✅ {workflow_name}: Compilado correctamente")
        except Exception as e:
            print(f"❌ {workflow_name}: Error - {e}")
            raise
    
    # Obtener métricas
    metrics = get_graph_metrics()
    print(f"📊 Métricas del sistema: {metrics['total_workflows']} workflows")

def print_usage():
    """Mostrar información de uso"""
    print("""
🤖 Chatbot de Incidencias con LangGraph

Uso:
    python main.py                    # Ejecutar con Chainlit (por defecto)
    INTERFACE=chainlit python main.py # Ejecutar con Chainlit
    INTERFACE=fastapi python main.py  # Ejecutar con FastAPI (futuro)
    INTERFACE=test python main.py     # Ejecutar tests
    INTERFACE=setup python main.py    # Ejecutar setup inicial

Variables de entorno importantes:
    INTERFACE      # Tipo de interfaz (chainlit, fastapi, test, setup)
    APP_DEBUG_MODE # Habilitar modo debug (true/false)
    LLM_OPENAI_API_KEY # API key de OpenAI
    DB_HOST        # Host de la base de datos

Ejemplos:
    APP_DEBUG_MODE=true python main.py
    INTERFACE=test APP_DEBUG_MODE=true python main.py
    
Para más información, revisa README.md
""")

def setup_development_environment():
    """Configurar entorno de desarrollo"""
    
    # Crear directorios necesarios si no existen
    directories = [
        "logs",
        "data", 
        "temp",
        "tests/__pycache__",
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Crear archivo .env si no existe
    env_template_path = Path(".env.template")
    env_path = Path(".env")
    
    if env_template_path.exists() and not env_path.exists():
        import shutil
        shutil.copy(env_template_path, env_path)
        print("📄 Archivo .env creado desde template")
        print("⚠️ Recuerda configurar las variables de entorno necesarias")
        print("🔑 Especialmente: LLM_OPENAI_API_KEY y configuración de BD")

if __name__ == "__main__":
    # Configurar entorno de desarrollo
    setup_development_environment()
    
    # Mostrar información si se ejecuta sin argumentos en modo interactivo
    if len(sys.argv) == 1 and sys.stdin.isatty():
        print("🚀 Iniciando Chatbot de Incidencias...")
        print("💡 Usa --help para ver todas las opciones disponibles")
        print()
    
    # Manejar argumentos de línea de comandos
    if len(sys.argv) > 1:
        if sys.argv[1] in ["--help", "-h"]:
            print_usage()
            sys.exit(0)
        elif sys.argv[1] == "--version":
            print("Chatbot de Incidencias v0.1.0")
            sys.exit(0)
    
    # Ejecutar aplicación principal
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Aplicación detenida por el usuario")
    except Exception as e:
        print(f"💥 Error fatal: {e}")
        sys.exit(1)