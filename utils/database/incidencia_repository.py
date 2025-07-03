# =====================================================
# utils/database/incidencia_repository.py - ACTUALIZADO para tipos JSON
# =====================================================
"""
Repositorio de incidencias actualizado para trabajar con tipos desde JSON.

CAMBIOS PRINCIPALES:
- Validación de tipos contra configuración JSON
- Campos específicos para Eroski
- Mejor integración con el workflow
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from models.incidencia import (
    IncidenciaDB, 
    IncidenciaCreate, 
    IncidenciaUpdate,
    PrioridadIncidencia,
    EstadoIncidencia,
    generate_ticket_number,
    incident_validator
)
from .base_repository import BaseRepository

class IncidenciaRepository(BaseRepository[IncidenciaDB]):
    """Repositorio para operaciones de incidencias con tipos dinámicos"""
    
    def __init__(self, connection_manager):
        super().__init__(connection_manager)
        self.logger = logging.getLogger("IncidenciaRepository")
    
    async def crear_incidencia(
        self, 
        incidencia_data: IncidenciaCreate
    ) -> Optional[IncidenciaDB]:
        """
        Crear nueva incidencia validando el tipo contra JSON config.
        
        Args:
            incidencia_data: Datos de la incidencia a crear
            
        Returns:
            IncidenciaDB creada o None si hubo error
        """
        try:
            # Validar tipo contra configuración JSON
            if not incident_validator.validate_type(incidencia_data.tipo):
                self.logger.warning(f"⚠️ Tipo de incidencia no válido: {incidencia_data.tipo}")
                # No fallar, pero loggear
            
            # Generar número de ticket único
            numero_ticket = generate_ticket_number()
            
            # SQL actualizado para campos específicos de Eroski
            query = """
                INSERT INTO incidencias 
                (numero_ticket, tipo, descripcion, prioridad, estado, fecha_creacion,
                 nombre_empleado, email_empleado, codigo_tienda, nombre_tienda, 
                 nombre_seccion, numero_serie_equipo, ubicacion_exacta, 
                 pasos_reproducir, impacto_operativo, respuestas_usuario)
                VALUES ($1, $2, $3, $4, $5, NOW(), $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
                RETURNING id, numero_ticket, tipo, descripcion, prioridad, estado, 
                         fecha_creacion, fecha_actualizacion, intentos_resolucion,
                         nombre_empleado, email_empleado, codigo_tienda, nombre_tienda,
                         nombre_seccion, numero_serie_equipo, ubicacion_exacta
            """
            
            # Convertir metadata a JSON para respuestas_usuario
            metadata_json = incidencia_data.metadata or {}
            
            row = await self.fetch_one(
                query,
                numero_ticket,
                incidencia_data.tipo,
                incidencia_data.descripcion,
                incidencia_data.prioridad.value,
                EstadoIncidencia.ABIERTA.value,
                incidencia_data.nombre_empleado,
                incidencia_data.email_empleado,
                incidencia_data.codigo_tienda,
                incidencia_data.nombre_tienda,
                incidencia_data.nombre_seccion,
                incidencia_data.numero_serie_equipo,
                incidencia_data.ubicacion_exacta,
                incidencia_data.pasos_reproducir,
                incidencia_data.impacto_operativo,
                metadata_json
            )
            
            if row:
                incidencia = IncidenciaDB(
                    id=row['id'],
                    numero_ticket=row['numero_ticket'],
                    tipo=row['tipo'],
                    descripcion=row['descripcion'],
                    prioridad=PrioridadIncidencia(row['prioridad']),
                    estado=EstadoIncidencia(row['estado']),
                    fecha_creacion=row['fecha_creacion'],
                    fecha_actualizacion=row['fecha_actualizacion'],
                    intentos_resolucion=row['intentos_resolucion'],
                    nombre_empleado=row['nombre_empleado'],
                    email_empleado=row['email_empleado'],
                    codigo_tienda=row['codigo_tienda'],
                    nombre_tienda=row['nombre_tienda'],
                    nombre_seccion=row['nombre_seccion'],
                    numero_serie_equipo=row['numero_serie_equipo'],
                    ubicacion_exacta=row['ubicacion_exacta']
                )
                
                self.logger.info(f"✅ Incidencia creada: {numero_ticket} (tipo: {incidencia_data.tipo})")
                return incidencia
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error creando incidencia: {e}")
            raise
    
    async def buscar_por_empleado(
        self, 
        email_empleado: str, 
        estados: Optional[List[EstadoIncidencia]] = None,
        limit: int = 10
    ) -> List[IncidenciaDB]:
        """
        Buscar incidencias por empleado.
        
        Args:
            email_empleado: Email del empleado
            estados: Lista de estados a filtrar (opcional)
            limit: Máximo número de resultados
            
        Returns:
            Lista de incidencias
        """
        try:
            # Construir query dinámicamente
            base_query = """
                SELECT id, numero_ticket, tipo, descripcion, prioridad, estado,
                       fecha_creacion, fecha_actualizacion, fecha_resolucion,
                       tiempo_resolucion_minutos, intentos_resolucion,
                       nombre_empleado, email_empleado, codigo_tienda, nombre_tienda,
                       nombre_seccion, numero_serie_equipo, ubicacion_exacta,
                       solucion_aplicada, escalado_a, notas_internas
                FROM incidencias 
                WHERE email_empleado = $1
            """
            
            params = [email_empleado]
            param_count = 1
            
            if estados:
                param_count += 1
                estados_str = [estado.value for estado in estados]
                base_query += f" AND estado = ANY(${param_count})"
                params.append(estados_str)
            
            base_query += f" ORDER BY fecha_creacion DESC LIMIT ${param_count + 1}"
            params.append(limit)
            
            rows = await self.fetch_all(base_query, *params)
            
            incidencias = []
            for row in rows:
                incidencia = IncidenciaDB(
                    id=row['id'],
                    numero_ticket=row['numero_ticket'],
                    tipo=row['tipo'],
                    descripcion=row['descripcion'],
                    prioridad=PrioridadIncidencia(row['prioridad']),
                    estado=EstadoIncidencia(row['estado']),
                    fecha_creacion=row['fecha_creacion'],
                    fecha_actualizacion=row['fecha_actualizacion'],
                    fecha_resolucion=row['fecha_resolucion'],
                    tiempo_resolucion_minutos=row['tiempo_resolucion_minutos'],
                    intentos_resolucion=row['intentos_resolucion'],
                    nombre_empleado=row['nombre_empleado'],
                    email_empleado=row['email_empleado'],
                    codigo_tienda=row['codigo_tienda'],
                    nombre_tienda=row['nombre_tienda'],
                    nombre_seccion=row['nombre_seccion'],
                    numero_serie_equipo=row['numero_serie_equipo'],
                    ubicacion_exacta=row['ubicacion_exacta'],
                    solucion_aplicada=row['solucion_aplicada'],
                    escalado_a=row['escalado_a'],
                    notas_internas=row['notas_internas']
                )
                incidencias.append(incidencia)
            
            self.logger.info(f"🔍 Encontradas {len(incidencias)} incidencias para {email_empleado}")
            return incidencias
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando incidencias: {e}")
            return []
    
    async def buscar_por_tienda(
        self, 
        codigo_tienda: str, 
        estados: Optional[List[EstadoIncidencia]] = None,
        limit: int = 50
    ) -> List[IncidenciaDB]:
        """
        Buscar incidencias por tienda.
        
        Args:
            codigo_tienda: Código de la tienda
            estados: Estados a filtrar
            limit: Límite de resultados
            
        Returns:
            Lista de incidencias
        """
        try:
            base_query = """
                SELECT id, numero_ticket, tipo, descripcion, prioridad, estado,
                       fecha_creacion, fecha_actualizacion, fecha_resolucion,
                       tiempo_resolucion_minutos, intentos_resolucion,
                       nombre_empleado, email_empleado, codigo_tienda, nombre_tienda,
                       nombre_seccion, numero_serie_equipo, ubicacion_exacta,
                       solucion_aplicada, escalado_a, notas_internas
                FROM incidencias 
                WHERE codigo_tienda = $1
            """
            
            params = [codigo_tienda]
            param_count = 1
            
            if estados:
                param_count += 1
                estados_str = [estado.value for estado in estados]
                base_query += f" AND estado = ANY(${param_count})"
                params.append(estados_str)
            
            base_query += f" ORDER BY fecha_creacion DESC LIMIT ${param_count + 1}"
            params.append(limit)
            
            rows = await self.fetch_all(base_query, *params)
            return [self._row_to_incidencia(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando por tienda: {e}")
            return []
    
    async def actualizar_estado(
        self, 
        incidencia_id: int, 
        nuevo_estado: EstadoIncidencia,
        solucion: Optional[str] = None,
        notas: Optional[str] = None
    ) -> bool:
        """
        Actualizar estado de incidencia.
        
        Args:
            incidencia_id: ID de la incidencia
            nuevo_estado: Nuevo estado
            solucion: Solución aplicada (opcional)
            notas: Notas internas (opcional)
            
        Returns:
            True si se actualizó correctamente
        """
        try:
            # Determinar si se debe marcar como resuelta
            fecha_resolucion = None
            if nuevo_estado in [EstadoIncidencia.RESUELTA, EstadoIncidencia.CERRADA]:
                fecha_resolucion = datetime.now()
            
            query = """
                UPDATE incidencias 
                SET estado = $1, 
                    fecha_actualizacion = NOW(),
                    solucion_aplicada = COALESCE($2, solucion_aplicada),
                    notas_internas = COALESCE($3, notas_internas),
                    fecha_resolucion = COALESCE($4, fecha_resolucion)
                WHERE id = $5
            """
            
            result = await self.execute(
                query,
                nuevo_estado.value,
                solucion,
                notas,
                fecha_resolucion,
                incidencia_id
            )
            
            success = result == 1
            if success:
                self.logger.info(f"✅ Estado actualizado para incidencia {incidencia_id}: {nuevo_estado.value}")
            else:
                self.logger.warning(f"⚠️ No se encontró incidencia con ID {incidencia_id}")
                
            return success
            
        except Exception as e:
            self.logger.error(f"❌ Error actualizando estado: {e}")
            raise
    
    async def incrementar_intentos(self, incidencia_id: int) -> bool:
        """Incrementar contador de intentos de resolución"""
        try:
            query = """
                UPDATE incidencias 
                SET intentos_resolucion = intentos_resolucion + 1,
                    fecha_actualizacion = NOW()
                WHERE id = $1
            """
            
            result = await self.execute(query, incidencia_id)
            return result == 1
            
        except Exception as e:
            self.logger.error(f"❌ Error incrementando intentos: {e}")
            return False
    
    async def obtener_metricas_tienda(self, codigo_tienda: str) -> Dict[str, Any]:
        """
        Obtener métricas de incidencias por tienda.
        
        Args:
            codigo_tienda: Código de la tienda
            
        Returns:
            Diccionario con métricas
        """
        try:
            query = """
                SELECT 
                    COUNT(*) as total_incidencias,
                    COUNT(CASE WHEN estado = 'abierta' THEN 1 END) as abiertas,
                    COUNT(CASE WHEN estado = 'resuelta' THEN 1 END) as resueltas,
                    COUNT(CASE WHEN estado = 'escalada' THEN 1 END) as escaladas,
                    AVG(tiempo_resolucion_minutos) as tiempo_promedio,
                    tipo,
                    COUNT(*) as incidencias_por_tipo
                FROM incidencias 
                WHERE codigo_tienda = $1 
                  AND fecha_creacion >= NOW() - INTERVAL '30 days'
                GROUP BY tipo
                ORDER BY incidencias_por_tipo DESC
            """
            
            rows = await self.fetch_all(query, codigo_tienda)
            
            # Procesar resultados
            tipos_mas_comunes = [
                {"tipo": row["tipo"], "cantidad": row["incidencias_por_tipo"]}
                for row in rows[:5]  # Top 5
            ]
            
            # Totales
            total_query = """
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN estado = 'abierta' THEN 1 END) as abiertas,
                    COUNT(CASE WHEN estado = 'resuelta' THEN 1 END) as resueltas,
                    COUNT(CASE WHEN estado = 'escalada' THEN 1 END) as escaladas,
                    AVG(tiempo_resolucion_minutos) as tiempo_promedio
                FROM incidencias 
                WHERE codigo_tienda = $1 
                  AND fecha_creacion >= NOW() - INTERVAL '30 days'
            """
            
            totales = await self.fetch_one(total_query, codigo_tienda)
            
            return {
                "codigo_tienda": codigo_tienda,
                "periodo": "últimos 30 días",
                "total_incidencias": totales["total"] or 0,
                "incidencias_abiertas": totales["abiertas"] or 0,
                "incidencias_resueltas": totales["resueltas"] or 0,
                "incidencias_escaladas": totales["escaladas"] or 0,
                "tiempo_promedio_resolucion": round(totales["tiempo_promedio"] or 0, 1),
                "tipos_mas_comunes": tipos_mas_comunes
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error obteniendo métricas: {e}")
            return {
                "codigo_tienda": codigo_tienda,
                "error": "No se pudieron obtener las métricas"
            }
    
    async def buscar_incidencias_similares(
        self, 
        tipo: str, 
        descripcion: str, 
        codigo_tienda: Optional[str] = None,
        limit: int = 5
    ) -> List[IncidenciaDB]:
        """
        Buscar incidencias similares para sugerir soluciones.
        
        Args:
            tipo: Tipo de incidencia
            descripcion: Descripción del problema
            codigo_tienda: Código de tienda (opcional)
            limit: Límite de resultados
            
        Returns:
            Lista de incidencias similares
        """
        try:
            # Usar similitud de texto para encontrar incidencias parecidas
            base_query = """
                SELECT id, numero_ticket, tipo, descripcion, prioridad, estado,
                       fecha_creacion, solucion_aplicada, tiempo_resolucion_minutos,
                       nombre_empleado, codigo_tienda, nombre_tienda
                FROM incidencias 
                WHERE tipo = $1 
                  AND estado IN ('resuelta', 'cerrada')
                  AND solucion_aplicada IS NOT NULL
            """
            
            params = [tipo]
            param_count = 1
            
            if codigo_tienda:
                param_count += 1
                base_query += f" AND codigo_tienda = ${param_count}"
                params.append(codigo_tienda)
            
            # Ordenar por fecha (más recientes primero)
            base_query += f" ORDER BY fecha_creacion DESC LIMIT ${param_count + 1}"
            params.append(limit)
            
            rows = await self.fetch_all(base_query, *params)
            return [self._row_to_incidencia_simple(row) for row in rows]
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando similares: {e}")
            return []
    
    def _row_to_incidencia(self, row: Dict) -> IncidenciaDB:
        """Convertir fila de BD a modelo IncidenciaDB completo"""
        return IncidenciaDB(
            id=row['id'],
            numero_ticket=row['numero_ticket'],
            tipo=row['tipo'],
            descripcion=row['descripcion'],
            prioridad=PrioridadIncidencia(row['prioridad']),
            estado=EstadoIncidencia(row['estado']),
            fecha_creacion=row['fecha_creacion'],
            fecha_actualizacion=row['fecha_actualizacion'],
            fecha_resolucion=row.get('fecha_resolucion'),
            tiempo_resolucion_minutos=row.get('tiempo_resolucion_minutos'),
            intentos_resolucion=row.get('intentos_resolucion', 0),
            nombre_empleado=row['nombre_empleado'],
            email_empleado=row['email_empleado'],
            codigo_tienda=row.get('codigo_tienda'),
            nombre_tienda=row.get('nombre_tienda'),
            nombre_seccion=row.get('nombre_seccion'),
            numero_serie_equipo=row.get('numero_serie_equipo'),
            ubicacion_exacta=row.get('ubicacion_exacta'),
            solucion_aplicada=row.get('solucion_aplicada'),
            escalado_a=row.get('escalado_a'),
            notas_internas=row.get('notas_internas')
        )
    
    def _row_to_incidencia_simple(self, row: Dict) -> IncidenciaDB:
        """Convertir fila de BD a modelo IncidenciaDB con campos mínimos"""
        return IncidenciaDB(
            id=row['id'],
            numero_ticket=row['numero_ticket'],
            tipo=row['tipo'],
            descripcion=row['descripcion'],
            prioridad=PrioridadIncidencia(row.get('prioridad', 'media')),
            estado=EstadoIncidencia(row.get('estado', 'cerrada')),
            fecha_creacion=row['fecha_creacion'],
            fecha_actualizacion=row['fecha_creacion'],  # Fallback
            nombre_empleado=row.get('nombre_empleado', ''),
            email_empleado=row.get('email_empleado', ''),
            codigo_tienda=row.get('codigo_tienda'),
            nombre_tienda=row.get('nombre_tienda'),
            solucion_aplicada=row.get('solucion_aplicada'),
            tiempo_resolucion_minutos=row.get('tiempo_resolucion_minutos')
        )