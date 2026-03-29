#!/usr/bin/env python3
"""
Bot de texto SAMI — chat interactivo contra un servidor vLLM.

Lee el system prompt desde system_prompt.txt y mantiene un historial
de conversacion en memoria para dar contexto al modelo.

Uso:
    python sami_bot.py
"""

import sys
import time
from pathlib import Path
from typing import List

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from config import VLLM_BASE_URL, VLLM_MODEL, VLLM_API_KEY, setup_logging, require_vllm

logger = setup_logging("sami_bot")

PROMPT_PATH = Path(__file__).parent / "system_prompt.txt"


def load_system_prompt() -> str:
    """Lee el system prompt desde archivo. Sale del programa si no existe."""
    if not PROMPT_PATH.exists():
        logger.error("No se encontro el archivo de prompt: %s", PROMPT_PATH)
        sys.exit(1)
    text = PROMPT_PATH.read_text(encoding="utf-8")
    logger.info("System prompt cargado (%d caracteres) desde %s", len(text), PROMPT_PATH)
    return text


class SAMIBot:
    """Cliente de chat que envia mensajes a un servidor vLLM y mantiene historial."""

    def __init__(self) -> None:
        self.client = ChatOpenAI(
            base_url=VLLM_BASE_URL,
            model=VLLM_MODEL,
            api_key=VLLM_API_KEY,
            temperature=0.7,
        )
        self.system_prompt: str = load_system_prompt()
        self.history: List[BaseMessage] = []

    def chat(self, user_input: str) -> str:
        """Envia un mensaje al modelo y devuelve la respuesta como texto."""
        start = time.time()
        self.history.append(HumanMessage(content=user_input))
        messages = [SystemMessage(content=self.system_prompt)] + self.history

        try:
            response = self.client.invoke(messages)
            elapsed = time.time() - start
            logger.debug("Respuesta recibida en %.2f s", elapsed)
            self.history.append(response)
            return response.content
        except ConnectionError as e:
            logger.error("No se pudo conectar a %s: %s", VLLM_BASE_URL, e)
            return f"Error de conexion: {e}"
        except Exception as e:
            logger.error("Error inesperado al invocar el modelo: %s", e)
            return f"Error: {e}"


def main() -> None:
    """Bucle principal de chat por consola."""
    require_vllm()
    logger.info("Servidor vLLM: %s | Modelo: %s", VLLM_BASE_URL, VLLM_MODEL)
    bot = SAMIBot()

    print("\n" + "=" * 60)
    print(" SAMI - Asistente de Apoyo Psicologico Virtual")
    print("=" * 60)
    print("Escribe 'salir' para terminar la sesion\n")

    # Saludo inicial (sin pasar por el modelo)
    print("SAMI: Hola, soy SAMI. Me alegra que hayas decidido buscar apoyo, "
          "eso requiere mucha valentia.\nTe voy a acompanar paso a paso. "
          "Cuando te sientas listo, comenzamos. Te parece bien?\n")

    while True:
        try:
            user_input = input("Tu: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ("salir", "exit", "quit"):
                print("\nSAMI: Cuidate mucho. Recuerda que siempre hay ayuda disponible.")
                break
            response = bot.chat(user_input)
            print(f"\nSAMI: {response}\n")
        except KeyboardInterrupt:
            print("\n\nSAMI: Entiendo que necesitas pausar. Cuidate.")
            break
        except EOFError:
            break


if __name__ == "__main__":
    main()
