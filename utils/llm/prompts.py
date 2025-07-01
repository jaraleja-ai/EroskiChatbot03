
# =====================================================
# utils/llm/prompts.py - Templates de prompts reutilizables
# =====================================================
from langchain.prompts import PromptTemplate

# Prompt para clasificación de urgencia
URGENCY_CLASSIFICATION_PROMPT = PromptTemplate(
    input_variables=["descripcion"],
    template="""
Analiza la siguiente descripción de incidencia y clasifica su urgencia:

Descripción: {descripcion}

Niveles de urgencia:
- CRITICA: Sistema completamente caído, pérdida de datos, afecta a múltiples usuarios
- ALTA: Problema severo que impide trabajo normal, afecta productividad significativamente  
- MEDIA: Problema molesto pero existen workarounds, afecta funcionalidad parcialmente
- BAJA: Problema menor, solicitud de mejora, no afecta trabajo crítico

Considera:
- Impacto en la productividad
- Número de usuarios afectados
- Disponibilidad de soluciones alternativas
- Criticidad del sistema afectado

Responde solo: CRITICA, ALTA, MEDIA o BAJA
"""
)

# Prompt para generar resumen de incidencia
INCIDENT_SUMMARY_PROMPT = PromptTemplate(
    input_variables=["tipo", "descripcion", "detalles"],
    template="""
Genera un resumen técnico estructurado de la siguiente incidencia:

Tipo: {tipo}
Descripción: {descripcion}
Detalles: {detalles}

El resumen debe incluir:
1. Problema principal en 1-2 líneas
2. Síntomas observados
3. Componentes/sistemas afectados
4. Pasos iniciales de diagnóstico recomendados

Formato: Párrafos cortos, máximo 100 palabras total.
"""
)