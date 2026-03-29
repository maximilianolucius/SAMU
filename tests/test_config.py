"""Tests para config.py — configuracion centralizada."""

import logging
from unittest.mock import patch

import pytest

import config


class TestSetupLogging:
    def test_returns_logger_instance(self):
        logger = config.setup_logging("test_module")
        assert isinstance(logger, logging.Logger)

    def test_logger_has_correct_name(self):
        logger = config.setup_logging("mi_modulo")
        assert logger.name == "mi_modulo"

    def test_different_names_give_different_loggers(self):
        a = config.setup_logging("modulo_a")
        b = config.setup_logging("modulo_b")
        assert a is not b
        assert a.name != b.name


class TestRequireElevenlabs:
    def test_raises_when_api_key_empty(self):
        with patch.object(config, "ELEVENLABS_API_KEY", ""):
            with pytest.raises(SystemExit, match="ELEVENLABS_API_KEY"):
                config.require_elevenlabs()

    def test_raises_when_agent_id_empty(self):
        with patch.object(config, "ELEVENLABS_API_KEY", "sk_fake"):
            with patch.object(config, "AGENT_ID", ""):
                with pytest.raises(SystemExit, match="AGENT_ID"):
                    config.require_elevenlabs()

    def test_passes_when_both_set(self):
        with patch.object(config, "ELEVENLABS_API_KEY", "sk_fake"):
            with patch.object(config, "AGENT_ID", "agent_fake"):
                config.require_elevenlabs()  # no exception


class TestRequireVllm:
    def test_raises_when_base_url_empty(self):
        with patch.object(config, "VLLM_BASE_URL", ""):
            with pytest.raises(SystemExit, match="VLLM_BASE_URL"):
                config.require_vllm()

    def test_passes_when_url_set(self):
        with patch.object(config, "VLLM_BASE_URL", "http://localhost:8000/v1"):
            config.require_vllm()  # no exception


class TestDefaultValues:
    def test_elevenlabs_base_url(self):
        assert config.ELEVENLABS_BASE_URL == "https://api.elevenlabs.io"

    def test_elevenlabs_timeout(self):
        assert config.ELEVENLABS_TIMEOUT == 30

    def test_flask_port_is_int(self):
        assert isinstance(config.FLASK_PORT, int)

    def test_log_format_contains_level(self):
        assert "%(levelname)s" in config.LOG_FORMAT
