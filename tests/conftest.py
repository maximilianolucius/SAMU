"""Fixtures compartidas para todos los tests."""

import json
from unittest.mock import MagicMock

import pytest

import app as app_module


@pytest.fixture()
def client():
    """Flask test client sin llamadas reales."""
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def socketio_client():
    """SocketIO test client."""
    app_module.app.config["TESTING"] = True
    return app_module.socketio.test_client(app_module.app)


@pytest.fixture(autouse=True)
def clear_call_sessions():
    """Limpia el estado de llamadas activas entre tests."""
    app_module.call_sessions.clear()
    yield
    app_module.call_sessions.clear()


def make_mock_response(json_data=None, status_code=200, text="", headers=None):
    """Crea un mock de requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text or json.dumps(json_data or {})
    resp.headers = headers or {"Content-Type": "application/json"}
    if json_data is not None:
        resp.json.return_value = json_data
    else:
        resp.json.side_effect = ValueError("No JSON")
    return resp


def make_mock_stream_response(chunks=None, status_code=200, headers=None):
    """Crea un mock de requests.Response para streaming."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {"Content-Type": "audio/mpeg"}
    resp.iter_content.return_value = iter(chunks or [b"audio-data"])
    return resp
