# =====================================================
# scripts/test_azure_embeddings.py - Probar Azure OpenAI
# =====================================================
"""
Script para probar la configuración de Azure OpenAI
antes de vectorizar el manual.
"""

import asyncio
import os
from pathlib import Path

async def test_azure_embeddings():
    """Probar configuración Azure OpenAI"""
    
    print("🧪 PRUEBA DE AZURE OPENAI")
    print("=" * 40)
    
    # 1. Verificar variables de entorno
    print("1️⃣ Verificando configuración...")
    
    required_vars = [
        'LLM_AZURE_OPENAI_API_KEY',
        'LLM_AZURE_OPENAI_ENDPOINT', 
        'LLM_AZURE_API_VERSION',
        'LLM_AZURE_EMBEDDING_DEPLOYMENT'
    ]
    
    config = {}
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            config[var] = value.strip()
            # Ocultar API key en logs
            display_value = value[:8] + "..." if 'API_KEY' in var else value
            print(f"   ✅ {var}: {display_value}")
        else:
            missing_vars.append(var)
            print(f"   ❌ {var}: NO CONFIGURADA")
    
    if missing_vars:
        print(f"\n❌ Variables faltantes: {missing_vars}")
        print("💡 Verificar archivo .env")
        return False
    
    # 2. Probar conexión y embedding
    print("\n2️⃣ Probando conexión a Azure OpenAI...")
    
    try:
        from openai import AzureOpenAI
        
        # Crear cliente
        client = AzureOpenAI(
            api_key=config['LLM_AZURE_OPENAI_API_KEY'],
            azure_endpoint=config['LLM_AZURE_OPENAI_ENDPOINT'],
            api_version=config['LLM_AZURE_API_VERSION']
        )
        
        print("✅ Cliente Azure OpenAI creado")
        
        # Probar embedding con texto de prueba
        print("🔄 Generando embedding de prueba...")
        
        test_text = "Esta es una prueba de embedding para la balanza DIBAL Mistral"
        
        response = client.embeddings.create(
            model=config['LLM_AZURE_EMBEDDING_DEPLOYMENT'],
            input=test_text
        )
        
        embedding = response.data[0].embedding
        embedding_size = len(embedding)
        
        print(f"✅ Embedding generado exitosamente")
        print(f"📊 Tamaño del vector: {embedding_size} dimensiones")
        print(f"📋 Primeros 5 valores: {embedding[:5]}")
        
        # Verificar que el tamaño es correcto
        expected_size = 1536  # Tamaño estándar para embeddings Azure OpenAI
        if embedding_size == expected_size:
            print(f"✅ Tamaño correcto ({expected_size} dimensiones)")
        else:
            print(f"⚠️ Tamaño inesperado: {embedding_size} (esperado: {expected_size})")
        
        print("\n🎉 Configuración Azure OpenAI funciona correctamente")
        print("\n🎯 PRÓXIMOS PASOS:")
        print("   1. Ejecutar: python scripts/check_current_status.py")
        print("   2. Después: python -m scripts.setup_db")
        print("   3. Finalmente: python -m scripts.vectorize_manual")
        
        return True
        
    except ImportError:
        print("❌ Librería openai no instalada")
        print("💡 Instalar: pip install openai")
        return False
        
    except Exception as e:
        print(f"❌ Error probando Azure OpenAI: {e}")
        print("\n🔧 POSIBLES SOLUCIONES:")
        print("   1. Verificar que el API key es correcto")
        print("   2. Verificar que el endpoint es correcto")
        print("   3. Verificar que el deployment existe en Azure")
        print("   4. Verificar permisos en Azure OpenAI")
        return False

async def main():
    """Entry point"""
    # Cargar variables de entorno desde .env (buscar en directorio raíz)
    current_dir = Path(__file__).parent
    root_dir = current_dir.parent.parent  # Subir dos niveles: scripts -> database -> raíz
    env_file = root_dir / ".env"
    
    if env_file.exists():
        print(f"📋 Cargando configuración desde {env_file}...")
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"\'')
    else:
        print(f"⚠️ Archivo .env no encontrado en {env_file}")
        print("💡 Asegúrate de que .env esté en la raíz del proyecto")
        return
    
    success = await test_azure_embeddings()
    
    if not success:
        print("\n❌ La configuración de Azure OpenAI tiene problemas")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())