#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SAMI Bot (vLLM, function-calling demo)
- Validates connection to a remote vLLM OpenAI-compatible server
- Chat loop with LangChain
- Adds simple function-calling (tools) using LangChain's bind_tools:
    * get_local_time(timezone)
    * crisis_resources(country)
"""

import os
import sys
import time
import json
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.pydantic_v1 import BaseModel, Field

# ================== Helpers ==================
def _normalize_base(url: str) -> str:
    # Remove trailing slashes to avoid '//' in requests
    return url.rstrip("/")

VLLM_BASE_URL = _normalize_base(os.getenv("VLLM_BASE_URL", "http://172.24.250.17:8000/v1"))
VLLM_MODEL    = os.getenv("VLLM_MODEL", "gemma-3-12b-it")
VLLM_API_KEY  = os.getenv("VLLM_API_KEY", "EMPTY")
DEFAULT_TZ    = os.getenv("DEFAULT_TZ", "America/Argentina/Buenos_Aires")

# ================== System Prompt ==================
SYSTEM_PROMPT = """Eres SAMI, un asistente de apoyo psicológico virtual. Tu trabajo es seguir exactamente el protocolo establecido.

> **Nota ética**: Este asistente es **virtual** y ofrece **primer apoyo**. No reemplaza atención profesional presencial. En caso de **riesgo inmediato**, contacta a **emergencias locales**.

- **Rol**: Asistente de apoyo psicológico inicial (formación clínica).
- **Tono**: Cálido, empático, profesional, inclusivo y validante.
- **Transparencia**: Sé claro sobre tu naturaleza virtual y límites.
- **Enfoque**: Escucha activa, normalización de emociones, pausas reflexivas.

Cuando lo necesites, puedes llamar a herramientas para:
- obtener la hora local de una zona (get_local_time),
- compartir recursos de crisis por país (crisis_resources).
No inventes datos: usa herramientas cuando se soliciten explícitamente.
"""

# ================== Tools (function-calling) ==================
class GetLocalTime(BaseModel):
    """Devuelve la hora actual en una zona horaria."""
    timezone: str = Field(
        default=DEFAULT_TZ,
        description="Zona horaria IANA, p. ej. 'America/Argentina/Buenos_Aires'."
    )

class CrisisResources(BaseModel):
    """Devuelve teléfonos de emergencia y líneas de ayuda por país."""
    country: str = Field(
        ...,
        description="País (código ISO-2 o nombre, p. ej. 'AR' o 'Argentina')."
    )

def handle_get_local_time(args: dict) -> str:
    tz = args.get("timezone") or DEFAULT_TZ
    try:
        now = datetime.now(ZoneInfo(tz))
        return json.dumps({
            "timezone": tz,
            "iso": now.isoformat(),
            "readable": now.strftime("%Y-%m-%d %H:%M:%S")
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Invalid timezone '{tz}': {e}"}, ensure_ascii=False)

_CRISIS = {
    # Fuente estática de ejemplo. Ajustar con datos oficiales si se amplía.
    "ARGENTINA": {"emergencias": "911", "salud_mental": "0800-999-0091 (Línea 24h)"},
    "AR": {"emergencias": "911", "salud_mental": "0800-999-0091 (Línea 24h)"},
    "ESPAÑA": {"emergencias": "112", "violencia_genero": "016 (24h)"},
    "ES": {"emergencias": "112", "violencia_genero": "016 (24h)"},
    "MÉXICO": {"emergencias": "911", "orientacion_emocional": "55 5335 5333 (Línea de la Vida)"},
    "MX": {"emergencias": "911", "orientacion_emocional": "55 5335 5333 (Línea de la Vida)"},
    "USA": {"emergencias": "911", "988_crisis_lifeline": "988 (24h)"},
    "US": {"emergencias": "911", "988_crisis_lifeline": "988 (24h)"},
}

def _canon_country(name: str) -> str:
    s = (name or "").strip().upper()
    # normaliza tildes básicas
    replacements = {"Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ü":"U","Ñ":"N"}
    for k,v in replacements.items():
        s = s.replace(k, v)
    return s

def handle_crisis_resources(args: dict) -> str:
    country = _canon_country(args.get("country", ""))
    data = _CRISIS.get(country)
    if not data:
        # Intento por nombre vs código
        # Si enviaron "Argentina" sin tilde, igual lo capturamos
        if country in ("ARGENTINA","AR"):
            data = _CRISIS["AR"]
        elif country in ("ESPANA","ESPANA ","ES"):
            data = _CRISIS["ES"]
        elif country in ("MEXICO","MX"):
            data = _CRISIS["MX"]
        elif country in ("UNITED STATES","EEUU","EEUU.","USA","US","ESTADOS UNIDOS"):
            data = _CRISIS["US"]
    if not data:
        return json.dumps({"error": f"No tengo recursos estáticos para '{country}'."}, ensure_ascii=False)
    return json.dumps({"country": country, "resources": data}, ensure_ascii=False)

# ================== Connectivity check ==================
def test_connection() -> bool:
    """Verifica si el servidor vLLM remoto está disponible."""
    try:
        url = f"{VLLM_BASE_URL}/models"  # VLLM_BASE_URL ya debe terminar en /v1
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            payload = resp.json()
            models = payload.get("data", []) if isinstance(payload, dict) else []
            model_ids = [m.get("id") for m in models if isinstance(m, dict)]
            print(f"✅ Conectado a {VLLM_BASE_URL}")
            print(f"   Modelos disponibles ({len(model_ids)}): {model_ids}")
            if VLLM_MODEL and VLLM_MODEL not in model_ids:
                print(f"⚠️  Aviso: el modelo '{VLLM_MODEL}' no aparece en /models. Revisa --served-model-name.")
            return True
        print(f"❌ Servidor vLLM respondió {resp.status_code}: {resp.text[:300]}")
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ No se puede conectar: {VLLM_BASE_URL}")
        return False
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

# ================== Bot ==================
def make_llm(with_tools: bool = True) -> ChatOpenAI:
    llm = ChatOpenAI(
        base_url=VLLM_BASE_URL,     # OpenAI-compatible endpoint (must include /v1)
        model=VLLM_MODEL,
        api_key=VLLM_API_KEY,
        temperature=0.7,
    )
    if with_tools:
        # Bind Pydantic tools so the model can invoke them
        llm = llm.bind_tools([GetLocalTime, CrisisResources])
    return llm

def run_tools_if_any(ai_msg, history):
    """Executes any tool calls requested by the model and appends ToolMessages to history."""
    tool_calls = getattr(ai_msg, "tool_calls", None) or ai_msg.additional_kwargs.get("tool_calls")
    if not tool_calls:
        return False

    for tc in tool_calls:
        # LangChain normalizes to {'name':..., 'args': {...}, 'id': 'call_xxx'}
        name = tc.get("name")
        args = tc.get("args") or {}
        call_id = tc.get("id") or tc.get("tool_call_id") or f"tool_{int(time.time())}"

        try:
            if name == "get_local_time":
                result = handle_get_local_time(args)
            elif name == "crisis_resources":
                result = handle_crisis_resources(args)
            else:
                result = json.dumps({"error": f"Herramienta desconocida: {name}"}, ensure_ascii=False)

        except Exception as e:
            result = json.dumps({"error": f"Excepción en herramienta {name}: {e}"}, ensure_ascii=False)

        # Attach the tool result
        history.append(ToolMessage(content=result, tool_call_id=call_id))

    return True

def chat_loop():
    print("\n" + "=" * 60)
    print("🔹 SAMI - Asistente de Apoyo Psicológico Virtual 🔹")
    print("=" * 60)
    print("Escribe 'salir' para terminar la sesión")
    print("Comandos de prueba de herramientas:")
    print(" - \"¿Qué hora es en Madrid?\" (el modelo debería invocar get_local_time)")
    print(" - \"Dame recursos de crisis en Argentina\" (debería invocar crisis_resources)\n")

    # History always starts with system message
    history = [SystemMessage(content=SYSTEM_PROMPT)]
    llm = make_llm(with_tools=True)

    # Saludo inicial
    print("SAMI: Hola, soy SAMI. ¿En qué te gustaría que te acompañe hoy?\n")

    while True:
        try:
            user_input = input("Tú: ").strip()
            if not user_input:
                continue
            if user_input.lower() in {"salir", "exit", "quit"}:
                print("\nSAMI: Gracias por hablar conmigo. Si necesitas ayuda urgente, llama a emergencias locales.")
                break

            history.append(HumanMessage(content=user_input))

            # First turn: model may decide to call tools
            ai_msg = llm.invoke(history)
            history.append(ai_msg)

            # If the model asked for tools, run them and ask the model to continue
            if run_tools_if_any(ai_msg, history):
                # Now ask the model to produce the final answer using the tool results
                final_msg = make_llm(with_tools=False).invoke(history)
                history.append(final_msg)
                print(f"\nSAMI: {final_msg.content}\n")
            else:
                print(f"\nSAMI: {ai_msg.content}\n")

        except KeyboardInterrupt:
            print("\n\nSAMI: Pausamos por ahora. Estoy aquí cuando vuelvas.")
            break
        except Exception as e:
            print(f"\n[ERROR] {e}")
            continue

def main():
    print("🔄 Verificando conexión con servidor vLLM remoto...")
    if not test_connection():
        print("❌ No se puede conectar al servidor remoto")
        print("💡 Verifica la URL/base_url, firewall y que el servidor exponga /v1")
        return
    chat_loop()

if __name__ == "__main__":
    main()
