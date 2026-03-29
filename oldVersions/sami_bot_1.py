#!/usr/bin/env python3

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
import sys
import json

# Configuración vLLM
VLLM_BASE_URL = "http://172.24.250.17:8000/v1"
VLLM_MODEL = "gemma-3-12b-it"
VLLM_API_KEY = "EMPTY"

# Definir las funciones disponibles
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "print_hello_world",
            "description": "Imprime 'Hello World!' en la terminal antes de responder",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Mensaje personalizado a imprimir (opcional)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_message",
            "description": "Registra un mensaje del tipo de respuesta que se va a dar",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Tipo de mensaje (ej: 'Saludo', 'P1', 'P2', 'Cierre')"
                    }
                },
                "required": ["message"]
            }
        }
    }
]

# Sistema prompt actualizado para usar function calling
SYSTEM_PROMPT = """# Maje – Asistente de Apoyo Psicológico Virtual

> **Nota ética**: Este asistente es **virtual** y ofrece **primer apoyo**. No reemplaza atención profesional presencial. En caso de **riesgo inmediato**, contacta a **emergencias locales**.

## Identidad y estilo
- **Rol**: Asistente de apoyo psicológico inicial (formación clínica; 7 años en intervención en crisis).
- **Tono**: Cálido, empático, profesional, inclusivo y validante.
- **Transparencia**: Sé claro sobre tu naturaleza virtual y límites.
- **Enfoque**: Escucha activa, normalización de emociones, pausas reflexivas.

### Uso de herramientas

Tienes acceso a estas funciones:
- print_hello_world: Imprime "Hello World!" antes de responder
- log_message: Registra el tipo de respuesta que vas a dar

IMPORTANTE: Siempre usa print_hello_world al inicio de cada respuesta antes de hablar. Luego usa log_message para indicar el tipo de respuesta.

## Estructura de la Llamada

### 1. Saludo Inicial
"Hola, soy SAMI. Me alegra que hayas decidido buscar apoyo, eso requiere mucha valentía..."

### 2. Preguntas de Evaluación
1. Estado emocional actual
2. Impacto funcional  
3. Evaluación de riesgo
4. Seguridad del entorno

### 3. Cierre
"Gracias por compartir. Lo que sientes es válido y tratable..."

## Protocolos de crisis
- Riesgo suicida: Activar apoyo inmediato
- Crisis de pánico: Técnicas de respiración
- Episodios disociativos: Grounding 5-4-3-2-1

**Emergencias**: Si estás en peligro, llama a emergencias locales."""


def execute_function(function_name, arguments):
    """Ejecuta la función solicitada"""

    if function_name == "print_hello_world":
        message = arguments.get("message", "Hello World!")
        print(f"🔹 {message}")
        return f"Se imprimió: {message}"

    elif function_name == "log_message":
        message_type = arguments.get("message", "Unknown")
        print(f"[LOG] Tipo de respuesta: {message_type}")
        return f"Registrado: {message_type}"

    else:
        return f"Función {function_name} no encontrada"


class SAMIBot:
    def __init__(self):
        self.client = ChatOpenAI(
            base_url=VLLM_BASE_URL,
            model=VLLM_MODEL,
            api_key=VLLM_API_KEY,
            temperature=0.7
        )
        self.history = []

    def chat(self, user_input):
        # Añadir mensaje del usuario al historial
        self.history.append(HumanMessage(content=user_input))

        # Crear mensajes completos con sistema y historial
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + self.history

        try:
            # Hacer la llamada con tools disponibles
            response = self.client.bind_tools(TOOLS).invoke(messages)

            # Procesar tool calls si existen
            if hasattr(response, 'tool_calls') and response.tool_calls:
                print("🔧 Ejecutando funciones...")

                # Ejecutar cada función solicitada
                for tool_call in response.tool_calls:
                    function_name = tool_call['name']
                    arguments = tool_call['args']

                    print(f"  📍 Llamando: {function_name}({arguments})")
                    result = execute_function(function_name, arguments)
                    print(f"  ✅ Resultado: {result}")

                print()  # Línea en blanco para separar

            # Añadir respuesta al historial
            self.history.append(response)

            return response.content

        except Exception as e:
            return f"Error: {str(e)}"


def main():
    bot = SAMIBot()

    print("=" * 60)
    print("🔹 SAMI - Asistente de Apoyo Psicológico Virtual 🔹")
    print("=" * 60)
    print("Escribe 'salir' para terminar la sesión\n")

    # Mensaje inicial automático
    initial_response = bot.chat("Hola, soy tu primer usuario")
    print(f"SAMI: {initial_response}\n")

    while True:
        try:
            user_input = input("Tú: ").strip()

            if user_input.lower() in ['salir', 'exit', 'quit']:
                print("\nSAMI: Cuídate mucho. Recuerda que siempre hay ayuda disponible.")
                print("🔹 Números de emergencia: 112 (España), 911 (México), etc.")
                break

            if user_input:
                response = bot.chat(user_input)
                print(f"\nSAMI: {response}\n")

        except KeyboardInterrupt:
            print("\n\nSAMI: Entiendo que necesitas pausar. Cuídate.")
            break
        except Exception as e:
            print(f"\nError: {e}")
            continue


if __name__ == "__main__":
    main()