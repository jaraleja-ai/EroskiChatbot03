# =====================================================
# database/scripts/check_vectors_status.py - Verificar estado de vectores
# =====================================================
"""
Script para verificar si los chunks tienen vectores almacenados
y en qué formato están.
"""

import asyncio
import asyncpg
import os
import json
from pathlib import Path

async def check_vectors_status():
    """Verificar estado actual de los vectores"""
    
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
    
    print("🔍 VERIFICADOR DE ESTADO DE VECTORES")
    print("=" * 50)
    
    try:
        conn = await asyncpg.connect(connection_string)
        
        # 1. Verificar estructura de la tabla
        print("\n1️⃣ Verificando estructura de knowledge_base...")
        
        columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'knowledge_base' AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        vector_columns = []
        for col in columns:
            print(f"   📝 {col['column_name']}: {col['data_type']}")
            if 'vector' in col['data_type'] or 'embedding' in col['column_name']:
                vector_columns.append(col['column_name'])
        
        if vector_columns:
            print(f"   ✅ Columnas de vectores encontradas: {vector_columns}")
        else:
            print("   ⚠️ No se encontraron columnas de vectores")
        
        # 2. Contar chunks total
        print("\n2️⃣ Estadísticas de chunks...")
        
        total_chunks = await conn.fetchval("SELECT COUNT(*) FROM knowledge_base")
        print(f"   📊 Total chunks: {total_chunks}")
        
        # 3. Verificar diferentes tipos de vectores
        print("\n3️⃣ Verificando tipos de vectores...")
        
        # Verificar columna chunk_embedding (pgvector)
        try:
            pgvector_count = await conn.fetchval("""
                SELECT COUNT(*) FROM knowledge_base 
                WHERE chunk_embedding IS NOT NULL
            """)
            print(f"   🔢 Chunks con pgvector (chunk_embedding): {pgvector_count}")
        except Exception as e:
            print(f"   ❌ Columna chunk_embedding no existe: {str(e)[:50]}...")
            pgvector_count = 0
        
        # Verificar columna chunk_embedding_json (JSON)
        try:
            json_vector_count = await conn.fetchval("""
                SELECT COUNT(*) FROM knowledge_base 
                WHERE chunk_embedding_json IS NOT NULL AND chunk_embedding_json != 'null'
            """)
            print(f"   📄 Chunks con JSON vectors (chunk_embedding_json): {json_vector_count}")
        except Exception as e:
            print(f"   ❌ Columna chunk_embedding_json no existe: {str(e)[:50]}...")
            json_vector_count = 0
        
        # Verificar flag embedding_pendiente
        try:
            pending_count = await conn.fetchval("""
                SELECT COUNT(*) FROM knowledge_base 
                WHERE embedding_pendiente = true
            """)
            print(f"   ⏳ Chunks pendientes de vectorizar: {pending_count}")
        except Exception as e:
            print(f"   ❌ Columna embedding_pendiente no existe: {str(e)[:50]}...")
            pending_count = total_chunks
        
        # 4. Analizar cobertura de vectorización
        print("\n4️⃣ Análisis de cobertura...")
        
        total_vectorized = pgvector_count + json_vector_count
        if total_chunks > 0:
            coverage = (total_vectorized / total_chunks) * 100
            print(f"   📊 Cobertura total: {coverage:.1f}% ({total_vectorized}/{total_chunks})")
        
        if pgvector_count == 0 and json_vector_count == 0:
            print("   ❌ NO HAY VECTORES ALMACENADOS")
            print("   💡 Los chunks están, pero sin vectorizar")
        elif pgvector_count > 0:
            print("   ✅ VECTORES PGVECTOR: Óptimo para búsqueda")
        elif json_vector_count > 0:
            print("   ✅ VECTORES JSON: Funcional para búsqueda")
        
        # 5. Mostrar ejemplos de chunks
        print("\n5️⃣ Ejemplos de chunks...")
        
        # Chunk con vector
        if pgvector_count > 0:
            vector_chunk = await conn.fetchrow("""
                SELECT id, pagina_numero, seccion, LENGTH(chunk_text) as text_length,
                       vector_dims(chunk_embedding) as vector_dims
                FROM knowledge_base 
                WHERE chunk_embedding IS NOT NULL
                LIMIT 1
            """)
            
            if vector_chunk:
                print(f"   ✅ Chunk #{vector_chunk['id']} (pgvector):")
                print(f"      📄 Página {vector_chunk['pagina_numero']} - {vector_chunk['seccion']}")
                print(f"      📊 Texto: {vector_chunk['text_length']} chars, Vector: {vector_chunk['vector_dims']} dims")
        
        elif json_vector_count > 0:
            json_chunk = await conn.fetchrow("""
                SELECT id, pagina_numero, seccion, LENGTH(chunk_text) as text_length,
                       jsonb_array_length(chunk_embedding_json) as vector_dims
                FROM knowledge_base 
                WHERE chunk_embedding_json IS NOT NULL AND chunk_embedding_json != 'null'
                LIMIT 1
            """)
            
            if json_chunk:
                print(f"   ✅ Chunk #{json_chunk['id']} (JSON vector):")
                print(f"      📄 Página {json_chunk['pagina_numero']} - {json_chunk['seccion']}")
                print(f"      📊 Texto: {json_chunk['text_length']} chars, Vector: {json_chunk['vector_dims']} dims")
        
        # Chunk sin vector
        no_vector_chunk = await conn.fetchrow("""
            SELECT id, pagina_numero, seccion, LENGTH(chunk_text) as text_length
            FROM knowledge_base 
            WHERE (chunk_embedding IS NULL OR chunk_embedding IS NULL) 
            AND (chunk_embedding_json IS NULL OR chunk_embedding_json = 'null')
            LIMIT 1
        """)
        
        if no_vector_chunk:
            print(f"   ⚠️ Chunk #{no_vector_chunk['id']} (sin vector):")
            print(f"      📄 Página {no_vector_chunk['pagina_numero']} - {no_vector_chunk['seccion']}")
            print(f"      📊 Texto: {no_vector_chunk['text_length']} chars, Vector: NO")
        
        # 6. Verificar índices vectoriales
        print("\n6️⃣ Verificando índices vectoriales...")
        
        vector_indexes = await conn.fetch("""
            SELECT indexname, tablename, indexdef
            FROM pg_indexes 
            WHERE tablename = 'knowledge_base' 
            AND (indexname LIKE '%embedding%' OR indexname LIKE '%vector%')
        """)
        
        if vector_indexes:
            print("   ✅ Índices vectoriales encontrados:")
            for idx in vector_indexes:
                print(f"      🔹 {idx['indexname']}")
        else:
            print("   ⚠️ No se encontraron índices vectoriales")
        
        # 7. Recomendaciones
        print("\n" + "=" * 50)
        print("📋 DIAGNÓSTICO Y RECOMENDACIONES")
        print("=" * 50)
        
        if total_vectorized == 0:
            print("❌ PROBLEMA: No hay vectores almacenados")
            print("\n💡 SOLUCIONES:")
            print("   1. 🔄 Vectorizar chunks existentes:")
            print("      python database/scripts/vectorize_existing_chunks.py")
            print("   2. 📖 Re-procesar manual completo:")
            print("      python database/scripts/vectorize_manual.py")
            print("      (responder 's' cuando pregunte si re-vectorizar)")
            
        elif total_vectorized < total_chunks:
            print(f"⚠️ PARCIAL: {total_vectorized}/{total_chunks} chunks vectorizados")
            print("\n💡 SOLUCIÓN:")
            print("   🔄 Completar vectorización pendiente:")
            print("      python database/scripts/vectorize_existing_chunks.py")
            
        else:
            print("✅ PERFECTO: Todos los chunks están vectorizados")
            print("\n🎯 PRÓXIMOS PASOS:")
            print("   1. 🧪 Probar búsqueda vectorial:")
            print("      python database/scripts/test_vector_search.py")
            print("   2. 🚀 Ejecutar chatbot completo:")
            print("      python main.py")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error verificando vectores: {e}")

if __name__ == "__main__":
    asyncio.run(check_vectors_status())