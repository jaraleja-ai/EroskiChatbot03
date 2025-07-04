# REEMPLAZAR este método existente:
def _provide_solution(self, state: EroskiState, phase2_result: SpecificProblemDecision) -> Command:
    # ... código que ya tenías con la persistencia básica

# CON esta versión que incluye mensajes:
def _provide_solution(self, state: EroskiState, phase2_result: SpecificProblemDecision) -> Command:
    """Proporcionar solución identificada y actualizar persistencia completa"""
    
    incident_code = state.get("incident_code", "N/A")
    
    solution_message = f"""✅ **Problema identificado: {state.get('incident_type', '').title()}**

📋 **Problema específico:** {phase2_result.specific_problem}

🔧 **Solución paso a paso:**
{phase2_result.proposed_solution}

🤔 **¿Quieres intentar esta solución?**
- Responde **'sí'** para que te guíe paso a paso
- Responde **'no entiendo'** si necesitas más explicación
- Responde **'ya lo intenté'** si ya probaste esto

📋 *Código de incidencia: {incident_code}*"""

    # ✅ ACTUALIZAR PERSISTENCIA COMPLETA CON MENSAJES
    try:
        from pathlib import Path
        import json
        from datetime import datetime
        from langchain_core.messages import HumanMessage, AIMessage
        
        incidents_file = Path("incidents_database.json")
        
        if incidents_file.exists():
            with open(incidents_file, 'r', encoding='utf-8') as f:
                incidents_data = json.load(f)
            
            if incident_code in incidents_data:
                
                # Actualizar datos de clasificación
                incidents_data[incident_code].update({
                    "tipo_incidencia": state.get("incident_type"),
                    "problema_especifico": phase2_result.specific_problem,
                    "solucion_aplicada": phase2_result.proposed_solution,
                    "estado_solucion": "propuesta",
                    "timestamp_actualizacion": datetime.now().isoformat()
                })
                
                # ✅ GUARDAR TODOS LOS MENSAJES
                messages = state.get("messages", [])
                all_messages = messages + [AIMessage(content=solution_message)]
                
                serialized_messages = []
                for msg in all_messages:
                    if isinstance(msg, HumanMessage):
                        serialized_messages.append({
                            "tipo": "usuario",
                            "contenido": msg.content,
                            "timestamp": datetime.now().isoformat()
                        })
                    elif isinstance(msg, AIMessage):
                        serialized_messages.append({
                            "tipo": "bot",
                            "contenido": msg.content,
                            "timestamp": datetime.now().isoformat()
                        })
                
                incidents_data[incident_code]["mensajes"] = serialized_messages
                
                with open(incidents_file, 'w', encoding='utf-8') as f:
                    json.dump(incidents_data, f, indent=2, ensure_ascii=False)
                
                self.logger.info(f"✅ Persistencia y mensajes actualizados para {incident_code}")
                self.logger.info(f"   - Mensajes guardados: {len(serialized_messages)}")
        
    except Exception as e:
        self.logger.error(f"❌ Error actualizando persistencia: {e}")
    
    return Command(
        update={
            **state,
            "messages": state["messages"] + [AIMessage(content=solution_message)],
            "current_step": "verify_solution",
            "awaiting_user_input": True,
            "solution_provided": True
        }
    )

