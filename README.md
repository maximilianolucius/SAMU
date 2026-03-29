# SAMI — Asistente de Apoyo Psicologico Virtual

Sistema de primer apoyo psicologico virtual que combina un LLM (vLLM + Gemma) con
ElevenLabs Conversational AI para interaccion por voz. Incluye un dashboard web
para monitorear y gestionar el agente y sus conversaciones.

## Arquitectura

```
                       ┌──────────────────┐
                       │  ElevenLabs API  │
                       │  (voz + agente)  │
                       └────────┬─────────┘
                                │
                    ┌───────────┼───────────┐
                    │                       │
            ┌───────▼───────┐       ┌───────▼───────┐
            │   app.py      │       │ eleven_lab.py │
            │  Dashboard    │       │  Cliente      │
            │  Flask + WS   │       │  de voz       │
            └───────────────┘       └───────────────┘

            ┌───────────────┐
            │  sami_bot.py  │──── vLLM Server (Gemma 3 12B)
            │  Chat texto   │
            └───────────────┘
```

## Componentes

| Archivo           | Descripcion                                                              |
|-------------------|--------------------------------------------------------------------------|
| `sami_bot.py`     | Bot de texto. Chat interactivo por consola contra un servidor vLLM.      |
| `app.py`          | Dashboard web (Flask + SocketIO). Proxea la API de ElevenLabs con 26 endpoints. Recibe webhooks en tiempo real. |
| `eleven_lab.py`   | Cliente de voz. Inicia una sesion con el agente de ElevenLabs usando microfono y altavoz. |
| `config.py`       | Configuracion centralizada. Carga `.env`, configura logging, valida variables. |

## Requisitos previos

- **Python 3.10+**
- **Servidor vLLM** corriendo con un modelo compatible (ej: Gemma 3 12B) — solo para `sami_bot.py`
- **Cuenta de ElevenLabs** con un agente de Conversational AI creado — para `app.py` y `eleven_lab.py`
- **PyAudio** (dependencia de sistema para `eleven_lab.py`):
  - Ubuntu/Debian: `sudo apt install portaudio19-dev`
  - macOS: `brew install portaudio`

## Instalacion

```bash
# Crear entorno virtual
python -m venv .venv
source .venv/bin/activate

# Instalar dependencias
pip install -r requirements.txt
```

## Configuracion

Copia el template de variables de entorno y editalo:

```bash
cp .env.example .env
```

| Variable              | Requerido por       | Descripcion                                     |
|-----------------------|---------------------|-------------------------------------------------|
| `ELEVENLABS_API_KEY`  | app, eleven_lab     | API key de ElevenLabs                            |
| `AGENT_ID`            | app, eleven_lab     | ID del agente en ElevenLabs                      |
| `VLLM_BASE_URL`       | sami_bot            | URL del servidor vLLM (ej: `http://host:8000/v1`) |
| `VLLM_MODEL`          | sami_bot            | Modelo a usar (default: `gemma-3-12b-it`)       |
| `VLLM_API_KEY`        | sami_bot            | API key del servidor vLLM (default: `EMPTY`)    |
| `FLASK_SECRET_KEY`    | app                 | Secret key para sesiones Flask                  |
| `FLASK_HOST`          | app                 | Host del dashboard (default: `0.0.0.0`)         |
| `FLASK_PORT`          | app                 | Puerto del dashboard (default: `5016`)          |
| `LOG_LEVEL`           | todos               | Nivel de logging: DEBUG, INFO, WARNING, ERROR   |

## Uso

### Bot de texto (consola)

```bash
python sami_bot.py
```

Chat interactivo que usa el system prompt de `system_prompt.txt`. Escribe `salir` para terminar.

### Dashboard web

```bash
python app.py
```

Abre `http://localhost:5016` en el navegador. El dashboard tiene 8 secciones:

| Seccion          | Que muestra                                                    |
|------------------|----------------------------------------------------------------|
| Resumen          | Stats del agente, ultimas conversaciones                       |
| Conversaciones   | Lista con filtros, detalle con transcript, audio player        |
| Buscar           | Busqueda full-text y semantica sobre transcripts               |
| Agente           | System prompt, configuracion completa en JSON                  |
| Knowledge Base   | Documentos de la KB y su contenido                             |
| Uso / Costos     | Grafico de uso diario, info de suscripcion                     |
| En vivo          | Llamadas activas + feed de webhooks en tiempo real             |
| API Raw          | Explorador para ejecutar cualquier endpoint y ver JSON crudo   |

### API endpoints del dashboard

El dashboard expone 26 endpoints REST que proxean la API de ElevenLabs:

```
GET  /api/agent                              Configuracion del agente
PATCH /api/agent                             Actualizar agente
GET  /api/agent/widget                       Config del widget
GET  /api/agent/link                         Link compartible
GET  /api/agent/kb-size                      Tamano de la KB
GET  /api/agent/branches                     Branches (versionado)

GET  /api/conversations                      Listar (con filtros + paginacion)
GET  /api/conversations/<id>                 Detalle + transcript
GET  /api/conversations/<id>/audio           Stream de audio (mp3)
DELETE /api/conversations/<id>               Eliminar conversacion
POST /api/conversations/<id>/feedback        Enviar like/dislike

GET  /api/conversations/search/text          Busqueda full-text
GET  /api/conversations/search/smart         Busqueda semantica

GET  /api/analytics/live-count               Llamadas activas ahora
GET  /api/analytics/usage                    Estadisticas de uso

GET  /api/user                               Info del usuario
GET  /api/user/subscription                  Detalle de suscripcion

GET  /api/kb                                 Listar documentos KB
GET  /api/kb/<id>                            Detalle de documento
GET  /api/kb/<id>/content                    Contenido del documento
GET  /api/kb/<id>/dependent-agents           Agentes que usan el doc

GET  /api/voices                             Voces disponibles
GET  /api/models                             Modelos TTS
GET  /api/llm-models                         Modelos LLM para ConvAI

POST /webhook                                Receptor de webhooks
```

### Cliente de voz

```bash
python eleven_lab.py
```

Inicia una sesion de voz con el agente usando microfono y altavoz. Ctrl+C para terminar.

## Tests

```bash
python -m pytest tests/ -v
```

100 tests unitarios cubriendo todos los modulos, sin llamadas a APIs externas.

## System prompt

El prompt principal esta en `system_prompt.txt`. Define el comportamiento de SAMI:

- Protocolo de 5 preguntas de evaluacion (P1-P5)
- Protocolos de crisis (riesgo suicida, panico, disociacion)
- Adaptacion tonal segun estado emocional del usuario
- Uso del Client Tool `logMessage` para tracking

Prompts alternativos disponibles en `prompts/`:
- `maje_system_prompt.txt` — version alternativa del asistente
- `encuestadora_prompt.txt` — bot de encuestas politicas (proyecto separado)

## Estructura del proyecto

```
SAMU/
├── config.py              # Configuracion centralizada + logging
├── sami_bot.py            # Bot de texto (vLLM)
├── app.py                 # Dashboard web (Flask + SocketIO)
├── eleven_lab.py          # Cliente de voz (ElevenLabs SDK)
│
├── system_prompt.txt      # Prompt principal de SAMI
├── pyproject.toml         # Metadatos del proyecto + config pytest
├── requirements.txt       # Dependencias con versiones pinneadas
├── .env.example           # Template de variables de entorno
├── .gitignore             # Archivos ignorados
│
├── tests/                 # Tests unitarios (pytest)
├── config/                # Diccionario de pronunciacion ElevenLabs
├── prompts/               # Prompts alternativos
├── templates/             # HTML (dashboard + demos)
├── docs/                  # Documentacion y research
└── oldVersions/           # Versiones anteriores archivadas
```

## Troubleshooting

| Problema | Solucion |
|----------|----------|
| `ELEVENLABS_API_KEY no esta configurada` | Crea el archivo `.env` a partir de `.env.example` |
| `No se encontro el archivo de prompt` | Verifica que `system_prompt.txt` existe en la raiz |
| `No se pudo conectar a ElevenLabs` | Verifica tu API key y conexion a internet |
| `Error de conexion` (sami_bot) | Verifica que el servidor vLLM esta corriendo en la URL configurada |
| Sin audio en `eleven_lab.py` | Instala portaudio: `sudo apt install portaudio19-dev` y reinstala `pip install elevenlabs[pyaudio]` |
| Dashboard no carga | Verifica que el puerto 5016 no esta ocupado |
