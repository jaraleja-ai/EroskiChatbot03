# =====================================================
# utils/database/incidencia_repository.py - Repositorio de incidencias
# =====================================================
from models.incidencia import (
    IncidenciaDB, IncidenciaCreate, TipoIncidencia, 
    EstadoIncidencia, PrioridadIncidencia
)
from datetime import datetime
from .base_repository import BaseRepository
import uuid
from typing import List, Optional

class IncidenciaRepository(BaseRepository[IncidenciaDB]):
    """Repositorio para operaciones de incidencias"""
    
    async def crear_incidencia(
        self, 
        usuario_id: int, 
        tipo: TipoIncidencia,
        descripcion: str, 
        prioridad: str = "media"
    ) -> Optional[IncidenciaDB]:
        """
        Crear nueva incidencia.
        
        Args:
            usuario_id: ID del usuario
            tipo: Tipo de incidencia
            descripcion: Descripción del problema
            prioridad: Prioridad de la incidencia
            
        Returns:
            IncidenciaDB creada o None si hubo error
        """
        # Generar número de ticket único
        numero_ticket = self._generate_ticket_number()
        
        query = """
            INSERT INTO incidencias 
            (usuario_id, numero_ticket, tipo, descripcion, prioridad, estado, fecha_creacion)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING id, usuario_id, numero_ticket, tipo, descripcion, prioridad, 
                     estado, fecha_creacion, fecha_actualizacion, intentos_resolucion
        """
        
        try:
            row = await self.fetch_one(
                query,
                usuario_id,
                numero_ticket,
                tipo.value,
                descripcion,
                prioridad,
                EstadoIncidencia.ABIERTA.value
            )
            
            if row:
                incidencia = IncidenciaDB(
                    id=row['id'],
                    usuario_id=row['usuario_id'],
                    numero_ticket=row['numero_ticket'],
                    tipo=TipoIncidencia(row['tipo']),
                    descripcion=row['descripcion'],
                    prioridad=PrioridadIncidencia(row['prioridad']),
                    estado=EstadoIncidencia(row['estado']),
                    fecha_creacion=row['fecha_creacion'],
                    fecha_actualizacion=row['fecha_actualizacion'],
                    intentos_resolucion=row['intentos_resolucion']
                )
                
                self.logger.info(f"✅ Incidencia creada: {numero_ticket} ({tipo.value})")
                return incidencia
            
            return None
            
        except Exception as e:
            self.logger.error(f"❌ Error creando incidencia: {e}")
            raise
    
    def _generate_ticket_number(self) -> str:
        """Generar número de ticket único"""
        prefix = "INC"
        timestamp = datetime.now().strftime("%Y%m%d")
        random_suffix = str(uuid.uuid4())[:8].upper()
        return f"{prefix}-{timestamp}-{random_suffix}"
    
    async def actualizar_estado(
        self, 
        incidencia_id: int, 
        nuevo_estado: EstadoIncidencia
    ) -> bool:
        """
        Actualizar estado de incidencia.
        
        Args:
            incidencia_id: ID de la incidencia
            nuevo_estado: Nuevo estado
            
        Returns:
            True si se actualizó correctamente
        """
        # Si se está resolviendo, calcular tiempo de resolución
        if nuevo_estado == EstadoIncidencia.RESUELTA:
            query = """
                UPDATE incidencias 
                SET estado = $2, 
                    fecha_actualizacion = NOW(),
                    fecha_resolucion = NOW(),
                    tiempo_resolucion_minutos = EXTRACT(EPOCH FROM (NOW() - fecha_creacion))/60
                WHERE id = $1
            """
        else:
            query = """
                UPDATE incidencias 
                SET estado = $2, fecha_actualizacion = NOW()
                WHERE id = $1
            """
        
        try:
            result = await self.execute_query(query, incidencia_id, nuevo_estado.value)
            updated = result.split()[-1] == "1"
            
            if updated:
                self.logger.info(f"✅ Estado actualizado para incidencia {incidencia_id}: {nuevo_estado.value}")
            
            return updated
            
        except Exception as e:
            self.logger.error(f"❌ Error actualizando estado: {e}")
            raise
    
    async def buscar_incidencias_usuario(
        self, 
        usuario_id: int, 
        limite: int = 10
    ) -> List[IncidenciaDB]:
        """
        Buscar incidencias de un usuario.
        
        Args:
            usuario_id: ID del usuario
            limite: Límite de resultados
            
        Returns:
            Lista de incidencias del usuario
        """
        query = """
            SELECT id, usuario_id, numero_ticket, tipo, descripcion, prioridad,
                   estado, fecha_creacion, fecha_actualizacion, fecha_resolucion,
                   tiempo_resolucion_minutos, intentos_resolucion
            FROM incidencias 
            WHERE usuario_id = $1
            ORDER BY fecha_creacion DESC
            LIMIT $2
        """
        
        try:
            rows = await self.fetch_many(query, usuario_id, limite)
            
            incidencias = []
            for row in rows:
                incidencia = IncidenciaDB(
                    id=row['id'],
                    usuario_id=row['usuario_id'],
                    numero_ticket=row['numero_ticket'],
                    tipo=TipoIncidencia(row['tipo']),
                    descripcion=row['descripcion'],
                    prioridad=PrioridadIncidencia(row['prioridad']),
                    estado=EstadoIncidencia(row['estado']),
                    fecha_creacion=row['fecha_creacion'],
                    fecha_actualizacion=row['fecha_actualizacion'],
                    fecha_resolucion=row['fecha_resolucion'],
                    tiempo_resolucion_minutos=row['tiempo_resolucion_minutos'],
                    intentos_resolucion=row['intentos_resolucion']
                )
                incidencias.append(incidencia)
            
            self.logger.debug(f"📄 Incidencias encontradas para usuario {usuario_id}: {len(incidencias)}")
            return incidencias
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando incidencias: {e}")
            raise

