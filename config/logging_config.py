# =====================================================
# config/logging_config.py - Configuración de logging
# =====================================================
import logging
import sys
from logging.handlers import RotatingFileHandler

from .settings import get_settings

def setup_logging():
    """
    Configurar logging centralizado para toda la aplicación.
    
    Configura:
    - Handler para archivo con rotación
    - Handler para consola  
    - Formateadores consistentes
    - Niveles específicos por módulo
    """
    settings = get_settings()
    log_config = settings.logging
    
    # Crear directorio de logs si no existe
    log_config.log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configurar formato
    formatter = logging.Formatter(log_config.format)
    
    # Handler para archivo con rotación
    file_handler = RotatingFileHandler(
        log_config.file_path,
        maxBytes=log_config.max_file_size,
        backupCount=log_config.backup_count,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # Handler para consola con colores en desarrollo
    console_handler = logging.StreamHandler(sys.stdout)
    if settings.app.is_development:
        console_handler.setFormatter(ColoredFormatter(log_config.format))
    else:
        console_handler.setFormatter(formatter)
    
    # Configurar logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_config.level.upper()))
    
    # Limpiar handlers existentes
    root_logger.handlers.clear()
    
    # Agregar nuevos handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Configurar loggers específicos
    configure_module_loggers(settings)
    
    # Silenciar loggers externos verbosos
    silence_external_loggers()
    
    logging.info("✅ Sistema de logging configurado correctamente")

def configure_module_loggers(settings):
    """Configurar niveles de log específicos por módulo"""
    module_configs = {
        "Node": settings.logging.node_log_level,
        "Workflow": "INFO",
        "Database": settings.logging.database_log_level,
        "LLM": settings.logging.llm_log_level,
        "ChatbotManager": "INFO",
        "Config": "INFO",
    }
    
    for module_name, level in module_configs.items():
        logger = logging.getLogger(module_name)
        logger.setLevel(getattr(logging, level.upper()))

def silence_external_loggers():
    """Silenciar loggers externos que son muy verbosos"""
    external_loggers = [
        "asyncpg",
        "openai", 
        "httpx",
        "urllib3",
        "chainlit",
    ]
    
    for logger_name in external_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

class ColoredFormatter(logging.Formatter):
    """Formatter con colores para desarrollo"""
    
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green  
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[35m',  # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)
