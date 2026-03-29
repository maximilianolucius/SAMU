"""Tests para app.py — dashboard Flask y proxy de la API ElevenLabs."""

import json
from unittest.mock import patch, MagicMock

import pytest
import requests

import app as app_module
from tests.conftest import make_mock_response, make_mock_stream_response


# ---------------------------------------------------------------------------
# Helpers (_get, _post, _patch, _delete)
# ---------------------------------------------------------------------------

class TestGetHelper:
    def test_success(self):
        mock_resp = make_mock_response({"agents": []}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            data, status = app_module._get("/v1/test")
        assert data == {"agents": []}
        assert status == 200

    def test_connection_error(self):
        with patch("app.requests.get", side_effect=requests.ConnectionError):
            data, status = app_module._get("/v1/test")
        assert status == 502
        assert "error" in data

    def test_non_json_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.side_effect = ValueError("No JSON")
        mock_resp.text = "<html>Error</html>"
        with patch("app.requests.get", return_value=mock_resp):
            data, status = app_module._get("/v1/test")
        assert "error" in data
        assert status == 200

    def test_passes_params(self):
        mock_resp = make_mock_response({"ok": True}, 200)
        with patch("app.requests.get", return_value=mock_resp) as mock_get:
            app_module._get("/v1/test", params={"page_size": 10})
        _, kwargs = mock_get.call_args
        assert kwargs["params"] == {"page_size": 10}

    def test_api_error_status(self):
        mock_resp = make_mock_response({"error": "unauthorized"}, 401)
        with patch("app.requests.get", return_value=mock_resp):
            data, status = app_module._get("/v1/test")
        assert status == 401


class TestPostHelper:
    def test_success(self):
        mock_resp = make_mock_response({"status": "ok"}, 200)
        with patch("app.requests.post", return_value=mock_resp):
            data, status = app_module._post("/v1/test", {"feedback": "like"})
        assert status == 200

    def test_connection_error(self):
        with patch("app.requests.post", side_effect=requests.ConnectionError):
            data, status = app_module._post("/v1/test")
        assert status == 502


class TestPatchHelper:
    def test_success(self):
        mock_resp = make_mock_response({"updated": True}, 200)
        with patch("app.requests.patch", return_value=mock_resp):
            data, status = app_module._patch("/v1/test", {"name": "new"})
        assert status == 200

    def test_connection_error(self):
        with patch("app.requests.patch", side_effect=requests.ConnectionError):
            data, status = app_module._patch("/v1/test")
        assert status == 502


class TestDeleteHelper:
    def test_empty_body_200(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = ""
        with patch("app.requests.delete", return_value=mock_resp):
            data, status = app_module._delete("/v1/test")
        assert data == {"ok": True}
        assert status == 200

    def test_with_json_body(self):
        mock_resp = make_mock_response({"deleted": True}, 200)
        mock_resp.text = '{"deleted": true}'
        with patch("app.requests.delete", return_value=mock_resp):
            data, status = app_module._delete("/v1/test")
        assert data == {"deleted": True}

    def test_connection_error(self):
        with patch("app.requests.delete", side_effect=requests.ConnectionError):
            data, status = app_module._delete("/v1/test")
        assert status == 502


# ---------------------------------------------------------------------------
# Dashboard page
# ---------------------------------------------------------------------------

class TestDashboardPage:
    def test_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"SAMU" in resp.data


# ---------------------------------------------------------------------------
# Webhook
# ---------------------------------------------------------------------------

class TestWebhook:
    def test_conversation_started(self, client):
        resp = client.post("/webhook", json={
            "conversation_id": "conv_123",
            "event_type": "conversation_started",
        })
        assert resp.status_code == 200
        assert "conv_123" in app_module.call_sessions

    def test_conversation_ended_removes_session(self, client):
        app_module.call_sessions["conv_123"] = {"status": "active"}
        resp = client.post("/webhook", json={
            "conversation_id": "conv_123",
            "event_type": "conversation_ended",
        })
        assert resp.status_code == 200
        assert "conv_123" not in app_module.call_sessions

    def test_user_transcript(self, client):
        resp = client.post("/webhook", json={
            "conversation_id": "conv_123",
            "event_type": "user_transcript",
            "transcript": "Hola, necesito ayuda",
        })
        assert resp.status_code == 200

    def test_agent_response(self, client):
        resp = client.post("/webhook", json={
            "conversation_id": "conv_123",
            "event_type": "agent_response",
            "response": "Te escucho",
        })
        assert resp.status_code == 200

    def test_unknown_event_type(self, client):
        resp = client.post("/webhook", json={
            "conversation_id": "conv_123",
            "event_type": "custom_event",
        })
        assert resp.status_code == 200

    def test_malformed_json(self, client):
        resp = client.post("/webhook", data="not json",
                          content_type="application/json")
        assert resp.status_code == 500

    def test_missing_conversation_id(self, client):
        resp = client.post("/webhook", json={
            "event_type": "conversation_started",
        })
        # Should not crash, conversation_id will be None
        assert resp.status_code == 200

    def test_ended_event_for_unknown_session(self, client):
        resp = client.post("/webhook", json={
            "conversation_id": "never_seen",
            "event_type": "conversation_ended",
        })
        assert resp.status_code == 200  # pop with default, no KeyError


# ---------------------------------------------------------------------------
# Agent routes
# ---------------------------------------------------------------------------

class TestAgentRoutes:
    def test_get_agent(self, client):
        mock_resp = make_mock_response({"agent_id": "a1", "name": "SAMI"}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/agent")
        assert resp.status_code == 200
        assert resp.json["name"] == "SAMI"

    def test_patch_agent(self, client):
        mock_resp = make_mock_response({"updated": True}, 200)
        with patch("app.requests.patch", return_value=mock_resp):
            resp = client.patch("/api/agent", json={"name": "SAMI v2"})
        assert resp.status_code == 200

    def test_get_widget(self, client):
        mock_resp = make_mock_response({"widget_config": {}}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/agent/widget")
        assert resp.status_code == 200

    def test_get_link(self, client):
        mock_resp = make_mock_response({"token": "abc"}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/agent/link")
        assert resp.status_code == 200

    def test_get_kb_size(self, client):
        mock_resp = make_mock_response({"number_of_pages": 42}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/agent/kb-size")
        assert resp.status_code == 200
        assert resp.json["number_of_pages"] == 42

    def test_get_branches(self, client):
        mock_resp = make_mock_response([{"id": "branch_1"}], 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/agent/branches")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Conversation routes
# ---------------------------------------------------------------------------

class TestConversationRoutes:
    def test_list_conversations(self, client):
        mock_resp = make_mock_response({"conversations": [], "has_more": False}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/conversations")
        assert resp.status_code == 200

    def test_list_with_filters(self, client):
        mock_resp = make_mock_response({"conversations": [], "has_more": False}, 200)
        with patch("app.requests.get", return_value=mock_resp) as mock_get:
            resp = client.get("/api/conversations?call_successful=success&page_size=10")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["call_successful"] == "success"
        assert kwargs["params"]["page_size"] == 10

    def test_list_optional_filters_excluded_when_none(self, client):
        mock_resp = make_mock_response({"conversations": []}, 200)
        with patch("app.requests.get", return_value=mock_resp) as mock_get:
            resp = client.get("/api/conversations")
        _, kwargs = mock_get.call_args
        # Optional keys like 'cursor', 'rating_min' should not be in params
        assert "cursor" not in kwargs["params"]
        assert "rating_min" not in kwargs["params"]

    def test_conversation_detail(self, client):
        detail = {"conversation_id": "c1", "transcript": []}
        mock_resp = make_mock_response(detail, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/conversations/c1")
        assert resp.status_code == 200
        assert resp.json["conversation_id"] == "c1"

    def test_conversation_delete(self, client):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = ""
        with patch("app.requests.delete", return_value=mock_resp):
            resp = client.delete("/api/conversations/c1")
        assert resp.status_code == 200
        assert resp.json["ok"] is True

    def test_conversation_feedback(self, client):
        mock_resp = make_mock_response({"ok": True}, 200)
        with patch("app.requests.post", return_value=mock_resp):
            resp = client.post("/api/conversations/c1/feedback",
                             json={"feedback": "like"})
        assert resp.status_code == 200


class TestConversationAudio:
    def test_audio_stream_success(self, client):
        mock_resp = make_mock_stream_response([b"chunk1", b"chunk2"])
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/conversations/c1/audio")
        assert resp.status_code == 200
        assert resp.content_type == "audio/mpeg"
        assert resp.data == b"chunk1chunk2"

    def test_audio_not_available(self, client):
        mock_resp = make_mock_stream_response(status_code=404)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/conversations/c1/audio")
        assert resp.status_code == 404

    def test_audio_connection_error(self, client):
        with patch("app.requests.get", side_effect=requests.ConnectionError):
            resp = client.get("/api/conversations/c1/audio")
        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Search routes
# ---------------------------------------------------------------------------

class TestSearchRoutes:
    def test_text_search(self, client):
        mock_resp = make_mock_response({"results": [], "has_more": False}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/conversations/search/text?text_query=ayuda")
        assert resp.status_code == 200

    def test_smart_search(self, client):
        mock_resp = make_mock_response({"results": [], "has_more": False}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/conversations/search/smart?text_query=crisis")
        assert resp.status_code == 200

    def test_text_search_passes_query(self, client):
        mock_resp = make_mock_response({"results": []}, 200)
        with patch("app.requests.get", return_value=mock_resp) as mock_get:
            client.get("/api/conversations/search/text?text_query=test&page_size=5")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["text_query"] == "test"
        assert kwargs["params"]["page_size"] == "5"


# ---------------------------------------------------------------------------
# Analytics routes
# ---------------------------------------------------------------------------

class TestAnalyticsRoutes:
    def test_live_count(self, client):
        mock_resp = make_mock_response({"count": 3}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/analytics/live-count")
        assert resp.json["count"] == 3

    def test_usage_stats(self, client):
        mock_resp = make_mock_response({"time": [], "usage": {}}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/analytics/usage?start_unix=1000&end_unix=2000&metric=credits")
        assert resp.status_code == 200

    def test_user_info(self, client):
        mock_resp = make_mock_response({"user_id": "u1"}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/user")
        assert resp.status_code == 200

    def test_subscription(self, client):
        mock_resp = make_mock_response({"tier": "pro", "character_count": 500}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/user/subscription")
        assert resp.json["tier"] == "pro"


# ---------------------------------------------------------------------------
# Knowledge Base routes
# ---------------------------------------------------------------------------

class TestKBRoutes:
    def test_list_kb(self, client):
        mock_resp = make_mock_response({"documents": []}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/kb")
        assert resp.status_code == 200

    def test_kb_doc_detail(self, client):
        mock_resp = make_mock_response({"id": "doc1", "name": "FAQ"}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/kb/doc1")
        assert resp.json["name"] == "FAQ"

    def test_kb_doc_content(self, client):
        mock_resp = make_mock_response({"content": "texto del documento"}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/kb/doc1/content")
        assert "texto" in resp.json["content"]

    def test_kb_dependent_agents(self, client):
        mock_resp = make_mock_response({"agents": ["a1"]}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/kb/doc1/dependent-agents")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Reference data routes
# ---------------------------------------------------------------------------

class TestReferenceRoutes:
    def test_voices(self, client):
        mock_resp = make_mock_response({"voices": []}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/voices")
        assert resp.status_code == 200

    def test_models(self, client):
        mock_resp = make_mock_response([{"model_id": "eleven_turbo_v2"}], 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/models")
        assert resp.status_code == 200

    def test_llm_models(self, client):
        mock_resp = make_mock_response({"models": []}, 200)
        with patch("app.requests.get", return_value=mock_resp):
            resp = client.get("/api/llm-models")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Edge cases & robustness
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_api_route_with_elevenlabs_down(self, client):
        """Todas las rutas deben devolver 502, no crashear, si ElevenLabs no responde."""
        with patch("app.requests.get", side_effect=requests.ConnectionError):
            for path in ["/api/agent", "/api/conversations", "/api/analytics/live-count",
                        "/api/kb", "/api/voices", "/api/models", "/api/user"]:
                resp = client.get(path)
                assert resp.status_code == 502, f"{path} no retorno 502"

    def test_headers_include_api_key(self):
        headers = app_module._headers()
        assert "xi-api-key" in headers
        assert "Content-Type" in headers

    def test_multiple_webhooks_accumulate_sessions(self, client):
        for i in range(5):
            client.post("/webhook", json={
                "conversation_id": f"conv_{i}",
                "event_type": "conversation_started",
            })
        assert len(app_module.call_sessions) == 5

    def test_webhook_end_then_start_same_id(self, client):
        client.post("/webhook", json={
            "conversation_id": "conv_1",
            "event_type": "conversation_started",
        })
        client.post("/webhook", json={
            "conversation_id": "conv_1",
            "event_type": "conversation_ended",
        })
        assert "conv_1" not in app_module.call_sessions

        # Re-start with same ID
        client.post("/webhook", json={
            "conversation_id": "conv_1",
            "event_type": "conversation_started",
        })
        assert "conv_1" in app_module.call_sessions
