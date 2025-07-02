
    """Registrar decisión del actor para debugging"""
    decision_record = {
        "timestamp": datetime.now().isoformat(),
        "decision": decision,
        "target": target,
        "actor": self.name
    }
    self._actor_state["decision_history"].append(decision_record)
    
    # Mantener solo últimas 10 decisiones
    if len(self._actor_state["decision_history"]) > 10:
        self._actor_state["decision_history"] = self._actor_state["decision_history"][-10:]