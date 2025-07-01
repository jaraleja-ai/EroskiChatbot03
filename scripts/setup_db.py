# =====================================================
# scripts/setup_db.py - Script para configurar la base de datos
# =====================================================
"""
Script para configurar completamente la base de datos del chatbot.

Funcionalidades:
- Crear base de datos si no existe
- Crear todas las tablas necesarias
- Insertar datos de prueba
- Verificar conexión y configuración
- Crear índices para optimización
"""

import asyncio
import asyncpg
import logging
from typing import List, Dict, Any
from datetime import datetime
import sys
from pathlib import Path

# Agregar el directorio raíz al path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from config.settings import get_settings
from config.logging_config import setup_logging

logger = logging.getLogger("DatabaseSetup")

class DatabaseSetup:
    """Configurador de base de datos"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db_config = self.settings.database
        
    async def setup_complete_database(self):
        """Configurar base de datos completa"""
        try:
            logger.info("🗄️ Iniciando configuración completa de base de datos...")
            
            # 1. Crear base de datos
            await self.create_database_if_not_exists()
            
            # 2. Crear tablas
            await self.create_tables()
            
            # 3. Crear índices
            await self.create_indexes()
            
            # 4. Insertar datos de prueba
            await self.insert_sample_data()
            
            # 5. Verificar configuración
            await self.verify_setup()
            
            logger.info("✅ Configuración de base de datos completada exitosamente")
            
        except Exception as e:
            logger.error(f"❌ Error en configuración de BD: {e}")
            raise
    
    async def create_database_if_not_exists(self):
        """Crear base de datos si no existe"""
        logger.info(f"📋 Creando base de datos: {self.db_config.name}")
        
        # Conectar a postgres para crear la BD
        try:
            conn = await asyncpg.connect(
                host=self.db_config.host,
                port=self.db_config.port,
                user=self.db_config.user,
                password=self.db_config.password,
                database="postgres"  # Conectar a postgres por defecto
            )
            
            try:
                # Verificar si la BD existe
                result = await conn.fetchval(
                    "SELECT 1 FROM pg_database WHERE datname = $1",
                    self.db_config.name
                )
                
                if result:
                    logger.info(f"✅ Base de datos {self.db_config.name} ya existe")
                else:
                    # Crear base de datos
                    await conn.execute(f'CREATE DATABASE "{self.db_config.name}"')
                    logger.info(f"✅ Base de datos {self.db_config.name} creada")
                    
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error creando base de datos: {e}")
            raise
    
    async def create_tables(self):
        """Crear todas las tablas necesarias"""
        logger.info("📋 Creando tablas...")
        
        conn = await asyncpg.connect(self.db_config.connection_string)
        
        try:
            # Habilitar extensiones necesarias
            await self._enable_extensions(conn)
            
            # Crear tablas en orden de dependencias
            await self._create_users_table(conn)
            await self._create_incidencias_table(conn)
            await self._create_audit_table(conn)
            
            logger.info("✅ Todas las tablas creadas correctamente")
            
        finally:
            await conn.close()
    
    async def _enable_extensions(self, conn):
        """Habilitar extensiones de PostgreSQL"""
        extensions = [
            "CREATE EXTENSION IF NOT EXISTS pg_trgm;",  # Para búsqueda de similitud
            "CREATE EXTENSION IF NOT EXISTS unaccent;",  # Para búsqueda sin acentos
        ]
        
        for extension in extensions:
            try:
                await conn.execute(extension)
                logger.debug(f"✅ Extensión habilitada: {extension}")
            except Exception as e:
                logger.warning(f"⚠️ No se pudo habilitar extensión: {e}")
    
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
            preguntas_realizadas TEXT[], -- Array de preguntas hechas
            respuestas_usuario JSONB DEFAULT '{}', -- Respuestas del usuario
            intentos_resolucion INTEGER DEFAULT 0,
            escalado_a VARCHAR(100), -- A quién se escaló
            notas_internas TEXT,
            
            -- Constraints
            CONSTRAINT incidencias_descripcion_valida CHECK (LENGTH(descripcion) >= 10),
            CONSTRAINT incidencias_ticket_valido CHECK (numero_ticket ~ '^INC-[0-9]{8}-[A-Z0-9]{8}$'),
            CONSTRAINT incidencias_tiempo_resolucion_positivo CHECK (tiempo_resolucion_minutos > 0)
        );
        """
        
        await conn.execute(create_table_sql)
        logger.info("✅ Tabla 'incidencias' creada")
    
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
            timestamp_accion TIMESTAMP DEFAULT NOW(),
            
            -- Índice para búsquedas frecuentes
            INDEX idx_auditoria_tabla_registro (tabla_afectada, registro_id),
            INDEX idx_auditoria_timestamp (timestamp_accion)
        );
        """
        
        await conn.execute(create_table_sql)
        logger.info("✅ Tabla 'auditoria' creada")
    
    async def create_indexes(self):
        """Crear índices para optimización"""
        logger.info("📋 Creando índices de optimización...")
        
        conn = await asyncpg.connect(self.db_config.connection_string)
        
        try:
            indexes = [
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
                
                # Índice para búsqueda de texto en descripción
                "CREATE INDEX IF NOT EXISTS idx_incidencias_descripcion_busqueda ON incidencias USING gin (to_tsvector('spanish', descripcion));",
            ]
            
            for index_sql in indexes:
                try:
                    await conn.execute(index_sql)
                    logger.debug(f"✅ Índice creado: {index_sql[:50]}...")
                except Exception as e:
                    logger.warning(f"⚠️ Error creando índice: {e}")
            
            logger.info("✅ Índices de optimización creados")
            
        finally:
            await conn.close()
    
    async def insert_sample_data(self):
        """Insertar datos de prueba"""
        logger.info("📋 Insertando datos de prueba...")
        
        conn = await asyncpg.connect(self.db_config.connection_string)
        
        try:
            # Verificar si ya hay datos
            user_count = await conn.fetchval("SELECT COUNT(*) FROM usuarios")
            
            if user_count > 0:
                logger.info(f"✅ Ya existen {user_count} usuarios, omitiendo datos de prueba")
                return
            
            # Insertar usuarios de prueba
            await self._insert_sample_users(conn)
            
            # Insertar incidencias de prueba
            await self._insert_sample_incidencias(conn)
            
            logger.info("✅ Datos de prueba insertados")
            
        finally:
            await conn.close()
    
    async def _insert_sample_users(self, conn):
        """Insertar usuarios de prueba"""
        users_data = [
            {
                "nombre": "Juan",
                "apellido": "Pérez García", 
                "email": "juan.perez@empresa.com",
                "numero_empleado": "EMP001",
                "rol": "empleado",
                "departamento": "Desarrollo"
            },
            {
                "nombre": "María",
                "apellido": "González López",
                "email": "maria.gonzalez@empresa.com", 
                "numero_empleado": "EMP002",
                "rol": "empleado",
                "departamento": "Marketing"
            },
            {
                "nombre": "Carlos",
                "apellido": "Rodríguez Sánchez",
                "email": "carlos.rodriguez@empresa.com",
                "numero_empleado": "SUP001", 
                "rol": "supervisor",
                "departamento": "IT"
            },
            {
                "nombre": "Ana",
                "apellido": "Martínez Torres",
                "email": "ana.martinez@empresa.com",
                "numero_empleado": "EMP003",
                "rol": "empleado", 
                "departamento": "Ventas"
            },
            {
                "nombre": "Luis",
                "apellido": "Fernández Ruiz",
                "email": "luis.fernandez@empresa.com",
                "numero_empleado": "ADM001",
                "rol": "administrador",
                "departamento": "IT"
            }
        ]
        
        for user_data in users_data:
            await conn.execute("""
                INSERT INTO usuarios (nombre, apellido, email, numero_empleado, rol, departamento)
                VALUES ($1, $2, $3, $4, $5, $6)
            """, 
            user_data["nombre"],
            user_data["apellido"], 
            user_data["email"],
            user_data["numero_empleado"],
            user_data["rol"],
            user_data["departamento"]
            )
        
        logger.info(f"✅ {len(users_data)} usuarios de prueba insertados")
    
    async def _insert_sample_incidencias(self, conn):
        """Insertar incidencias de prueba"""
        # Obtener IDs de usuarios
        users = await conn.fetch("SELECT id, numero_empleado FROM usuarios LIMIT 3")
        
        incidencias_data = [
            {
                "usuario_id": users[0]["id"],
                "numero_ticket": "INC-20241201-ABC12345",
                "tipo": "hardware",
                "descripcion": "Mi computadora se está ejecutando muy lenta desde esta mañana",
                "prioridad": "media",
                "estado": "abierta"
            },
            {
                "usuario_id": users[1]["id"], 
                "numero_ticket": "INC-20241201-DEF67890",
                "tipo": "software",
                "descripcion": "No puedo abrir Microsoft Excel, aparece un error",
                "prioridad": "alta",
                "estado": "en_progreso"
            },
            {
                "usuario_id": users[2]["id"] if len(users) > 2 else users[0]["id"],
                "numero_ticket": "INC-20241130-GHI13579",
                "tipo": "red",
                "descripcion": "Problemas de conexión a internet en mi área",
                "prioridad": "media", 
                "estado": "resuelta",
                "fecha_resolucion": datetime.now(),
                "tiempo_resolucion_minutos": 45
            }
        ]
        
        for inc_data in incidencias_data:
            if "fecha_resolucion" in inc_data:
                await conn.execute("""
                    INSERT INTO incidencias (usuario_id, numero_ticket, tipo, descripcion, prioridad, estado, fecha_resolucion, tiempo_resolucion_minutos)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                inc_data["usuario_id"],
                inc_data["numero_ticket"],
                inc_data["tipo"],
                inc_data["descripcion"],
                inc_data["prioridad"],
                inc_data["estado"],
                inc_data["fecha_resolucion"],
                inc_data["tiempo_resolucion_minutos"]
                )
            else:
                await conn.execute("""
                    INSERT INTO incidencias (usuario_id, numero_ticket, tipo, descripcion, prioridad, estado)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """,
                inc_data["usuario_id"],
                inc_data["numero_ticket"],
                inc_data["tipo"],
                inc_data["descripcion"],
                inc_data["prioridad"],
                inc_data["estado"]
                )
        
        logger.info(f"✅ {len(incidencias_data)} incidencias de prueba insertadas")
    
    async def verify_setup(self):
        """Verificar que la configuración sea correcta"""
        logger.info("🔍 Verificando configuración de base de datos...")
        
        conn = await asyncpg.connect(self.db_config.connection_string)
        
        try:
            # Verificar tablas
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
            """)
            
            table_names = [table["table_name"] for table in tables]
            expected_tables = ["usuarios", "incidencias", "auditoria"]
            
            for expected_table in expected_tables:
                if expected_table in table_names:
                    logger.info(f"✅ Tabla '{expected_table}' existe")
                else:
                    raise Exception(f"Tabla '{expected_table}' no encontrada")
            
            # Verificar datos
            user_count = await conn.fetchval("SELECT COUNT(*) FROM usuarios")
            inc_count = await conn.fetchval("SELECT COUNT(*) FROM incidencias")
            
            logger.info(f"📊 Datos verificados: {user_count} usuarios, {inc_count} incidencias")
            
            # Test de consulta con similitud
            try:
                similar_users = await conn.fetch("""
                    SELECT nombre, apellido, similarity(nombre || ' ' || apellido, 'Juan Perez') as sim
                    FROM usuarios 
                    WHERE similarity(nombre || ' ' || apellido, 'Juan Perez') > 0.1
                    ORDER BY sim DESC
                    LIMIT 3
                """)
                
                logger.info(f"✅ Búsqueda por similitud funciona: {len(similar_users)} resultados")
                
            except Exception as e:
                logger.warning(f"⚠️ Búsqueda por similitud no disponible: {e}")
            
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
    print("🗄️ Configurador de Base de Datos del Chatbot")
    print("=" * 50)
    
    success = await setup_database()
    
    if success:
        print("\n🎉 ¡Configuración completada exitosamente!")
        print("🚀 Puedes ejecutar la aplicación con: python main.py")
    else:
        print("\n❌ Configuración falló. Revisa los logs para más detalles.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())