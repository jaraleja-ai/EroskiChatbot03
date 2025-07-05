# =====================================================
# database/scripts/test_text_search.py - Probar búsqueda de texto
# =====================================================
"""
Script para probar la funcionalidad de búsqueda de texto
en el manual de la balanza DIBAL Mistral.
"""

import asyncio
import asyncpg
import logging
import os
from pathlib import Path
from typing import List, Dict, Any

# Setup path
ROOT_DIR = Path(__file__).parent.parent.parent

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestTextSearch")

class TextSearchTester:
    """Probador de búsqueda de texto en knowledge base"""
    
    def __init__(self):
        # Configuración de BD
        self.db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 5432)),
            "database": os.getenv("DB_NAME", "chatbot_db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "")
        }
        
    @property
    def connection_string(self) -> str:
        """Construir string de conexión"""
        return (f"postgresql://{self.db_config['user']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
    
    async def test_search_functionality(self):
        """Probar diferentes tipos de búsqueda"""
        try:
            logger.info("🧪 Iniciando pruebas de búsqueda...")
            
            # 1. Verificar estado de la knowledge base
            await self._check_knowledge_base_status()
            
            # 2. Probar búsquedas de ejemplo
            test_queries = [
                "calibración",
                "error",
                "etiqueta",
                "instalación",
                "peso",
                "configuración balanza",
                "problemas impresora",
                "código de error",
                "manual de usuario"
            ]
            
            for query in test_queries:
                logger.info(f"\n🔍 Probando búsqueda: '{query}'")
                await self._test_text_search(query)
                await self._test_keyword_search(query)
            
            # 3. Probar búsqueda por tipo de contenido
            await self._test_content_type_search()
            
            logger.info("\n✅ Todas las pruebas completadas")
            
        except Exception as e:
            logger.error(f"❌ Error en pruebas: {e}")
            raise
    
    async def _check_knowledge_base_status(self):
        """Verificar estado de la knowledge base"""
        logger.info("📊 Verificando estado de knowledge base...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Estadísticas básicas
            total_chunks = await conn.fetchval("SELECT COUNT(*) FROM knowledge_base")
            total_docs = await conn.fetchval("SELECT COUNT(DISTINCT documento_origen) FROM knowledge_base")
            
            logger.info(f"   📚 Documentos: {total_docs}")
            logger.info(f"   📄 Total chunks: {total_chunks}")
            
            # Verificar índices de texto
            text_index_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_indexes 
                    WHERE indexname = 'idx_kb_texto_busqueda'
                )
            """)
            
            keyword_index_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_indexes 
                    WHERE indexname = 'idx_kb_palabras_clave'
                )
            """)
            
            logger.info(f"   🔍 Índice texto completo: {'✅' if text_index_exists else '❌'}")
            logger.info(f"   🏷️ Índice palabras clave: {'✅' if keyword_index_exists else '❌'}")
            
        finally:
            await conn.close()
    
    async def _test_text_search(self, query: str, limit: int = 3):
        """Probar búsqueda de texto completo"""
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Búsqueda usando índice de texto completo
            search_sql = """
            SELECT 
                id,
                seccion,
                pagina_numero,
                LEFT(chunk_text, 150) as preview,
                ts_rank_cd(to_tsvector('spanish', chunk_text), plainto_tsquery('spanish', $1)) as relevance
            FROM knowledge_base 
            WHERE to_tsvector('spanish', chunk_text) @@ plainto_tsquery('spanish', $1)
            ORDER BY relevance DESC
            LIMIT $2
            """
            
            results = await conn.fetch(search_sql, query, limit)
            
            if results:
                logger.info(f"   📝 Búsqueda texto: {len(results)} resultados")
                for i, result in enumerate(results, 1):
                    logger.info(f"      {i}. Página {result['pagina_numero']} - {result['seccion']}")
                    logger.info(f"         Relevancia: {result['relevance']:.3f}")
                    logger.info(f"         Preview: {result['preview']}...")
            else:
                logger.info("   📝 Búsqueda texto: No se encontraron resultados")
                
        finally:
            await conn.close()
    
    async def _test_keyword_search(self, query: str, limit: int = 3):
        """Probar búsqueda por palabras clave"""
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Búsqueda en array de palabras clave
            keyword_sql = """
            SELECT 
                id,
                seccion,
                pagina_numero,
                palabras_clave,
                LEFT(chunk_text, 100) as preview
            FROM knowledge_base 
            WHERE palabras_clave && $1
            ORDER BY array_length(palabras_clave, 1) DESC
            LIMIT $2
            """
            
            # Convertir query en array de palabras
            keywords = [word.strip().lower() for word in query.split()]
            
            results = await conn.fetch(keyword_sql, keywords, limit)
            
            if results:
                logger.info(f"   🏷️ Búsqueda keywords: {len(results)} resultados")
                for i, result in enumerate(results, 1):
                    matching_keywords = [kw for kw in result['palabras_clave'] if any(q in kw for q in keywords)]
                    logger.info(f"      {i}. Página {result['pagina_numero']} - Keywords: {matching_keywords}")
            else:
                logger.info("   🏷️ Búsqueda keywords: No se encontraron resultados")
                
        finally:
            await conn.close()
    
    async def _test_content_type_search(self):
        """Probar búsqueda por tipo de contenido"""
        logger.info("\n📋 Probando búsqueda por tipo de contenido...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Buscar contenido de solución de problemas
            problem_sql = """
            SELECT 
                seccion,
                pagina_numero,
                LEFT(chunk_text, 200) as preview
            FROM knowledge_base 
            WHERE chunk_metadata->>'tipo_contenido' = 'solucion_problemas'
            ORDER BY pagina_numero
            LIMIT 2
            """
            
            problems = await conn.fetch(problem_sql)
            
            if problems:
                logger.info("   🚨 Contenido de solución de problemas:")
                for problem in problems:
                    logger.info(f"      📄 Página {problem['pagina_numero']} - {problem['seccion']}")
                    logger.info(f"         {problem['preview']}...")
            
            # Buscar códigos de error
            error_sql = """
            SELECT 
                seccion,
                pagina_numero,
                palabras_clave,
                LEFT(chunk_text, 150) as preview
            FROM knowledge_base 
            WHERE chunk_metadata->>'tipo_contenido' = 'error_code'
            ORDER BY pagina_numero
            LIMIT 2
            """
            
            errors = await conn.fetch(error_sql)
            
            if errors:
                logger.info("   ⚠️ Contenido con códigos de error:")
                for error in errors:
                    error_keywords = [kw for kw in error['palabras_clave'] if 'error_' in kw]
                    logger.info(f"      📄 Página {error['pagina_numero']} - Errores: {error_keywords}")
                    logger.info(f"         {error['preview']}...")
            
            # Buscar contenido de calibración
            calibration_sql = """
            SELECT 
                seccion,
                pagina_numero,
                LEFT(chunk_text, 150) as preview
            FROM knowledge_base 
            WHERE chunk_metadata->>'tipo_contenido' = 'calibracion'
            ORDER BY pagina_numero
            LIMIT 2
            """
            
            calibrations = await conn.fetch(calibration_sql)
            
            if calibrations:
                logger.info("   ⚖️ Contenido de calibración:")
                for cal in calibrations:
                    logger.info(f"      📄 Página {cal['pagina_numero']} - {cal['seccion']}")
                    logger.info(f"         {cal['preview']}...")
                    
        finally:
            await conn.close()
    
    async def interactive_search(self):
        """Búsqueda interactiva para probar manualmente"""
        logger.info("\n🔍 MODO BÚSQUEDA INTERACTIVA")
        logger.info("Escribe consultas para probar la búsqueda (o 'quit' para salir)")
        
        while True:
            try:
                query = input("\n🔎 Buscar: ").strip()
                
                if query.lower() in ['quit', 'exit', 'salir', 'q']:
                    break
                
                if not query:
                    continue
                
                print(f"\n🔍 Buscando: '{query}'")
                await self._detailed_search(query)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error en búsqueda: {e}")
    
    async def _detailed_search(self, query: str):
        """Búsqueda detallada con múltiples métodos"""
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Búsqueda combinada
            combined_sql = """
            WITH text_search AS (
                SELECT 
                    id, seccion, pagina_numero, chunk_text,
                    ts_rank_cd(to_tsvector('spanish', chunk_text), plainto_tsquery('spanish', $1)) as text_score,
                    'texto' as method
                FROM knowledge_base 
                WHERE to_tsvector('spanish', chunk_text) @@ plainto_tsquery('spanish', $1)
            ),
            keyword_search AS (
                SELECT 
                    id, seccion, pagina_numero, chunk_text,
                    array_length(palabras_clave, 1)::float / 10 as text_score,
                    'keywords' as method
                FROM knowledge_base 
                WHERE palabras_clave && $2
            )
            SELECT * FROM text_search
            UNION ALL
            SELECT * FROM keyword_search
            ORDER BY text_score DESC
            LIMIT 5
            """
            
            keywords = [word.strip().lower() for word in query.split()]
            results = await conn.fetch(combined_sql, query, keywords)
            
            if results:
                print(f"   📊 {len(results)} resultados encontrados:")
                for i, result in enumerate(results, 1):
                    print(f"\n   {i}. 📄 Página {result['pagina_numero']} - {result['seccion']}")
                    print(f"      🔍 Método: {result['method']} (puntuación: {result['text_score']:.3f})")
                    
                    # Mostrar fragmento relevante
                    text = result['chunk_text']
                    if len(text) > 300:
                        # Buscar la parte más relevante del texto
                        query_words = query.lower().split()
                        best_pos = 0
                        best_score = 0
                        
                        for word in query_words:
                            pos = text.lower().find(word)
                            if pos != -1:
                                score = len(word)
                                if score > best_score:
                                    best_score = score
                                    best_pos = max(0, pos - 100)
                        
                        preview = text[best_pos:best_pos + 300] + "..."
                    else:
                        preview = text
                    
                    print(f"      📝 {preview}")
            else:
                print("   ❌ No se encontraron resultados")
                
        finally:
            await conn.close()

async def main():
    """Entry point del script"""
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
    
    print("🧪 PROBADOR DE BÚSQUEDA DE TEXTO")
    print("=" * 45)
    print("📖 Manual: DIBAL Mistral")
    print("🔍 Método: Búsqueda de texto completo")
    print("=" * 45)
    
    tester = TextSearchTester()
    
    try:
        # Ejecutar pruebas automáticas
        await tester.test_search_functionality()
        
        # Ofrecer búsqueda interactiva
        response = input("\n¿Quieres probar búsqueda interactiva? (s/n): ").lower().strip()
        if response in ['s', 'si', 'sí', 'y', 'yes']:
            await tester.interactive_search()
        
        print("\n✅ ¡Pruebas completadas!")
        print("\n🎯 PRÓXIMO PASO:")
        print("   🚀 Ejecutar chatbot: python main.py")
        
    except Exception as e:
        print(f"\n❌ Error en pruebas: {e}")

if __name__ == "__main__":
    asyncio.run(main())