# =====================================================
# scripts/quick_db_check.py - Verificación Rápida de BD
# =====================================================

import asyncio
import asyncpg
import os
from pathlib import Path

async def check_database():
    """Verificar conexión y estado de la base de datos"""
    
    # Configuración desde variables de entorno
    db_config = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", "password123"),
        "database": os.getenv("DB_NAME", "chatbot_db")
    }
    
    print("🔍 VERIFICACIÓN RÁPIDA DE BASE DE DATOS")
    print("=" * 50)
    print(f"Host: {db_config['host']}")
    print(f"Puerto: {db_config['port']}")
    print(f"Usuario: {db_config['user']}")
    print(f"Base de datos: {db_config['database']}")
    print()
    
    # 1. Verificar conexión a postgres (BD por defecto)
    try:
        print("1️⃣ Verificando conexión a PostgreSQL...")
        conn = await asyncpg.connect(
            host=db_config["host"],
            port=db_config["port"],
            user=db_config["user"],
            password=db_config["password"],
            database="postgres"  # BD por defecto
        )
        
        version = await conn.fetchval("SELECT version()")
        print(f"✅ PostgreSQL conectado: {version.split(',')[0]}")
        
        # Listar bases de datos
        databases = await conn.fetch("SELECT datname FROM pg_database WHERE datistemplate = false")
        db_names = [db['datname'] for db in databases]
        print(f"📋 Bases de datos existentes: {db_names}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error conectando a PostgreSQL: {e}")
        return False
    
    # 2. Verificar si nuestra BD existe
    target_db = db_config["database"]
    if target_db in db_names:
        print(f"✅ La base de datos '{target_db}' existe")
        
        # 3. Verificar conexión a nuestra BD
        try:
            print(f"2️⃣ Conectando a '{target_db}'...")
            conn = await asyncpg.connect(**db_config)
            
            # Verificar tablas
            tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
            """)
            table_names = [t['table_name'] for t in tables]
            print(f"📊 Tablas encontradas: {table_names}")
            
            # Contar registros si hay tablas
            if 'usuarios' in table_names:
                user_count = await conn.fetchval("SELECT COUNT(*) FROM usuarios")
                print(f"👥 Usuarios: {user_count}")
            
            if 'incidencias' in table_names:
                inc_count = await conn.fetchval("SELECT COUNT(*) FROM incidencias")
                print(f"🎫 Incidencias: {inc_count}")
            
            await conn.close()
            print("✅ Todo está funcionando correctamente")
            return True
            
        except Exception as e:
            print(f"❌ Error conectando a '{target_db}': {e}")
            return False
    else:
        print(f"❌ La base de datos '{target_db}' NO existe")
        
        # 4. Ofrecer crearla
        respuesta = input(f"¿Crear la base de datos '{target_db}'? (s/n): ").lower().strip()
        
        if respuesta in ['s', 'si', 'sí', 'y', 'yes']:
            try:
                print(f"🔧 Creando base de datos '{target_db}'...")
                conn = await asyncpg.connect(
                    host=db_config["host"],
                    port=db_config["port"],
                    user=db_config["user"],
                    password=db_config["password"],
                    database="postgres"
                )
                
                await conn.execute(f'CREATE DATABASE "{target_db}"')
                await conn.close()
                
                print(f"✅ Base de datos '{target_db}' creada exitosamente")
                print("💡 Ahora ejecuta: python -m scripts.setup_db")
                return True
                
            except Exception as e:
                print(f"❌ Error creando BD: {e}")
                return False
        else:
            print("❌ Base de datos no creada")
            return False

if __name__ == "__main__":
    # Cargar variables de entorno desde .env si existe
    env_file = Path(".env")
    if env_file.exists():
        print("📋 Cargando configuración desde .env...")
        with open(env_file) as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    else:
        print("⚠️ Archivo .env no encontrado, usando valores por defecto")
    
    success = asyncio.run(check_database())
    
    if success:
        print("\n🎯 PRÓXIMOS PASOS:")
        print("1. Si las tablas no existen: python -m scripts.setup_db")
        print("2. Para cargar empleados: python -m scripts.seed_eroski_employees")
    else:
        print("\n❌ Hay problemas de configuración que resolver")