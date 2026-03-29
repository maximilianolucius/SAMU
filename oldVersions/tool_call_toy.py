# pip install openai>=1.40
from openai import OpenAI
import json
from datetime import datetime

# --- TU SETUP (hardcodeado) ---
VLLM_BASE_URL = "http://172.24.250.17:8000/v1"
VLLM_MODEL    = "gemma-3-12b-it"
VLLM_API_KEY  = "EMPTY"

client = OpenAI(base_url=VLLM_BASE_URL, api_key=VLLM_API_KEY)

# --- Tool(s) locales ---
def get_weather(location: str, unit: str):
    # Demo simple (aquí iría tu llamada real a API/DB)
    return f"Getting the weather for {location} in {unit}..."

tool_functions = {"get_weather": get_weather}

tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather in a given location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {"type": "string", "description": "City and state, e.g., 'San Francisco, CA'"},
                "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
            },
            "required": ["location", "unit"]
        }
    }
}]

messages = [
    {"role": "user", "content": "What's the weather like in San Francisco?"}
]

# 1) Primer pase: el modelo decide si llamar tool(s)
response = client.chat.completions.create(
    model=VLLM_MODEL,
    messages=messages,
    tools=tools,
    tool_choice="auto"
)

choice = response.choices[0]
msg = choice.message

if msg.tool_calls:
    # Tomamos la primera tool call (pueden venir varias)
    tc = msg.tool_calls[0].function
    print(f"Function called: {tc.name}")
    print(f"Arguments: {tc.arguments}")

    # 2) Ejecutamos la tool localmente
    args = json.loads(tc.arguments or "{}")
    # Fallback por si faltan args (defensivo)
    args.setdefault("unit", "celsius")
    result = tool_functions[tc.name](**args)
    print(f"Result: {result}")

    # 3) Reinyectamos el resultado y pedimos la respuesta final del LLM
    messages.append({"role": "assistant", "tool_calls": msg.tool_calls})
    messages.append({
        "role": "tool",
        "tool_call_id": msg.tool_calls[0].id,
        "name": tc.name,
        "content": result
    })

    final = client.chat.completions.create(model=VLLM_MODEL, messages=messages)
    print("\nLLM final answer:")
    print(final.choices[0].message.content or "(no content)")
else:
    # El modelo respondió directo sin usar tools
    print(msg.content or "(no content)")

