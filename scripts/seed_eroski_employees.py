# =====================================================
# scripts/seed_eroski_employees.py - Poblar BD con empleados Eroski
# =====================================================
"""
Script para poblar la base de datos con empleados de ejemplo específicos de Eroski.

EMPLEADOS DE EJEMPLO:
- Empleados de diferentes tiendas
- Diversos departamentos y roles
- Datos realistas de Eroski
- Diferentes niveles de acceso
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Agregar el directorio raíz al path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from utils.database.connection_manager import get_connection_manager
from models.user import UsuarioCreate, RolUsuario
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SeedEroskiEmployees")

async def seed_eroski_employees():
    """Poblar base de datos con empleados de ejemplo de Eroski"""
    
    logger.info("🌱 Iniciando poblado de empleados de Eroski...")
    
    try:
        # Obtener connection manager
        connection_manager = await get_connection_manager()
        user_repository = connection_manager.get_user_repository()
        
        # Definir empleados de ejemplo
        eroski_employees = [
            # ========== OFICINAS CENTRALES ELORRIO ==========
            {
                "nombre": "Juan Carlos",
                "apellido": "Pérez García",
                "email": "juan.perez@eroski.es",
                "numero_empleado": "ERO001",
                "departamento": "Desarrollo",
                "rol": RolUsuario.EMPLEADO
            },
            {
                "nombre": "María",
                "apellido": "González López",
                "email": "maria.gonzalez@eroski.es", 
                "numero_empleado": "ERO002",
                "departamento": "Marketing",
                "rol": RolUsuario.EMPLEADO
            },
            {
                "nombre": "Ana",
                "apellido": "Supervisor Técnica",
                "email": "ana.supervisor@eroski.es",
                "numero_empleado": "ERO003",
                "departamento": "Desarrollo",
                "rol": RolUsuario.SUPERVISOR
            },
            {
                "nombre": "Carlos",
                "apellido": "Director IT", 
                "email": "carlos.director@eroski.es",
                "numero_empleado": "ERO004",
                "departamento": "Desarrollo",
                "rol": RolUsuario.ADMINISTRADOR
            },
            
            # ========== EROSKI BILBAO CENTRO ==========
            {
                "nombre": "Mikel",
                "apellido": "Etxebarria Urrutia",
                "email": "mikel.etxebarria@eroski.es",
                "numero_empleado": "BIL001", 
                "departamento": "Caja",
                "rol": RolUsuario.EMPLEADO
            },
            {
                "nombre": "Ainara",
                "apellido": "Zabala Mendoza",
                "email": "ainara.zabala@eroski.es",
                "numero_empleado": "BIL002",
                "departamento": "Carnicería",
                "rol": RolUsuario.EMPLEADO
            },
            {
                "nombre": "Iker",
                "apellido": "Supervisor Bilbao",
                "email": "iker.supervisor@eroski.es", 
                "numero_empleado": "BIL003",
                "departamento": "Supervisión",
                "rol": RolUsuario.SUPERVISOR
            },
            
            # ========== EROSKI MADRID SALAMANCA ==========
            {
                "nombre": "Carmen",
                "apellido": "Rodríguez Martín",
                "email": "carmen.rodriguez@eroski.es",
                "numero_empleado": "MAD001",
                "departamento": "Pescadería", 
                "rol": RolUsuario.EMPLEADO
            },
            {
                "nombre": "David",
                "apellido": "López Fernández",
                "email": "david.lopez@eroski.es",
                "numero_empleado": "MAD002",
                "departamento": "Frutería",
                "rol": RolUsuario.EMPLEADO
            },
            {
                "nombre": "Laura",
                "apellido": "Supervisor Madrid",
                "email": "laura.supervisor@eroski.es",
                "numero_empleado": "MAD003", 
                "departamento": "Supervisión",
                "rol": RolUsuario.SUPERVISOR
            },
            
            # ========== EROSKI BARCELONA DIAGONAL ==========
            {
                "nombre": "Jordi",
                "apellido": "Martínez Puig",
                "email": "jordi.martinez@eroski.es",
                "numero_empleado": "BCN001",
                "departamento": "Panadería",
                "rol": RolUsuario.EMPLEADO
            },
            {
                "nombre": "Montse", 
                "apellido": "Vila Solà",
                "email": "montse.vila@eroski.es",
                "numero_empleado": "BCN002",
                "departamento": "Caja",
                "rol": RolUsuario.EMPLEADO
            },
            
            # ========== EROSKI SEVILLA CENTRO ==========
            {
                "nombre": "José Manuel",
                "apellido": "García Jiménez", 
                "email": "josem.garcia@eroski.es",
                "numero_empleado": "SEV001",
                "departamento": "Almacén",
                "rol": RolUsuario.EMPLEADO
            },
            {
                "nombre": "Rocío",
                "apellido": "Moreno Ruiz",
                "email": "rocio.moreno@eroski.es",
                "numero_empleado": "SEV002",
                "departamento": "Atención al Cliente",
                "rol": RolUsuario.EMPLEADO
            },
            
            # ========== USUARIOS DE PRUEBA ==========
            {
                "nombre": "Admin",
                "apellido": "Test Eroski",
                "email": "admin.test@eroski.es",
                "numero_empleado": "TEST001",
                "departamento": "Desarrollo",
                "rol": RolUsuario.ADMINISTRADOR
            },
            {
                "nombre": "Usuario",
                "apellido": "Test Demo",
                "email": "demo.user@eroski.es", 
                "numero_empleado": "TEST002",
                "departamento": "Caja",
                "rol": RolUsuario.EMPLEADO
            }
        ]
        
        # Crear empleados en la base de datos
        created_count = 0
        skipped_count = 0
        
        for emp_data in eroski_employees:
            try:
                # Verificar si ya existe
                existing = await user_repository.obtener_por_email(emp_data["email"])
                
                if existing:
                    logger.info(f"⏭️ Empleado ya existe: {emp_data['email']}")
                    skipped_count += 1
                    continue
                
                # Crear nuevo empleado
                usuario_create = UsuarioCreate(**emp_data)
                nuevo_usuario = await user_repository.crear_usuario(usuario_create)
                
                if nuevo_usuario:
                    logger.info(f"✅ Empleado creado: {nuevo_usuario.nombre_completo} ({nuevo_usuario.email})")
                    created_count += 1
                else:
                    logger.warning(f"⚠️ No se pudo crear empleado: {emp_data['email']}")
                    
            except Exception as e:
                logger.error(f"❌ Error creando empleado {emp_data['email']}: {e}")
        
        # Resumen final
        logger.info(f"""
🎉 Poblado de empleados completado:
✅ Empleados creados: {created_count}
⏭️ Empleados existentes: {skipped_count}
📊 Total procesados: {len(eroski_employees)}
""")
        
        # Mostrar estadísticas de la BD
        await show_database_stats(user_repository)
        
    except Exception as e:
        logger.error(f"❌ Error en poblado de empleados: {e}")
        raise

async def show_database_stats(user_repository):
    """Mostrar estadísticas de la base de datos"""
    try:
        logger.info("📊 Estadísticas de la base de datos:")
        
        # Contar empleados por departamento
        # TODO: Implementar método de estadísticas en UserRepository
        # Por ahora, información básica
        
        logger.info("📋 Base de datos poblada con empleados de Eroski")
        logger.info("🏪 Tiendas representadas: Bilbao, Madrid, Barcelona, Sevilla")
        logger.info("👥 Departamentos: Desarrollo, Caja, Carnicería, Pescadería, etc.")
        logger.info("🔑 Roles: Empleados, Supervisores, Administradores")
        
    except Exception as e:
        logger.warning(f"⚠️ Error mostrando estadísticas: {e}")

async def clear_all_employees():
    """CUIDADO: Eliminar todos los empleados de la BD (solo para testing)"""
    logger.warning("⚠️ ELIMINAR TODOS LOS EMPLEADOS - Solo para testing")
    
    response = input("¿Estás seguro de que quieres eliminar TODOS los empleados? (escribir 'SI ELIMINAR'): ")
    
    if response != "SI ELIMINAR":
        logger.info("❌ Operación cancelada")
        return
    
    try:
        connection_manager = await get_connection_manager()
        
        # Ejecutar DELETE directamente (cuidado!)
        async with connection_manager.get_connection() as conn:
            result = await conn.execute("DELETE FROM usuarios")
            logger.warning(f"🗑️ Empleados eliminados: {result}")
            
    except Exception as e:
        logger.error(f"❌ Error eliminando empleados: {e}")

def main():
    """Función principal"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Poblar BD con empleados de Eroski")
    parser.add_argument("--clear", action="store_true", help="Eliminar todos los empleados (CUIDADO)")
    parser.add_argument("--seed", action="store_true", default=True, help="Poblar con empleados de ejemplo")
    
    args = parser.parse_args()
    
    if args.clear:
        asyncio.run(clear_all_employees())
    elif args.seed:
        asyncio.run(seed_eroski_employees())
    else:
        print("Uso: python scripts/seed_eroski_employees.py [--seed|--clear]")

if __name__ == "__main__":
    main()