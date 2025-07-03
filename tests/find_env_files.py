# find_env_files.py - Buscar todos los archivos .env
import os
import sys
from pathlib import Path

def find_env_files():
    """Buscar todos los archivos .env posibles"""
    
    print("🔍 BUSCANDO ARCHIVOS .env")
    print("=" * 40)
    
    # 1. Directorio actual
    current_dir = Path.cwd()
    print(f"📁 Directorio actual: {current_dir}")
    
    # 2. Buscar .env en directorio actual
    print(f"\n1️⃣ Archivos .env en directorio actual:")
    env_files_current = list(current_dir.glob(".env*"))
    
    if env_files_current:
        for env_file in env_files_current:
            print(f"   ✅ {env_file}")
            if env_file.name == ".env":
                print(f"      📝 Contenido:")
                try:
                    with open(env_file, 'r') as f:
                        lines = f.readlines()
                    
                    for line in lines[:10]:  # Primeras 10 líneas
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if 'PASSWORD' in line:
                                parts = line.split('=', 1)
                                if len(parts) > 1:
                                    print(f"         {parts[0]}=***hidden***")
                            else:
                                print(f"         {line}")
                                
                except Exception as e:
                    print(f"      ❌ Error leyendo: {e}")
    else:
        print("   ❌ No se encontraron archivos .env")
    
    # 3. Buscar en directorios padre
    print(f"\n2️⃣ Buscando en directorios padre:")
    parent_dirs = [current_dir.parent, current_dir.parent.parent]
    
    for parent_dir in parent_dirs:
        if parent_dir.exists():
            env_files_parent = list(parent_dir.glob(".env*"))
            if env_files_parent:
                print(f"   📁 {parent_dir}:")
                for env_file in env_files_parent:
                    print(f"      ✅ {env_file}")
    
    # 4. Variables de entorno del sistema
    print(f"\n3️⃣ Variables de entorno del sistema:")
    db_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    
    for var in db_vars:
        value = os.getenv(var)
        if value:
            if 'PASSWORD' in var:
                print(f"   ✅ {var}=***hidden***")
            else:
                print(f"   ✅ {var}={value}")
        else:
            print(f"   ❌ {var}=<no definida>")
    
    # 5. Verificar dotenv
    print(f"\n4️⃣ Verificando carga de python-dotenv:")
    try:
        from dotenv import load_dotenv, find_dotenv
        
        # Buscar .env automáticamente
        dotenv_path = find_dotenv()
        if dotenv_path:
            print(f"   ✅ python-dotenv encontró: {dotenv_path}")
        else:
            print(f"   ❌ python-dotenv no encontró archivo .env")
        
        # Cargar manualmente desde directorio actual
        current_env = current_dir / ".env"
        if current_env.exists():
            print(f"   🔧 Cargando manualmente: {current_env}")
            load_dotenv(current_env)
            
            # Verificar variables después de cargar
            print(f"   📊 Variables después de cargar:")
            for var in db_vars:
                value = os.getenv(var)
                if value:
                    if 'PASSWORD' in var:
                        print(f"      ✅ {var}=***hidden***")
                    else:
                        print(f"      ✅ {var}={value}")
                else:
                    print(f"      ❌ {var}=<no definida>")
                    
    except ImportError:
        print(f"   ❌ python-dotenv no está instalado")
    except Exception as e:
        print(f"   ❌ Error con dotenv: {e}")
    
    # 6. Verificar configuración de settings
    print(f"\n5️⃣ Verificando configuración actual:")
    try:
        # Importar después de cargar .env
        from config.settings import get_settings
        
        settings = get_settings()
        db_config = settings.database
        
        print(f"   📊 Configuración cargada:")
        print(f"      Host: {db_config.host}")
        print(f"      Port: {db_config.port}")
        print(f"      Database: {db_config.name}")  # 🔥 ESTA ES LA CLAVE
        print(f"      User: {db_config.user}")
        
    except Exception as e:
        print(f"   ❌ Error cargando settings: {e}")
    
    # 7. Instrucciones de corrección
    print(f"\n6️⃣ INSTRUCCIONES DE CORRECCIÓN:")
    print("=" * 30)
    
    current_env_file = current_dir / ".env"
    if current_env_file.exists():
        print(f"✅ Archivo .env encontrado en: {current_env_file}")
        print(f"📝 Para corregir DB_NAME:")
        print(f"   1. Editar: {current_env_file}")
        print(f"   2. Cambiar: DB_NAME=chatbot")
        print(f"   3. Por: DB_NAME=chatbot_db")
        print(f"   4. Guardar y reiniciar aplicación")
    else:
        print(f"❌ No hay archivo .env en directorio actual")
        print(f"💡 Crear archivo .env con:")
        print(f"   DB_HOST=localhost")
        print(f"   DB_PORT=5432")
        print(f"   DB_NAME=chatbot_db")
        print(f"   DB_USER=postgres")
        print(f"   DB_PASSWORD=tu_password")

if __name__ == "__main__":
    find_env_files()