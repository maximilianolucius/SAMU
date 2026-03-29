"""Tests para eleven_lab.py — cliente de voz y flujo de encuesta."""

from unittest.mock import patch, MagicMock

import pytest

import eleven_lab
from eleven_lab import SurveyState, QUESTIONS


class TestSurveyState:
    def test_initial_state(self):
        s = SurveyState()
        assert s.current_idx == 0
        assert s.answers == {}

    def test_current_question_returns_first(self):
        s = SurveyState()
        assert s.current_question() == QUESTIONS[0]

    def test_current_question_returns_none_when_done(self):
        s = SurveyState(current_idx=len(QUESTIONS))
        assert s.current_question() is None

    def test_record_answer_stores_text(self):
        s = SurveyState()
        s.record_answer_and_advance("Juan Perez")
        assert s.answers[0] == "Juan Perez"

    def test_record_answer_strips_whitespace(self):
        s = SurveyState()
        s.record_answer_and_advance("  respuesta  ")
        assert s.answers[0] == "respuesta"

    def test_record_answer_advances_index(self):
        s = SurveyState()
        s.record_answer_and_advance("respuesta")
        assert s.current_idx == 1

    def test_full_survey_flow(self):
        s = SurveyState()
        answers = ["Juan", "juan@test.com", "30"]
        for answer in answers:
            assert s.current_question() is not None
            s.record_answer_and_advance(answer)
        assert s.current_question() is None
        assert len(s.answers) == 3
        assert s.answers[0] == "Juan"
        assert s.answers[1] == "juan@test.com"
        assert s.answers[2] == "30"

    def test_record_after_complete_is_noop(self):
        s = SurveyState(current_idx=len(QUESTIONS))
        s.record_answer_and_advance("extra")
        assert len(s.answers) == 0
        assert s.current_idx == len(QUESTIONS)

    def test_current_question_second(self):
        s = SurveyState()
        s.record_answer_and_advance("first")
        assert s.current_question() == QUESTIONS[1]

    def test_current_question_last(self):
        s = SurveyState()
        for i in range(len(QUESTIONS) - 1):
            s.record_answer_and_advance(f"answer_{i}")
        assert s.current_question() == QUESTIONS[-1]


class TestCallbacks:
    def test_on_agent_response_does_not_crash(self):
        eleven_lab.on_agent_response("Hola, bienvenido")

    def test_on_agent_response_correction_does_not_crash(self):
        eleven_lab.on_agent_response_correction("original", "corregido")

    def test_on_user_transcript_records_answer(self):
        eleven_lab.state = SurveyState()
        eleven_lab.on_user_transcript("Mi nombre es Juan")
        assert eleven_lab.state.answers[0] == "Mi nombre es Juan"
        assert eleven_lab.state.current_idx == 1

    def test_on_user_transcript_completes_survey(self):
        eleven_lab.state = SurveyState()
        eleven_lab.conversation = None  # no real conversation
        for answer in ["Juan", "juan@test.com", "30"]:
            eleven_lab.on_user_transcript(answer)
        assert eleven_lab.state.current_question() is None

    def test_on_user_transcript_sends_next_question(self):
        eleven_lab.state = SurveyState()
        mock_conv = MagicMock()
        eleven_lab.conversation = mock_conv

        eleven_lab.on_user_transcript("Juan")
        mock_conv.send_user_message.assert_called_once()
        msg = mock_conv.send_user_message.call_args[0][0]
        assert QUESTIONS[1] in msg

    def test_on_user_transcript_no_send_when_complete(self):
        eleven_lab.state = SurveyState(current_idx=len(QUESTIONS))
        mock_conv = MagicMock()
        eleven_lab.conversation = mock_conv

        eleven_lab.on_user_transcript("extra input")
        mock_conv.send_user_message.assert_not_called()


class TestMain:
    def test_main_requires_elevenlabs(self):
        with patch.object(eleven_lab, "ELEVENLABS_API_KEY", ""):
            with pytest.raises(SystemExit):
                eleven_lab.main()
