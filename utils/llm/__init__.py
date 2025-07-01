# =====================================================
# utils/llm/__init__.py - Exportaciones
# =====================================================
from .providers import get_llm, reset_llm
from .message_generator import generate_natural_message, detect_confirmation_intent, generate_followup_questions
from .prompts import URGENCY_CLASSIFICATION_PROMPT, INCIDENT_SUMMARY_PROMPT

__all__ = [
    "get_llm",
    "reset_llm",
    "generate_natural_message", 
    "detect_confirmation_intent",
    "generate_followup_questions",
    "URGENCY_CLASSIFICATION_PROMPT",
    "INCIDENT_SUMMARY_PROMPT"
]