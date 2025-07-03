# force_env_override.py - Forzar que .env sobrescriba variables del sistema
import os
import asyncio
from pathlib import Path

def force_env_override():
    """Forzar que las variables del .env sobrescriban las del sistema"""
    
    print("🔧 FORZANDO OVERRIDE DE VARIABLES DEL SISTEMA")
    print("=" * 50)
    
    # 1. Mostrar variables actuales del sistema
    print("1️⃣ Variables actuales del sistema:")
    system_vars = {}
    db_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    
    for var in db_vars:
        value = os.getenv(var)
        system_vars[var] = value
        if value:
            if 'PASSWORD' in var:
                print(f"   🔒 {var}=***hidden*** (sistema)")
            else:
                print(f"   🔒 {var}={value} (sistema)")
        else:
            print(f"   ⚪ {var}=<no definida>")
    
    # 2. Leer archivo .env manualmente
    print(f"\n2️⃣ Leyendo archivo .env...")
    env_file = Path('.env')
    env_vars = {}
    
    if env_file.exists():
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    
                    if key.startswith('DB_'):
                        env_vars[key] = value
                        if 'PASSWORD' in key:
                            print(f"   📁 {key}=***hidden*** (.env)")
                        else:
                            print(f"   📁 {key}={value} (.env)")
            
        except Exception as e:
            print(f"   ❌ Error leyendo .env: {e}")
            return False
    else:
        print(f"   ❌ Archivo .env no encontrado")
        return False
    
    # 3. Comparar y sobrescribir
    print(f"\n3️⃣ Aplicando override...")
    
    changes_made = False
    for var in db_vars:
        system_value = system_vars.get(var)
        env_value = env_vars.get(var)
        
        if env_value and env_value != system_value:
            print(f"   🔄 {var}: '{system_value}' → '{env_value}'")
            os.environ[var] = env_value
            changes_made = True
        elif env_value:
            print(f"   ✅ {var}: sin cambios")
        else:
            print(f"   ⚠️ {var}: no definida en .env")
    
    if not changes_made:
        print(f"   ⚪ No se hicieron cambios")
    
    # 4. Verificar resultado final
    print(f"\n4️⃣ Variables finales:")
    all_good = True
    
    for var in db_vars:
        value = os.getenv(var)
        if value:
            if 'PASSWORD' in var:
                print(f"   ✅ {var}=***hidden***")
            else:
                print(f"   ✅ {var}={value}")
        else:
            print(f"   ❌ {var}=<no definida>")
            all_good = False
    
    return all_good

async def test_with_overridden_vars():
    """Probar conexión con variables sobrescritas"""
    
    print(f"\n5️⃣ PROBANDO CONEXIÓN CON VARIABLES CORREGIDAS")
    print("=" * 50)
    
    try:
        # Recargar configuración para que use las nuevas variables
        import sys
        if 'config.settings' in sys.modules:
            import importlib
            importlib.reload(sys.modules['config.settings'])
        
        from config.settings import get_settings
        settings = get_settings()
        db_config = settings.database
        
        print(f"📊 Configuración actual:")
        print(f"   Host: {db_config.host}")
        print(f"   Port: {db_config.port}")
        print(f"   Database: {db_config.name}")  # 🔥 Debería ser chatbot_db
        print(f"   User: {db_config.user}")
        
        if db_config.name != 'chatbot_db':
            print(f"   ❌ PROBLEMA: Database sigue siendo '{db_config.name}' en lugar de 'chatbot_db'")
            print(f"   💡 Verifica que DB_NAME=chatbot_db esté en tu .env")
            return False
        
        # Probar conexión
        import asyncpg
        
        print(f"\n🔌 Conectando a {db_config.name}...")
        conn = await asyncpg.connect(
            host=db_config.host,
            port=db_config.port,
            user=db_config.user,
            password=db_config.password,
            database=db_config.name
        )
        
        print(f"✅ Conexión exitosa a {db_config.name}")
        
        # Buscar usuario específico
        target_email = "maria.gonzalez.ero001@eroski.es"
        print(f"🔍 Buscando: {target_email}")
        
        user = await conn.fetchrow("""
            SELECT nombre, apellido, email, activo
            FROM usuarios 
            WHERE LOWER(email) = LOWER($1)
        """, target_email)
        
        if user:
            status = "✅" if user['activo'] else "⚠️"
            print(f"🎉 USUARIO ENCONTRADO EN chatbot_db:")
            print(f"   {status} {user['nombre']} {user['apellido']}")
            print(f"   📧 {user['email']}")
            print(f"   🟢 Activo: {user['activo']}")
            
            await conn.close()
            return True
        else:
            print(f"❌ Usuario no encontrado en chatbot_db")
            
            # Mostrar algunos usuarios para referencia
            users = await conn.fetch("""
                SELECT nombre, apellido, email, activo
                FROM usuarios 
                WHERE activo = true
                LIMIT 3
            """)
            
            if users:
                print(f"\n👥 Usuarios disponibles en chatbot_db:")
                for u in users:
                    print(f"   ✅ {u['nombre']} {u['apellido']} - {u['email']}")
            else:
                print(f"⚠️ No hay usuarios activos en chatbot_db")
            
            await conn.close()
            return False
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

async def main():
    """Función principal"""
    
    # Forzar override
    success = force_env_override()
    
    if success:
        # Probar conexión
        connection_ok = await test_with_overridden_vars()
        
        if connection_ok:
            print(f"\n🎉 ¡PERFECTO! PROBLEMA RESUELTO")
            print(f"✅ Variables corregidas")
            print(f"✅ Conexión a chatbot_db exitosa")
            print(f"✅ Usuario encontrado")
            print(f"\n🚀 Ahora puedes ejecutar:")
            print(f"   chainlit run interfaces/chainlit_app.py --debug --port 8000")
        else:
            print(f"\n⚠️ Variables corregidas pero hay otros problemas")
    else:
        print(f"\n❌ No se pudieron corregir las variables")
        print(f"💡 Verifica tu archivo .env")

if __name__ == "__main__":
    asyncio.run(main())