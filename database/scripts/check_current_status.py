# =====================================================
# scripts/check_current_status.py - Verificar estado actual
# =====================================================
"""
Script para verificar el estado actual de la base de datos
antes de aplicar los cambios de RAG.
"""

import asyncio
import asyncpg
import os
import json
from pathlib import Path
from typing import Dict, List, Any

async def check_current_status():
    """Verificar estado actual completo"""
    
    # Configuración desde variables de entorno
    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
        "database": os.getenv("DB_NAME", "chatbot_db")
    }
    
    print("🔍 VERIFICACIÓN DE ESTADO ACTUAL")
    print("=" * 50)
    print(f"📍 Host: {db_config['host']}")
    print(f"📍 Puerto: {db_config['port']}")
    print(f"📍 Usuario: {db_config['user']}")
    print(f"📍 Base de datos: {db_config['database']}")
    print()
    
    try:
        # 1. Verificar conexión
        print("1️⃣ Verificando conexión...")
        conn = await asyncpg.connect(
            host=db_config["host"],
            port=db_config["port"],
            user=db_config["user"],
            password=db_config["password"],
            database=db_config["database"]
        )
        
        print("✅ Conexión exitosa")
        
        # 2. Listar todas las tablas
        print("\n2️⃣ Verificando tablas existentes...")
        tables = await conn.fetch("""
            SELECT table_name, table_type
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        table_names = [t['table_name'] for t in tables]
        print(f"📊 Tablas encontradas ({len(table_names)}):")
        for table in tables:
            print(f"   📄 {table['table_name']} ({table['table_type']})")
        
        # 3. Verificar estructura de tabla usuarios
        if 'usuarios' in table_names:
            print("\n3️⃣ Analizando estructura de tabla 'usuarios'...")
            await analyze_table_structure(conn, 'usuarios')
            
            # Contar usuarios
            user_count = await conn.fetchval("SELECT COUNT(*) FROM usuarios")
            print(f"👥 Total usuarios: {user_count}")
            
            if user_count > 0:
                # Mostrar algunos usuarios
                sample_users = await conn.fetch("""
                    SELECT nombre, apellido, email, numero_empleado, rol, departamento
                    FROM usuarios 
                    LIMIT 3
                """)
                print("📋 Usuarios ejemplo:")
                for user in sample_users:
                    print(f"   • {user['nombre']} {user['apellido']} ({user['email']}) - {user['rol']}")
        else:
            print("\n⚠️ Tabla 'usuarios' NO existe")
        
        # 4. Verificar estructura de tabla incidencias
        if 'incidencias' in table_names:
            print("\n4️⃣ Analizando estructura de tabla 'incidencias'...")
            await analyze_table_structure(conn, 'incidencias')
            
            # Contar incidencias
            inc_count = await conn.fetchval("SELECT COUNT(*) FROM incidencias")
            print(f"🎫 Total incidencias: {inc_count}")
            
            if inc_count > 0:
                # Mostrar algunas incidencias
                sample_incidents = await conn.fetch("""
                    SELECT numero_ticket, tipo, estado, descripcion
                    FROM incidencias 
                    LIMIT 3
                """)
                print("📋 Incidencias ejemplo:")
                for inc in sample_incidents:
                    desc = inc['descripcion'][:50] + "..." if len(inc['descripcion']) > 50 else inc['descripcion']
                    print(f"   • {inc['numero_ticket']} ({inc['tipo']}) - {inc['estado']}: {desc}")
        else:
            print("\n⚠️ Tabla 'incidencias' NO existe")
        
        # 5. Verificar extensiones PostgreSQL
        print("\n5️⃣ Verificando extensiones PostgreSQL...")
        extensions = await conn.fetch("""
            SELECT extname, extversion 
            FROM pg_extension 
            WHERE extname IN ('pg_trgm', 'unaccent', 'vector')
        """)
        
        ext_names = [ext['extname'] for ext in extensions]
        print(f"🔧 Extensiones instaladas: {ext_names}")
        
        for ext in extensions:
            print(f"   ✅ {ext['extname']} v{ext['extversion']}")
        
        # Verificar extensiones que faltan
        required_extensions = ['pg_trgm', 'unaccent', 'vector']
        missing_extensions = [ext for ext in required_extensions if ext not in ext_names]
        
        if missing_extensions:
            print(f"⚠️ Extensiones faltantes: {missing_extensions}")
            if 'vector' in missing_extensions:
                print("💡 pgvector se instalará automáticamente con setup_db")
        
        # 6. Verificar tablas RAG (si existen)
        rag_tables = ['knowledge_base', 'tipologias_incidencias', 'rag_queries']
        existing_rag_tables = [table for table in rag_tables if table in table_names]
        
        if existing_rag_tables:
            print(f"\n6️⃣ Tablas RAG existentes: {existing_rag_tables}")
            for rag_table in existing_rag_tables:
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {rag_table}")
                print(f"   📊 {rag_table}: {count} registros")
        else:
            print("\n6️⃣ No hay tablas RAG (esto es normal)")
        
        await conn.close()
        
        # 7. Generar resumen
        print("\n" + "="*50)
        print("📋 RESUMEN DEL ESTADO ACTUAL")
        print("="*50)
        
        if 'usuarios' in table_names and 'incidencias' in table_names:
            print("✅ Estructura básica: COMPLETA")
            print("   ✅ Tabla usuarios existe")
            print("   ✅ Tabla incidencias existe")
        else:
            print("❌ Estructura básica: INCOMPLETA")
            if 'usuarios' not in table_names:
                print("   ❌ Tabla usuarios falta")
            if 'incidencias' not in table_names:
                print("   ❌ Tabla incidencias falta")
        
        if existing_rag_tables:
            print("✅ Funcionalidad RAG: PARCIALMENTE CONFIGURADA")
            print(f"   📊 Tablas RAG: {len(existing_rag_tables)}/3")
        else:
            print("⚪ Funcionalidad RAG: NO CONFIGURADA (esto es normal)")
        
        # 8. Recomendaciones
        print("\n🎯 RECOMENDACIONES:")
        
        if not table_names:
            print("   🔧 Ejecutar setup completo: python -m scripts.setup_db")
        elif 'usuarios' not in table_names or 'incidencias' not in table_names:
            print("   🔧 Completar estructura básica: python -m scripts.setup_db")
        elif not existing_rag_tables:
            print("   🔧 Agregar funcionalidad RAG: python -m scripts.setup_db")
            print("   📖 Después vectorizar manual: python -m scripts.vectorize_manual")
        else:
            print("   ✅ Sistema parece estar configurado correctamente")
        
        return True
        
    except Exception as e:
        print(f"❌ Error verificando estado: {e}")
        return False

async def analyze_table_structure(conn, table_name: str):
    """Analizar estructura detallada de una tabla"""
    try:
        columns = await conn.fetch("""
            SELECT 
                column_name, 
                data_type, 
                is_nullable, 
                column_default,
                character_maximum_length
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = $1
            ORDER BY ordinal_position
        """, table_name)
        
        print(f"📋 Estructura de '{table_name}' ({len(columns)} columnas):")
        
        for col in columns:
            nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
            max_len = f"({col['character_maximum_length']})" if col['character_maximum_length'] else ""
            default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
            
            print(f"   📝 {col['column_name']}: {col['data_type']}{max_len} {nullable}{default}")
        
        # Verificar campos específicos para RAG en incidencias
        if table_name == 'incidencias':
            rag_fields = ['codigo_tienda', 'nombre_tienda', 'nombre_seccion', 
                         'numero_serie', 'solucion_rag', 'confianza_solucion', 'chunks_utilizados']
            
            existing_rag_fields = [col['column_name'] for col in columns if col['column_name'] in rag_fields]
            missing_rag_fields = [field for field in rag_fields if field not in existing_rag_fields]
            
            if existing_rag_fields:
                print(f"   ✅ Campos RAG existentes: {existing_rag_fields}")
            
            if missing_rag_fields:
                print(f"   ⚪ Campos RAG que se agregarán: {missing_rag_fields}")
            
    except Exception as e:
        print(f"   ❌ Error analizando estructura: {e}")

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
    
    success = await check_current_status()
    
    if not success:
        print("\n❌ No se pudo verificar el estado")
        print("💡 Verifica la configuración de conexión en .env")

if __name__ == "__main__":
    asyncio.run(main())