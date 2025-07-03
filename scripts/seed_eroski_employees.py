# =====================================================
# scripts/seed_eroski_employees.py - CORREGIDO v3
# =====================================================
"""
Script para insertar empleados de prueba específicos de Eroski.

CORREGIDO PARA:
- Adaptarse a la estructura real de la tabla usuarios
- Manejar restricción de 4 caracteres en campo 'rol'
- Usar 'activo' en lugar de 'estado'
- Sintaxis corregida sin strings sin terminar
"""

import asyncio
import asyncpg
import logging
from datetime import datetime, date
from typing import List, Dict, Any, Optional
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("EroskiSeeder")

class EroskiEmployeeSeederV3:
    """Seeder corregido para empleados de Eroski"""
    
    def __init__(self):
        # Configuración de BD
        import os
        self.db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", 5432)),
            "database": os.getenv("DB_NAME", "chatbot_db"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "password123")
        }
        
        # Cache de estructura de tabla
        self.table_structure = None
        
        # Datos específicos de Eroski
        self.tiendas_eroski = [
            {
                "codigo": "ERO001",
                "nombre": "Eroski Bilbao Centro",
                "tipo": "hipermercado"
            },
            {
                "codigo": "ERO002",
                "nombre": "Eroski San Sebastián",
                "tipo": "supermercado"
            },
            {
                "codigo": "ERO003",
                "nombre": "Eroski Vitoria-Gasteiz",
                "tipo": "hipermercado"
            }
        ]
    
    @property
    def connection_string(self) -> str:
        """Construir string de conexión"""
        return (f"postgresql://{self.db_config['user']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}")
    
    async def get_table_structure(self, table_name: str) -> Dict[str, Any]:
        """Obtener estructura de una tabla"""
        if self.table_structure and table_name in self.table_structure:
            return self.table_structure[table_name]
        
        try:
            conn = await asyncpg.connect(self.connection_string)
            
            try:
                # Verificar si la tabla existe
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_schema = 'public' AND table_name = $1
                    );
                """, table_name)
                
                if not table_exists:
                    return {"exists": False, "columns": {}}
                
                # Obtener columnas con restricciones de longitud
                columns = await conn.fetch("""
                    SELECT 
                        column_name, 
                        data_type, 
                        is_nullable, 
                        column_default,
                        character_maximum_length
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' AND table_name = $1
                    ORDER BY ordinal_position
                """, table_name)
                
                column_info = {}
                for col in columns:
                    column_info[col['column_name']] = {
                        "type": col['data_type'],
                        "nullable": col['is_nullable'] == 'YES',
                        "default": col['column_default'],
                        "max_length": col['character_maximum_length']
                    }
                
                structure = {
                    "exists": True,
                    "columns": column_info,
                    "column_names": list(column_info.keys())
                }
                
                # Cache
                if not self.table_structure:
                    self.table_structure = {}
                self.table_structure[table_name] = structure
                
                return structure
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error obteniendo estructura de {table_name}: {e}")
            return {"exists": False, "columns": {}, "error": str(e)}
    
    async def verificar_prerequisitos(self) -> bool:
        """Verificar que todo esté listo para insertar datos"""
        try:
            logger.info("🔍 Verificando prerrequisitos...")
            
            # 1. Verificar conectividad
            conn = await asyncpg.connect(self.connection_string)
            await conn.fetchval("SELECT 1")
            await conn.close()
            logger.info("✅ Conectividad a BD exitosa")
            
            # 2. Verificar estructura de usuarios
            usuarios_structure = await self.get_table_structure("usuarios")
            
            if not usuarios_structure["exists"]:
                logger.error("❌ La tabla 'usuarios' no existe")
                logger.info("💡 Ejecuta primero: python -m scripts.setup_db")
                return False
            
            # 3. Mostrar columnas disponibles con restricciones
            columns = usuarios_structure["columns"]
            logger.info("📋 Estructura de tabla 'usuarios':")
            for col_name, col_info in columns.items():
                max_len = col_info.get('max_length')
                max_len_str = f" (max: {max_len})" if max_len else ""
                logger.info(f"   📝 {col_name}: {col_info['type']}{max_len_str}")
            
            # 4. Verificar columnas mínimas requeridas
            required_columns = ['nombre', 'apellido', 'email', 'numero_empleado']
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                logger.error(f"❌ Columnas requeridas faltantes: {missing_columns}")
                return False
            
            # 5. Verificar restricción del campo rol
            rol_info = columns.get('rol', {})
            rol_max_length = rol_info.get('max_length')
            if rol_max_length:
                logger.info(f"⚠️ Campo 'rol' limitado a {rol_max_length} caracteres")
            
            logger.info("✅ Todos los prerrequisitos cumplidos")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error verificando prerrequisitos: {e}")
            return False
    
    async def insertar_empleados_eroski(self) -> bool:
        """Insertar empleados de prueba específicos de Eroski"""
        try:
            if not await self.verificar_prerequisitos():
                return False
            
            conn = await asyncpg.connect(self.connection_string)
            
            try:
                # Verificar si hay datos existentes de Eroski
                count_existing = await conn.fetchval("SELECT COUNT(*) FROM usuarios WHERE email LIKE '%@eroski.es'")
                
                if count_existing > 0:
                    logger.info(f"⚠️ Se encontraron {count_existing} empleados de Eroski existentes")
                    print(f"\n¿Qué quieres hacer con los {count_existing} empleados existentes?")
                    print("1. Eliminar y recrear todos los datos")
                    print("2. Conservar datos existentes y salir")
                    print("3. Agregar empleados con emails diferentes")
                    
                    opcion = input("Selecciona una opción (1/2/3): ").strip()
                    
                    if opcion == "1":
                        logger.info(f"🧹 Limpiando {count_existing} registros previos de Eroski...")
                        
                        # 1. Primero eliminar incidencias que referencian empleados de Eroski
                        try:
                            inc_deleted = await conn.fetchval("""
                                SELECT COUNT(*) FROM incidencias 
                                WHERE numero_empleado IN (
                                    SELECT numero_empleado FROM usuarios WHERE email LIKE '%@eroski.es'
                                )
                            """)
                            
                            if inc_deleted > 0:
                                await conn.execute("""
                                    DELETE FROM incidencias 
                                    WHERE numero_empleado IN (
                                        SELECT numero_empleado FROM usuarios WHERE email LIKE '%@eroski.es'
                                    )
                                """)
                                logger.info(f"   🎫 {inc_deleted} incidencias relacionadas eliminadas")
                        except Exception as e:
                            logger.warning(f"   ⚠️ Error eliminando incidencias: {e}")
                        
                        # 2. Luego eliminar usuarios de Eroski
                        await conn.execute("DELETE FROM usuarios WHERE email LIKE '%@eroski.es'")
                        logger.info(f"   👥 {count_existing} usuarios de Eroski eliminados")
                        
                    elif opcion == "2":
                        logger.info("✅ Conservando datos existentes")
                        await self._mostrar_resumen(conn)
                        return True
                        
                    elif opcion == "3":
                        logger.info("🔄 Generando empleados con sufijo único...")
                        # Agregar sufijo a emails para evitar duplicados
                        import time
                        timestamp_suffix = str(int(time.time()))[-4:]  # Últimos 4 dígitos del timestamp
                        email_suffix = f".{timestamp_suffix}"
                    else:
                        logger.info("❌ Opción no válida, saliendo...")
                        return False
                else:
                    email_suffix = ""
                
                # Obtener estructura actual
                usuarios_structure = await self.get_table_structure("usuarios")
                available_columns = usuarios_structure["column_names"]
                column_info = usuarios_structure["columns"]
                
                # Insertar empleados por tienda
                total_insertados = 0
                
                for tienda in self.tiendas_eroski:
                    empleados_tienda = self._generar_empleados_para_tienda(tienda, column_info, email_suffix)
                    
                    for empleado in empleados_tienda:
                        if await self._insertar_empleado_adaptativo(conn, empleado, available_columns, column_info):
                            total_insertados += 1
                
                logger.info(f"✅ {total_insertados} empleados de Eroski insertados exitosamente")
                
                # Mostrar resumen
                await self._mostrar_resumen(conn)
                
                return True
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error insertando empleados de Eroski: {e}")
            return False
    
    def _generar_empleados_para_tienda(self, tienda: Dict[str, Any], column_info: Dict[str, Any], email_suffix: str = "") -> List[Dict[str, Any]]:
        """Generar empleados de prueba para una tienda específica"""
        
        # Determinar valores válidos para 'rol' basado en restricciones
        rol_max_length = column_info.get('rol', {}).get('max_length', 50)
        
        # Mapear roles según restricción de longitud
        if rol_max_length and rol_max_length <= 4:
            # Si rol está limitado a 4 caracteres, usar códigos cortos
            roles = {
                "gerente": "ger",     # 3 caracteres
                "supervisor": "sup",   # 3 caracteres  
                "empleado": "emp"      # 3 caracteres
            }
        else:
            # Si no hay restricción, usar nombres completos
            roles = {
                "gerente": "gerente",
                "supervisor": "supervisor",
                "empleado": "empleado"
            }
        
        # Generar números de empleado cortos (máximo 4 caracteres)
        # Usar formato: E001, E002, etc. para la tienda
        tienda_num = tienda['codigo'][-1]  # Último dígito del código (1, 2, 3)
        
        empleados_base = [
            # Gerencia
            {
                "numero_empleado": f"G{tienda_num}01",  # G101, G201, G301
                "nombre": "María Carmen",
                "apellido": "González Ruiz",
                "email": f"maria.gonzalez.{tienda['codigo'].lower()}{email_suffix}@eroski.es",
                "rol": roles["gerente"],
                "departamento": "Gerencia"
            },
            # Supervisores
            {
                "numero_empleado": f"S{tienda_num}01",  # S101, S201, S301
                "nombre": "Iker",
                "apellido": "Etxeberria Aguirre",
                "email": f"iker.etxeberria.{tienda['codigo'].lower()}{email_suffix}@eroski.es",
                "rol": roles["supervisor"], 
                "departamento": "Operaciones"
            },
            # Empleados de sección
            {
                "numero_empleado": f"E{tienda_num}01",  # E101, E201, E301
                "nombre": "Ainhoa",
                "apellido": "Martínez López",
                "email": f"ainhoa.martinez.{tienda['codigo'].lower()}{email_suffix}@eroski.es",
                "rol": roles["empleado"],
                "departamento": "Frutería"
            },
            {
                "numero_empleado": f"E{tienda_num}02",  # E102, E202, E302
                "nombre": "Mikel",
                "apellido": "Urrutia Fernández",
                "email": f"mikel.urrutia.{tienda['codigo'].lower()}{email_suffix}@eroski.es",
                "rol": roles["empleado"],
                "departamento": "Carnicería"
            },
            # Empleados de caja
            {
                "numero_empleado": f"E{tienda_num}03",  # E103, E203, E303
                "nombre": "Leire",
                "apellido": "Saenz de Urturi",
                "email": f"leire.saenz.{tienda['codigo'].lower()}{email_suffix}@eroski.es",
                "rol": roles["empleado"],
                "departamento": "Caja"
            },
            {
                "numero_empleado": f"E{tienda_num}04",  # E104, E204, E304
                "nombre": "Jon",
                "apellido": "Bilbao Echevarría",
                "email": f"jon.bilbao.{tienda['codigo'].lower()}{email_suffix}@eroski.es",
                "rol": roles["empleado"],
                "departamento": "Caja"
            }
        ]
        
        # Añadir información de tienda a cada empleado
        for empleado in empleados_base:
            empleado.update({
                "codigo_tienda": tienda["codigo"],
                "nombre_tienda": tienda["nombre"],
                "tipo_tienda": tienda["tipo"],
                "activo": True,  # Usar 'activo' en lugar de 'estado'
                "fecha_alta": date.today()
            })
        
        return empleados_base
    
    def _validate_field_length(self, value: str, max_length: Optional[int]) -> str:
        """Validar y truncar campo si es necesario"""
        if not max_length or max_length >= len(value):
            return value
        
        # Truncar pero mantener información importante
        if max_length >= 3:
            return value[:max_length]
        else:
            # Para campos muy cortos, usar códigos
            return value[:max_length]
    
    async def _insertar_empleado_adaptativo(
        self, 
        conn: asyncpg.Connection, 
        empleado: Dict[str, Any], 
        available_columns: List[str],
        column_info: Dict[str, Any]
    ) -> bool:
        """Insertar empleado adaptándose a las columnas y restricciones disponibles"""
        try:
            # Mapear campos del empleado a columnas de BD
            field_mapping = {
                "numero_empleado": "numero_empleado",
                "nombre": "nombre", 
                "apellido": "apellido",
                "email": "email",
                "rol": "rol",
                "departamento": "departamento",
                "activo": "activo"  # Cambiar de 'estado' a 'activo'
            }
            
            # Filtrar solo campos que existen en la tabla
            insert_fields = {}
            insert_columns = []
            insert_values = []
            placeholders = []
            
            param_count = 1
            
            for field_name, db_column in field_mapping.items():
                if db_column in available_columns and field_name in empleado:
                    value = empleado[field_name]
                    
                    # Validar longitud si es string
                    if isinstance(value, str):
                        col_info = column_info.get(db_column, {})
                        max_length = col_info.get('max_length')
                        if max_length:
                            value = self._validate_field_length(value, max_length)
                    
                    insert_fields[db_column] = value
                    insert_columns.append(db_column)
                    insert_values.append(value)
                    placeholders.append(f"${param_count}")
                    param_count += 1
            
            # Agregar created_at si existe la columna
            if "created_at" in available_columns:
                insert_columns.append("created_at")
                insert_values.append(datetime.now())
                placeholders.append(f"${param_count}")
            
            # Construir query dinámicamente
            columns_str = ", ".join(insert_columns)
            placeholders_str = ", ".join(placeholders)
            
            query = f"INSERT INTO usuarios ({columns_str}) VALUES ({placeholders_str}) RETURNING id"
            
            result = await conn.fetchval(query, *insert_values)
            
            if result:
                logger.debug(f"✅ Empleado insertado: {empleado['nombre']} {empleado['apellido']} (ID: {result})")
                return True
            else:
                logger.warning(f"⚠️ No se pudo insertar: {empleado['email']}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Error insertando empleado {empleado.get('email', 'unknown')}: {e}")
            logger.debug(f"📋 Datos del empleado: {empleado}")
            return False
    
    async def _mostrar_resumen(self, conn: asyncpg.Connection) -> None:
        """Mostrar resumen de empleados insertados"""
        try:
            # Contar empleados de Eroski
            total_query = "SELECT COUNT(*) FROM usuarios WHERE email LIKE '%@eroski.es'"
            total = await conn.fetchval(total_query)
            
            logger.info(f"\n📊 RESUMEN: {total} empleados de Eroski insertados")
            
            # Mostrar algunos ejemplos
            if total > 0:
                ejemplos_query = """
                    SELECT nombre, apellido, email, departamento, numero_empleado, rol
                    FROM usuarios 
                    WHERE email LIKE '%@eroski.es'
                    ORDER BY numero_empleado
                    LIMIT 5
                """
                
                ejemplos = await conn.fetch(ejemplos_query)
                
                logger.info("\n🧪 EMPLEADOS DE PRUEBA PARA TESTING:")
                for emp in ejemplos:
                    logger.info(f"   📧 {emp['email']}")
                    logger.info(f"      👤 {emp['nombre']} {emp['apellido']} | 🏢 {emp['departamento']} | 👔 {emp['rol']}")
                    logger.info(f"      🆔 {emp['numero_empleado']}")
                    logger.info("")
                
                logger.info(f"💡 TOTAL: {total} empleados disponibles para testing del chatbot")
                logger.info("🎯 Usa cualquiera de estos emails para probar el sistema de autenticación")
            
        except Exception as e:
            logger.error(f"❌ Error mostrando resumen: {e}")
    
    async def insertar_incidencias_ejemplo(self) -> bool:
        """Insertar algunas incidencias de ejemplo usando empleados de Eroski"""
        try:
            logger.info("🎫 Insertando incidencias de ejemplo...")
            
            # Verificar estructura de incidencias
            incidencias_structure = await self.get_table_structure("incidencias")
            
            if not incidencias_structure["exists"]:
                logger.warning("⚠️ La tabla 'incidencias' no existe, omitiendo incidencias de ejemplo")
                return False
            
            conn = await asyncpg.connect(self.connection_string)
            
            try:
                # Obtener empleados de Eroski para crear incidencias
                empleados = await conn.fetch("""
                    SELECT id, nombre, apellido, email, departamento, numero_empleado
                    FROM usuarios 
                    WHERE email LIKE '%@eroski.es'
                    LIMIT 3
                """)
                
                if not empleados:
                    logger.warning("⚠️ No hay empleados de Eroski disponibles para crear incidencias")
                    return False
                
                available_columns = incidencias_structure["column_names"]
                logger.info(f"📋 Columnas disponibles en incidencias: {available_columns}")
                
                # Adaptar incidencias según estructura real de la tabla
                incidencias_ejemplo = [
                    {
                        "descripcion_problema": "La balanza de la sección de frutería no imprime etiquetas correctamente. Los precios salen borrosos y los clientes se quejan.",
                        "nombre_seccion": "Frutería",
                        "solucion": None,
                        "estado": "abierta"
                    },
                    {
                        "descripcion_problema": "El terminal de la caja 3 no lee las tarjetas de crédito. Los clientes tienen que pagar en efectivo y se están formando colas largas.",
                        "nombre_seccion": "Caja",
                        "solucion": None,
                        "estado": "abierta"
                    },
                    {
                        "descripcion_problema": "No hay conexión a internet en toda la sección de carnicería. No podemos consultar precios ni actualizar el inventario.",
                        "nombre_seccion": "Carnicería",
                        "solucion": None,
                        "estado": "abierta"
                    }
                ]
                
                # Crear incidencias adaptadas a la estructura real
                for i, inc_data in enumerate(incidencias_ejemplo):
                    if i < len(empleados):
                        empleado = empleados[i]
                        
                        # Construir datos de inserción basados en columnas disponibles
                        insert_data = {}
                        
                        # Mapear campos según estructura real
                        field_mapping = {
                            "numero_empleado": empleado["numero_empleado"],
                            "codigo_tienda": f"ERO{str(i+1).zfill(3)}",  # ERO001, ERO002, etc.
                            "nombre_tienda": f"Eroski Tienda {i+1}",
                            "nombre_seccion": inc_data["nombre_seccion"],
                            "descripcion_problema": inc_data["descripcion_problema"],
                            "solucion": inc_data["solucion"],
                            "estado": inc_data["estado"],
                            "email": empleado["email"]
                        }
                        
                        # Solo incluir campos que existen en la tabla
                        for field, value in field_mapping.items():
                            if field in available_columns:
                                insert_data[field] = value
                        
                        # Agregar fecha_creacion si existe
                        if "fecha_creacion" in available_columns:
                            insert_data["fecha_creacion"] = datetime.now()
                        
                        if not insert_data:
                            logger.warning("⚠️ No hay campos compatibles para insertar incidencia")
                            continue
                        
                        # Construir query dinámicamente
                        columns = list(insert_data.keys())
                        values = list(insert_data.values())
                        placeholders = [f"${i+1}" for i in range(len(values))]
                        
                        query = f"INSERT INTO incidencias ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
                        
                        result = await conn.fetchval(query, *values)
                        
                        if result:
                            logger.info(f"✅ Incidencia creada: ID-{result} ({inc_data['nombre_seccion']})")
                        else:
                            logger.warning(f"⚠️ Error creando incidencia de {inc_data['nombre_seccion']}")
                
                logger.info("✅ Incidencias de ejemplo insertadas exitosamente")
                return True
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ Error insertando incidencias ejemplo: {e}")
            return False

async def main():
    """Función principal"""
    logger.info("🚀 Iniciando seeder corregido v3 de empleados de Eroski...")
    
    seeder = EroskiEmployeeSeederV3()
    
    try:
        # Insertar empleados
        if await seeder.insertar_empleados_eroski():
            logger.info("✅ Empleados insertados exitosamente")
            
            # Preguntar si insertar incidencias de ejemplo
            print("\n¿Insertar incidencias de ejemplo? (s/n): ", end="")
            respuesta = input().lower().strip()
            
            if respuesta in ['s', 'si', 'sí', 'y', 'yes']:
                if await seeder.insertar_incidencias_ejemplo():
                    logger.info("✅ Incidencias de ejemplo insertadas")
                else:
                    logger.warning("⚠️ Incidencias de ejemplo no se pudieron insertar completamente")
        else:
            logger.error("❌ Error insertando empleados")
            return False
        
        logger.info("\n🎉 ¡Seeder completado exitosamente!")
        logger.info("🧪 Ahora puedes probar el chatbot con los empleados de Eroski insertados")
        logger.info("📧 Emails de prueba terminan en @eroski.es")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en seeder principal: {e}")
        return False

if __name__ == "__main__":
    # Ejecutar seeder
    success = asyncio.run(main())
    sys.exit(0 if success else 1)