# 📁 ARCHIVOS AFECTADOS EN LA MIGRACIÓN

## 🔥 ARCHIVOS QUE SE MODIFICAN (6 archivos principales)

### 1. `models/state.py` 
**Cambio:** MODERADO - Expandir GraphState
```python
# ANTES: Estado básico
class GraphState(TypedDict):
    messages: list
    nombre: str
    email: str

# DESPUÉS: Estado escalable  
class GraphState(TypedDict):
    # Control de flujo
    current_step: str
    awaiting_input: bool
    next_action: str
    # ... todos los campos nuevos
```

### 2. `workflow/incidencia_workflow.py`
**Cambio:** GRANDE - Nuevo sistema de routing
```python
# ANTES: Routing complejo con muchos ifs
def route_identificacion(state):
    if esto and aquello:
        return "nodo_x"
    elif otra_cosa:
        return "nodo_y"
    # ... mucha lógica

# DESPUÉS: Routing simple
def route_conversation(state):
    if state.get("awaiting_input"): 
        return "__interrupt__"
    return STEP_MAP[state.get("current_step")]
```

### 3. `nodes/identificar_usuario.py`
**Cambio:** MODERADO - Usar nuevo patrón
```python
# ANTES: Lógica de routing en el nodo
return Command(update={...})

# DESPUÉS: Usar helpers de transición
return self.transition_to("waiting_confirmation", awaiting_input=True)
```

### 4. `nodes/base_node.py`
**Cambio:** PEQUEÑO - Agregar helpers
```python
# AGREGAR: Métodos helper para transiciones
def transition_to(self, next_step, awaiting_input=False, **updates):
def wait_for_input(self, next_step, message, next_action=None):
```

### 5. `graph.py`
**Cambio:** PEQUEÑO - Usar nuevo routing
```python
# ANTES: Múltiples routers
workflow.add_conditional_edges("identificar_usuario", route_identificacion)
workflow.add_conditional_edges("otro_nodo", route_otro)

# DESPUÉS: Un solo router
for node in workflow.nodes:
    workflow.add_conditional_edges(node, route_conversation)
```

### 6. `interfaces/chainlit_app.py`
**Cambio:** MÍNIMO - Usar interrupciones
```python
# ANTES: Streaming continuo
async for event in graph.astream(state):
    # procesar

# DESPUÉS: Interrupciones
result = graph.invoke(state, thread_id=session_id)
# Se para automáticamente en __interrupt__
```

## ✅ ARCHIVOS QUE NO SE TOCAN (La mayoría)

- `config/` - Sin cambios
- `utils/` - Sin cambios  
- `models/user.py` - Sin cambios
- `models/incidencia.py` - Sin cambios
- Todos los archivos de BD - Sin cambios
- `main.py` - Sin cambios
- `.env` - Sin cambios
- `requirements.txt` - Sin cambios

## 🆕 ARCHIVOS NUEVOS (Opcionales)

### `workflow/conversation_steps.py` (NUEVO)
```python
class ConversationSteps:
    START = "start"
    IDENTIFYING_USER = "identifying_user"
    # ... definiciones de pasos
```

### `nodes/` - Nodos nuevos (cuando los agregues)
- `categorizar_incidencia.py`
- `recopilar_detalles.py`  
- `analizar_incidencia.py`
- `proponer_solucion.py`
- `crear_ticket.py`

## 📊 RESUMEN DE ESFUERZO

| Archivo | Líneas a cambiar | Complejidad | Tiempo |
|---------|------------------|-------------|---------|
| `models/state.py` | ~30 líneas | Fácil | 30 min |
| `workflow/incidencia_workflow.py` | ~100 líneas | Media | 2 horas |
| `nodes/identificar_usuario.py` | ~50 líneas | Media | 1 hora |
| `nodes/base_node.py` | ~20 líneas | Fácil | 30 min |
| `graph.py` | ~10 líneas | Fácil | 15 min |
| `interfaces/chainlit_app.py` | ~5 líneas | Fácil | 15 min |

**TOTAL: ~4-5 horas de desarrollo**

## 🎯 VENTAJAS DE HACERLO AHORA

- ✅ No hay deuda técnica acumulada
- ✅ No hay usuarios en producción que afectar
- ✅ Puedes testear desde cero
- ✅ Base sólida para crecer
- ✅ Patrón consistente desde el inicio