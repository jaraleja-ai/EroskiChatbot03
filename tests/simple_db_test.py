# simple_db_test.py - Test básico de conectividad y datos
import asyncio
import asyncpg
import logging
from config.settings import get_settings

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DatabaseTest")

async def simple_db_test():
    """Test simple de base de datos con logging detallado"""
    settings = get_settings()
    db_config = settings.database
    
    logger.info("🔍 INICIANDO TEST DE BASE DE DATOS")
    
    try:
        # Conectar a la BD
        logger.info(f"📡 Conectando a {db_config.host}:{db_config.port}/{db_config.name}")
        conn = await asyncpg.connect(
            host=db_config.host,
            port=db_config.port,
            user=db_config.user,
            password=db_config.password,
            database=db_config.name
        )
        
        logger.info("✅ CONEXIÓN EXITOSA")
        
        # Test 1: Verificar tabla existe
        logger.info("📋 Verificando tabla usuarios...")
        table_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = 'usuarios'
            )
        """)
        
        if table_exists:
            logger.info("✅ Tabla 'usuarios' existe")
        else:
            logger.error("❌ Tabla 'usuarios' NO existe")
            await conn.close()
            return
        
        # Test 2: Contar usuarios
        logger.info("🔢 Contando usuarios...")
        total_users = await conn.fetchval("SELECT COUNT(*) FROM usuarios")
        active_users = await conn.fetchval("SELECT COUNT(*) FROM usuarios WHERE activo = true")
        
        logger.info(f"📊 Total usuarios: {total_users}")
        logger.info(f"✅ Usuarios activos: {active_users}")
        
        if total_users == 0:
            logger.warning("⚠️ No hay usuarios en la tabla")
            await conn.close()
            return
        
        # Test 3: Obtener primeros 3 usuarios
        logger.info("👥 Obteniendo primeros 3 usuarios...")
        users = await conn.fetch("""
            SELECT id, nombre, apellido, email, numero_empleado, 
                   rol, departamento, activo, created_at, updated_at
            FROM usuarios 
            ORDER BY id 
            LIMIT 3
        """)
        
        if users:
            logger.info(f"✅ Obtenidos {len(users)} usuarios")
            
            for i, user in enumerate(users, 1):
                logger.info(f"👤 USUARIO {i}:")
                logger.info(f"   ID: {user['id']}")
                logger.info(f"   Nombre: {user['nombre']}")
                logger.info(f"   Apellido: {user['apellido']}")
                logger.info(f"   Email: {user['email']}")
                logger.info(f"   Número: {user['numero_empleado']}")
                logger.info(f"   Rol: {user['rol']}")
                logger.info(f"   Departamento: {user['departamento']}")
                logger.info(f"   Activo: {user['activo']}")
                logger.info(f"   Creado: {user['created_at']}")
                
                # También mostrar en consola
                print(f"👤 Usuario {i}: {user['nombre']} {user['apellido']} - {user['email']} - Activo: {user['activo']}")
        else:
            logger.warning("⚠️ No se obtuvieron usuarios")
        
        # Test 4: Buscar el usuario específico
        target_email = "maria.gonzalez.ero001@eroski.es"
        logger.info(f"🔍 Buscando usuario específico: {target_email}")
        
        specific_user = await conn.fetchrow("""
            SELECT id, nombre, apellido, email, numero_empleado, 
                   rol, departamento, activo, created_at, updated_at
            FROM usuarios 
            WHERE email = $1
        """, target_email)
        
        if specific_user:
            logger.info("✅ Usuario específico ENCONTRADO:")
            logger.info(f"   ID: {specific_user['id']}")
            logger.info(f"   Nombre: {specific_user['nombre']}")
            logger.info(f"   Apellido: {specific_user['apellido']}")
            logger.info(f"   Email: {specific_user['email']}")
            logger.info(f"   Activo: {specific_user['activo']}")
            print(f"✅ ENCONTRADO: {specific_user['nombre']} {specific_user['apellido']} - {specific_user['email']}")
        else:
            logger.warning(f"❌ Usuario específico NO encontrado: {target_email}")
            
            # Buscar similares
            logger.info("🔍 Buscando usuarios similares...")
            similar = await conn.fetch("""
                SELECT email, nombre, apellido, activo
                FROM usuarios 
                WHERE email ILIKE '%maria%' OR nombre ILIKE '%maria%'
            """)
            
            if similar:
                logger.info("📧 Usuarios similares encontrados:")
                for user in similar:
                    logger.info(f"   {user['email']} - {user['nombre']} {user['apellido']} - Activo: {user['activo']}")
                    print(f"📧 Similar: {user['email']} - {user['nombre']} {user['apellido']}")
            else:
                logger.info("❌ No se encontraron usuarios similares")
        
        # Test 5: Probar la query exacta del código
        logger.info("🧪 Probando query exacta del código...")
        code_query = """
            SELECT id, nombre, apellido, email, numero_empleado, 
                   rol, departamento, activo, created_at, updated_at
            FROM usuarios 
            WHERE LOWER(email) = LOWER($1) AND activo = true
        """
        
        code_result = await conn.fetchrow(code_query, target_email)
        
        if code_result:
            logger.info("✅ Query del código FUNCIONA")
            logger.info(f"   Encontrado: {code_result['nombre']} {code_result['apellido']}")
            print(f"✅ Query código OK: {code_result['nombre']} {code_result['apellido']}")
        else:
            logger.warning("❌ Query del código NO encuentra usuario")
            print("❌ Query del código falla")
        
        await conn.close()
        logger.info("🔒 Conexión cerrada")
        
    except Exception as e:
        logger.error(f"❌ Error en test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(simple_db_test())