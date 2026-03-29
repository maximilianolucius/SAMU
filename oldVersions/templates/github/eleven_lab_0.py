# pip install "elevenlabs[pyaudio]"
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

AGENT_ID = os.getenv("AGENT_ID")  # público o firmado
API_KEY  = os.getenv("ELEVENLABS_API_KEY")  # sólo si tu agente requiere auth


API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
AGENT_ID = os.getenv("AGENT_ID", "")



# Define tu cuestionario
QUESTIONS = [
    "¿Cuál es tu nombre completo?",
    "¿Cuál es tu correo electrónico?",
    "¿Cuál es tu edad?"
]

@dataclass
class SurveyState:
    current_idx: int = 0
    answers: Dict[int, str] = field(default_factory=dict)

    def current_question(self) -> Optional[str]:
        return QUESTIONS[self.current_idx] if self.current_idx < len(QUESTIONS) else None

    def record_answer_and_advance(self, text: str):
        if self.current_idx < len(QUESTIONS):
            self.answers[self.current_idx] = text.strip()
            self.current_idx += 1

state = SurveyState()

def on_agent_response(text: str):
    # Sólo para logging/UI
    print(f"[AGENT] {text}")

def on_agent_response_correction(original: str, corrected: str):
    print(f"[AGENT*] {original} -> {corrected}")

def on_user_transcript(text: str):
    # Llegan transcripciones FINALES por turno del usuario (no parciales)
    print(f"[USER] {text}")
    if state.current_question() is not None:
        state.record_answer_and_advance(text)
        if state.current_question() is None:
            print("\n[✔] Encuesta completa. Respuestas:")
            for i, q in enumerate(QUESTIONS):
                print(f" - P{i+1}: {q} -> {state.answers.get(i, '')}")
        else:
            # Opcional: forzar al agente a hacer la siguiente pregunta con un mensaje de usuario
            # (si tu flujo lo requiere; también podés dejar que el prompt del agente lo haga solo)
            conversation.send_user_message(f"Por favor, continúa con la siguiente pregunta: {state.current_question()}")

# Cliente y conversación
elevenlabs = ElevenLabs(api_key=API_KEY if API_KEY else None)

conversation = Conversation(
    elevenlabs,
    AGENT_ID,
    requires_auth=bool(API_KEY),
    audio_interface=DefaultAudioInterface(),
    callback_agent_response=on_agent_response,
    callback_agent_response_correction=on_agent_response_correction,
    callback_user_transcript=on_user_transcript,
)

# Inicia la sesión (opcional: identifica a tu usuario final)
conversation.start_session()





# Espera a que termine la sesión (Ctrl+C para cortar)
conv_id = conversation.wait_for_session_end()
print("Conversation ID:", conv_id)
