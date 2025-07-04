async def _search_database_and_continue(self, state: EroskiState, decision: ConversationDecision, base_update: Dict) -> Command:
    """Buscar en BD y continuar - LÓGICA INTELIGENTE"""
    
    email = decision.extracted_data.get("email")
    self.logger.info(f"🔍 Ejecutando búsqueda en BD para: {email}")
    
    try:
        # 1. BUSCAR EN BASE DE DATOS
        db_result = await self._search_employee_database(email)
        
        if db_result.get("found"):
            # 2. USUARIO ENCONTRADO EN BD - COMPLETAR CON DATOS DE BD
            employee = db_result["employee"]
            self.logger.info(f"✅ Usuario encontrado en BD: {employee.get('name')}")
            
            # Combinar datos de BD con datos extraídos por LLM
            enhanced_data = {
                **base_update["auth_data_collected"],
                "name": employee.get("name", decision.extracted_data.get("name")),
                "email": email,
                "employee_id": employee.get("id"),
                "store_name": employee.get("store_name"),
                "section": decision.extracted_data.get("section", "Por especificar"),
                "found_in_database": True
            }
            
            # Mensaje personalizado con datos de BD
            success_message = f"""✅ **¡Perfecto {employee.get('name', 'usuario')}!** Te he encontrado en el sistema.

**Datos confirmados:**
👤 **Nombre:** {employee.get('name')}
🏪 **Tienda:** {employee.get('store_name')}
📧 **Email:** {email}

Ahora cuéntame: **¿qué problema técnico necesitas reportar?** 🔧"""
            
            # COMPLETAR AUTENTICACIÓN
            base_update.update({
                "auth_data_collected": enhanced_data,
                "authenticated": True,
                "authentication_stage": "completed",
                "datos_usuario_completos": True,
                "ready_for_classification": True,
                "awaiting_user_input": False,  # ✅ NO esperar más input
                "employee_name": employee.get('name'),
                "incident_store_name": employee.get('store_name'),
                "incident_section": enhanced_data.get("section"),
                "incident_email": email,
                "found_in_database": True,
                "employee_data": employee,
                "messages": state.get("messages", []) + [AIMessage(content=success_message)]
            })
            
            return Command(update=base_update)
        
        else:
            # 3. USUARIO NO ENCONTRADO - CONTINUAR INTELIGENTEMENTE
            self.logger.info(f"❌ Usuario no encontrado en BD: {email}")
            
            # ✅ LÓGICA INTELIGENTE: Verificar qué campos YA TENEMOS
            current_data = base_update["auth_data_collected"]
            
            # Verificar campos obligatorios
            has_name = bool(current_data.get("name"))
            has_store = bool(current_data.get("store_name"))
            has_section = bool(current_data.get("section"))
            
            self.logger.info(f"📋 Campos actuales - Nombre: {has_name}, Tienda: {has_store}, Sección: {has_section}")
            
            # ✅ DETERMINAR QUE CAMPOS FALTAN
            missing_fields = []
            if not has_name:
                missing_fields.append("nombre completo")
            if not has_store:
                missing_fields.append("nombre de tu tienda")
            if not has_section:
                missing_fields.append("sección donde ocurrió el problema")
            
            # ✅ GENERAR MENSAJE INTELIGENTE SEGÚN LO QUE FALTA
            if not missing_fields:
                # YA TENEMOS TODO - COMPLETAR AUTENTICACIÓN
                self.logger.info("✅ Todos los campos están completos, finalizando autenticación")
                return self._complete_authentication_with_manual_data(state, current_data, base_update)
            
            else:
                # FALTAN CAMPOS - PEDIRLOS ESPECÍFICAMENTE
                return self._request_missing_fields_intelligently(state, current_data, missing_fields, base_update)
    
    except Exception as e:
        self.logger.error(f"❌ Error en búsqueda BD: {e}")
        return self._handle_database_error(state, base_update, str(e))

def _complete_authentication_with_manual_data(self, state: EroskiState, current_data: Dict, base_update: Dict) -> Command:
    """Completar autenticación con datos manuales cuando ya tenemos todo"""
    
    confirmation_message = f"""✅ **¡Información recopilada correctamente!**

👤 **Empleado:** {current_data.get('name')}
📧 **Email:** {current_data.get('email')}
🏪 **Tienda:** {current_data.get('store_name')}
📍 **Sección:** {current_data.get('section')}

Ahora cuéntame: **¿qué problema técnico estás experimentando?** 🔧"""
    
    base_update.update({
        "authenticated": True,
        "authentication_stage": "completed",
        "datos_usuario_completos": True,
        "ready_for_classification": True,
        "awaiting_user_input": False,  # ✅ NO esperar más input - CONTINUAR
        "employee_name": current_data.get('name'),
        "incident_store_name": current_data.get('store_name'),
        "incident_section": current_data.get('section'),
        "incident_email": current_data.get('email'),
        "found_in_database": False,
        "messages": state.get("messages", []) + [AIMessage(content=confirmation_message)]
    })
    
    return Command(update=base_update)

def _request_missing_fields_intelligently(self, state: EroskiState, current_data: Dict, missing_fields: List[str], base_update: Dict) -> Command:
    """Pedir solo los campos que faltan de forma inteligente"""
    
    # ✅ CONSTRUIR MENSAJE PERSONALIZADO SEGÚN LO QUE YA TENEMOS
    
    # Mostrar lo que ya tenemos
    confirmed_parts = []
    if current_data.get("name"):
        confirmed_parts.append(f"👤 **Nombre:** {current_data['name']}")
    if current_data.get("email"):
        confirmed_parts.append(f"📧 **Email:** {current_data['email']}")
    if current_data.get("store_name"):
        confirmed_parts.append(f"🏪 **Tienda:** {current_data['store_name']}")
    if current_data.get("section"):
        confirmed_parts.append(f"📍 **Sección:** {current_data['section']}")
    
    confirmed_text = "\n".join(confirmed_parts) if confirmed_parts else ""
    
    # ✅ PEDIR SOLO LO QUE FALTA
    if len(missing_fields) == 1:
        missing_text = f"tu **{missing_fields[0]}**"
    elif len(missing_fields) == 2:
        missing_text = f"tu **{missing_fields[0]}** y **{missing_fields[1]}**"
    else:
        missing_text = f"tu **{', '.join(missing_fields[:-1])}** y **{missing_fields[-1]}**"
    
    # Construir mensaje
    if confirmed_text:
        message = f"""Perfecto, ya tengo algunos datos:

{confirmed_text}

Para completar tu información, necesito que me proporciones {missing_text}.

**Ejemplo:** "Trabajo en Eroski Madrid Centro en la sección de carnicería" """
    else:
        message = f"""Tu email no está en nuestra base de datos, pero no hay problema. 👍

Para continuar, necesito que me proporciones {missing_text}.

**Ejemplo:** "Soy María García, trabajo en Eroski Madrid Centro en panadería" """
    
    base_update.update({
        "awaiting_user_input": True,  # ✅ Esperar más información específica
        "found_in_database": False,
        "missing_fields": missing_fields,  # Guardar qué campos faltan
        "messages": state.get("messages", []) + [AIMessage(content=message)]
    })
    
    return Command(update=base_update)

def _handle_database_error(self, state: EroskiState, base_update: Dict, error: str) -> Command:
    """Manejar error de base de datos de forma inteligente"""
    
    current_data = base_update["auth_data_collected"]
    
    # Verificar qué campos faltan aún con el error
    missing_fields = []
    if not current_data.get("name"):
        missing_fields.append("nombre completo")
    if not current_data.get("store_name"):
        missing_fields.append("nombre de tu tienda")
    if not current_data.get("section"):
        missing_fields.append("sección donde trabajas")
    
    if not missing_fields:
        # Tenemos todo, continuar a pesar del error
        error_message = """Ha habido un problema técnico al verificar tu email, pero ya tengo toda tu información necesaria. 👍

¡Continuemos! **¿Qué problema técnico estás experimentando?** 🔧"""
        
        base_update.update({
            "awaiting_user_input": False,  # Continuar
            "authentication_stage": "completed",
            "datos_usuario_completos": True,
            "database_error": error
        })
    else:
        # Faltan campos, pedirlos
        missing_text = ", ".join(missing_fields)
        error_message = f"""Ha ocurrido un error técnico al verificar tu email. 😔

No te preocupes, puedo ayudarte igualmente. Necesito que me proporciones: **{missing_text}**.

**Ejemplo:** "Soy Juan García, trabajo en Eroski Bilbao Centro en carnicería" """
        
        base_update.update({
            "awaiting_user_input": True,
            "database_error": error
        })
    
    base_update["messages"] = state.get("messages", []) + [AIMessage(content=error_message)]
    
    return Command(update=base_update)

# =====================================================
# EJEMPLO DE FLUJOS CON LA NUEVA LÓGICA
# =====================================================

"""
FLUJO 1: Usuario da email + todos los datos
Usuario: "juan@eroski.es, soy Juan García, trabajo en Eroski Madrid Centro en carnicería"
→ BD: No encontrado
→ Sistema: ✅ Ya tengo todo (nombre, tienda, sección)
→ Respuesta: "¡Información completa! ¿Qué problema tienes?"

FLUJO 2: Usuario da solo email
Usuario: "maria@empresa.com"  
→ BD: No encontrado
→ Sistema: ❌ Faltan nombre, tienda, sección
→ Respuesta: "Tu email no está en BD. Necesito tu nombre completo, nombre de tienda y sección"

FLUJO 3: Usuario da email + nombre
Usuario: "pedro@test.com, soy Pedro López"
→ BD: No encontrado  
→ Sistema: ❌ Faltan tienda, sección
→ Respuesta: "Perfecto Pedro, ya tengo tu nombre y email. Necesito nombre de tu tienda y sección"

FLUJO 4: Usuario da email + nombre + tienda
Usuario: "ana@test.com, soy Ana, trabajo en Eroski Sevilla Norte"
→ BD: No encontrado
→ Sistema: ❌ Solo falta sección  
→ Respuesta: "Perfecto Ana, ya tengo tu nombre, email y tienda. Solo necesito la sección donde ocurrió el problema"
"""