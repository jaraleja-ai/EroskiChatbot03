
async def authenticate_employee_node(state: EroskiState) -> Command:
    """
    Nodo de autenticación con lógica de continuación/parada.
    """
    from langgraph.types import Command
    from langchain_core.messages import AIMessage, HumanMessage
    from datetime import datetime
    
    logger = logging.getLogger("AuthNode")
    
    # ========== CASO 1: USUARIO YA AUTENTICADO ==========
    if state.get("employee_email") and state.get("store_info"):
        logger.info("✅ Usuario ya autenticado, continuando...")
        return Command(update={
            "current_node": "authenticate", 
            "last_activity": datetime.now()
        })
    
    # ========== CASO 2: PRIMERA VEZ O REINTENTO ==========
    messages = state.get("messages", [])
    
    # Si no hay mensajes, es primera vez
    if not messages:
        logger.info("🆕 Primera ejecución, solicitando credenciales")
        
        welcome_message = """¡Hola! Soy el asistente de incidencias de Eroski 🤖

Para ayudarte, necesito identificarte. Por favor, proporciona:
📧 **Tu email corporativo** (nombre@eroski.es)  
🏪 **Tu tienda** (nombre o código)

Por ejemplo: "Mi email es juan.perez@eroski.es y trabajo en Eroski Bilbao"
"""
        
        return Command(update={
            "messages": [AIMessage(content=welcome_message)],
            "current_node": "authenticate",
            "attempts": 1,
            "awaiting_user_input": True,
            "last_activity": datetime.now()
        })
    
    # ========== CASO 3: PROCESAR RESPUESTA DEL USUARIO ==========
    # Buscar último mensaje del usuario
    last_user_message = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break
    
    if last_user_message:
        logger.info("📥 Procesando respuesta del usuario")
        
        # Extraer credenciales (simplificado)
        import re
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@eroski\.es\b', last_user_message, re.IGNORECASE)
        
        if email_match:
            email = email_match.group().lower()
            name = email.split('@')[0].replace('.', ' ').title()
            
            # Extraer tienda (simplificado)
            store_match = re.search(r'eroski\s+([a-záéíóúñ\s]+)', last_user_message, re.IGNORECASE)
            store = store_match.group(1).strip() if store_match else "Tienda no especificada"
            
            logger.info(f"✅ Usuario autenticado: {name}")
            
            return Command(update={
                "employee_email": email,
                "employee_name": name,
                "store_info": store,
                "authenticated": True,
                "awaiting_user_input": False,
                "attempts": 0,
                "messages": messages + [AIMessage(content=f"¡Perfecto {name}! Ya te tengo identificado. ¿En qué puedo ayudarte?")],
                "current_node": "authenticate",
                "last_activity": datetime.now()
            })
    
    # ========== CASO 4: INFORMACIÓN INSUFICIENTE ==========
    attempts = state.get("attempts", 0)
    
    if attempts >= 3:
        logger.warning("⚠️ Demasiados intentos de autenticación")
        return Command(update={
            "escalation_needed": True,
            "escalation_reason": "No se pudo autenticar después de 3 intentos",
            "current_node": "authenticate"
        })
    
    # Solicitar información nuevamente
    retry_message = f"""No he podido verificar tu identidad (intento {attempts}/3).

Por favor, asegúrate de incluir:
📧 Tu email corporativo completo (@eroski.es)
🏪 El nombre o código de tu tienda

¿Puedes intentar de nuevo?"""
    
    return Command(update={
        "messages": messages + [AIMessage(content=retry_message)],
        "attempts": attempts + 1,
        "awaiting_user_input": True,
        "current_node": "authenticate",
        "last_activity": datetime.now()
    })
