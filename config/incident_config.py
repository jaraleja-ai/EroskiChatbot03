# =====================================================
# config/incident_config.py - Sistema de Configuración de Incidencias
# =====================================================
"""
Sistema completo para gestionar tipos de incidencia desde archivos JSON.

CARACTERÍSTICAS:
- Carga tipos de incidencia desde JSON
- Recarga automática cuando el archivo cambia
- Cache en memoria para rendimiento
- Búsqueda inteligente por palabras clave
- Validación de configuración
- API simple para consultas
- Soporte para múltiples archivos de configuración

ESTRUCTURA JSON ESPERADA:
{
  "incident_types": {
    "tpv": {
      "name": "TPV (Terminal Punto de Venta)",
      "description": "Problemas con cajas registradoras",
      "keywords": ["tpv", "caja", "terminal"],
      "urgency_level": 3,
      "category": "hardware",
      "requires_technical_support": true
    }
  }
}
"""

import json
import logging
from typing import Dict, List, Optional, Any, Set
from pathlib import Path
from datetime import datetime
import os
import hashlib
from dataclasses import dataclass
import re

logger = logging.getLogger("IncidentConfig")

@dataclass
class IncidentType:
    """
    Clase que representa un tipo de incidencia.
    """
    id: str
    name: str
    description: str
    keywords: List[str]
    urgency_level: int = 2
    category: str = "general"
    requires_technical_support: bool = False
    estimated_resolution_minutes: Optional[int] = None
    common_issues: Optional[List[str]] = None
    escalation_contacts: Optional[List[str]] = None
    
    def matches_keywords(self, text: str) -> float:
        """
        Calcular qué tan bien coincide el texto con las palabras clave.
        
        Args:
            text: Texto a analizar
            
        Returns:
            Puntuación de coincidencia (0.0 a 1.0)
        """
        text_lower = text.lower()
        matches = 0
        total_keywords = len(self.keywords)
        
        if total_keywords == 0:
            return 0.0
        
        for keyword in self.keywords:
            if keyword.lower() in text_lower:
                matches += 1
        
        return matches / total_keywords
    
    def get_severity_label(self) -> str:
        """Obtener etiqueta de severidad legible"""
        severity_map = {
            1: "Baja",
            2: "Media", 
            3: "Alta",
            4: "Crítica"
        }
        return severity_map.get(self.urgency_level, "Desconocida")

class IncidentConfigLoader:
    """
    Cargador y gestor de configuración de tipos de incidencia.
    
    RESPONSABILIDADES:
    - Cargar configuración desde archivos JSON
    - Mantener cache en memoria
    - Detectar cambios en archivos
    - Validar configuración
    - Proporcionar API de búsqueda
    """
    
    def __init__(self, config_paths: Optional[List[str]] = None):
        self.config_paths = config_paths or [
            "config/incident_types.json",
            "config/eroski_incidents.json"  # Archivo específico de Eroski
        ]
        
        self.incident_types: Dict[str, IncidentType] = {}
        self.config_data: Dict[str, Any] = {}
        self.file_mtimes: Dict[str, float] = {}
        self.last_loaded: Optional[datetime] = None
        
        # Cache para búsquedas
        self._search_cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_max_size = 100
        
        # Estadísticas
        self.stats = {
            "loads": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "searches": 0
        }
        
        # Cargar configuración inicial
        self.load_config()
    
    def load_config(self) -> bool:
        """
        Cargar configuración desde todos los archivos JSON.
        
        Returns:
            True si se cargó correctamente al menos un archivo
        """
        try:
            self.stats["loads"] += 1
            logger.info("📁 Cargando configuración de incidencias...")
            
            success_count = 0
            all_incident_types = {}
            
            for config_path in self.config_paths:
                if self._load_single_config(config_path, all_incident_types):
                    success_count += 1
            
            if success_count == 0:
                logger.error("❌ No se pudo cargar ningún archivo de configuración")
                self._load_default_config()
                return False
            
            # Convertir a objetos IncidentType
            self.incident_types = {}
            for incident_id, incident_data in all_incident_types.items():
                try:
                    incident_type = IncidentType(
                        id=incident_id,
                        name=incident_data.get("name", incident_id),
                        description=incident_data.get("description", ""),
                        keywords=incident_data.get("keywords", []),
                        urgency_level=incident_data.get("urgency_level", 2),
                        category=incident_data.get("category", "general"),
                        requires_technical_support=incident_data.get("requires_technical_support", False),
                        estimated_resolution_minutes=incident_data.get("estimated_resolution_minutes"),
                        common_issues=incident_data.get("common_issues"),
                        escalation_contacts=incident_data.get("escalation_contacts")
                    )
                    self.incident_types[incident_id] = incident_type
                    
                except Exception as e:
                    logger.error(f"❌ Error creando IncidentType para {incident_id}: {e}")
            
            # Limpiar cache de búsquedas
            self._search_cache.clear()
            
            self.last_loaded = datetime.now()
            logger.info(f"✅ Configuración cargada: {len(self.incident_types)} tipos de incidencia")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cargando configuración: {e}")
            self._load_default_config()
            return False
    
    def _load_single_config(self, config_path: str, all_incident_types: Dict[str, Any]) -> bool:
        """
        Cargar un archivo de configuración específico.
        
        Args:
            config_path: Ruta del archivo
            all_incident_types: Diccionario donde agregar los tipos
            
        Returns:
            True si se cargó correctamente
        """
        try:
            config_file = Path(config_path)
            
            if not config_file.exists():
                logger.warning(f"⚠️ Archivo no encontrado: {config_path}")
                return False
            
            # Verificar si el archivo cambió
            current_mtime = config_file.stat().st_mtime
            if (config_path in self.file_mtimes and 
                current_mtime == self.file_mtimes[config_path]):
                logger.debug(f"📄 Archivo sin cambios: {config_path}")
                return True
            
            # Cargar archivo
            with open(config_file, 'r', encoding='utf-8') as f:
                file_data = json.load(f)
            
            # Validar estructura
            if not self._validate_config_structure(file_data, config_path):
                return False
            
            # Agregar tipos de incidencia
            incident_types = file_data.get("incident_types", {})
            for incident_id, incident_data in incident_types.items():
                if incident_id in all_incident_types:
                    logger.warning(f"⚠️ Tipo duplicado '{incident_id}' en {config_path}")
                
                all_incident_types[incident_id] = incident_data
            
            # Actualizar tiempo de modificación
            self.file_mtimes[config_path] = current_mtime
            
            logger.info(f"✅ Cargado {config_path}: {len(incident_types)} tipos")
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Error JSON en {config_path}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Error cargando {config_path}: {e}")
            return False
    
    def _validate_config_structure(self, data: Dict[str, Any], file_path: str) -> bool:
        """Validar estructura del archivo de configuración"""
        try:
            if "incident_types" not in data:
                logger.error(f"❌ Falta sección 'incident_types' en {file_path}")
                return False
            
            incident_types = data["incident_types"]
            if not isinstance(incident_types, dict):
                logger.error(f"❌ 'incident_types' debe ser diccionario en {file_path}")
                return False
            
            # Validar cada tipo
            for incident_id, incident_data in incident_types.items():
                if not self._validate_incident_type(incident_id, incident_data, file_path):
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error validando {file_path}: {e}")
            return False
    
    def _validate_incident_type(self, incident_id: str, incident_data: Dict, file_path: str) -> bool:
        """Validar un tipo de incidencia específico"""
        required_fields = ["name", "description", "keywords"]
        
        for field in required_fields:
            if field not in incident_data:
                logger.error(f"❌ Tipo '{incident_id}' falta campo '{field}' en {file_path}")
                return False
        
        # Validar keywords es lista
        if not isinstance(incident_data.get("keywords"), list):
            logger.error(f"❌ Tipo '{incident_id}': keywords debe ser lista en {file_path}")
            return False
        
        # Validar urgency_level
        urgency = incident_data.get("urgency_level", 2)
        if not isinstance(urgency, int) or urgency < 1 or urgency > 4:
            logger.warning(f"⚠️ Tipo '{incident_id}': urgency_level inválido en {file_path}")
        
        return True
    
    def _load_default_config(self):
        """Cargar configuración por defecto en caso de error"""
        logger.warning("⚠️ Cargando configuración por defecto")
        
        default_types = {
            "general": IncidentType(
                id="general",
                name="Incidencia General",
                description="Problema general no clasificado",
                keywords=["problema", "error", "fallo", "ayuda"],
                urgency_level=2,
                category="general"
            ),
            "tpv": IncidentType(
                id="tpv",
                name="TPV (Terminal Punto de Venta)",
                description="Problemas con cajas registradoras y terminales de pago",
                keywords=["tpv", "caja", "terminal", "pago", "tarjeta"],
                urgency_level=3,
                category="hardware",
                requires_technical_support=True
            ),
            "red": IncidentType(
                id="red",
                name="Problemas de Red",
                description="Problemas de conectividad e internet",
                keywords=["internet", "wifi", "red", "conexion", "lento"],
                urgency_level=4,
                category="network",
                requires_technical_support=True
            ),
            "otros": IncidentType(
                id="otros",
                name="Otros Problemas",
                description="Otras incidencias no categorizadas",
                keywords=["otro", "otros", "diferente"],
                urgency_level=1,
                category="others"
            )
        }
        
        self.incident_types = default_types
    
    def reload_if_changed(self) -> bool:
        """
        Recargar configuración si algún archivo cambió.
        
        Returns:
            True si se recargó
        """
        try:
            changed = False
            
            for config_path in self.config_paths:
                config_file = Path(config_path)
                if not config_file.exists():
                    continue
                
                current_mtime = config_file.stat().st_mtime
                if (config_path not in self.file_mtimes or 
                    current_mtime != self.file_mtimes[config_path]):
                    changed = True
                    break
            
            if changed:
                logger.info("🔄 Detectados cambios en configuración, recargando...")
                return self.load_config()
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error verificando cambios: {e}")
            return False
    
    # ========== API DE CONSULTA ==========
    
    def get_incident_types(self) -> Dict[str, IncidentType]:
        """
        Obtener todos los tipos de incidencia.
        
        Returns:
            Diccionario con todos los tipos
        """
        self.reload_if_changed()
        return self.incident_types.copy()
    
    def get_incident_type(self, incident_id: str) -> Optional[IncidentType]:
        """
        Obtener un tipo específico de incidencia.
        
        Args:
            incident_id: ID del tipo
            
        Returns:
            IncidentType o None si no existe
        """
        self.reload_if_changed()
        return self.incident_types.get(incident_id)
    
    def get_incident_names(self) -> List[str]:
        """Obtener lista de nombres de todos los tipos"""
        return [incident.name for incident in self.incident_types.values()]
    
    def get_incident_ids(self) -> List[str]:
        """Obtener lista de IDs de todos los tipos"""
        return list(self.incident_types.keys())
    
    def search_by_keywords(self, text: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Buscar tipos de incidencia por palabras clave.
        
        Args:
            text: Texto a buscar
            limit: Máximo número de resultados
            
        Returns:
            Lista ordenada por relevancia
        """
        self.stats["searches"] += 1
        
        # Verificar cache
        cache_key = f"{text.lower()}:{limit}"
        if cache_key in self._search_cache:
            self.stats["cache_hits"] += 1
            return self._search_cache[cache_key].copy()
        
        self.stats["cache_misses"] += 1
        self.reload_if_changed()
        
        matches = []
        text_clean = self._clean_search_text(text)
        
        for incident_type in self.incident_types.values():
            score = self._calculate_match_score(incident_type, text_clean)
            
            if score > 0:
                matches.append({
                    "incident_id": incident_type.id,
                    "incident_type": incident_type,
                    "score": score,
                    "match_reason": self._get_match_reason(incident_type, text_clean)
                })
        
        # Ordenar por puntuación
        matches.sort(key=lambda x: x["score"], reverse=True)
        result = matches[:limit]
        
        # Guardar en cache
        self._cache_search_result(cache_key, result)
        
        return result
    
    def _clean_search_text(self, text: str) -> str:
        """Limpiar texto de búsqueda"""
        # Remover caracteres especiales y normalizar
        text = re.sub(r'[^\w\s]', ' ', text.lower())
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _calculate_match_score(self, incident_type: IncidentType, text: str) -> float:
        """Calcular puntuación de coincidencia"""
        score = 0.0
        
        # Coincidencias exactas en keywords (peso alto)
        keyword_score = incident_type.matches_keywords(text)
        score += keyword_score * 10
        
        # Coincidencias en nombre (peso medio)
        name_words = incident_type.name.lower().split()
        text_words = text.split()
        
        name_matches = sum(1 for word in name_words if word in text_words)
        if name_matches > 0:
            score += (name_matches / len(name_words)) * 5
        
        # Coincidencias en descripción (peso bajo)
        desc_words = incident_type.description.lower().split()
        desc_matches = sum(1 for word in desc_words if word in text_words)
        if desc_matches > 0:
            score += (desc_matches / len(desc_words)) * 2
        
        # Bonus por urgencia alta
        if incident_type.urgency_level >= 3:
            score += 1
        
        return score
    
    def _get_match_reason(self, incident_type: IncidentType, text: str) -> str:
        """Obtener razón de la coincidencia"""
        reasons = []
        
        # Verificar keywords
        matched_keywords = [kw for kw in incident_type.keywords if kw.lower() in text]
        if matched_keywords:
            reasons.append(f"Keywords: {', '.join(matched_keywords[:3])}")
        
        # Verificar nombre
        name_words = incident_type.name.lower().split()
        text_words = text.split()
        matched_name_words = [word for word in name_words if word in text_words]
        if matched_name_words:
            reasons.append(f"Nombre: {', '.join(matched_name_words[:2])}")
        
        return "; ".join(reasons) if reasons else "Coincidencia general"
    
    def _cache_search_result(self, cache_key: str, result: List[Dict[str, Any]]):
        """Guardar resultado en cache"""
        if len(self._search_cache) >= self._cache_max_size:
            # Limpiar cache más antiguo
            oldest_key = next(iter(self._search_cache))
            del self._search_cache[oldest_key]
        
        self._search_cache[cache_key] = result.copy()
    
    def get_by_category(self, category: str) -> List[IncidentType]:
        """
        Obtener tipos por categoría.
        
        Args:
            category: Categoría a filtrar
            
        Returns:
            Lista de tipos en la categoría
        """
        self.reload_if_changed()
        return [
            incident_type for incident_type in self.incident_types.values()
            if incident_type.category == category
        ]
    
    def get_urgent_types(self, min_urgency: int = 3) -> List[IncidentType]:
        """
        Obtener tipos urgentes.
        
        Args:
            min_urgency: Nivel mínimo de urgencia
            
        Returns:
            Lista de tipos urgentes
        """
        self.reload_if_changed()
        return [
            incident_type for incident_type in self.incident_types.values()
            if incident_type.urgency_level >= min_urgency
        ]
    
    def requires_technical_support(self, incident_id: str) -> bool:
        """
        Verificar si requiere soporte técnico.
        
        Args:
            incident_id: ID del tipo
            
        Returns:
            True si requiere soporte técnico
        """
        incident_type = self.get_incident_type(incident_id)
        return incident_type.requires_technical_support if incident_type else True
    
    def get_escalation_contacts(self, incident_id: str) -> List[str]:
        """
        Obtener contactos de escalación.
        
        Args:
            incident_id: ID del tipo
            
        Returns:
            Lista de contactos
        """
        incident_type = self.get_incident_type(incident_id)
        return incident_type.escalation_contacts or [] if incident_type else []
    
    def get_estimated_resolution_time(self, incident_id: str) -> Optional[int]:
        """
        Obtener tiempo estimado de resolución.
        
        Args:
            incident_id: ID del tipo
            
        Returns:
            Minutos estimados o None
        """
        incident_type = self.get_incident_type(incident_id)
        return incident_type.estimated_resolution_minutes if incident_type else None
    
    def get_categories(self) -> Set[str]:
        """Obtener todas las categorías disponibles"""
        self.reload_if_changed()
        return {incident_type.category for incident_type in self.incident_types.values()}
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtener estadísticas del sistema"""
        return {
            **self.stats,
            "total_types": len(self.incident_types),
            "cache_size": len(self._search_cache),
            "last_loaded": self.last_loaded.isoformat() if self.last_loaded else None,
            "config_files": len(self.config_paths),
            "categories": list(self.get_categories())
        }

# ========== INSTANCIA GLOBAL ==========

_global_config_loader: Optional[IncidentConfigLoader] = None

def get_incident_config() -> IncidentConfigLoader:
    """
    Obtener instancia global del cargador de configuración.
    
    Returns:
        Instancia global del cargador
    """
    global _global_config_loader
    
    if _global_config_loader is None:
        _global_config_loader = IncidentConfigLoader()
    
    return _global_config_loader

# ========== FUNCIONES DE CONVENIENCIA ==========

def search_incident_types(text: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Función de conveniencia para buscar tipos de incidencia.
    
    Args:
        text: Texto a buscar
        limit: Máximo número de resultados
        
    Returns:
        Lista de coincidencias
    """
    config = get_incident_config()
    return config.search_by_keywords(text, limit)

def get_incident_by_id(incident_id: str) -> Optional[IncidentType]:
    """
    Función de conveniencia para obtener tipo por ID.
    
    Args:
        incident_id: ID del tipo
        
    Returns:
        IncidentType o None
    """
    config = get_incident_config()
    return config.get_incident_type(incident_id)

def reload_incident_config() -> bool:
    """
    Función de conveniencia para recargar configuración.
    
    Returns:
        True si se recargó correctamente
    """
    config = get_incident_config()
    return config.load_config()