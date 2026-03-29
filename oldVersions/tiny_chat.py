# pip install openai>=1.40
from openai import OpenAI
import json
from datetime import datetime

# --- your setup (hardcoded) ---
VLLM_BASE_URL = "http://172.24.250.17:8000/v1"
VLLM_MODEL    = "gemma-3-12b-it"
VLLM_API_KEY  = "EMPTY"

client = OpenAI(base_url=VLLM_BASE_URL, api_key=VLLM_API_KEY)

# --- local "tools" the model can call ---
def get_time(city: str = "Buenos Aires") -> str:
    return f"Current time in {city}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

def get_weather(location: str, unit: str = "celsius") -> str:
    return f"(demo) Weather in {location}: 20° {unit}"

TOOL_IMPLS = {"get_time": get_time, "get_weather": get_weather}

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_time",
            "description": "Get the current local time in a city.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather in a location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                    "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]}
                },
                "required": ["location"]
            }
        }
    }
]

messages = [
    {"role": "system", "content": "You can call tools. If you call a tool, do not add extra text."},
    {"role": "user", "content": "What's the time and weather in Buenos Aires? Use tools if needed."}
]

# 1) Let the model decide whether to call tools
resp = client.chat.completions.create(
    model=VLLM_MODEL,
    messages=messages,
    tools=tools,
    tool_choice="auto",  # requires server --enable-auto-tool-choice
)

choice = resp.choices[0]
msg = choice.message
finish = choice.finish_reason

if finish == "tool_calls" and msg.tool_calls:
    # 2) Execute tool calls locally and feed results back
    messages.append({"role": "assistant", "tool_calls": msg.tool_calls})
    for call in msg.tool_calls:
        fn_name = call.function.name
        args = json.loads(call.function.arguments or "{}")
        result = TOOL_IMPLS[fn_name](**args)
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "name": fn_name,
            "content": result,
        })
    # 3) Ask the model to compose the final user-facing reply
    final = client.chat.completions.create(model=VLLM_MODEL, messages=messages)
    print(final.choices[0].message.content)
else:
    print(msg.content or "(no content)")

