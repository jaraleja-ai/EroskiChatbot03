# =====================================================
# database/scripts/setup_db_no_vector.py - Sin pgvector (temporal)
# =====================================================
"""
Script para agregar funcionalidad RAG básica SIN pgvector
Versión temporal hasta instalar pgvector.
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
logger = logging.getLogger("SetupRAGNoVector")

class RAGSetupNoVector:
    """Configurador RAG sin pgvector (temporal)"""
    
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
    
    async def setup_rag_basic(self):
        """Configurar RAG básico sin vectores"""
        try:
            logger.info("🚀 Iniciando configuración RAG básica...")
            logger.info("⚠️ MODO TEMPORAL: Sin búsqueda vectorial")
            logger.info("🔒 MODO SEGURO: Preservando datos existentes")
            
            # 1. Habilitar extensiones básicas
            await self._enable_basic_extensions()
            
            # 2. Crear tablas RAG (sin vectores)
            await self._create_basic_rag_tables()
            
            # 3. Agregar campos RAG a incidencias
            await self._add_rag_fields_to_incidencias()
            
            # 4. Crear índices básicos
            await self._create_basic_indexes()
            
            # 5. Insertar tipologías
            await self._insert_tipologias()
            
            # 6. Verificar configuración
            await self._verify_basic_setup()
            
            logger.info("✅ RAG básico configurado exitosamente")
            logger.info("💡 Para vectores: instalar pgvector y ejecutar setup_db_compatible.py")
            
        except Exception as e:
            logger.error(f"❌ Error configurando RAG: {e}")
            raise
    
    async def _enable_basic_extensions(self):
        """Habilitar extensiones básicas"""
        logger.info("🔧 Habilitando extensiones básicas...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            extensions = [
                "CREATE EXTENSION IF NOT EXISTS pg_trgm;",    # Para búsquedas de texto
                "CREATE EXTENSION IF NOT EXISTS unaccent;",   # Para normalización
            ]
            
            for extension in extensions:
                try:
                    await conn.execute(extension)
                    ext_name = extension.split()[5]
                    logger.info(f"   ✅ {ext_name} habilitada")
                except Exception as e:
                    logger.warning(f"   ⚠️ {extension}: {e}")
            
        finally:
            await conn.close()
    
    async def _create_basic_rag_tables(self):
        """Crear tablas RAG básicas (sin vectores)"""
        logger.info("📚 Creando tablas RAG básicas...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Tabla para chunks (sin embeddings por ahora)
            knowledge_base_sql = """
            CREATE TABLE IF NOT EXISTS knowledge_base (
                id SERIAL PRIMARY KEY,
                documento_origen VARCHAR(255) NOT NULL,
                chunk_text TEXT NOT NULL,
                chunk_metadata JSONB DEFAULT '{}',
                pagina_numero INTEGER,
                seccion VARCHAR(200),
                capitulo VARCHAR(200),
                palabras_clave TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                
                -- Campos para cuando se instale pgvector
                embedding_pendiente BOOLEAN DEFAULT TRUE,
                
                CONSTRAINT kb_chunk_text_valido CHECK (LENGTH(chunk_text) >= 50)
            );
            """
            
            await conn.execute(knowledge_base_sql)
            logger.info("   ✅ Tabla 'knowledge_base' creada (sin vectores)")
            
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
            
            # Tabla para tracking RAG (sin vectores de queries)
            rag_queries_sql = """
            CREATE TABLE IF NOT EXISTS rag_queries (
                id SERIAL PRIMARY KEY,
                numero_empleado VARCHAR(4),
                query_original TEXT NOT NULL,
                chunks_encontrados JSONB DEFAULT '[]',
                respuesta_generada TEXT,
                metodo_busqueda VARCHAR(50) DEFAULT 'texto',  -- 'texto' o 'vector'
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
        """Agregar campos RAG a tabla incidencias"""
        logger.info("🔄 Agregando campos RAG a 'incidencias'...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Verificar columnas existentes
            existing_columns = await conn.fetch("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = 'incidencias' AND table_schema = 'public'
            """)
            
            existing_column_names = [col['column_name'] for col in existing_columns]
            
            # Campos RAG que necesitamos
            rag_fields = {
                'numero_serie': 'VARCHAR(100)',
                'solucion_rag': 'TEXT',
                'confianza_solucion': 'DECIMAL(3,2)',
                'chunks_utilizados': 'JSONB DEFAULT \'[]\'',
                'metodo_resolucion': 'VARCHAR(50) DEFAULT \'manual\''  # 'manual', 'rag', 'escalado'
            }
            
            # Agregar campos faltantes
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
    
    async def _create_basic_indexes(self):
        """Crear índices básicos (sin vectoriales)"""
        logger.info("📋 Creando índices básicos...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            indexes = [
                # Índices de texto completo
                "CREATE INDEX IF NOT EXISTS idx_kb_texto_busqueda ON knowledge_base USING gin(to_tsvector('spanish', chunk_text));",
                "CREATE INDEX IF NOT EXISTS idx_kb_palabras_clave ON knowledge_base USING gin(palabras_clave);",
                
                # Índices básicos para knowledge_base
                "CREATE INDEX IF NOT EXISTS idx_kb_documento ON knowledge_base(documento_origen);",
                "CREATE INDEX IF NOT EXISTS idx_kb_seccion ON knowledge_base(seccion);",
                "CREATE INDEX IF NOT EXISTS idx_kb_pagina ON knowledge_base(pagina_numero);",
                
                # Índices para tipologías
                "CREATE INDEX IF NOT EXISTS idx_tipologias_categoria ON tipologias_incidencias(categoria);",
                "CREATE INDEX IF NOT EXISTS idx_tipologias_equipos ON tipologias_incidencias USING gin(equipos_aplicables);",
                
                # Índices para incidencias
                "CREATE INDEX IF NOT EXISTS idx_incidencias_codigo_tienda ON incidencias(codigo_tienda);",
                "CREATE INDEX IF NOT EXISTS idx_incidencias_numero_empleado ON incidencias(numero_empleado);",
                "CREATE INDEX IF NOT EXISTS idx_incidencias_estado ON incidencias(estado);",
                
                # Índices para rag_queries
                "CREATE INDEX IF NOT EXISTS idx_rag_queries_numero_empleado ON rag_queries(numero_empleado);",
                "CREATE INDEX IF NOT EXISTS idx_rag_queries_fecha ON rag_queries(created_at);",
                "CREATE INDEX IF NOT EXISTS idx_rag_queries_metodo ON rag_queries(metodo_busqueda);"
            ]
            
            created_count = 0
            for index_sql in indexes:
                try:
                    await conn.execute(index_sql)
                    created_count += 1
                except Exception as e:
                    logger.warning(f"   ⚠️ Índice no creado: {str(e)[:50]}...")
            
            logger.info(f"   ✅ {created_count}/{len(indexes)} índices creados")
            
        finally:
            await conn.close()
    
    async def _insert_tipologias(self):
        """Insertar tipologías iniciales"""
        logger.info("📋 Insertando tipologías...")
        
        conn = await asyncpg.connect(self.connection_string)
        
        try:
            # Verificar si ya existen
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
                    "tiempo": 30,
                    "solucion": "Verificar conexiones y calibración según manual"
                },
                {
                    "categoria": "Hardware", 
                    "subcategoria": "TPV",
                    "descripcion": "Fallos en terminales punto de venta",
                    "equipos": ["TPV Toshiba", "TPV HP"],
                    "urgencia": 4,
                    "tiempo": 20,
                    "escalacion": True
                },
                {
                    "categoria": "Etiquetado",
                    "subcategoria": "Balanza",
                    "descripcion": "Problemas con impresión de etiquetas en balanza",
                    "equipos": ["DIBAL Mistral"],
                    "urgencia": 3,
                    "tiempo": 25,
                    "solucion": "Revisar configuración de etiquetas y papel"
                },
                {
                    "categoria": "Software",
                    "subcategoria": "Sistema POS",
                    "descripcion": "Errores en software punto de venta Eroski",
                    "equipos": ["Sistema Eroski POS"],
                    "urgencia": 4,
                    "tiempo": 45,
                    "escalacion": True
                }
            ]
            
            import json
            
            for tip in tipologias_data:
                await conn.execute("""
                    INSERT INTO tipologias_incidencias 
                    (categoria, subcategoria, descripcion, equipos_aplicables, nivel_urgencia, 
                     tiempo_resolucion_estimado, requiere_escalacion, solucion_automatica)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, 
                    tip["categoria"], tip["subcategoria"], tip["descripcion"],
                    json.dumps(tip["equipos"]), tip["urgencia"], tip["tiempo"],
                    tip.get("escalacion", False), tip.get("solucion", "")
                )
            
            logger.info(f"   ✅ {len(tipologias_data)} tipologías insertadas")
            
        finally:
            await conn.close()
    
    async def _verify_basic_setup(self):
        """Verificar configuración básica"""
        logger.info("🔍 Verificando configuración...")
        
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
    
    print("🗄️ CONFIGURADOR RAG BÁSICO")
    print("=" * 40)
    print("⚠️ TEMPORAL: Sin búsqueda vectorial")
    print("🔒 SEGURO: Preserva datos existentes")
    print("📚 PREPARA: Estructura para pgvector")
    print("=" * 40)
    
    setup = RAGSetupNoVector()
    
    try:
        await setup.setup_rag_basic()
        
        print("\n🎉 ¡RAG básico configurado exitosamente!")
        print("\n📋 ESTADO ACTUAL:")
        print("   ✅ Estructura RAG lista")
        print("   ✅ Datos preservados")
        print("   ⚠️ Sin búsqueda vectorial (falta pgvector)")
        
        print("\n🔧 PARA ACTIVAR VECTORES:")
        print("1. 📥 Instalar pgvector:")
        print("   - Descargar: https://github.com/pgvector/pgvector/releases")
        print("   - Instalar en PostgreSQL")
        print("2. 🔄 Ejecutar: python database/scripts/setup_db_compatible.py")
        
        print("\n📚 MIENTRAS TANTO:")
        print("1. 📖 Colocar manual: docs/Manual Balanza DIBAL Mistral.pdf")
        print("2. 🔄 Procesar texto: python database/scripts/process_manual_text.py")
        
    except Exception as e:
        print(f"\n❌ Error en configuración: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())