# =====================================================
# database/scripts/setup_db_compatible.py - Compatible con estructura existente
# =====================================================
"""
Script para agregar funcionalidad RAG a tu estructura existente
SIN TOCAR los datos actuales.
"""

import asyncio
import asyncpg
import logging
import sys
from pathlib import Path

# Setup path para imports
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("SetupRAG")

class RAGSetupCompatible:
    """Configurador RAG compatible con estructura existente"""
    
    def __init__(self):
        # Configuración de BD desde variables de entorno
        import os
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
    
    async def setup_rag_functionality(self):
        """Agregar funcionalidad RAG manteniendo estructura existente"""
        try:
            logger.info("🚀 Iniciando configuración RAG...")
            logger.info("🔒 MODO SEGURO: Preservando datos existentes")
            
            # 1. Habilitar extensiones
            await self._enable_extensions()
            
            # 2. Crear tablas RAG nuevas
            await self._create_rag_tables()
            
            # 3. Agregar campos RAG faltantes a incidencias
            await self._add_rag_fields_to_incidencias()
            
            # 4. Crear índices optimizados
            await self._create_rag_indexes()
            
            # 5. Insertar tipologías iniciales
            await self._insert_tipologias()
            
            # 6. Verificar configuración
            await self._verify_rag_setup()
            
            logger.info("✅ Funcionalidad RAG agregada exitosamente")
            logger.info("💡 Próximo paso: python database/scripts/vectorize_manual.py")
            
        except Exception as e:
            logger.error(f"❌ Error configurando RAG: {e}")
            raise
    
    async def _enable_extensions(self):
        """Habilitar extensiones PostgreSQL necesarias"""
        logger.info("🔧 Habilitando extensiones PostgreSQL...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            extensions = [
                "CREATE EXTENSION IF NOT EXISTS vector;",     # Para RAG
                "CREATE EXTENSION IF NOT EXISTS pg_trgm;",    # Para búsquedas de texto
                "CREATE EXTENSION IF NOT EXISTS unaccent;",   # Para normalización
            ]
            
            for extension in extensions:
                try:
                    await conn.execute(extension)
                    ext_name = extension.split()[5]  # Extraer nombre
                    logger.info(f"   ✅ {ext_name} habilitada")
                except Exception as e:
                    logger.warning(f"   ⚠️ {extension}: {e}")
            
        finally:
            await conn.close()
    
    async def _create_rag_tables(self):
        """Crear tablas nuevas para RAG"""
        logger.info("📚 Creando tablas RAG...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Tabla para chunks vectorizados
            knowledge_base_sql = """
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id SERIAL PRIMARY KEY,
                documento_origen VARCHAR(255) NOT NULL,
                chunk_text TEXT NOT NULL,
                chunk_embedding vector(1536),
                chunk_metadata JSONB DEFAULT '{}',
                pagina_numero INTEGER,
                seccion VARCHAR(200),
                capitulo VARCHAR(200),
                palabras_clave TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                CONSTRAINT kb_chunk_text_valido CHECK (LENGTH(chunk_text) >= 50)
            );
            """
            
            await conn.execute(knowledge_base_sql)
            logger.info("   ✅ Tabla 'knowledge_base' creada")
            
            # Tabla para tipologías
            tipologias_sql = """
            CREATE TABLE IF NOT EXISTS tipologias_incidencias (
                id SERIAL PRIMARY KEY,
                categoria VARCHAR(100) NOT NULL,
                subcategoria VARCHAR(100),
                descripcion TEXT,
                equipos_aplicables JSONB DEFAULT '[]',
                nivel_urgencia INTEGER DEFAULT 2 CHECK (nivel_urgencia BETWEEN 1 AND 5),
                requiere_escalacion BOOLEAN DEFAULT FALSE,
                tiempo_resolucion_estimado INTEGER,
                solucion_automatica TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                UNIQUE(categoria, subcategoria)
            );
            """
            
            await conn.execute(tipologias_sql)
            logger.info("   ✅ Tabla 'tipologias_incidencias' creada")
            
            # Tabla para tracking RAG
            rag_queries_sql = """
            CREATE TABLE IF NOT EXISTS rag_queries (
                id SERIAL PRIMARY KEY,
                numero_empleado VARCHAR(4),  -- Compatible con tu estructura
                query_original TEXT NOT NULL,
                query_vectorizada vector(1536),
                chunks_encontrados JSONB DEFAULT '[]',
                respuesta_generada TEXT,
                rating_usuario INTEGER CHECK (rating_usuario BETWEEN 1 AND 5),
                fue_util BOOLEAN,
                tiempo_respuesta_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            
            await conn.execute(rag_queries_sql)
            logger.info("   ✅ Tabla 'rag_queries' creada")
            
        finally:
            await conn.close()
    
    async def _add_rag_fields_to_incidencias(self):
        """Agregar campos RAG faltantes a tabla incidencias existente"""
        logger.info("🔄 Agregando campos RAG a tabla 'incidencias'...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Verificar qué campos ya existen
            existing_columns = await conn.fetch("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'incidencias' AND table_schema = 'public'
            """)
            
            existing_column_names = [col['column_name'] for col in existing_columns]
            logger.info(f"   📋 Columnas existentes: {existing_column_names}")
            
            # Campos RAG que necesitamos agregar
            rag_fields = {
                'numero_serie': 'VARCHAR(100)',
                'solucion_rag': 'TEXT',
                'confianza_solucion': 'DECIMAL(3,2)',
                'chunks_utilizados': 'JSONB DEFAULT \'[]\''
            }
            
            # Agregar solo los campos que faltan
            for field_name, field_type in rag_fields.items():
                if field_name not in existing_column_names:
                    try:
                        alter_sql = f"ALTER TABLE incidencias ADD COLUMN {field_name} {field_type};"
                        await conn.execute(alter_sql)
                        logger.info(f"   ✅ Campo '{field_name}' agregado")
                    except Exception as e:
                        logger.warning(f"   ⚠️ No se pudo agregar '{field_name}': {e}")
                else:
                    logger.info(f"   ✅ Campo '{field_name}' ya existe")
            
        finally:
            await conn.close()
    
    async def _create_rag_indexes(self):
        """Crear índices para búsqueda vectorial"""
        logger.info("📋 Creando índices RAG...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            indexes = [
                # Índices vectoriales
                "CREATE INDEX IF NOT EXISTS idx_kb_embedding_cosine ON knowledge_base USING ivfflat (chunk_embedding vector_cosine_ops) WITH (lists = 100);",
                
                # Índices de apoyo para knowledge_base
                "CREATE INDEX IF NOT EXISTS idx_kb_documento ON knowledge_base(documento_origen);",
                "CREATE INDEX IF NOT EXISTS idx_kb_seccion ON knowledge_base(seccion);",
                "CREATE INDEX IF NOT EXISTS idx_kb_palabras_clave ON knowledge_base USING gin(palabras_clave);",
                
                # Índice de texto completo
                "CREATE INDEX IF NOT EXISTS idx_kb_texto_busqueda ON knowledge_base USING gin(to_tsvector('spanish', chunk_text));",
                
                # Índices para tipologías
                "CREATE INDEX IF NOT EXISTS idx_tipologias_categoria ON tipologias_incidencias(categoria);",
                "CREATE INDEX IF NOT EXISTS idx_tipologias_equipos ON tipologias_incidencias USING gin(equipos_aplicables);",
                
                # Índices para incidencias (campos existentes)
                "CREATE INDEX IF NOT EXISTS idx_incidencias_codigo_tienda ON incidencias(codigo_tienda);",
                "CREATE INDEX IF NOT EXISTS idx_incidencias_numero_empleado ON incidencias(numero_empleado);",
                
                # Índices para rag_queries
                "CREATE INDEX IF NOT EXISTS idx_rag_queries_numero_empleado ON rag_queries(numero_empleado);",
                "CREATE INDEX IF NOT EXISTS idx_rag_queries_fecha ON rag_queries(created_at);"
            ]
            
            created_count = 0
            for index_sql in indexes:
                try:
                    await conn.execute(index_sql)
                    created_count += 1
                except Exception as e:
                    logger.warning(f"   ⚠️ Índice no creado: {str(e)[:50]}...")
            
            logger.info(f"   ✅ {created_count}/{len(indexes)} índices creados/verificados")
            
        finally:
            await conn.close()
    
    async def _insert_tipologias(self):
        """Insertar tipologías iniciales específicas de Eroski"""
        logger.info("📋 Insertando tipologías iniciales...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Verificar si ya hay tipologías
            count = await conn.fetchval("SELECT COUNT(*) FROM tipologias_incidencias")
            if count > 0:
                logger.info("   ✅ Tipologías ya existen")
                return
            
            tipologias_data = [
                {
                    "categoria": "Hardware",
                    "subcategoria": "Balanza",
                    "descripcion": "Problemas con básculas y balanzas DIBAL Mistral",
                    "equipos": ["DIBAL Mistral", "DIBAL Serie K"],
                    "urgencia": 3,
                    "tiempo": 30
                },
                {
                    "categoria": "Hardware", 
                    "subcategoria": "TPV",
                    "descripcion": "Fallos en terminales punto de venta",
                    "equipos": ["TPV Toshiba", "TPV HP"],
                    "urgencia": 4,
                    "tiempo": 20
                },
                {
                    "categoria": "Etiquetado",
                    "subcategoria": "Balanza",
                    "descripcion": "Problemas con impresión de etiquetas en balanza",
                    "equipos": ["DIBAL Mistral"],
                    "urgencia": 3,
                    "tiempo": 25
                },
                {
                    "categoria": "Software",
                    "subcategoria": "Sistema POS",
                    "descripcion": "Errores en software punto de venta Eroski",
                    "equipos": ["Sistema Eroski POS"],
                    "urgencia": 4,
                    "tiempo": 45
                }
            ]
            
            for tip in tipologias_data:
                await conn.execute("""
                    INSERT INTO tipologias_incidencias 
                    (categoria, subcategoria, descripcion, equipos_aplicables, nivel_urgencia, tiempo_resolucion_estimado)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, 
                    tip["categoria"], tip["subcategoria"], tip["descripcion"],
                    tip["equipos"], tip["urgencia"], tip["tiempo"]
                )
            
            logger.info(f"   ✅ {len(tipologias_data)} tipologías insertadas")
            
        finally:
            await conn.close()
    
    async def _verify_rag_setup(self):
        """Verificar que la configuración RAG es correcta"""
        logger.info("🔍 Verificando configuración RAG...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Verificar tablas RAG
            rag_tables = ['knowledge_base', 'tipologias_incidencias', 'rag_queries']
            
            for table in rag_tables:
                exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = $1
                    )
                """, table)
                
                if exists:
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    logger.info(f"   ✅ {table}: {count} registros")
                else:
                    logger.error(f"   ❌ {table}: NO EXISTE")
            
            # Verificar extensión vector
            vector_exists = await conn.fetchval("""
                SELECT EXISTS (SELECT FROM pg_extension WHERE extname = 'vector')
            """)
            
            if vector_exists:
                logger.info("   ✅ Extensión pgvector habilitada")
            else:
                logger.warning("   ⚠️ Extensión pgvector no disponible")
            
            # Verificar campos RAG en incidencias
            inc_columns = await conn.fetch("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'incidencias'
            """)
            
            column_names = [col['column_name'] for col in inc_columns]
            rag_fields = ['numero_serie', 'solucion_rag', 'confianza_solucion', 'chunks_utilizados']
            
            existing_rag = [field for field in rag_fields if field in column_names]
            logger.info(f"   ✅ Campos RAG en incidencias: {existing_rag}")
            
        finally:
            await conn.close()

async def main():
    """Entry point"""
    # Cargar variables de entorno
    current_dir = Path(__file__).parent
    root_dir = current_dir.parent.parent
    env_file = root_dir / ".env"
    
    if env_file.exists():
        import os
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value.strip('"\'')
    
    print("🗄️ CONFIGURADOR RAG COMPATIBLE")
    print("=" * 45)
    print("🔒 MODO SEGURO: Preserva datos existentes")
    print("🆕 AGREGAR: Solo funcionalidad RAG")
    print("=" * 45)
    
    setup = RAGSetupCompatible()
    
    try:
        await setup.setup_rag_functionality()
        
        print("\n🎉 ¡Configuración RAG completada exitosamente!")
        print("\n📚 PRÓXIMOS PASOS:")
        print("1. 📖 Colocar manual PDF en: docs/Manual Balanza DIBAL Mistral.pdf")
        print("2. 🔄 Vectorizar manual: python database/scripts/vectorize_manual.py")
        print("3. 🧪 Probar RAG: python database/scripts/test_rag.py")
        
    except Exception as e:
        print(f"\n❌ Error en configuración: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())