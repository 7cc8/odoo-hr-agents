"""
اختبارات شاملة لمحرك تحويل الصوت إلى نص: «محرك الهمس» (Tests for WhisperSTTService)
================================================================================
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from whisper_service import TranscriptionResult, WhisperSTTService


class TestWhisperSTTService(unittest.TestCase):
    def setUp(self):
        self.service = WhisperSTTService(model_size="tiny", device="cpu", compute_type="int8")

    def test_transcribe_missing_file_returns_error(self):
        res = self.service.transcribe("non_existent_audio_file.ogg")
        self.assertFalse(res.is_success)
        self.assertEqual(res.text, "")
        self.assertIn("غير موجود", res.error_message)

    def test_transcription_result_to_dict(self):
        tr = TranscriptionResult(
            text="أريد تقديم إجازة",
            language="ar",
            duration=3.5,
            backend="faster_whisper_tiny",
            confidence=0.95,
        )
        d = tr.to_dict()
        self.assertEqual(d["text"], "أريد تقديم إجازة")
        self.assertEqual(d["language"], "ar")
        self.assertEqual(d["duration"], 3.5)
        self.assertEqual(d["backend"], "faster_whisper_tiny")
        self.assertTrue(d["is_success"])

    @patch("whisper_service.WhisperSTTService._get_local_model")
    def test_transcribe_local_mocked(self, mock_get_model):
        mock_model = MagicMock()
        mock_seg1 = MagicMock()
        mock_seg1.text = "استعلام عن"
        mock_seg2 = MagicMock()
        mock_seg2.text = "رصيد الإجازات"

        mock_info = MagicMock()
        mock_info.language = "ar"
        mock_info.duration = 4.2
        mock_info.language_probability = 0.98

        mock_model.transcribe.return_value = ([mock_seg1, mock_seg2], mock_info)
        mock_get_model.return_value = mock_model

        # Create temporary dummy file
        dummy_file = Path("output/temp_test_audio.ogg")
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.write_bytes(b"dummy audio content")

        try:
            res = self.service.transcribe(dummy_file, language="ar")
            self.assertTrue(res.is_success)
            self.assertEqual(res.text, "استعلام عن رصيد الإجازات")
            self.assertEqual(res.language, "ar")
            self.assertEqual(res.duration, 4.2)
            self.assertEqual(res.confidence, 0.98)
            self.assertIn("faster_whisper", res.backend)
        finally:
            dummy_file.unlink(missing_ok=True)

    @patch("whisper_service.WhisperSTTService._transcribe_groq")
    def test_transcribe_prefers_groq_when_key_present(self, mock_groq):
        mock_groq.return_value = TranscriptionResult(
            text="كشف مسيرات الرواتب",
            language="ar",
            duration=2.1,
            backend="groq_whisper_large_v3_turbo",
            confidence=0.99,
        )
        service = WhisperSTTService(groq_api_key="gsk_test_mock_key")
        dummy_file = Path("output/temp_test_audio_groq.ogg")
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.write_bytes(b"dummy content")

        try:
            res = service.transcribe(dummy_file)
            self.assertTrue(res.is_success)
            self.assertEqual(res.text, "كشف مسيرات الرواتب")
            self.assertEqual(res.backend, "groq_whisper_large_v3_turbo")
            mock_groq.assert_called_once()
        finally:
            dummy_file.unlink(missing_ok=True)

    @patch("whisper_service.WhisperSTTService._transcribe_openai")
    def test_transcribe_openai_when_key_present(self, mock_openai):
        mock_openai.return_value = TranscriptionResult(
            text="سجل التدقيق الرقابي",
            language="ar",
            duration=1.5,
            backend="openai_whisper_1",
            confidence=0.98,
        )
        service = WhisperSTTService(openai_api_key="sk-test-mock-key")
        dummy_file = Path("output/temp_test_audio_openai.ogg")
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.write_bytes(b"dummy content")

        try:
            res = service.transcribe(dummy_file)
            self.assertTrue(res.is_success)
            self.assertEqual(res.text, "سجل التدقيق الرقابي")
            self.assertEqual(res.backend, "openai_whisper_1")
            mock_openai.assert_called_once()
        finally:
            dummy_file.unlink(missing_ok=True)

    def test_delete_after_removes_file(self):
        dummy_file = Path("output/temp_test_audio_del.ogg")
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.write_bytes(b"dummy content")

        with patch.object(self.service, "_transcribe_local") as mock_local:
            mock_local.return_value = TranscriptionResult(text="تجربة", is_success=True)
            res = self.service.transcribe(dummy_file, delete_after=True)
            self.assertTrue(res.is_success)
            self.assertFalse(dummy_file.exists())

    @patch("whisper_service.WhisperSTTService._get_local_model")
    def test_laughter_hallucination_filtered_to_greeting(self, mock_get_model):
        mock_model = MagicMock()
        mock_seg = MagicMock()
        mock_seg.text = "اهههههههه"
        mock_info = MagicMock()
        mock_info.language = "ar"
        mock_info.duration = 1.2
        mock_info.language_probability = 0.9

        mock_model.transcribe.return_value = ([mock_seg], mock_info)
        mock_get_model.return_value = mock_model

        dummy_file = Path("output/temp_test_laugh.ogg")
        dummy_file.parent.mkdir(parents=True, exist_ok=True)
        dummy_file.write_bytes(b"dummy laugh audio")

        try:
            res = self.service._transcribe_local(dummy_file, language="ar")
            self.assertTrue(res.is_success)
            self.assertEqual(res.text, "ألو")
        finally:
            dummy_file.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

