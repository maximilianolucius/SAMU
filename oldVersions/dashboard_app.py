"""
Monitor de conversaciones de ElevenLabs via polling a la API REST.

Consulta periodicamente el endpoint de conversaciones para detectar
llamadas nuevas, activas y finalizadas, e imprime un resumen en consola.

Uso:
    python dashboard_app.py
"""

import time
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

import requests

from config import (
    ELEVENLABS_API_KEY, AGENT_ID, ELEVENLABS_BASE_URL, ELEVENLABS_TIMEOUT,
    setup_logging, require_elevenlabs,
)

logger = setup_logging("dashboard")


class ElevenLabsMonitor:
    """Monitorea conversaciones de un agente ElevenLabs en tiempo real via polling."""

    def __init__(self, api_key: str, agent_id: str) -> None:
        self.api_key = api_key
        self.agent_id = agent_id
        self.base_url = f"{ELEVENLABS_BASE_URL}/v1/convai"
        self.headers: Dict[str, str] = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        }

    def get_conversations(self) -> Optional[Dict[str, Any]]:
        """Obtiene la lista de conversaciones desde la API."""
        url = f"{self.base_url}/conversations"
        try:
            r = requests.get(url, headers=self.headers, timeout=ELEVENLABS_TIMEOUT)
            if r.status_code == 200:
                return r.json()
            logger.warning("API devolvio status %d: %s", r.status_code, r.text[:200])
            return None
        except requests.RequestException as e:
            logger.error("Error al obtener conversaciones: %s", e)
            return None

    def get_conversation_details(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el detalle completo de una conversacion (transcript, metricas)."""
        url = f"{self.base_url}/conversations/{conversation_id}"
        try:
            r = requests.get(url, headers=self.headers, timeout=ELEVENLABS_TIMEOUT)
            if r.status_code == 200:
                return r.json()
            logger.warning("Error obteniendo detalle de %s: status %d", conversation_id, r.status_code)
            return None
        except requests.RequestException as e:
            logger.error("Error al obtener detalle de %s: %s", conversation_id, e)
            return None

    def monitor_real_time(self, interval: int = 5) -> None:
        """Bucle de monitoreo que consulta la API cada `interval` segundos."""
        logger.info("Monitoreando agente %s cada %d segundos", self.agent_id, interval)
        print("=" * 60)

        last_conversations: Set[str] = set()

        while True:
            try:
                conversations = self.get_conversations()
                if not conversations:
                    time.sleep(interval)
                    continue

                current_conversations: Set[str] = set()
                active_calls: List[Dict[str, Any]] = []

                for conv in conversations.get("conversations", []):
                    conv_id = conv.get("conversation_id", "")
                    current_conversations.add(conv_id)

                    # Detectar nuevas conversaciones
                    if conv_id not in last_conversations:
                        logger.info("Nueva llamada: %s", conv_id[:16])
                        details = self.get_conversation_details(conv_id)
                        if details:
                            self._print_conversation_details(details)

                    if conv.get("status") == "active":
                        active_calls.append(conv)

                # Detectar llamadas terminadas
                for old_id in last_conversations - current_conversations:
                    logger.info("Llamada terminada: %s", old_id[:16])

                self._print_summary(active_calls)
                last_conversations = current_conversations
                time.sleep(interval)

            except KeyboardInterrupt:
                logger.info("Monitoreo detenido por el usuario")
                break
            except Exception as e:
                logger.error("Error en monitoreo: %s", e)
                traceback.print_exc()
                time.sleep(interval)

    def _print_conversation_details(self, details: Dict[str, Any]) -> None:
        """Imprime los detalles de una conversacion en consola."""
        transcript = details.get("transcript", [])
        if transcript:
            print(f"   Mensajes: {len(transcript)}")
            for msg in transcript[-3:]:
                speaker = "Usuario" if msg.get("role") == "user" else "Agente"
                msg_text = msg.get("message", "") or ""
                text = msg_text[:50] + "..." if len(msg_text) > 50 else msg_text
                print(f"       {speaker}: {text}")

        duration = details.get("duration_seconds", 0)
        if duration:
            print(f"   Duracion: {duration}s")

        feedback = details.get("user_feedback")
        if feedback:
            print(f"   Feedback: {feedback}")
        print("-" * 50)

    def _print_summary(self, active_calls: List[Dict[str, Any]]) -> None:
        """Imprime un resumen de las llamadas activas."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"\nRESUMEN ({timestamp}) — Llamadas activas: {len(active_calls)}")
        for call in active_calls:
            conv_id = call.get("conversation_id", "")
            start_time = call.get("start_time", "N/A")
            print(f"   {conv_id[:16]}... (desde {start_time})")
        print("=" * 60)


if __name__ == "__main__":
    require_elevenlabs()
    monitor = ElevenLabsMonitor(ELEVENLABS_API_KEY, AGENT_ID)
    monitor.monitor_real_time(interval=10)
