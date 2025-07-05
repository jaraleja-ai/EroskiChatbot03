# =====================================================
# database/scripts/verify_pgvector.py - Verificar instalación pgvector
# =====================================================
"""
Script para verificar que pgvector está instalado correctamente.
"""

import asyncio
import asyncpg
import os
from pathlib import Path

async def verify_pgvector():
    """Verificar instalación de pgvector"""
    
    # Cargar variables de entorno
    current_dir = Path(__file__).parent
    root_dir = current_dir.parent.parent
    env_file = root_dir / ".env"
    
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"\'')
    
    # Configuración de BD
    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "database": os.getenv("DB_NAME", "chatbot_db"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "")
    }
    
    connection_string = (f"postgresql://{db_config['user']}:{db_config['password']}"
                        f"@{db_config['host']}:{db_config['port']}/{db_config['database']}")
    
    print("🔍 VERIFICADOR DE PGVECTOR")
    print("=" * 40)
    
    try:
        conn = await asyncpg.connect(connection_string)
        
        # 1. Verificar si la extensión está disponible
        print("\n1️⃣ Verificando disponibilidad de pgvector...")
        
        available_extensions = await conn.fetch("""
            SELECT name, default_version 
            FROM pg_available_extensions 
            WHERE name = 'vector'
        """)
        
        if available_extensions:
            ext = available_extensions[0]
            print(f"   ✅ pgvector disponible - versión {ext['default_version']}")
        else:
            print("   ❌ pgvector NO está disponible")
            print("   💡 Verificar que los archivos estén copiados correctamente")
            await conn.close()
            return False
        
        # 2. Intentar crear la extensión
        print("\n2️⃣ Intentando crear extensión...")
        
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            print("   ✅ Extensión vector creada/verificada")
        except Exception as e:
            print(f"   ❌ Error creando extensión: {e}")
            await conn.close()
            return False
        
        # 3. Verificar que la extensión está instalada
        print("\n3️⃣ Verificando extensión instalada...")
        
        installed_extensions = await conn.fetch("""
            SELECT extname, extversion 
            FROM pg_extension 
            WHERE extname = 'vector'
        """)
        
        if installed_extensions:
            ext = installed_extensions[0]
            print(f"   ✅ pgvector instalado - versión {ext['extversion']}")
        else:
            print("   ❌ pgvector NO está instalado")
            await conn.close()
            return False
        
        # 4. Probar funcionalidad básica
        print("\n4️⃣ Probando funcionalidad básica...")
        
        try:
            # Crear tabla de prueba con columna vector
            await conn.execute("""
                CREATE TEMP TABLE test_vectors (
                    id SERIAL PRIMARY KEY,
                    embedding vector(3)
                );
            """)
            print("   ✅ Creación de tabla con vector: OK")
            
            # Insertar vector de prueba
            await conn.execute("""
                INSERT INTO test_vectors (embedding) 
                VALUES ('[1, 2, 3]');
            """)
            print("   ✅ Inserción de vector: OK")
            
            # Buscar por similitud
            result = await conn.fetchval("""
                SELECT embedding <-> '[1, 2, 4]' as distance
                FROM test_vectors 
                ORDER BY distance 
                LIMIT 1;
            """)
            print(f"   ✅ Búsqueda por similitud: OK (distancia = {result:.3f})")
            
        except Exception as e:
            print(f"   ❌ Error en prueba de funcionalidad: {e}")
            await conn.close()
            return False
        
        # 5. Verificar operadores disponibles
        print("\n5️⃣ Verificando operadores de distancia...")
        
        operators = await conn.fetch("""
            SELECT oprname, oprleft::regtype, oprright::regtype
            FROM pg_operator 
            WHERE oprname IN ('<->', '<#>', '<=>')
            AND oprleft::regtype::text = 'vector'
            ORDER BY oprname;
        """)
        
        if operators:
            print("   ✅ Operadores de distancia disponibles:")
            for op in operators:
                print(f"      🔹 {op['oprname']} para {op['oprleft']} {op['oprname']} {op['oprright']}")
        else:
            print("   ⚠️ No se encontraron operadores de distancia")
        
        # 6. Información de versión de PostgreSQL
        print("\n6️⃣ Información del sistema...")
        
        pg_version = await conn.fetchval("SELECT version();")
        print(f"   📊 PostgreSQL: {pg_version.split(',')[0]}")
        
        vector_version = await conn.fetchval("""
            SELECT extversion FROM pg_extension WHERE extname = 'vector'
        """)
        print(f"   📊 pgvector: {vector_version}")
        
        await conn.close()
        
        print("\n" + "=" * 40)
        print("🎉 ¡PGVECTOR INSTALADO CORRECTAMENTE!")
        print("=" * 40)
        print("\n🎯 PRÓXIMOS PASOS:")
        print("   1. 🔄 Ejecutar: python database/scripts/setup_db_compatible.py")
        print("   2. 📖 Vectorizar: python database/scripts/vectorize_manual.py")
        print("   3. 🧪 Probar: python database/scripts/test_vector_search.py")
        
        return True
        
    except Exception as e:
        print(f"❌ Error conectando a la base de datos: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(verify_pgvector())
    if not success:
        print("\n💡 SOLUCIONES POSIBLES:")
        print("   1. Verificar que PostgreSQL esté ejecutándose")
        print("   2. Verificar que los archivos pgvector estén en las carpetas correctas")
        print("   3. Reiniciar PostgreSQL después de copiar archivos")
        print("   4. Verificar permisos de archivos copiados")