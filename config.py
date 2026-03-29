"""
Configuracion centralizada del proyecto SAMU.

Carga variables de entorno desde .env, configura logging
y expone constantes usadas por todos los modulos.
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# ElevenLabs
# ---------------------------------------------------------------------------
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
AGENT_ID: str = os.getenv("AGENT_ID", "")
ELEVENLABS_BASE_URL: str = "https://api.elevenlabs.io"
ELEVENLABS_TIMEOUT: int = 30

# ---------------------------------------------------------------------------
# vLLM (servidor de inferencia)
# ---------------------------------------------------------------------------
VLLM_BASE_URL: str = os.getenv("VLLM_BASE_URL", "http://localhost:8000/v1")
VLLM_MODEL: str = os.getenv("VLLM_MODEL", "gemma-3-12b-it")
VLLM_API_KEY: str = os.getenv("VLLM_API_KEY", "EMPTY")

# ---------------------------------------------------------------------------
# Flask
# ---------------------------------------------------------------------------
FLASK_SECRET_KEY: str = os.getenv("FLASK_SECRET_KEY", "change-this-secret")
FLASK_HOST: str = os.getenv("FLASK_HOST", "0.0.0.0")
FLASK_PORT: int = int(os.getenv("FLASK_PORT", "5016"))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FORMAT: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(name: str) -> logging.Logger:
    """Crea y devuelve un logger con formato estandar para el modulo dado."""
    logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL, stream=sys.stdout)
    return logging.getLogger(name)


def require_elevenlabs() -> None:
    """Valida que las credenciales de ElevenLabs esten configuradas."""
    if not ELEVENLABS_API_KEY:
        raise SystemExit("Error: ELEVENLABS_API_KEY no esta configurada en .env")
    if not AGENT_ID:
        raise SystemExit("Error: AGENT_ID no esta configurado en .env")


def require_vllm() -> None:
    """Valida que la configuracion de vLLM este presente."""
    if not VLLM_BASE_URL:
        raise SystemExit("Error: VLLM_BASE_URL no esta configurada en .env")
