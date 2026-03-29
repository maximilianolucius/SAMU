#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SAMI Bot (vLLM, function-calling demo) — v2
- Fix: Pydantic v2 imports (no deprecation warning)
- Tools:
    * get_local_time(timezone: str | None, location: str | None)
    * crisis_resources(country: str)
- Robust tool execution:
    * Uses LangChain tool_calls when present.
    * Fallback: parses ```tool_code ...``` / inline calls like get_local_time(location="Salta").
"""

import os
import re
import time
import json
import requests
from typing import Optional, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

# ✅ Pydantic v2 (no deprecation warning)
from pydantic import BaseModel, Field

# ================== Helpers ==================
def _normalize_base(url: str) -> str:
    return url.rstrip("/")

VLLM_BASE_URL = _normalize_base(os.getenv("VLLM_BASE_URL", "http://172.24.250.17:8000/v1"))
VLLM_MODEL    = os.getenv("VLLM_MODEL", "gemma-3-12b-it")
VLLM_API_KEY  = os.getenv("VLLM_API_KEY", "EMPTY")
DEFAULT_TZ    = os.getenv("DEFAULT_TZ", "America/Argentina/Buenos_Aires")

# Minimal mapping city -> IANA TZ to support location requests
CITY_TZ = {
    "SALTA": "America/Argentina/Salta",
    "BUENOS AIRES": "America/Argentina/Buenos_Aires",
    "CORDOBA": "America/Argentina/Cordoba",
    "MENDOZA": "America/Argentina/Mendoza",
    "TUCUMAN": "America/Argentina/Tucuman",
    "MADRID": "Europe/Madrid",
    "SEVILLA": "Europe/Madrid",
    "SEVILLE": "Europe/Madrid",
    "MALAGA": "Europe/Madrid",
    "BARCELONA": "Europe/Madrid",
    "MEXICO CITY": "America/Mexico_City",
    "CDMX": "America/Mexico_City",
    "NEW YORK": "America/New_York",
    "NYC": "America/New_York",
    "MIAMI": "America/New_York",
}

def _canon(s: Optional[str]) -> str:
    if not s:
        return ""
    t = s.strip().upper()
    # Normalize accents minimally
    replacements = {"Á":"A","É":"E","Í":"I","Ó":"O","Ú":"U","Ü":"U","Ñ":"N"}
    for k,v in replacements.items():
        t = t.replace(k, v)
    return t

# ================== System Prompt ==================
SYSTEM_PROMPT = """Eres SAMI, un asistente de apoyo psicológico virtual. Tu trabajo es seguir el protocolo.

> **Nota ética**: Este asistente ofrece **primer apoyo** y no reemplaza atención profesional. Ante **riesgo inmediato**, llama a **emergencias locales**.

- **Rol**: Apoyo psicológico inicial.
- **Tono**: Cálido, empático, profesional, inclusivo, validante.
- **Transparencia**: Eres un asistente digital, con límites.
- **Enfoque**: Escucha activa, normalización emocional, pausas reflexivas.

Cuando el usuario pida hora local o recursos de crisis:
1) **Debes invocar herramientas** (function calling) y **esperar su resultado**.
2) Herramientas disponibles (nombres y argumentos):
   - get_local_time(timezone: str | None, location: str | None)
   - crisis_resources(country: str)
3) No inventes datos de herramientas. Si no puedes resolver la zona horaria desde una ciudad, usa el DEFAULT_TZ.
"""

# ================== Tools (function-calling) ==================
class GetLocalTime(BaseModel):
    """Devuelve la hora actual en una zona horaria o en una ciudad conocida."""
    timezone: Optional[str] = Field(default=None, description="Zona IANA, p. ej. 'America/Argentina/Salta'")
    location: Optional[str] = Field(default=None, description="Ciudad, p. ej. 'Salta'")

class CrisisResources(BaseModel):
    """Devuelve teléfonos de emergencia y líneas de ayuda por país."""
    country: str = Field(..., description="País (ISO-2 o nombre).")

def handle_get_local_time(args: Dict[str, Any]) -> str:
    tz = args.get("timezone")
    location = args.get("location")
    if not tz and location:
        tz = CITY_TZ.get(_canon(location)) or DEFAULT_TZ
    tz = tz or DEFAULT_TZ
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
    "ARGENTINA": {"emergencias": "911", "salud_mental": "0800-999-0091 (24h)", "prevencion_suicidio": "135 / (011) 5275-1135"},
    "AR": {"emergencias": "911", "salud_mental": "0800-999-0091 (24h)", "prevencion_suicidio": "135 / (011) 5275-1135"},

    "ESPANA": {"emergencias": "112", "violencia_genero": "016 (24h)", "024_salud_mental": "024 (24h)"},
    "ES": {"emergencias": "112", "violencia_genero": "016 (24h)", "024_salud_mental": "024 (24h)"},

    "MEXICO": {"emergencias": "911", "linea_de_la_vida": "800 911 2000 / 55 5335 5333 (24h)"},
    "MX": {"emergencias": "911", "linea_de_la_vida": "800 911 2000 / 55 5335 5333 (24h)"},

    "US": {"emergencias": "911", "988_crisis_lifeline": "988 (24h)"},
    "USA": {"emergencias": "911", "988_crisis_lifeline": "988 (24h)"},
}

def handle_crisis_resources(args: Dict[str, Any]) -> str:
    country = _canon(args.get("country", ""))
    data = _CRISIS.get(country)
    if not data:
        # Aliases simples
        aliases = {
            "ARG": "AR", "ARGENTINA": "AR",
            "ESPANA": "ES", "ESPAÑA": "ES",
            "MEXICO": "MX", "ESTADOS UNIDOS": "US", "UNITED STATES": "US", "EEUU": "US"
        }
        key = aliases.get(country, "")
        data = _CRISIS.get(key)
    if not data:
        return json.dumps({"error": f"No tengo recursos estáticos para '{country}'."}, ensure_ascii=False)
    return json.dumps({"country": country, "resources": data}, ensure_ascii=False)

# ================== Connectivity check ==================
def test_connection() -> bool:
    try:
        url = f"{VLLM_BASE_URL}/models"
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
        base_url=VLLM_BASE_URL,
        model=VLLM_MODEL,
        api_key=VLLM_API_KEY,
        temperature=0.7,
    )
    if with_tools:
        llm = llm.bind_tools([GetLocalTime, CrisisResources])
    return llm

def _parse_tool_code_block(text: str) -> list[dict]:
    """
    Fallback parser for code blocks like:
    ```tool_code
    get_local_time(location="Salta")
    ```
    or inline: get_local_time(timezone="Europe/Madrid")
    Returns a list of {'name': str, 'args': dict}
    """
    calls = []
    # Block form
    block_pat = re.compile(r"```tool_code\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    for block in block_pat.findall(text):
        m = re.search(r"(?P<name>get_local_time|crisis_resources)\s*\((?P<args>.*)\)", block, re.IGNORECASE | re.DOTALL)
        if m:
            name = m.group("name")
            args_src = m.group("args")
            args = {}
            for k, v in re.findall(r'(\w+)\s*=\s*"(.*?)"', args_src):
                args[k] = v
            calls.append({"name": name, "args": args})

    # Inline single-line form
    for m in re.finditer(r"(?P<name>get_local_time|crisis_resources)\s*\((?P<args>[^)]*)\)", text, re.IGNORECASE):
        name = m.group("name")
        args_src = m.group("args")
        args = {}
        for k, v in re.findall(r'(\w+)\s*=\s*"(.*?)"', args_src):
            args[k] = v
        calls.append({"name": name, "args": args})

    return calls

def run_tools_if_any(ai_msg, history) -> bool:
    """Executes tool calls requested by the model; supports both OpenAI tool_calls and fallback parser."""
    executed = False

    # Preferred: OpenAI-style tool_calls
    tool_calls = getattr(ai_msg, "tool_calls", None) or ai_msg.additional_kwargs.get("tool_calls")
    if tool_calls:
        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args") or {}
            call_id = tc.get("id") or tc.get("tool_call_id") or f"tool_{int(time.time())}"
            result = _dispatch_tool(name, args)
            history.append(ToolMessage(content=result, tool_call_id=call_id))
            executed = True

    # Fallback: parse code blocks / inline calls if the model only printed them
    if not executed:
        calls = _parse_tool_code_block(ai_msg.content or "")
        for i, c in enumerate(calls):
            result = _dispatch_tool(c["name"], c["args"])
            history.append(ToolMessage(content=result, tool_call_id=f"fallback_{int(time.time())}_{i}"))
            executed = True

    return executed

def _dispatch_tool(name: str, args: Dict[str, Any]) -> str:
    try:
        if name.lower() == "get_local_time":
            return handle_get_local_time(args)
        if name.lower() == "crisis_resources":
            return handle_crisis_resources(args)
        return json.dumps({"error": f"Herramienta desconocida: {name}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": f"Excepción en herramienta {name}: {e}"}, ensure_ascii=False)

def chat_loop():
    print("\n" + "=" * 60)
    print("🔹 SAMI - Asistente de Apoyo Psicológico Virtual 🔹")
    print("=" * 60)
    print("Escribe 'salir' para terminar la sesión\n")

    history = [SystemMessage(content=SYSTEM_PROMPT)]
    llm = make_llm(with_tools=True)

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

            ai_msg = llm.invoke(history)
            history.append(ai_msg)

            if run_tools_if_any(ai_msg, history):
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
