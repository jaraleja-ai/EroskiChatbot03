# debug_specific_user.py - Diagnóstico específico del usuario
import asyncio
import asyncpg
from config.settings import get_settings


async def debug_specific_user():
    """Diagnóstico específico del usuario maria.gonzalez.ero001@eroski.es"""
    settings = get_settings()
    db_config = settings.database
    
    target_email = "maria.gonzalez.ero001@eroski.es"
    

    print(db_config)
    exit()

    try:
        # Conectar a la BD
        conn = await asyncpg.connect(
            host=db_config.host,
            port=db_config.port,
            user=db_config.user,
            password=db_config.password,
            database=db_config.name
        )
        
        print("🔍 DIAGNÓSTICO ESPECÍFICO DEL USUARIO")
        print("=" * 50)
        print(f"📧 Email objetivo: {target_email}")
        
        # 1. Búsqueda exacta
        print(f"\n1️⃣ Búsqueda exacta:")
        exact_match = await conn.fetchrow("""
            SELECT id, nombre, apellido, email, numero_empleado, departamento, activo
            FROM usuarios 
            WHERE email = $1
        """, target_email)
        
        if exact_match:
            print("✅ ENCONTRADO con búsqueda exacta:")
            for key, value in dict(exact_match).items():
                print(f"   {key}: {value}")
        else:
            print("❌ NO encontrado con búsqueda exacta")
        
        # 2. Búsqueda case-insensitive
        print(f"\n2️⃣ Búsqueda case-insensitive:")
        case_insensitive = await conn.fetchrow("""
            SELECT id, nombre, apellido, email, numero_empleado, departamento, activo
            FROM usuarios 
            WHERE LOWER(email) = LOWER($1)
        """, target_email)
        
        if case_insensitive:
            print("✅ ENCONTRADO con búsqueda case-insensitive:")
            for key, value in dict(case_insensitive).items():
                print(f"   {key}: {value}")
        else:
            print("❌ NO encontrado con búsqueda case-insensitive")
        
        # 3. Búsqueda con LIKE
        print(f"\n3️⃣ Búsqueda con LIKE:")
        like_search = await conn.fetch("""
            SELECT id, nombre, apellido, email, numero_empleado, departamento, activo
            FROM usuarios 
            WHERE email LIKE $1
        """, f"%{target_email}%")
        
        if like_search:
            print("✅ ENCONTRADO con búsqueda LIKE:")
            for row in like_search:
                for key, value in dict(row).items():
                    print(f"   {key}: {value}")
        else:
            print("❌ NO encontrado con búsqueda LIKE")
        
        # 4. Búsqueda parcial por nombre
        print(f"\n4️⃣ Búsqueda parcial por 'maria':")
        partial_name = await conn.fetch("""
            SELECT id, nombre, apellido, email, numero_empleado, departamento, activo
            FROM usuarios 
            WHERE LOWER(nombre) LIKE '%maria%'
        """)
        
        if partial_name:
            print("✅ ENCONTRADO usuarios con 'maria':")
            for row in partial_name:
                for key, value in dict(row).items():
                    print(f"   {key}: {value}")
        else:
            print("❌ NO encontrado usuarios con 'maria'")
        
        # 5. Búsqueda parcial por apellido
        print(f"\n5️⃣ Búsqueda parcial por 'gonzalez':")
        partial_surname = await conn.fetch("""
            SELECT id, nombre, apellido, email, numero_empleado, departamento, activo
            FROM usuarios 
            WHERE LOWER(apellido) LIKE '%gonzalez%'
        """)
        
        if partial_surname:
            print("✅ ENCONTRADO usuarios con 'gonzalez':")
            for row in partial_surname:
                for key, value in dict(row).items():
                    print(f"   {key}: {value}")
        else:
            print("❌ NO encontrado usuarios con 'gonzalez'")
        
        # 6. Mostrar todos los emails para comparar
        print(f"\n6️⃣ Todos los emails en la BD:")
        all_emails = await conn.fetch("""
            SELECT email, nombre, apellido, activo
            FROM usuarios 
            ORDER BY email
        """)
        
        if all_emails:
            print("📧 Lista completa de emails:")
            for row in all_emails:
                status = "✅" if row['activo'] else "❌"
                # Mostrar caracteres especiales
                email_repr = repr(row['email'])
                print(f"   {status} {email_repr} - {row['nombre']} {row['apellido']}")
        else:
            print("❌ No hay emails en la BD")
        
        # 7. Verificar caracteres especiales
        print(f"\n7️⃣ Análisis de caracteres:")
        print(f"Email objetivo: {repr(target_email)}")
        print(f"Longitud: {len(target_email)}")
        print(f"Bytes: {target_email.encode('utf-8')}")
        
        # 8. Probar la query exacta del código
        print(f"\n8️⃣ Probando query exacta del código:")
        code_query = """
            SELECT id, nombre, apellido, email, numero_empleado, 
                   rol, departamento, activo, created_at, updated_at
            FROM usuarios 
            WHERE LOWER(email) = LOWER($1) AND activo = true
        """
        
        code_result = await conn.fetchrow(code_query, target_email)
        
        if code_result:
            print("✅ ENCONTRADO con query del código:")
            for key, value in dict(code_result).items():
                print(f"   {key}: {value}")
        else:
            print("❌ NO encontrado con query del código")
            
            # Probar sin el filtro activo
            print("\n   🔍 Probando sin filtro 'activo':")
            no_active_filter = await conn.fetchrow("""
                SELECT id, nombre, apellido, email, numero_empleado, 
                       rol, departamento, activo, created_at, updated_at
                FROM usuarios 
                WHERE LOWER(email) = LOWER($1)
            """, target_email)
            
            if no_active_filter:
                print("✅ ENCONTRADO sin filtro activo:")
                for key, value in dict(no_active_filter).items():
                    print(f"   {key}: {value}")
                    
                if not no_active_filter['activo']:
                    print("🚨 PROBLEMA: El usuario existe pero está marcado como INACTIVO")
            else:
                print("❌ NO encontrado incluso sin filtro activo")
        
        # 9. VERIFICACIÓN DE CONECTIVIDAD - Obtener 3 usuarios cualquiera
        print(f"\n9️⃣ VERIFICACIÓN DE CONECTIVIDAD - Primeros 3 usuarios:")
        try:
            test_users = await conn.fetch("""
                SELECT id, nombre, apellido, email, numero_empleado, 
                       rol, departamento, activo, created_at, updated_at
                FROM usuarios 
                ORDER BY id 
                LIMIT 3
            """)
            
            if test_users:
                print("✅ CONEXIÓN EXITOSA - Usuarios encontrados:")
                for i, user in enumerate(test_users, 1):
                    print(f"\n   👤 Usuario {i}:")
                    print(f"      ID: {user['id']}")
                    print(f"      Nombre: {user['nombre']}")
                    print(f"      Apellido: {user['apellido']}")
                    print(f"      Email: {repr(user['email'])}")  # repr para ver caracteres especiales
                    print(f"      Número Empleado: {user['numero_empleado']}")
                    print(f"      Rol: {user['rol']}")
                    print(f"      Departamento: {user['departamento']}")
                    print(f"      Activo: {user['activo']}")
                    print(f"      Creado: {user['created_at']}")
                    print(f"      Actualizado: {user['updated_at']}")
                    
                    # Log también por logging
                    import logging
                    logger = logging.getLogger("DatabaseTest")
                    logger.info(f"Usuario {i}: {user['nombre']} {user['apellido']} - {user['email']} - Activo: {user['activo']}")
                    
            else:
                print("❌ NO hay usuarios en la tabla")
                
        except Exception as e:
            print(f"❌ Error obteniendo usuarios de prueba: {e}")
        
        # 10. CONTEO TOTAL
        print(f"\n🔟 CONTEO TOTAL:")
        try:
            total_count = await conn.fetchval("SELECT COUNT(*) FROM usuarios")
            active_count = await conn.fetchval("SELECT COUNT(*) FROM usuarios WHERE activo = true")
            inactive_count = await conn.fetchval("SELECT COUNT(*) FROM usuarios WHERE activo = false")
            
            print(f"📊 Total usuarios: {total_count}")
            print(f"✅ Usuarios activos: {active_count}")
            print(f"❌ Usuarios inactivos: {inactive_count}")
            
            # Log también
            import logging
            logger = logging.getLogger("DatabaseTest")
            logger.info(f"BD Stats - Total: {total_count}, Activos: {active_count}, Inactivos: {inactive_count}")
            
        except Exception as e:
            print(f"❌ Error obteniendo conteos: {e}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error en diagnóstico: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_specific_user())