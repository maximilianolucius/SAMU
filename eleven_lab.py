#!/usr/bin/env python3
"""
Cliente de voz SAMI — sesion conversacional con ElevenLabs Conversational AI.

Usa el SDK de ElevenLabs para iniciar una sesion de voz con el agente,
capturando audio del microfono y reproduciendo las respuestas.
Incluye un flujo de encuesta basico como ejemplo.

Requisitos extra:
    pip install "elevenlabs[pyaudio]"

Uso:
    python eleven_lab.py
"""

from dataclasses import dataclass, field
from typing import Dict, Optional

from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

from config import ELEVENLABS_API_KEY, AGENT_ID, setup_logging, require_elevenlabs

logger = setup_logging("eleven_lab")

# Preguntas de la encuesta de ejemplo
QUESTIONS = [
    "Cual es tu nombre completo?",
    "Cual es tu correo electronico?",
    "Cual es tu edad?",
]


@dataclass
class SurveyState:
    """Estado de la encuesta: rastrea la pregunta actual y las respuestas recolectadas."""

    current_idx: int = 0
    answers: Dict[int, str] = field(default_factory=dict)

    def current_question(self) -> Optional[str]:
        """Devuelve la pregunta actual o None si la encuesta termino."""
        if self.current_idx < len(QUESTIONS):
            return QUESTIONS[self.current_idx]
        return None

    def record_answer_and_advance(self, text: str) -> None:
        """Guarda la respuesta y avanza a la siguiente pregunta."""
        if self.current_idx < len(QUESTIONS):
            self.answers[self.current_idx] = text.strip()
            self.current_idx += 1


def on_agent_response(text: str) -> None:
    """Callback: se ejecuta cada vez que el agente responde."""
    logger.info("[AGENT] %s", text)


def on_agent_response_correction(original: str, corrected: str) -> None:
    """Callback: se ejecuta cuando el agente corrige una respuesta previa."""
    logger.info("[AGENT*] %s -> %s", original, corrected)


def on_user_transcript(text: str) -> None:
    """Callback: se ejecuta con la transcripcion final de cada turno del usuario."""
    logger.info("[USER] %s", text)
    if state.current_question() is not None:
        state.record_answer_and_advance(text)
        if state.current_question() is None:
            logger.info("Encuesta completa:")
            for i, q in enumerate(QUESTIONS):
                logger.info("  P%d: %s -> %s", i + 1, q, state.answers.get(i, ""))
        elif conversation is not None:
            conversation.send_user_message(
                f"Por favor, continua con la siguiente pregunta: {state.current_question()}"
            )


# Estado global del flujo de encuesta
state = SurveyState()
conversation: Optional[Conversation] = None


def main() -> None:
    """Inicia la sesion de voz con ElevenLabs y espera a que termine."""
    global conversation

    require_elevenlabs()
    logger.info("Iniciando sesion de voz con agente %s", AGENT_ID)

    client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
    conversation = Conversation(
        client,
        AGENT_ID,
        requires_auth=True,
        audio_interface=DefaultAudioInterface(),
        callback_agent_response=on_agent_response,
        callback_agent_response_correction=on_agent_response_correction,
        callback_user_transcript=on_user_transcript,
    )

    conversation.start_session()
    conv_id = conversation.wait_for_session_end()
    logger.info("Sesion finalizada. Conversation ID: %s", conv_id)


if __name__ == "__main__":
    main()
