# =====================================================
# scripts/setup_db.py - Script extendido para RAG y vectorización
# =====================================================
"""
Script para configurar completamente la base de datos del chatbot.
EXTENDIDO CON: Tablas para RAG, vectorización y tipologías.
"""

import asyncio
import asyncpg
import logging
from typing import List, Dict, Any
from datetime import datetime
import sys
from pathlib import Path

# Agregar el directorio raíz al path
ROOT_DIR = Path(__file__).parent.parent.parent  # Subir tres niveles: scripts -> database -> raíz
sys.path.insert(0, str(ROOT_DIR))

from config.settings import get_settings
from config.logging_config import setup_logging

logger = logging.getLogger("DatabaseSetup")

class DatabaseSetup:
    """Configurador de base de datos extendido con RAG"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db_config = self.settings.database
        
    async def setup_complete_database(self):
        """Configurar base de datos completa con RAG"""
        try:
            logger.info("🗄️ Iniciando configuración completa de base de datos...")
            
            # 1. Crear base de datos
            await self.create_database_if_not_exists()
            
            # 2. Crear tablas (incluyendo RAG)
            await self.create_tables()
            
            # 3. Crear índices (incluyendo vectoriales)
            await self.create_indexes()
            
            # 4. Insertar datos de prueba
            await self.insert_sample_data()
            
            # 5. Insertar tipologías iniciales
            await self.insert_tipologias()
            
            # 6. Verificar configuración
            await self.verify_setup()
            
            logger.info("✅ Configuración de base de datos completada exitosamente")
            logger.info("💡 Próximo paso: python -m scripts.vectorize_manual")
            
        except Exception as e:
            logger.error(f"❌ Error en configuración de BD: {e}")
            raise
    
    async def create_database_if_not_exists(self):
        """Crear base de datos si no existe"""
        logger.info(f"📋 Creando base de datos: {self.db_config.name}")
        
        try:
            conn = await asyncpg.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                user=self.db_config.user,
                password=self.db_config.password,
                database="postgres"
            )
            
            try:
                result = await conn.fetchval(
                    "SELECT 1 FROM pg_database WHERE datname = $1",
                    self.db_config.name
                )
                
                if result:
                    logger.info(f"✅ Base de datos {self.db_config.name} ya existe")
                else:
                    await conn.execute(f'CREATE DATABASE "{self.db_config.name}"')
                    logger.info(f"✅ Base de datos {self.db_config.name} creada")
                    
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error creando base de datos: {e}")
            raise
    
    async def create_tables(self):
        """Crear todas las tablas necesarias incluyendo RAG"""
        logger.info("📋 Creando tablas...")
        
        conn = await asyncpg.connect(self.db_config.connection_string)
        
        try:
            # Habilitar extensiones necesarias
            await self._enable_extensions(conn)
            
            # Crear tablas básicas
            await self._create_users_table(conn)
            await self._create_incidencias_table(conn)
            await self._create_audit_table(conn)
            
            # NUEVO: Crear tablas RAG
            await self._create_rag_tables(conn)
            
            logger.info("✅ Todas las tablas creadas correctamente")
            
        finally:
            await conn.close()
    
    async def _enable_extensions(self, conn):
        """Habilitar extensiones de PostgreSQL incluyendo pgvector"""
        extensions = [
            "CREATE EXTENSION IF NOT EXISTS pg_trgm;",
            "CREATE EXTENSION IF NOT EXISTS unaccent;",
            "CREATE EXTENSION IF NOT EXISTS vector;",  # Para RAG
        ]
        
        for extension in extensions:
            try:
                await conn.execute(extension)
                logger.debug(f"✅ Extensión habilitada: {extension}")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo habilitar extensión {extension}: {e}")
    
    async def _create_users_table(self, conn):
        """Crear tabla de usuarios"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL,
            apellido VARCHAR(100) NOT NULL,
            email VARCHAR(255) UNIQUE NOT NULL,
            numero_empleado VARCHAR(50) UNIQUE NOT NULL,
            rol VARCHAR(20) DEFAULT 'empleado' CHECK (rol IN ('empleado', 'supervisor', 'administrador')),
            departamento VARCHAR(100),
            tienda VARCHAR(100),
            estado VARCHAR(20) DEFAULT 'activo' CHECK (estado IN ('activo', 'inactivo', 'suspendido')),
            fecha_creacion TIMESTAMP DEFAULT NOW(),
            fecha_actualizacion TIMESTAMP DEFAULT NOW(),
            ultimo_acceso TIMESTAMP,
            
            -- Constraints adicionales
            CONSTRAINT usuarios_email_valido CHECK (email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
            CONSTRAINT usuarios_nombre_valido CHECK (LENGTH(nombre) >= 2),
            CONSTRAINT usuarios_apellido_valido CHECK (LENGTH(apellido) >= 2)
        );
        """
        
        await conn.execute(create_table_sql)
        logger.info("✅ Tabla 'usuarios' creada")
    
    async def _create_incidencias_table(self, conn):
        """Crear tabla de incidencias"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS incidencias (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
            numero_ticket VARCHAR(50) UNIQUE NOT NULL,
            tipo VARCHAR(50) NOT NULL CHECK (tipo IN ('hardware', 'software', 'red', 'acceso', 'email', 'impresora', 'telefonia', 'otro')),
            categoria VARCHAR(100),
            descripcion TEXT NOT NULL,
            prioridad VARCHAR(20) DEFAULT 'media' CHECK (prioridad IN ('baja', 'media', 'alta', 'critica')),
            estado VARCHAR(20) DEFAULT 'abierta' CHECK (estado IN ('abierta', 'en_progreso', 'pendiente_usuario', 'resuelta', 'cerrada', 'escalada')),
            fecha_creacion TIMESTAMP DEFAULT NOW(),
            fecha_actualizacion TIMESTAMP DEFAULT NOW(),
            fecha_resolucion TIMESTAMP,
            tiempo_resolucion_minutos INTEGER,
            
            -- Campos adicionales para tracking
            preguntas_realizadas TEXT[],
            respuestas_usuario JSONB DEFAULT '{}',
            intentos_resolucion INTEGER DEFAULT 0,
            escalado_a VARCHAR(100),
            notas_internas TEXT,
            
            -- NUEVO: Campos para RAG
            codigo_tienda VARCHAR(20),
            nombre_tienda VARCHAR(100),
            nombre_seccion VARCHAR(100),
            numero_serie VARCHAR(100),
            solucion_rag TEXT,
            confianza_solucion DECIMAL(3,2),
            chunks_utilizados JSONB DEFAULT '[]',
            
            -- Constraints
            CONSTRAINT incidencias_descripcion_valida CHECK (LENGTH(descripcion) >= 10),
            CONSTRAINT incidencias_ticket_valido CHECK (numero_ticket ~ '^INC-[0-9]{8}-[A-Z0-9]{8}$'),
            CONSTRAINT incidencias_tiempo_resolucion_positivo CHECK (tiempo_resolucion_minutos > 0 OR tiempo_resolucion_minutos IS NULL)
        );
        """
        
        await conn.execute(create_table_sql)
        logger.info("✅ Tabla 'incidencias' creada (con campos RAG)")
    
    async def _create_audit_table(self, conn):
        """Crear tabla de auditoría"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS auditoria (
            id SERIAL PRIMARY KEY,
            tabla_afectada VARCHAR(50) NOT NULL,
            registro_id INTEGER NOT NULL,
            accion VARCHAR(10) NOT NULL CHECK (accion IN ('INSERT', 'UPDATE', 'DELETE')),
            datos_anteriores JSONB,
            datos_nuevos JSONB,
            usuario_sistema VARCHAR(100),
            timestamp_accion TIMESTAMP DEFAULT NOW()
        );
        """
        
        await conn.execute(create_table_sql)
        logger.info("✅ Tabla 'auditoria' creada")
    
    async def _create_rag_tables(self, conn):
        """Crear tablas específicas para RAG y vectorización"""
        logger.info("📚 Creando tablas para RAG...")
        
        # Tabla para chunks vectorizados del manual
        create_kb_table = """
        CREATE TABLE IF NOT EXISTS knowledge_base (
            id SERIAL PRIMARY KEY,
            documento_origen VARCHAR(255) NOT NULL,
            chunk_text TEXT NOT NULL,
            chunk_embedding vector(1536), -- Compatible con Azure OpenAI embeddings
            chunk_metadata JSONB DEFAULT '{}',
            pagina_numero INTEGER,
            seccion VARCHAR(200),
            capitulo VARCHAR(200),
            palabras_clave TEXT[],
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Constraints
            CONSTRAINT kb_chunk_text_valido CHECK (LENGTH(chunk_text) >= 50),
            CONSTRAINT kb_documento_valido CHECK (LENGTH(documento_origen) > 0)
        );
        """
        
        await conn.execute(create_kb_table)
        logger.info("✅ Tabla 'knowledge_base' creada")
        
        # Tabla para tipologías de incidencias
        create_tipologias_table = """
        CREATE TABLE IF NOT EXISTS tipologias_incidencias (
            id SERIAL PRIMARY KEY,
            categoria VARCHAR(100) NOT NULL,
            subcategoria VARCHAR(100),
            descripcion TEXT,
            equipos_aplicables JSONB DEFAULT '[]',
            nivel_urgencia INTEGER DEFAULT 2 CHECK (nivel_urgencia BETWEEN 1 AND 5),
            requiere_escalacion BOOLEAN DEFAULT FALSE,
            tiempo_resolucion_estimado INTEGER, -- en minutos
            solucion_automatica TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            -- Constraints
            CONSTRAINT tip_categoria_valida CHECK (LENGTH(categoria) >= 3),
            UNIQUE(categoria, subcategoria)
        );
        """
        
        await conn.execute(create_tipologias_table)
        logger.info("✅ Tabla 'tipologias_incidencias' creada")
        
        # Tabla para tracking de queries RAG
        create_rag_queries_table = """
        CREATE TABLE IF NOT EXISTS rag_queries (
            id SERIAL PRIMARY KEY,
            usuario_id INTEGER REFERENCES usuarios(id),
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
        
        await conn.execute(create_rag_queries_table)
        logger.info("✅ Tabla 'rag_queries' creada")
    
    async def create_indexes(self):
        """Crear índices para optimización incluyendo vectoriales"""
        logger.info("📋 Creando índices de optimización...")
        
        conn = await asyncpg.connect(self.db_config.connection_string)
        
        try:
            # Índices básicos existentes
            basic_indexes = [
                # Índices para usuarios
                "CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);",
                "CREATE INDEX IF NOT EXISTS idx_usuarios_numero_empleado ON usuarios(numero_empleado);",
                "CREATE INDEX IF NOT EXISTS idx_usuarios_estado ON usuarios(estado);",
                "CREATE INDEX IF NOT EXISTS idx_usuarios_nombre_apellido ON usuarios(nombre, apellido);",
                
                # Índice de similitud para búsqueda de nombres
                "CREATE INDEX IF NOT EXISTS idx_usuarios_nombre_similitud ON usuarios USING gin ((nombre || ' ' || apellido) gin_trgm_ops);",
                
                # Índices para incidencias
                "CREATE INDEX IF NOT EXISTS idx_incidencias_usuario_id ON incidencias(usuario_id);",
                "CREATE INDEX IF NOT EXISTS idx_incidencias_numero_ticket ON incidencias(numero_ticket);",
                "CREATE INDEX IF NOT EXISTS idx_incidencias_tipo ON incidencias(tipo);",
                "CREATE INDEX IF NOT EXISTS idx_incidencias_estado ON incidencias(estado);",
                "CREATE INDEX IF NOT EXISTS idx_incidencias_prioridad ON incidencias(prioridad);",
                "CREATE INDEX IF NOT EXISTS idx_incidencias_fecha_creacion ON incidencias(fecha_creacion);",
                "CREATE INDEX IF NOT EXISTS idx_incidencias_estado_fecha ON incidencias(estado, fecha_creacion);",
                
                # Índices para campos RAG en incidencias
                "CREATE INDEX IF NOT EXISTS idx_incidencias_codigo_tienda ON incidencias(codigo_tienda);",
                "CREATE INDEX IF NOT EXISTS idx_incidencias_nombre_seccion ON incidencias(nombre_seccion);",
                "CREATE INDEX IF NOT EXISTS idx_incidencias_numero_serie ON incidencias(numero_serie);",
                
                # Índices para auditoría
                "CREATE INDEX IF NOT EXISTS idx_auditoria_tabla_registro ON auditoria(tabla_afectada, registro_id);",
                "CREATE INDEX IF NOT EXISTS idx_auditoria_timestamp ON auditoria(timestamp_accion);",
                "CREATE INDEX IF NOT EXISTS idx_auditoria_accion ON auditoria(accion);"
            ]
            
            # NUEVO: Índices para RAG
            rag_indexes = [
                # Índices vectoriales para knowledge_base
                "CREATE INDEX IF NOT EXISTS idx_kb_embedding_cosine ON knowledge_base USING ivfflat (chunk_embedding vector_cosine_ops) WITH (lists = 100);",
                "CREATE INDEX IF NOT EXISTS idx_kb_documento ON knowledge_base(documento_origen);",
                "CREATE INDEX IF NOT EXISTS idx_kb_seccion ON knowledge_base(seccion);",
                "CREATE INDEX IF NOT EXISTS idx_kb_pagina ON knowledge_base(pagina_numero);",
                "CREATE INDEX IF NOT EXISTS idx_kb_palabras_clave ON knowledge_base USING gin(palabras_clave);",
                
                # Índice de texto completo para búsqueda híbrida
                "CREATE INDEX IF NOT EXISTS idx_kb_texto_busqueda ON knowledge_base USING gin(to_tsvector('spanish', chunk_text));",
                
                # Índices para tipologías
                "CREATE INDEX IF NOT EXISTS idx_tipologias_categoria ON tipologias_incidencias(categoria);",
                "CREATE INDEX IF NOT EXISTS idx_tipologias_urgencia ON tipologias_incidencias(nivel_urgencia);",
                "CREATE INDEX IF NOT EXISTS idx_tipologias_equipos ON tipologias_incidencias USING gin(equipos_aplicables);",
                
                # Índices para rag_queries
                "CREATE INDEX IF NOT EXISTS idx_rag_queries_usuario ON rag_queries(usuario_id);",
                "CREATE INDEX IF NOT EXISTS idx_rag_queries_fecha ON rag_queries(created_at);",
                "CREATE INDEX IF NOT EXISTS idx_rag_queries_rating ON rag_queries(rating_usuario);",
                "CREATE INDEX IF NOT EXISTS idx_rag_queries_embedding ON rag_queries USING ivfflat (query_vectorizada vector_cosine_ops);"
            ]
            
            all_indexes = basic_indexes + rag_indexes
            
            for index_sql in all_indexes:
                try:
                    await conn.execute(index_sql)
                    logger.debug(f"✅ Índice creado: {index_sql[:50]}...")
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo crear índice: {e}")
            
            logger.info("✅ Índices creados correctamente (incluyendo vectoriales)")
            
        finally:
            await conn.close()
    
    async def insert_sample_data(self):
        """Insertar datos de prueba"""
        logger.info("📝 Insertando datos de prueba...")
        
        conn = await asyncpg.connect(self.db_config.connection_string)
        
        try:
            # Verificar si ya hay datos
            count = await conn.fetchval("SELECT COUNT(*) FROM usuarios")
            if count > 0:
                logger.info("✅ Ya existen datos de prueba")
                return
            
            await self._insert_sample_users(conn)
            await self._insert_sample_incidencias(conn)
            
        finally:
            await conn.close()
    
    async def insert_tipologias(self):
        """Insertar tipologías iniciales específicas de Eroski"""
        logger.info("📋 Insertando tipologías iniciales...")
        
        conn = await asyncpg.connect(self.db_config.connection_string)
        
        try:
            # Verificar si ya hay tipologías
            count = await conn.fetchval("SELECT COUNT(*) FROM tipologias_incidencias")
            if count > 0:
                logger.info("✅ Tipologías ya existen")
                return
            
            tipologias_data = [
                {
                    "categoria": "Hardware",
                    "subcategoria": "Balanza",
                    "descripcion": "Problemas con básculas y balanzas de tienda DIBAL",
                    "equipos_aplicables": ["DIBAL Mistral", "DIBAL Serie K", "Balanza Comercial"],
                    "nivel_urgencia": 3,
                    "tiempo_resolucion_estimado": 30,
                    "solucion_automatica": "Consultar manual de calibración y verificar conexiones"
                },
                {
                    "categoria": "Hardware",
                    "subcategoria": "TPV",
                    "descripcion": "Fallos en terminales punto de venta",
                    "equipos_aplicables": ["TPV Toshiba", "TPV HP", "TPV Dell"],
                    "nivel_urgencia": 4,
                    "tiempo_resolucion_estimado": 20,
                    "requiere_escalacion": True
                },
                {
                    "categoria": "Hardware",
                    "subcategoria": "Impresora",
                    "descripcion": "Problemas con impresoras de tickets y etiquetas",
                    "equipos_aplicables": ["Epson TM", "Zebra ZD", "Citizen CT"],
                    "nivel_urgencia": 2,
                    "tiempo_resolucion_estimado": 15
                },
                {
                    "categoria": "Software",
                    "subcategoria": "Sistema POS",
                    "descripcion": "Errores en software de punto de venta Eroski",
                    "equipos_aplicables": ["Sistema Eroski POS"],
                    "nivel_urgencia": 4,
                    "tiempo_resolucion_estimado": 45,
                    "requiere_escalacion": True
                },
                {
                    "categoria": "Etiquetado",
                    "subcategoria": "Balanza",
                    "descripcion": "Problemas con impresión de etiquetas en balanza DIBAL",
                    "equipos_aplicables": ["DIBAL Mistral", "DIBAL Serie K"],
                    "nivel_urgencia": 3,
                    "tiempo_resolucion_estimado": 25
                },
                {
                    "categoria": "Red",
                    "subcategoria": "Conectividad",
                    "descripcion": "Problemas de conexión a internet o red local",
                    "equipos_aplicables": ["Router", "Switch", "Cable UTP"],
                    "nivel_urgencia": 4,
                    "tiempo_resolucion_estimado": 25,
                    "requiere_escalacion": True
                }
            ]
            
            for tipologia in tipologias_data:
                await conn.execute("""
                    INSERT INTO tipologias_incidencias 
                    (categoria, subcategoria, descripcion, equipos_aplicables, nivel_urgencia, 
                     tiempo_resolucion_estimado, requiere_escalacion, solucion_automatica)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, 
                    tipologia["categoria"],
                    tipologia["subcategoria"],
                    tipologia["descripcion"],
                    tipologia["equipos_aplicables"],
                    tipologia["nivel_urgencia"],
                    tipologia.get("tiempo_resolucion_estimado"),
                    tipologia.get("requiere_escalacion", False),
                    tipologia.get("solucion_automatica")
                )
            
            logger.info(f"✅ {len(tipologias_data)} tipologías insertadas")
            
        finally:
            await conn.close()
    
    async def _insert_sample_users(self, conn):
        """Insertar usuarios de prueba específicos de Eroski"""
        usuarios_data = [
            {
                "nombre": "Juan Carlos",
                "apellido": "Pérez García",
                "email": "juan.perez@eroski.es",
                "numero_empleado": "EMP001",
                "rol": "empleado",
                "departamento": "Tecnología",
                "tienda": "Eroski Bilbao Centro"
            },
            {
                "nombre": "María",
                "apellido": "González López",
                "email": "maria.gonzalez@eroski.es",
                "numero_empleado": "EMP002",
                "rol": "supervisor",
                "departamento": "IT",
                "tienda": "Oficinas Centrales"
            },
            {
                "nombre": "Mikel",
                "apellido": "Etxeberria Zubiaurre",
                "email": "mikel.etxeberria@eroski.es",
                "numero_empleado": "EMP003",
                "rol": "empleado",
                "departamento": "Sistemas",
                "tienda": "Eroski San Sebastián"
            }
        ]
        
        for usuario in usuarios_data:
            await conn.execute("""
                INSERT INTO usuarios (nombre, apellido, email, numero_empleado, rol, departamento, tienda)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """, 
                usuario["nombre"], usuario["apellido"], usuario["email"],
                usuario["numero_empleado"], usuario["rol"], 
                usuario["departamento"], usuario["tienda"]
            )
        
        logger.info("✅ Usuarios de prueba insertados")
    
    async def _insert_sample_incidencias(self, conn):
        """Insertar incidencias de prueba"""
        # Obtener ID del primer usuario
        user_id = await conn.fetchval("SELECT id FROM usuarios LIMIT 1")
        
        if user_id:
            await conn.execute("""
                INSERT INTO incidencias 
                (usuario_id, numero_ticket, tipo, categoria, descripcion, codigo_tienda, nombre_tienda, nombre_seccion, numero_serie)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """, 
                user_id, "INC-20250105-ABC12345", "hardware", "Balanza",
                "La balanza DIBAL no imprime etiquetas correctamente",
                "ERO001", "Eroski Bilbao Centro", "Charcutería", "DIBAL-2024-001"
            )
        
        logger.info("✅ Incidencia de prueba insertada")
    
    async def verify_setup(self):
        """Verificar que la configuración es correcta"""
        logger.info("🔍 Verificando configuración...")
        
        conn = await asyncpg.connect(self.db_config.connection_string)
        
        try:
            # Listar todas las tablas
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """)
            
            table_names = [table['table_name'] for table in tables]
            logger.info(f"📋 Tablas encontradas: {', '.join(table_names)}")
            
            # Verificar tablas específicas
            expected_tables = ["usuarios", "incidencias", "auditoria", "knowledge_base", "tipologias_incidencias", "rag_queries"]
            
            for expected_table in expected_tables:
                if expected_table in table_names:
                    logger.info(f"✅ Tabla '{expected_table}' existe")
                else:
                    logger.warning(f"⚠️ Tabla '{expected_table}' no encontrada")
            
            # Verificar datos
            user_count = await conn.fetchval("SELECT COUNT(*) FROM usuarios")
            inc_count = await conn.fetchval("SELECT COUNT(*) FROM incidencias")
            tip_count = await conn.fetchval("SELECT COUNT(*) FROM tipologias_incidencias")
            
            logger.info(f"📊 Datos: {user_count} usuarios, {inc_count} incidencias, {tip_count} tipologías")
            
            # Verificar extensión pgvector
            vector_check = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM pg_extension WHERE extname = 'vector'
                )
            """)
            
            if vector_check:
                logger.info("✅ Extensión pgvector habilitada")
            else:
                logger.warning("⚠️ Extensión pgvector no disponible")
            
            logger.info("✅ Verificación de base de datos completada")
            
        finally:
            await conn.close()

async def setup_database():
    """Función principal para configurar base de datos"""
    try:
        # Configurar logging
        setup_logging()
        
        # Crear configurador
        db_setup = DatabaseSetup()
        
        # Ejecutar configuración completa
        await db_setup.setup_complete_database()
        
        print("✅ Base de datos configurada exitosamente")
        return True
        
    except Exception as e:
        print(f"❌ Error configurando base de datos: {e}")
        return False

async def main():
    """Entry point del script"""
    print("🗄️ Configurador de Base de Datos del Chatbot Eroski")
    print("=" * 55)
    print("🆕 INCLUYE: Tablas RAG, vectorización y tipologías")
    print("=" * 55)
    
    success = await setup_database()
    
    if success:
        print("\n🎉 ¡Configuración completada exitosamente!")
        print("\n📚 PRÓXIMOS PASOS:")
        print("1. 📖 Vectorizar manual: python -m scripts.vectorize_manual")
        print("2. 🧪 Probar conexión: python -m scripts.quick_db_check")
        print("3. 🚀 Ejecutar aplicación: python main.py")
    else:
        print("\n❌ Configuración falló. Revisa los logs para más detalles.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())