# =====================================================
# utils/llm/providers.py - Proveedores de LLM CORREGIDO
# =====================================================
from langchain_openai import AzureChatOpenAI
from typing import Optional
import logging

from config.settings import get_settings

logger = logging.getLogger("LLM.Provider")

# Cache global para instancia de LLM
_llm_instance: Optional[AzureChatOpenAI] = None

def get_llm() -> AzureChatOpenAI:
    """
    Obtener instancia singleton del LLM configurado.
    
    Returns:
        Instancia configurada de AzureChatOpenAI
    """
    global _llm_instance
    
    if _llm_instance is None:
        settings = get_settings()
        
        logger.info(f"🤖 Inicializando LLM: {settings.llm.model}")
        logger.info(f"🔵 Proveedor: Azure OpenAI")
        
        # 🔥 SOLUCIÓN: Usar configuración correcta de Azure OpenAI
        _llm_instance = AzureChatOpenAI(
            # Configuración de Azure OpenAI
            api_key=settings.llm.azure_openai_api_key,  # ✅ API key de Azure
            azure_endpoint=settings.llm.azure_openai_endpoint,  # ✅ Endpoint de Azure
            azure_deployment=settings.llm.azure_deployment_name,  # ✅ Deployment name
            api_version=settings.llm.azure_api_version,  # ✅ API version
            
            # Configuración común
            temperature=settings.llm.temperature,
            max_tokens=settings.llm.max_tokens,
            timeout=settings.llm.timeout
        )
        
        logger.info(f"✅ Azure OpenAI inicializado correctamente")
        logger.info(f"🔧 Deployment: {settings.llm.azure_deployment_name}")
        logger.info(f"🌐 Endpoint: {settings.llm.azure_openai_endpoint}")
    
    return _llm_instance

def reset_llm():
    """Resetear instancia de LLM (útil para tests)"""
    global _llm_instance
    _llm_instance = None
    logger.info("🔄 Instancia LLM reseteada")