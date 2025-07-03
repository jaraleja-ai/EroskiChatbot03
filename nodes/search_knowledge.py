# =====================================================
# nodes/eroski/search_knowledge.py - Nodo de Búsqueda de Conocimiento
# =====================================================
"""
Nodo para buscar información en base de conocimiento para consultas generales.

RESPONSABILIDADES:
- Buscar información relevante para consultas no técnicas
- Proporcionar respuestas informativas
- Acceder a documentación de procedimientos
- Responder preguntas sobre políticas y procesos
"""

from typing import Dict, Any, Optional, List
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.types import Command
from datetime import datetime
import logging
import re

from models.eroski_state import EroskiState, SolutionType
from nodes.base_node import BaseNode

class search_knowledge_node(BaseNode):
    """
    Nodo para buscar información en base de conocimiento.
    
    CARACTERÍSTICAS:
    - Búsqueda de información general
    - Respuestas sobre políticas y procedimientos
    - Información sobre servicios de Eroski
    - Guías de procesos internos
    """
    
    def __init__(self):
        super().__init__("SearchKnowledge")
        
        # Base de conocimiento de información general
        self.knowledge_base = {
            "horarios": {
                "keywords": ["horario", "horarios", "abierto", "cerrado", "hora"],
                "title": "Horarios de Tienda",
                "content": """**Horarios Generales Eroski:**

🕐 **Horarios Estándar:**
• Lunes a Sábado: 9:00 - 21:30
• Domingos: 10:00 - 15:00

🏪 **Hipermercados:**
• Lunes a Sábado: 9:00 - 22:00
• Domingos: 10:00 - 20:00

⛽ **Gasolineras:**
• Todos los días: 24 horas

⚠️ **Nota:** Los horarios pueden variar según la ubicación. Consulta con tu responsable de tienda para horarios específicos.""",
                "category": "información_general"
            },
            "devoluciones": {
                "keywords": ["devolución", "devolver", "cambio", "ticket", "recibo"],
                "title": "Proceso de Devoluciones",
                "content": """**Proceso de Devoluciones Eroski:**

📋 **Requisitos:**
• Ticket de compra original
• Producto en buen estado
• Máximo 15 días desde la compra

🔄 **Pasos a seguir:**
1. Verificar estado del producto
2. Revisar fecha en el ticket
3. Acceder al TPV con tu usuario
4. Seleccionar "Devolución"
5. Escanear código de barras del producto
6. Introducir motivo de devolución
7. Procesar reembolso o cambio

💳 **Reembolsos:**
• Efectivo: Inmediato
• Tarjeta: 3-5 días hábiles

📞 **Consultas especiales:** Contacta con tu supervisor""",
                "category": "procedimientos"
            },
            "usuario_tpv": {
                "keywords": ["usuario", "tpv", "login", "contraseña", "acceso"],
                "title": "Acceso al TPV",
                "content": """**Acceso al Sistema TPV:**

🔑 **Inicio de Sesión:**
• Usuario: Tu número de empleado
• Contraseña: Proporcionada por RRHH

🔄 **Cambio de Contraseña:**
1. Accede con tu usuario actual
2. Ve a "Configuración"
3. Selecciona "Cambiar contraseña"
4. Introduce contraseña actual
5. Introduce nueva contraseña (mínimo 8 caracteres)
6. Confirma nueva contraseña

🚫 **Problemas de Acceso:**
• Usuario bloqueado: Contacta con tu supervisor
• Contraseña olvidada: Solicita reset a RRHH
• Error de sistema: Contacta con soporte técnico

⚠️ **Importante:** Nunca compartas tu usuario con otros empleados""",
                "category": "procedimientos"
            },
            "descuentos": {
                "keywords": ["descuento", "promoción", "oferta", "precio"],
                "title": "Aplicación de Descuentos",
                "content": """**Aplicación de Descuentos y Promociones:**

🎯 **Tipos de Descuentos:**
• Descuentos automáticos (se aplican al escanear)
• Descuentos manuales (requieren autorización)
• Descuentos empleado (con tarjeta de empleado)

📱 **Proceso en TPV:**
1. Escanear productos normalmente
2. Para descuentos manuales: Tecla F5
3. Introducir código de descuento
4. Aplicar descuento al producto específico
5. Confirmar con supervisor si es necesario

👥 **Descuentos Empleado:**
• 5% en compras personales
• Aplica automáticamente con tarjeta de empleado
• Límite: 500€ mensuales

🔍 **Verificación:**
• Siempre verifica que el descuento sea válido
• Consulta con supervisor para descuentos altos
• Documenta descuentos especiales""",
                "category": "procedimientos"
            },
            "limpieza": {
                "keywords": ["limpieza", "limpiar", "higiene", "desinfectar"],
                "title": "Protocolos de Limpieza",
                "content": """**Protocolos de Limpieza e Higiene:**

🧽 **Limpieza General:**
• Superficies: Cada 2 horas
• Suelos: Cada 4 horas o cuando sea necesario
• Baños: Cada hora

🍖 **Áreas Alimentarias:**
• Antes de cada turno
• Después de manipular productos
• Cambio de guantes obligatorio

🧴 **Productos Autorizados:**
• Desinfectante multiusos
• Limpiacristales
• Desengrasante para cocina

⏰ **Frecuencia:**
• Apertura: Limpieza completa
• Cada 2 horas: Superficies de contacto
• Cierre: Limpieza profunda

📋 **Registro:**
• Anotar todas las limpiezas realizadas
• Firmar hoja de control
• Reportar cualquier incidencia""",
                "category": "procedimientos"
            },
            "seguridad": {
                "keywords": ["seguridad", "emergencia", "accidente", "peligro"],
                "title": "Protocolos de Seguridad",
                "content": """**Protocolos de Seguridad:**

🚨 **Emergencias:**
• Teléfono emergencias: 112
• Evacuación: Seguir rutas señalizadas
• Punto de encuentro: Parking exterior

🔥 **Incendios:**
1. Activar alarma
2. Llamar a bomberos (112)
3. Evacuar zona
4. Usar extintor solo si es seguro

⚡ **Accidentes:**
• Accidente laboral: Reportar inmediatamente
• Botiquín: Ubicado en cada sección
• Primeros auxilios: Solo personal capacitado

🏥 **Contactos de Emergencia:**
• Emergencias: 112
• Soporte técnico: +34 946 211 000
• Supervisor de turno: Ext. 100

📋 **Reporte:**
• Documentar todos los incidentes
• Completar parte de accidentes
• Notificar a RRHH""",
                "category": "seguridad"
            }
        }
    
    def get_required_fields(self) -> List[str]:
        return ["messages", "authenticated"]
    
    def get_actor_description(self) -> str:
        return "Busco información en base de conocimiento para consultas generales"
    
    async def execute(self, state: EroskiState) -> Command:
        """
        Ejecutar búsqueda de información.
        
        Args:
            state: Estado actual del workflow
            
        Returns:
            Command con la información encontrada
        """
        print("🎗️"*50)
        print(f"entra en el nodo: {self.__class__.__name__}")
        try:
            # Obtener consulta del usuario
            user_message = self.get_last_user_message(state)
            if not user_message:
                return self._request_clarification(state)
            
            # Buscar información relevante
            search_results = self._search_knowledge_base(user_message)
            
            if not search_results:
                return self._no_information_found(state, user_message)
            
            # Proporcionar información encontrada
            return self._provide_information(state, search_results)
            
        except Exception as e:
            self.logger.error(f"❌ Error buscando información: {e}")
            return self._escalate_error(state, str(e))
    
    def _search_knowledge_base(self, query: str) -> List[Dict[str, Any]]:
        """Buscar en base de conocimiento"""
        query_lower = query.lower()
        results = []
        
        for topic_id, topic_data in self.knowledge_base.items():
            score = self._calculate_relevance_score(query_lower, topic_data)
            
            if score > 0:
                results.append({
                    "topic_id": topic_id,
                    "topic_data": topic_data,
                    "score": score,
                    "title": topic_data["title"],
                    "content": topic_data["content"],
                    "category": topic_data["category"]
                })
        
        # Ordenar por relevancia
        results.sort(key=lambda x: x["score"], reverse=True)
        
        return results[:2]  # Top 2 resultados más relevantes
    
    def _calculate_relevance_score(self, query: str, topic_data: Dict[str, Any]) -> float:
        """Calcular puntuación de relevancia"""
        score = 0.0
        keywords = topic_data.get("keywords", [])
        
        # Puntuación por keywords exactas
        for keyword in keywords:
            if keyword in query:
                score += 1.0
        
        # Puntuación por palabras relacionadas
        query_words = query.split()
        for keyword in keywords:
            keyword_words = keyword.split()
            for qword in query_words:
                for kword in keyword_words:
                    if len(qword) > 3 and qword in kword:
                        score += 0.5
        
        return score
    
    def _provide_information(self, state: EroskiState, results: List[Dict[str, Any]]) -> Command:
        """Proporcionar información encontrada"""
        
        # Construir mensaje con la información
        info_message = self._build_information_message(results)
        
        # Determinar si necesita seguimiento
        needs_followup = len(results) > 1 or any(
            result["category"] == "procedimientos" for result in results
        )
        
        return Command(update={
            "solution_found": True,
            "solution_type": SolutionType.AUTOMATICA,
            "solution_content": results[0]["content"],
            "information_provided": [result["title"] for result in results],
            "search_results": results,
            "needs_followup": needs_followup,
            "messages": [AIMessage(content=info_message)],
            "current_node": "search_knowledge",
            "last_activity": datetime.now(),
            "awaiting_user_input": False
        })
    
    def _build_information_message(self, results: List[Dict[str, Any]]) -> str:
        """Construir mensaje con información encontrada"""
        
        if len(results) == 1:
            result = results[0]
            return f"""ℹ️ **INFORMACIÓN ENCONTRADA**

**Tema:** {result['title']}

{result['content']}

---

¿Esta información responde a tu consulta o necesitas algo más específico? 🤔"""