chatbot-langgraph/
├── 📁 nodes/                          # 🔥 NUEVO: Separar cada nodo
│   ├── __init__.py
│   ├── base_node.py                   # Clase base para todos los nodos
│   ├── identificar_usuario.py         # Nodo de identificación
│   ├── procesar_incidencia.py         # Nodo de procesamiento
│   ├── escalar_supervisor.py          # Nodo de escalación
│   └── finalizar_ticket.py            # Nodo de finalización
├── 📁 workflows/                      # 🔥 NUEVO: Orquestación de flujos
│   ├── __init__.py
│   ├── base_workflow.py               # Clase base para workflows
│   ├── incidencia_workflow.py         # Workflow principal
│   └── escalacion_workflow.py         # Workflow de escalación
├── 📁 models/                         # 🔥 MEJORADO: Separar modelos
│   ├── __init__.py
│   ├── state.py                       # Estado del grafo
│   ├── user.py                        # Modelos de usuario
│   ├── incidencia.py                  # Modelos de incidencia
│   └── database_models.py             # Modelos de BD
├── 📁 utils/                          # Utilidades mejoradas
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py              # Gestión de conexiones
│   │   ├── user_repository.py         # Operaciones de usuarios
│   │   └── incidencia_repository.py   # Operaciones de incidencias
│   ├── extractors/
│   │   ├── __init__.py
│   │   ├── user_extractor.py          # Extracción de datos de usuario
│   │   └── intent_extractor.py        # Extracción de intenciones
│   ├── validators/
│   │   ├── __init__.py
│   │   ├── user_validator.py          # Validaciones de usuario
│   │   └── business_rules.py          # Reglas de negocio
│   └── llm/
│       ├── __init__.py
│       ├── providers.py               # Proveedores de LLM
│       └── prompts.py                 # Templates de prompts
├── 📁 config/                         # 🔥 NUEVO: Configuración centralizada
│   ├── __init__.py
│   ├── settings.py                    # Configuraciones
│   ├── logging_config.py              # Configuración de logs
│   └── database_config.py             # Configuración de BD
├── 📁 interfaces/                     # 🔥 NUEVO: Interfaces de UI
│   ├── __init__.py
│   ├── chainlit_app.py                # App de Chainlit
│   ├── fastapi_app.py                 # API REST (futuro)
│   └── websocket_app.py               # WebSocket (futuro)
├── 📁 tests/                          # 🔥 NUEVO: Testing
│   ├── __init__.py
│   ├── test_nodes/
│   ├── test_workflows/
│   ├── test_utils/
│   └── fixtures/
├── 📁 scripts/                        # Scripts de utilidad
│   ├── setup_db.py                    # Configurar BD
│   ├── migrate.py                     # Migraciones
│   └── seed_data.py                   # Datos de prueba
├── main.py                            # 🔥 NUEVO: Entry point único
├── graph.py                           # Constructor del grafo
├── requirements.txt
├── .env.template
├── .env
├── langgraph.json                     # 🔥 NUEVO: Configuración LangGraph
├── pyproject.toml                     # 🔥 NUEVO: Dependencias modernas
└── README.md



# =====================================================
# README.md - Documentación del proyecto
# =====================================================
# Chatbot de Incidencias con LangGraph

🤖 **Un chatbot inteligente para manejo de incidencias técnicas construido con LangGraph y Chainlit.**

## ✨ Características

- 🧠 **Inteligencia Conversacional**: Procesamiento natural con LLMs
- 🔄 **Flujos Complejos**: Conversaciones multi-paso con LangGraph  
- 🗄️ **Integración con BD**: Gestión de usuarios en PostgreSQL
- 🎯 **Identificación Inteligente**: Reconocimiento automático de usuarios
- 🔧 **Escalación Automática**: Derivación inteligente a supervisores
- 📊 **Logging Avanzado**: Monitoreo y debugging completo
- 🧪 **Testing Robusto**: Suite completa de tests automatizados

## 🏗️ Arquitectura

```
chatbot-langgraph/
├── nodes/              # Nodos individuales del grafo
├── workflows/          # Orquestación de flujos de trabajo  
├── models/            # Modelos de datos y estado
├── utils/             # Utilidades y helpers
├── config/            # Configuración centralizada
├── interfaces/        # Interfaces de usuario (Chainlit, FastAPI)
├── tests/             # Tests automatizados
└── scripts/           # Scripts de utilidad
```

## 🚀 Instalación Rápida

```bash
# 1. Clonar y navegar
git clone <tu-repo>
cd chatbot-langgraph

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -e ".[dev]"

# 4. Configurar entorno
cp .env.template .env
# Editar .env con tus configuraciones

# 5. Configurar base de datos
python -m scripts.setup_db

# 6. Ejecutar tests
pytest

# 7. Iniciar aplicación
python main.py
```

## ⚙️ Configuración

### Variables de Entorno Principales

```bash
# API de OpenAI
LLM_OPENAI_API_KEY=tu_api_key

# Base de datos PostgreSQL  
DB_HOST=localhost
DB_NAME=chatbot_db
DB_USER=postgres
DB_PASSWORD=tu_password

# Configuración de la app
APP_DEBUG_MODE=false
APP_LOG_LEVEL=INFO
```

### Configuración de Base de Datos

```bash
# Crear BD y tablas
python -m scripts.setup_db

# Insertar datos de prueba
python -m scripts.seed_data
```

## 🎯 Uso

### Interfaz Chainlit (Por Defecto)
```bash
python main.py
# Abre http://localhost:8000
```

### Interfaz FastAPI (Futuro)
```bash
INTERFACE=fastapi python main.py
```

### Modo Test
```bash
INTERFACE=test python main.py
```

## 🧪 Testing

```bash
# Ejecutar todos los tests
pytest

# Tests con cobertura
pytest --cov

# Tests específicos
pytest tests/test_nodes/
pytest -k "test_user"
```

## 🔧 Desarrollo

### Agregar Nuevo Nodo

```python
# nodes/mi_nuevo_nodo.py
from .base_node import BaseNode, NodeExecutionResult

class MiNuevoNodo(BaseNode):
    def __init__(self):
        super().__init__("MiNuevoNodo")
    
    def get_required_fields(self):
        return ["messages"]
    
    async def execute(self, state):
        # Tu lógica aquí
        return Command(update={
            "messages": [AIMessage(content="Respuesta")],
            "nuevo_campo": "valor"
        })
```

### Scripts Útiles

```bash
# Formatear código
python -m scripts.format_code

# Ejecutar linting
ruff check .

# Configurar pre-commit hooks
pre-commit install
```

## 📚 Documentación

- [Guía de Desarrollo](docs/development.md)
- [API Reference](docs/api.md) 
- [Arquitectura](docs/architecture.md)
- [Deployment](docs/deployment.md)

## 🤝 Contribuir

1. Fork el proyecto
2. Crear rama feature (`git checkout -b feature/nueva-funcionalidad`)
3. Commit cambios (`git commit -am 'Agregar funcionalidad'`)
4. Push a la rama (`git push origin feature/nueva-funcionalidad`)
5. Crear Pull Request

## 📄 Licencia

Este proyecto está bajo la Licencia MIT - ver [LICENSE](LICENSE) para detalles.