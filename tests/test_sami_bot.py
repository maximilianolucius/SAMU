"""Tests para sami_bot.py — bot de texto SAMI."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import sami_bot


class TestLoadSystemPrompt:
    def test_loads_existing_file(self, tmp_path):
        prompt_file = tmp_path / "system_prompt.txt"
        prompt_file.write_text("Eres SAMI.", encoding="utf-8")
        with patch.object(sami_bot, "PROMPT_PATH", prompt_file):
            result = sami_bot.load_system_prompt()
        assert result == "Eres SAMI."

    def test_exits_when_file_missing(self, tmp_path):
        missing = tmp_path / "no_existe.txt"
        with patch.object(sami_bot, "PROMPT_PATH", missing):
            with pytest.raises(SystemExit):
                sami_bot.load_system_prompt()

    def test_reads_utf8_content(self, tmp_path):
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("Hola, ¿cómo estás?", encoding="utf-8")
        with patch.object(sami_bot, "PROMPT_PATH", prompt_file):
            result = sami_bot.load_system_prompt()
        assert "¿cómo estás?" in result

    def test_returns_full_content(self, tmp_path):
        content = "Linea 1\nLinea 2\nLinea 3"
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text(content, encoding="utf-8")
        with patch.object(sami_bot, "PROMPT_PATH", prompt_file):
            result = sami_bot.load_system_prompt()
        assert result == content


class TestSAMIBot:
    @pytest.fixture()
    def bot(self, tmp_path):
        prompt_file = tmp_path / "system_prompt.txt"
        prompt_file.write_text("Eres SAMI, un asistente.", encoding="utf-8")
        with patch.object(sami_bot, "PROMPT_PATH", prompt_file):
            with patch.object(sami_bot, "VLLM_BASE_URL", "http://fake:8000/v1"):
                bot = sami_bot.SAMIBot()
        return bot

    def test_init_loads_prompt(self, bot):
        assert "Eres SAMI" in bot.system_prompt

    def test_init_empty_history(self, bot):
        assert bot.history == []

    def test_chat_appends_to_history(self, bot):
        mock_response = MagicMock()
        mock_response.content = "Hola, te escucho."
        bot.client = MagicMock()
        bot.client.invoke.return_value = mock_response

        bot.chat("Hola")
        assert len(bot.history) == 2  # user msg + assistant response

    def test_chat_returns_response_content(self, bot):
        mock_response = MagicMock()
        mock_response.content = "Respuesta del modelo"
        bot.client = MagicMock()
        bot.client.invoke.return_value = mock_response

        result = bot.chat("Test")
        assert result == "Respuesta del modelo"

    def test_chat_handles_connection_error(self, bot):
        bot.client = MagicMock()
        bot.client.invoke.side_effect = ConnectionError("Connection refused")

        result = bot.chat("Hola")
        assert "Error de conexion" in result

    def test_chat_handles_generic_exception(self, bot):
        bot.client = MagicMock()
        bot.client.invoke.side_effect = RuntimeError("Unexpected error")

        result = bot.chat("Hola")
        assert "Error" in result

    def test_chat_preserves_history_across_calls(self, bot):
        mock_response = MagicMock()
        mock_response.content = "Respuesta"
        bot.client = MagicMock()
        bot.client.invoke.return_value = mock_response

        bot.chat("Mensaje 1")
        bot.chat("Mensaje 2")
        # 2 user + 2 assistant = 4
        assert len(bot.history) == 4

    def test_chat_builds_messages_with_system_prompt(self, bot):
        mock_response = MagicMock()
        mock_response.content = "OK"
        bot.client = MagicMock()
        bot.client.invoke.return_value = mock_response

        bot.chat("Test")

        # Verify invoke was called with system prompt as first message
        call_args = bot.client.invoke.call_args[0][0]
        assert call_args[0].content == bot.system_prompt  # SystemMessage

    def test_history_still_grows_after_error(self, bot):
        bot.client = MagicMock()
        bot.client.invoke.side_effect = ConnectionError("fail")

        bot.chat("Hola")
        # User message was added but no response
        assert len(bot.history) == 1


class TestMain:
    def test_exit_on_salir(self, tmp_path):
        prompt_file = tmp_path / "system_prompt.txt"
        prompt_file.write_text("prompt", encoding="utf-8")
        with patch.object(sami_bot, "PROMPT_PATH", prompt_file):
            with patch("builtins.input", side_effect=["salir"]):
                with patch.object(sami_bot, "VLLM_BASE_URL", "http://fake:8000/v1"):
                    sami_bot.main()  # should not hang

    def test_exit_on_keyboard_interrupt(self, tmp_path):
        prompt_file = tmp_path / "system_prompt.txt"
        prompt_file.write_text("prompt", encoding="utf-8")
        with patch.object(sami_bot, "PROMPT_PATH", prompt_file):
            with patch("builtins.input", side_effect=KeyboardInterrupt):
                with patch.object(sami_bot, "VLLM_BASE_URL", "http://fake:8000/v1"):
                    sami_bot.main()  # should not crash

    def test_exit_on_eof(self, tmp_path):
        prompt_file = tmp_path / "system_prompt.txt"
        prompt_file.write_text("prompt", encoding="utf-8")
        with patch.object(sami_bot, "PROMPT_PATH", prompt_file):
            with patch("builtins.input", side_effect=EOFError):
                with patch.object(sami_bot, "VLLM_BASE_URL", "http://fake:8000/v1"):
                    sami_bot.main()

    def test_skips_empty_input(self, tmp_path):
        prompt_file = tmp_path / "system_prompt.txt"
        prompt_file.write_text("prompt", encoding="utf-8")
        with patch.object(sami_bot, "PROMPT_PATH", prompt_file):
            with patch("builtins.input", side_effect=["", "  ", "salir"]):
                with patch.object(sami_bot, "VLLM_BASE_URL", "http://fake:8000/v1"):
                    sami_bot.main()
