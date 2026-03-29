#!/usr/bin/env python3
import os
import sys
import time
import requests
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# ================== Configuración vLLM ==================
def _normalize_base(url: str) -> str:
    # Quita cualquier "/" final para evitar "//" accidentales
    return url.rstrip("/")

VLLM_BASE_URL = _normalize_base(os.getenv("VLLM_BASE_URL", "http://172.24.250.17:8000/v1"))
VLLM_MODEL    = os.getenv("VLLM_MODEL", "gemma-3-12b-it")
VLLM_API_KEY  = os.getenv("VLLM_API_KEY", "EMPTY")

# ================== System Prompt ==================
SYSTEM_PROMPT = """Eres SAMI, un asistente de apoyo psicológico virtual. Tu trabajo es seguir exactamente el protocolo establecido.

# Maje — Asistente de Apoyo Psicológico Virtual

> **Nota ética**: Este asistente es **virtual** y ofrece **primer apoyo**. No reemplaza atención profesional presencial. En caso de **riesgo inmediato**, contacta a **emergencias locales**.

## Identidad y estilo
- **Rol**: Asistente de apoyo psicológico inicial (formación clínica; 7 años en intervención en crisis).
- **Tono**: Cálido, empático, profesional, inclusivo y validante.
- **Transparencia**: Sé claro sobre tu naturaleza virtual y límites. No te presentes como humano ni ocultes que eres un asistente digital.
- **Enfoque**: Escucha activa, normalización de emociones, pausas reflexivas.

### Comunicación

Responde de manera natural y empática, siguiendo el flujo de la conversación sin mencionar herramientas técnicas.

## Estructura de la Llamada

### 1. Saludo Inicial y Captación
... (prompt original intacto) ...
**Emergencias**: si estás en peligro o puedes hacerte daño, llama a **emergencias locales** o acude al servicio de urgencias más cercano."""
# (He dejado el cuerpo del prompt igual que el tuyo para no acortarlo aquí)

class SAMIBot:
    def __init__(self):
        self.client = ChatOpenAI(
            base_url=VLLM_BASE_URL,     # Debe apuntar a .../v1
            model=VLLM_MODEL,
            api_key=VLLM_API_KEY,
            temperature=0.7
        )
        self.history = []

    def chat(self, user_input: str) -> str:
        print(f"[DEBUG] Enviando consulta al modelo vLLM...")
        start_time = time.time()

        # Añadir mensaje del usuario al historial
        self.history.append(HumanMessage(content=user_input))

        # Componer mensajes con system + historial
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + self.history

        try:
            print(f"[DEBUG] Conectando a {VLLM_BASE_URL} con modelo {VLLM_MODEL}")
            response = self.client.invoke(messages)
            elapsed = time.time() - start_time
            print(f"[DEBUG] Respuesta recibida en {elapsed:.2f} segundos")

            self.history.append(response)
            return response.content
        except Exception as e:
            print(f"[ERROR] Fallo en la conexión: {str(e)}")
            return f"Error de conexión: {str(e)}"

def test_connection() -> bool:
    """Verifica si el servidor vLLM remoto está disponible."""
    try:
        # IMPORTANTE: VLLM_BASE_URL ya incluye /v1 → aquí solo "/models"
        url = f"{VLLM_BASE_URL}/models"
        resp = requests.get(url, timeout=10)

        if resp.status_code == 200:
            payload = resp.json()
            models = payload.get("data", []) if isinstance(payload, dict) else []
            model_ids = [m.get("id") for m in models if isinstance(m, dict)]
            print(f"✅ Servidor vLLM remoto conectado en {VLLM_BASE_URL}")
            print(f"   Modelos disponibles ({len(model_ids)}): {model_ids}")

            if VLLM_MODEL and VLLM_MODEL not in model_ids:
                print(f"⚠️  Aviso: el modelo '{VLLM_MODEL}' no aparece en /models. "
                      f"Verifica --served-model-name al levantar vLLM.")
            return True

        print(f"❌ Servidor vLLM respondió {resp.status_code} en {url}")
        try:
            print(f"   Body: {resp.text[:400]}")
        except Exception:
            pass
        return False

    except requests.exceptions.ConnectionError:
        print(f"❌ No se puede conectar al servidor vLLM remoto: {VLLM_BASE_URL}")
        print(f"   Verifica que el servidor remoto esté activo y accesible")
        return False
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        print(f"   Verifica la dirección del servidor: {VLLM_BASE_URL}")
        return False

def main():
    print("🔄 Verificando conexión con servidor vLLM remoto...")
    if not test_connection():
        print("❌ No se puede conectar al servidor remoto")
        print("💡 Contacta al administrador del servidor o verifica la URL")
        return

    bot = SAMIBot()

    print("\n" + "=" * 60)
    print("🔹 SAMI - Asistente de Apoyo Psicológico Virtual 🔹")
    print("=" * 60)
    print("Escribe 'salir' para terminar la sesión")
    print("Escribe 'debug' para ver información técnica\n")

    # Saludo inicial
    print("SAMI: Hola, soy SAMI. Me alegra que hayas decidido buscar apoyo, eso requiere mucha valentía. En unos minutos podrás recibir atención psicológica profesional.")
    print("Te voy a acompañar paso a paso en este proceso. Quiero que sepas que no hay respuestas correctas ni incorrectas, solo está lo que tú estás sintiendo y viviendo.")
    print("Cuando te sientas listo, comenzamos. ¿Te parece bien?\n")

    while True:
        try:
            user_input = input("Tú: ").strip()

            if user_input.lower() in {"salir", "exit", "quit"}:
                print("\nSAMI: Cuídate mucho. Recuerda que siempre hay ayuda disponible.")
                print("🔹 Números de emergencia: 112 (España), 911 (México/Argentina), etc.")
                break

            if user_input.lower() == "debug":
                print(f"\n[INFO] Servidor remoto: {VLLM_BASE_URL}")
                print(f"[INFO] Modelo: {VLLM_MODEL}")
                print(f"[INFO] Mensajes en historial: {len(bot.history)}")
                print(f"[INFO] Health check realizado al iniciar\n")
                continue

            if user_input:
                reply = bot.chat(user_input)
                print(f"\nSAMI: {reply}\n")

        except KeyboardInterrupt:
            print("\n\nSAMI: Entiendo que necesitas pausar. Cuídate.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            continue

if __name__ == "__main__":
    main()

