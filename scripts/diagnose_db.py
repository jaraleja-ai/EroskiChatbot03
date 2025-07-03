# =====================================================
# scripts/diagnose_db.py - Diagnóstico de Base de Datos
# =====================================================
"""
Script para diagnosticar la estructura actual de la base de datos
y detectar problemas antes de ejecutar seeders.
"""

import asyncio
import asyncpg
import logging
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DBDiagnosis")

class DatabaseDiagnostic:
    """Diagnosticador de base de datos"""
    
    def __init__(self):
        # Configuración de BD
        self.db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 5432)),
            "database": os.getenv("DB_NAME", "chatbot_db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "password123")
        }
    
    @property
    def connection_string(self) -> str:
        """Construir string de conexión"""
        return (f"postgresql://{self.db_config['user']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
    
    async def run_full_diagnosis(self) -> bool:
        """Ejecutar diagnóstico completo"""
        try:
            logger.info("🔍 Iniciando diagnóstico completo de base de datos...")
            
            # 1. Verificar conectividad
            if not await self.check_connectivity():
                return False
            
            # 2. Listar todas las tablas
            await self.list_tables()
            
            # 3. Verificar estructura de usuarios
            await self.check_usuarios_structure()
            
            # 4. Verificar estructura de incidencias
            await self.check_incidencias_structure()
            
            # 5. Verificar datos existentes
            await self.check_existing_data()
            
            # 6. Probar inserción simple
            await self.test_simple_insert()
            
            logger.info("✅ Diagnóstico completado")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error en diagnóstico: {e}")
            return False
    
    async def check_connectivity(self) -> bool:
        """Verificar conectividad a la base de datos"""
        try:
            logger.info("🔗 Verificando conectividad...")
            
            conn = await asyncpg.connect(self.connection_string)
            
            # Test simple
            result = await conn.fetchval("SELECT 1")
            await conn.close()
            
            if result == 1:
                logger.info("✅ Conectividad exitosa")
                return True
            else:
                logger.error("❌ Problema en conectividad")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error de conectividad: {e}")
            return False
    
    async def list_tables(self) -> List[str]:
        """Listar todas las tablas"""
        try:
            logger.info("📋 Listando todas las tablas...")
            
            conn = await asyncpg.connect(self.connection_string)
            
            try:
                tables = await conn.fetch("""
                    SELECT table_name, table_type
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                
                table_names = []
                logger.info("📊 Tablas encontradas:")
                for table in tables:
                    logger.info(f"   📄 {table['table_name']} ({table['table_type']})")
                    table_names.append(table['table_name'])
                
                return table_names
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error listando tablas: {e}")
            return []
    
    async def check_usuarios_structure(self) -> Dict[str, Any]:
        """Verificar estructura de la tabla usuarios"""
        try:
            logger.info("👥 Verificando estructura de tabla 'usuarios'...")
            
            conn = await asyncpg.connect(self.connection_string)
            
            try:
                # Verificar si la tabla existe
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = 'usuarios'
                    );
                """)
                
                if not table_exists:
                    logger.error("❌ La tabla 'usuarios' no existe")
                    return {"exists": False}
                
                # Obtener estructura de columnas
                columns = await conn.fetch("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = 'usuarios'
                    ORDER BY ordinal_position
                """)
                
                logger.info("📋 Estructura de tabla 'usuarios':")
                column_info = {}
                for col in columns:
                    nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                    default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                    logger.info(f"   📝 {col['column_name']}: {col['data_type']} {nullable}{default}")
                    column_info[col['column_name']] = {
                        "type": col['data_type'],
                        "nullable": col['is_nullable'] == 'YES',
                        "default": col['column_default']
                    }
                
                # Verificar columnas específicas que necesitamos
                required_columns = ['id', 'nombre', 'apellido', 'email', 'numero_empleado', 'rol', 'departamento']
                missing_columns = []
                
                for req_col in required_columns:
                    if req_col not in column_info:
                        missing_columns.append(req_col)
                
                if missing_columns:
                    logger.warning(f"⚠️ Columnas faltantes: {missing_columns}")
                else:
                    logger.info("✅ Todas las columnas requeridas están presentes")
                
                return {
                    "exists": True,
                    "columns": column_info,
                    "missing_columns": missing_columns
                }
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error verificando usuarios: {e}")
            return {"exists": False, "error": str(e)}
    
    async def check_incidencias_structure(self) -> Dict[str, Any]:
        """Verificar estructura de la tabla incidencias"""
        try:
            logger.info("🎫 Verificando estructura de tabla 'incidencias'...")
            
            conn = await asyncpg.connect(self.connection_string)
            
            try:
                # Verificar si la tabla existe
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = 'incidencias'
                    );
                """)
                
                if not table_exists:
                    logger.warning("⚠️ La tabla 'incidencias' no existe")
                    return {"exists": False}
                
                # Obtener estructura de columnas
                columns = await conn.fetch("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = 'incidencias'
                    ORDER BY ordinal_position
                """)
                
                logger.info("📋 Estructura de tabla 'incidencias':")
                column_info = {}
                for col in columns:
                    nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                    default = f" DEFAULT {col['column_default']}" if col['column_default'] else ""
                    logger.info(f"   📝 {col['column_name']}: {col['data_type']} {nullable}{default}")
                    column_info[col['column_name']] = {
                        "type": col['data_type'],
                        "nullable": col['is_nullable'] == 'YES',
                        "default": col['column_default']
                    }
                
                return {
                    "exists": True,
                    "columns": column_info
                }
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error verificando incidencias: {e}")
            return {"exists": False, "error": str(e)}
    
    async def check_existing_data(self) -> Dict[str, int]:
        """Verificar datos existentes"""
        try:
            logger.info("📊 Verificando datos existentes...")
            
            conn = await asyncpg.connect(self.connection_string)
            
            try:
                data_counts = {}
                
                # Contar usuarios
                try:
                    user_count = await conn.fetchval("SELECT COUNT(*) FROM usuarios")
                    data_counts['usuarios'] = user_count
                    logger.info(f"👥 Usuarios existentes: {user_count}")
                except Exception as e:
                    logger.warning(f"⚠️ Error contando usuarios: {e}")
                    data_counts['usuarios'] = -1
                
                # Contar incidencias
                try:
                    inc_count = await conn.fetchval("SELECT COUNT(*) FROM incidencias")
                    data_counts['incidencias'] = inc_count
                    logger.info(f"🎫 Incidencias existentes: {inc_count}")
                except Exception as e:
                    logger.warning(f"⚠️ Error contando incidencias: {e}")
                    data_counts['incidencias'] = -1
                
                # Mostrar algunos usuarios existentes
                if data_counts.get('usuarios', 0) > 0:
                    try:
                        usuarios_sample = await conn.fetch("""
                            SELECT nombre, apellido, email, rol, departamento
                            FROM usuarios 
                            LIMIT 5
                        """)
                        
                        logger.info("👤 Muestra de usuarios existentes:")
                        for user in usuarios_sample:
                            logger.info(f"   📧 {user['email']} - {user['nombre']} {user['apellido']} ({user['rol']})")
                    except Exception as e:
                        logger.warning(f"⚠️ Error obteniendo muestra: {e}")
                
                return data_counts
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error verificando datos: {e}")
            return {}
    
    async def test_simple_insert(self) -> bool:
        """Probar inserción simple"""
        try:
            logger.info("🧪 Probando inserción simple...")
            
            conn = await asyncpg.connect(self.connection_string)
            
            try:
                # Probar inserción de usuario de prueba
                test_email = "test.diagnosis@example.com"
                
                # Primero eliminar si existe
                await conn.execute("DELETE FROM usuarios WHERE email = $1", test_email)
                
                # Intentar inserción básica
                query = """
                    INSERT INTO usuarios (nombre, apellido, email, numero_empleado, rol, departamento)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                """
                
                result = await conn.fetchval(
                    query,
                    "Test",
                    "Diagnosis",
                    test_email,
                    "TEST001",
                    "empleado",
                    "Testing"
                )
                
                if result:
                    logger.info(f"✅ Inserción exitosa - ID: {result}")
                    
                    # Limpiar
                    await conn.execute("DELETE FROM usuarios WHERE id = $1", result)
                    logger.info("🧹 Registro de prueba eliminado")
                    
                    return True
                else:
                    logger.error("❌ Inserción falló - no se devolvió ID")
                    return False
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error en inserción de prueba: {e}")
            logger.error(f"📋 Detalles del error: {type(e).__name__}: {str(e)}")
            return False
    
    async def suggest_fixes(self) -> None:
        """Sugerir correcciones basadas en el diagnóstico"""
        logger.info("\n💡 SUGERENCIAS DE CORRECCIÓN:")
        logger.info("=" * 50)
        
        # Verificar estructura actual
        usuarios_info = await self.check_usuarios_structure()
        
        if not usuarios_info.get("exists", False):
            logger.info("🔧 La tabla 'usuarios' no existe:")
            logger.info("   ➤ Ejecutar: python -m scripts.setup_db")
            return
        
        missing_columns = usuarios_info.get("missing_columns", [])
        if missing_columns:
            logger.info(f"🔧 Columnas faltantes en 'usuarios': {missing_columns}")
            logger.info("   ➤ Ejecutar: python -m scripts.setup_db")
            return
        
        # Si llegamos aquí, el problema puede ser otro
        logger.info("🔧 Estructura aparenta estar correcta.")
        logger.info("   ➤ Puede ser un problema de permisos o versión de PostgreSQL")
        logger.info("   ➤ Verificar logs detallados arriba para más información")

async def main():
    """Función principal"""
    logger.info("🔍 DIAGNÓSTICO DE BASE DE DATOS")
    logger.info("=" * 50)
    
    diagnostic = DatabaseDiagnostic()
    
    # Ejecutar diagnóstico completo
    success = await diagnostic.run_full_diagnosis()
    
    if not success:
        await diagnostic.suggest_fixes()
        return False
    
    # Sugerir siguientes pasos
    logger.info("\n🎯 PRÓXIMOS PASOS:")
    logger.info("=" * 30)
    logger.info("✅ La base de datos parece estar correcta")
    logger.info("➤ Intenta ejecutar el seeder nuevamente:")
    logger.info("   python -m scripts.seed_eroski_employees")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)