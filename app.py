"""
SAMU Dashboard — interfaz web de gestion para ElevenLabs Conversational AI.

Servidor Flask + SocketIO que:
- Proxea la API REST de ElevenLabs (agente, conversaciones, analytics, KB)
- Recibe webhooks en tiempo real y los emite via WebSocket
- Sirve un dashboard HTML interactivo en /

Uso:
    python app.py
"""

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import requests
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_socketio import SocketIO, emit

from config import (
    ELEVENLABS_API_KEY, AGENT_ID, ELEVENLABS_BASE_URL, ELEVENLABS_TIMEOUT,
    FLASK_SECRET_KEY, FLASK_HOST, FLASK_PORT,
    setup_logging, require_elevenlabs,
)

logger = setup_logging("app")

app = Flask(__name__)
app.config["SECRET_KEY"] = FLASK_SECRET_KEY
socketio = SocketIO(app, cors_allowed_origins="*")

# Almacen en memoria de llamadas activas (poblado por webhooks)
call_sessions: Dict[str, Dict[str, Any]] = {}

JsonResponse = Tuple[Dict[str, Any], int]


# ---------------------------------------------------------------------------
# Helpers para llamar a la API de ElevenLabs
# ---------------------------------------------------------------------------

def _headers() -> Dict[str, str]:
    """Headers de autenticacion para la API de ElevenLabs."""
    return {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> JsonResponse:
    """GET a la API de ElevenLabs. Devuelve (json, status_code)."""
    url = f"{ELEVENLABS_BASE_URL}{path}"
    try:
        r = requests.get(url, headers=_headers(), params=params, timeout=ELEVENLABS_TIMEOUT)
        return r.json(), r.status_code
    except requests.ConnectionError:
        logger.error("No se pudo conectar a %s", url)
        return {"error": "No se pudo conectar a ElevenLabs"}, 502
    except ValueError:
        return {"error": "Respuesta no JSON", "status": r.status_code}, r.status_code


def _post(path: str, json_body: Optional[Dict[str, Any]] = None) -> JsonResponse:
    """POST a la API de ElevenLabs."""
    url = f"{ELEVENLABS_BASE_URL}{path}"
    try:
        r = requests.post(url, headers=_headers(), json=json_body, timeout=ELEVENLABS_TIMEOUT)
        return r.json(), r.status_code
    except requests.ConnectionError:
        return {"error": "No se pudo conectar a ElevenLabs"}, 502
    except ValueError:
        return {"error": "Respuesta no JSON"}, r.status_code


def _patch(path: str, json_body: Optional[Dict[str, Any]] = None) -> JsonResponse:
    """PATCH a la API de ElevenLabs."""
    url = f"{ELEVENLABS_BASE_URL}{path}"
    try:
        r = requests.patch(url, headers=_headers(), json=json_body, timeout=ELEVENLABS_TIMEOUT)
        return r.json(), r.status_code
    except requests.ConnectionError:
        return {"error": "No se pudo conectar a ElevenLabs"}, 502
    except ValueError:
        return {"error": "Respuesta no JSON"}, r.status_code


def _delete(path: str) -> JsonResponse:
    """DELETE a la API de ElevenLabs."""
    url = f"{ELEVENLABS_BASE_URL}{path}"
    try:
        r = requests.delete(url, headers=_headers(), timeout=ELEVENLABS_TIMEOUT)
        if r.status_code == 200 and not r.text.strip():
            return {"ok": True}, 200
        return r.json(), r.status_code
    except requests.ConnectionError:
        return {"error": "No se pudo conectar a ElevenLabs"}, 502
    except ValueError:
        return {"error": "Respuesta no JSON"}, r.status_code


def _proxy(result: JsonResponse) -> Response:
    """Convierte una tupla (data, status) en respuesta Flask JSON."""
    data, status = result
    return jsonify(data), status


# ---------------------------------------------------------------------------
# Paginas
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard() -> str:
    """Sirve el dashboard HTML principal."""
    return render_template("dashboard.html", agent_id=AGENT_ID)


# ---------------------------------------------------------------------------
# Webhooks (recibe eventos en tiempo real de ElevenLabs)
# ---------------------------------------------------------------------------

@app.route("/webhook", methods=["POST"])
def webhook() -> JsonResponse:
    """Recibe webhooks de ElevenLabs y los reemite via WebSocket."""
    try:
        data = request.json
        conversation_id = data.get("conversation_id")
        event_type = data.get("event_type", "unknown")
        payload = {
            "conversation_id": conversation_id,
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data,
        }
        logger.info("Webhook recibido: %s (conv: %s)", event_type, conversation_id)

        if event_type == "conversation_started":
            call_sessions[conversation_id] = payload
            socketio.emit("call_started", payload)
        elif event_type in ("user_transcript", "agent_response"):
            socketio.emit("new_transcript", payload)
        elif event_type == "conversation_ended":
            call_sessions.pop(conversation_id, None)
            socketio.emit("call_ended", payload)
        else:
            socketio.emit("webhook_event", payload)

        return {"status": "ok"}, 200
    except Exception as e:
        logger.error("Error procesando webhook: %s", e)
        return {"status": "error", "message": str(e)}, 500


@socketio.on("connect")
def handle_connect() -> None:
    """Envia el estado actual de llamadas al cliente que se conecta."""
    logger.debug("Cliente WebSocket conectado: %s", request.sid)
    emit("current_calls", list(call_sessions.values()))


# ---------------------------------------------------------------------------
# Agente
# ---------------------------------------------------------------------------

@app.route("/api/agent")
def api_agent() -> Response:
    """Configuracion completa del agente."""
    return _proxy(_get(f"/v1/convai/agents/{AGENT_ID}"))


@app.route("/api/agent", methods=["PATCH"])
def api_agent_update() -> Response:
    """Actualizar configuracion del agente (patch parcial)."""
    return _proxy(_patch(f"/v1/convai/agents/{AGENT_ID}", request.json))


@app.route("/api/agent/widget")
def api_agent_widget() -> Response:
    """Configuracion del widget embebible."""
    return _proxy(_get(f"/v1/convai/agents/{AGENT_ID}/widget"))


@app.route("/api/agent/link")
def api_agent_link() -> Response:
    """Link compartible del agente."""
    return _proxy(_get(f"/v1/convai/agents/{AGENT_ID}/link"))


@app.route("/api/agent/kb-size")
def api_agent_kb_size() -> Response:
    """Cantidad de paginas en la knowledge base del agente."""
    return _proxy(_get(f"/v1/convai/agent/{AGENT_ID}/knowledge-base/size"))


@app.route("/api/agent/branches")
def api_agent_branches() -> Response:
    """Branches del agente (versionado)."""
    return _proxy(_get(f"/v1/convai/agents/{AGENT_ID}/branches"))


# ---------------------------------------------------------------------------
# Conversaciones
# ---------------------------------------------------------------------------

@app.route("/api/conversations")
def api_conversations() -> Response:
    """Lista conversaciones con filtros y paginacion cursor-based."""
    params: Dict[str, Any] = {
        "agent_id": AGENT_ID,
        "page_size": request.args.get("page_size", 30, type=int),
        "summary_mode": request.args.get("summary_mode", "include"),
    }
    # Pasar filtros opcionales si estan presentes
    optional_keys = (
        "cursor", "call_successful", "call_start_before_unix",
        "call_start_after_unix", "call_duration_min_secs",
        "call_duration_max_secs", "rating_min", "rating_max",
        "has_feedback_comment", "user_id", "main_languages", "branch_id",
    )
    for key in optional_keys:
        val = request.args.get(key)
        if val is not None:
            params[key] = val
    return _proxy(_get("/v1/convai/conversations", params=params))


@app.route("/api/conversations/<conversation_id>")
def api_conversation_detail(conversation_id: str) -> Response:
    """Detalle completo de una conversacion con transcript y metricas."""
    return _proxy(_get(f"/v1/convai/conversations/{conversation_id}"))


@app.route("/api/conversations/<conversation_id>/audio")
def api_conversation_audio(conversation_id: str) -> Response:
    """Stream del audio de la conversacion (mp3)."""
    url = f"{ELEVENLABS_BASE_URL}/v1/convai/conversations/{conversation_id}/audio"
    try:
        r = requests.get(url, headers=_headers(), stream=True, timeout=60)
    except requests.ConnectionError:
        return jsonify({"error": "No se pudo conectar a ElevenLabs"}), 502
    if r.status_code != 200:
        return jsonify({"error": f"Audio no disponible ({r.status_code})"}), r.status_code
    return Response(
        stream_with_context(r.iter_content(chunk_size=4096)),
        content_type=r.headers.get("Content-Type", "audio/mpeg"),
    )


@app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
def api_conversation_delete(conversation_id: str) -> Response:
    """Eliminar una conversacion."""
    return _proxy(_delete(f"/v1/convai/conversations/{conversation_id}"))


@app.route("/api/conversations/<conversation_id>/feedback", methods=["POST"])
def api_conversation_feedback(conversation_id: str) -> Response:
    """Enviar feedback (like/dislike) a una conversacion."""
    return _proxy(_post(
        f"/v1/convai/conversations/{conversation_id}/feedback",
        request.json,
    ))


# ---------------------------------------------------------------------------
# Busqueda
# ---------------------------------------------------------------------------

@app.route("/api/conversations/search/text")
def api_search_text() -> Response:
    """Busqueda full-text sobre transcripts de conversaciones."""
    params: Dict[str, Any] = {"agent_id": AGENT_ID}
    for key in ("text_query", "page_size", "cursor", "sort_by",
                "call_successful", "call_start_before_unix",
                "call_start_after_unix"):
        val = request.args.get(key)
        if val is not None:
            params[key] = val
    return _proxy(_get("/v1/convai/conversations/messages/text-search", params=params))


@app.route("/api/conversations/search/smart")
def api_search_smart() -> Response:
    """Busqueda semantica sobre transcripts de conversaciones."""
    params: Dict[str, Any] = {"agent_id": AGENT_ID}
    for key in ("text_query", "page_size", "cursor"):
        val = request.args.get(key)
        if val is not None:
            params[key] = val
    return _proxy(_get("/v1/convai/conversations/messages/smart-search", params=params))


# ---------------------------------------------------------------------------
# Analytics / Uso
# ---------------------------------------------------------------------------

@app.route("/api/analytics/live-count")
def api_live_count() -> Response:
    """Cantidad de conversaciones activas en este momento."""
    return _proxy(_get("/v1/convai/analytics/live-count", params={"agent_id": AGENT_ID}))


@app.route("/api/analytics/usage")
def api_usage() -> Response:
    """Estadisticas de uso (creditos, caracteres, minutos, requests)."""
    params: Dict[str, Any] = {}
    for key in ("start_unix", "end_unix", "breakdown_type",
                "aggregation_interval", "metric",
                "include_workspace_metrics"):
        val = request.args.get(key)
        if val is not None:
            params[key] = val
    return _proxy(_get("/v1/usage/character-stats", params=params))


@app.route("/api/user")
def api_user() -> Response:
    """Informacion del usuario autenticado."""
    return _proxy(_get("/v1/user"))


@app.route("/api/user/subscription")
def api_user_subscription() -> Response:
    """Detalle de suscripcion (plan, limites, uso)."""
    return _proxy(_get("/v1/user/subscription"))


# ---------------------------------------------------------------------------
# Knowledge Base
# ---------------------------------------------------------------------------

@app.route("/api/kb")
def api_kb_list() -> Response:
    """Lista documentos de la knowledge base."""
    params: Dict[str, Any] = {
        "page_size": request.args.get("page_size", 50, type=int),
    }
    for key in ("search", "cursor", "parent_folder_id", "types"):
        val = request.args.get(key)
        if val is not None:
            params[key] = val
    return _proxy(_get("/v1/convai/knowledge-base", params=params))


@app.route("/api/kb/<doc_id>")
def api_kb_doc(doc_id: str) -> Response:
    """Detalle de un documento de la knowledge base."""
    return _proxy(_get(f"/v1/convai/knowledge-base/{doc_id}"))


@app.route("/api/kb/<doc_id>/content")
def api_kb_content(doc_id: str) -> Response:
    """Contenido completo extraido de un documento de la KB."""
    return _proxy(_get(f"/v1/convai/knowledge-base/{doc_id}/content"))


@app.route("/api/kb/<doc_id>/dependent-agents")
def api_kb_dependent_agents(doc_id: str) -> Response:
    """Agentes que usan este documento de la KB."""
    return _proxy(_get(f"/v1/convai/knowledge-base/{doc_id}/dependent-agents"))


# ---------------------------------------------------------------------------
# Voces y modelos (datos de referencia)
# ---------------------------------------------------------------------------

@app.route("/api/voices")
def api_voices() -> Response:
    """Lista las voces disponibles."""
    return _proxy(_get("/v1/voices"))


@app.route("/api/models")
def api_models() -> Response:
    """Lista los modelos TTS disponibles."""
    return _proxy(_get("/v1/models"))


@app.route("/api/llm-models")
def api_llm_models() -> Response:
    """Lista los modelos LLM disponibles para ConvAI."""
    return _proxy(_get("/v1/convai/llm/list"))


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    require_elevenlabs()
    logger.info("SAMU Dashboard iniciando — Agent: %s", AGENT_ID)
    socketio.run(app, debug=True, host=FLASK_HOST, port=FLASK_PORT)
