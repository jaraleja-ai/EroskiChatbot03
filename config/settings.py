# =====================================================
# config/settings.py - Configuración centralizada
# =====================================================
from pydantic_settings import BaseSettings
from typing import Optional, Literal
from pydantic import ConfigDict
from pathlib import Path

class DatabaseSettings(BaseSettings):
    """Configuración de base de datos PostgreSQL"""
    
    host: str = "localhost"
    port: int = 5432
    name: str = "chatbot_db"
    user: str = "postgres"
    password: str = ""  # Sin password por defecto para desarrollo
    pool_min_size: int = 1
    pool_max_size: int = 10
    command_timeout: int = 60
    
    model_config = ConfigDict(extra="ignore", env_prefix="DB_")
        
    @property
    def connection_string(self) -> str:
        """Generar string de conexión PostgreSQL"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"
    
    @property
    def test_connection_string(self) -> str:
        """String de conexión para tests"""
        test_db_name = f"test_{self.name}"
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{test_db_name}"

class LLMSettings(BaseSettings):
    """
    Configuración de LLM con soporte para Azure OpenAI
    """
    
    # Proveedor de LLM
    provider: Literal["openai", "azure"] = "azure"
    
    # Configuración de OpenAI (original)
    openai_api_key: Optional[str] = None
    
    # Configuración de Azure OpenAI
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_deployment_name: Optional[str] = None
    azure_api_version: str = "2024-02-15-preview"
    
    # Configuración común
    model: str = "gpt-4"
    temperature: float = 0.7
    max_tokens: int = 2000
    timeout: int = 30
    
    model_config = ConfigDict(extra="ignore", env_prefix="LLM_")

    def get_active_api_key(self) -> str:
        """Obtener la API key activa según el proveedor"""
        if self.provider == "azure":
            if not self.azure_openai_api_key:
                raise ValueError("AZURE_OPENAI_API_KEY requerida para provider 'azure'")
            return self.azure_openai_api_key
        else:
            if not self.openai_api_key:
                raise ValueError("OPENAI_API_KEY requerida para provider 'openai'")
            return self.openai_api_key
    
    def validate_azure_config(self) -> bool:
        """Validar configuración específica de Azure"""
        if self.provider != "azure":
            return True
            
        required_fields = [
            ("azure_openai_api_key", self.azure_openai_api_key),
            ("azure_openai_endpoint", self.azure_openai_endpoint), 
            ("azure_deployment_name", self.azure_deployment_name)
        ]
        
        missing_fields = [name for name, value in required_fields if not value]
        
        if missing_fields:
            raise ValueError(f"Campos requeridos para Azure: {missing_fields}")
        
        return True

class ApplicationSettings(BaseSettings):
    """Configuración general de la aplicación"""
    
    debug_mode: bool = False
    log_level: str = "INFO"
    session_timeout: int = 3600
    
    # Configuración específica del chatbot
    max_intentos_identificacion: int = 5
    max_intentos_incidencia: int = 3
    enable_auto_escalation: bool = True
    
    model_config = ConfigDict(extra="ignore", env_prefix="APP_")

    @property
    def is_development(self) -> bool:
        """Verificar si estamos en modo desarrollo"""
        return self.debug_mode or self.log_level == "DEBUG"

class WorkflowSettings(BaseSettings):
    """Configuración específica de workflows"""
    
    enable_database_lookup: bool = True
    require_email_confirmation: bool = True
    auto_escalate_after_attempts: int = 5
    enable_llm_message_generation: bool = True
    enable_similarity_matching: bool = True
    
    # Timeouts para diferentes operaciones
    user_response_timeout: int = 300  # 5 minutos
    database_query_timeout: int = 10  # 10 segundos
    llm_response_timeout: int = 30    # 30 segundos
    
    model_config = ConfigDict(extra="ignore", env_prefix="WORKFLOW_")

class LoggingSettings(BaseSettings):
    """Configuración de logging"""
    
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: str = "logs/chatbot.log"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    
    # Configuración específica por módulo
    node_log_level: str = "DEBUG"
    database_log_level: str = "WARNING" 
    llm_log_level: str = "INFO"
    
    model_config = ConfigDict(extra="ignore", env_prefix="LOG_")

    @property
    def log_dir(self) -> Path:
        """Directorio de logs"""
        return Path(self.file_path).parent

class ChainlitSettings(BaseSettings):
    """Configuración específica de Chainlit"""
    
    port: int = 8000
    host: str = "localhost"
    debug: bool = False
    
    # UI Configuration
    theme: str = "light"
    show_readme_as_default: bool = False
    enable_telemetry: bool = False
    
    model_config = ConfigDict(extra="ignore", env_prefix="CHAINLIT_")

class SecuritySettings(BaseSettings):
    """Configuración de seguridad"""
    
    secret_key: str = "change-me-in-production"
    token_expire_minutes: int = 30
    
    # Rate limiting
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    
    model_config = ConfigDict(extra="ignore", env_prefix="SECURITY_")

class Settings(BaseSettings):
    """Configuración principal que agrupa todas las demás"""
    
    # 🔥 CAMBIO CRÍTICO: Inicializar sub-configuraciones correctamente
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Inicializar cada sub-configuración independientemente
        # para que lean sus propias variables de entorno
        self.database = DatabaseSettings()
        self.llm = LLMSettings()
        self.app = ApplicationSettings()
        self.workflow = WorkflowSettings()
        self.logging = LoggingSettings()
        self.chainlit = ChainlitSettings()
        self.security = SecuritySettings()
    
    # Declarar los campos como Optional para evitar conflictos
    database: Optional[DatabaseSettings] = None
    llm: Optional[LLMSettings] = None
    app: Optional[ApplicationSettings] = None
    workflow: Optional[WorkflowSettings] = None
    logging: Optional[LoggingSettings] = None
    chainlit: Optional[ChainlitSettings] = None
    security: Optional[SecuritySettings] = None
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # 🔥 IMPORTANTE: Ignorar variables extra aquí también
    )
    
    def validate_configuration(self) -> list[str]:
        """Validar toda la configuración y retornar errores"""
        errors = []
        
        # Validar configuración de Azure
        try:
            self.llm.validate_azure_config()
        except ValueError as e:
            errors.append(f"Error en configuración LLM: {e}")
        
        # Validar directorio de logs
        try:
            self.logging.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            errors.append(f"No se puede crear directorio de logs: {e}")
        
        # Validar configuración de BD en producción
        if not self.app.is_development and self.database.password == "password":
            errors.append("Usar password por defecto en producción es inseguro")
        
        return errors

# Singleton pattern para configuración global
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """
    Obtener instancia singleton de configuración.
    
    Returns:
        Instancia de Settings con toda la configuración cargada
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

def reload_settings():
    """Recargar configuración (útil para tests o cambios en runtime)"""
    global _settings
    _settings = None

def validate_environment() -> bool:
    """
    Validar que el entorno esté configurado correctamente.
    
    Returns:
        True si todo está bien, False si hay errores
    """
    settings = get_settings()
    errors = settings.validate_configuration()
    
    if errors:
        import logging
        logger = logging.getLogger("Config")
        logger.error("Errores de configuración encontrados:")
        for error in errors:
            logger.error(f"  - {error}")
        return False
    
    return True