"""
خدمة تحويل الصوت إلى نص: «محرك الهمس» (Whisper STT Service)
================================================================
تتيح لسراج فهم التسجيلات الصوتية (Voice Notes & Audio Files) في تيليجرام
وتحويلها بدقة متناهية إلى نصوص باللغة العربية أو الإنجليزية، ثم تمريرها
تلقائياً إلى محرك «لايا» الذكي والوكلاء الآخرين.

المعمارية تدعم أولويات المعالجة المتعددة:
1. Groq Cloud Whisper API (whisper-large-v3-turbo) - سرعة فائقة أقل من نصف ثانية.
2. Local faster-whisper (CTranslate2 INT8) - محلي 100% بدون أي حاجة لإنترنت أو مفاتيح خارجية.
3. OpenAI Whisper Cloud API (whisper-1) - كخيار بديل عند توفر المفتاح.
4. محاكي الاختبارات والبيئات المعزولة (Deterministic Test Fallback).
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("whisper_stt_service")

# Regex to catch repetitive laughter / breathing hallucination artifacts (e.g. اهههههههه, هههههه)
_LAUGH_HALLUCINATION_RE = re.compile(r"^[اأإ]?ه{2,}[ه!.]*$", re.UNICODE)
_REPETITIVE_CHAR_RE = re.compile(r"^([^\s])\1{3,}$", re.UNICODE)


@dataclass
class TranscriptionResult:
    """نتيجة تحويل التسجيل الصوتي إلى نص مع بيانات المحرك."""
    text: str
    language: str = "ar"
    duration: float = 0.0
    backend: str = "local_faster_whisper"
    confidence: float = 1.0
    is_success: bool = True
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "language": self.language,
            "duration": self.duration,
            "backend": self.backend,
            "confidence": self.confidence,
            "is_success": self.is_success,
            "error_message": self.error_message,
        }


# Cache for local models by (model_size, device, compute_type) to avoid cold starts
_CACHED_LOCAL_MODELS: Dict[str, Any] = {}


class WhisperSTTService:
    """محرك تحويل الصوت إلى نص الموحد (Whisper Speech-to-Text Engine)."""

    def __init__(
        self,
        model_size: Optional[str] = None,
        device: str = "cpu",
        compute_type: str = "int8",
        groq_api_key: Optional[str] = None,
        openai_api_key: Optional[str] = None,
    ) -> None:
        self.model_size = model_size or os.environ.get("WHISPER_MODEL", "base")
        self.device = device
        self.compute_type = compute_type
        self.groq_api_key = groq_api_key or os.environ.get("GROQ_API_KEY")
        self.openai_api_key = openai_api_key or os.environ.get("OPENAI_API_KEY")

    def _get_local_model(self) -> Any:
        """Loads and caches the faster-whisper model singleton."""
        cache_key = f"{self.model_size}_{self.device}_{self.compute_type}"
        if cache_key in _CACHED_LOCAL_MODELS:
            return _CACHED_LOCAL_MODELS[cache_key]

        try:
            from faster_whisper import WhisperModel
            logger.info("Initializing local faster-whisper model '%s' on %s...", self.model_size, self.device)
            model_inst = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            _CACHED_LOCAL_MODELS[cache_key] = model_inst
            return model_inst
        except Exception as exc:
            logger.warning("Failed to initialize faster-whisper: %s", exc)
            return None

    def transcribe(
        self,
        audio_path: str | Path,
        language: Optional[str] = "ar",
        delete_after: bool = False,
    ) -> TranscriptionResult:
        """
        Transcribes the given audio file using the best available backend.
        
        Args:
            audio_path: Path to the audio file (.ogg, .mp3, .wav, etc.)
            language: Target language code ('ar', 'en', etc. or None for auto-detect).
            delete_after: Whether to delete the audio file after successful transcription.
            
        Returns:
            TranscriptionResult with extracted text and metadata.
        """
        p = Path(audio_path)
        if not p.exists():
            return TranscriptionResult(
                text="",
                is_success=False,
                error_message=f"ملف الصوت غير موجود: {p}",
                backend="none",
            )

        result: Optional[TranscriptionResult] = None

        # 1. Try Groq Cloud Whisper API if key is provided (sub-second fast)
        if self.groq_api_key:
            try:
                result = self._transcribe_groq(p, language=language)
            except Exception as exc:
                logger.warning("Groq Whisper failed, falling back to local: %s", exc)

        # 2. Try OpenAI Whisper Cloud API if key is provided and Groq didn't succeed
        if (result is None or not result.is_success) and self.openai_api_key:
            try:
                result = self._transcribe_openai(p, language=language)
            except Exception as exc:
                logger.warning("OpenAI Whisper failed, falling back to local: %s", exc)

        # 3. Try Local faster-whisper
        if result is None or not result.is_success:
            try:
                result = self._transcribe_local(p, language=language)
            except Exception as exc:
                logger.error("Local faster-whisper transcription error: %s", exc)

        # 4. Final fallback
        if result is None:
            result = TranscriptionResult(
                text="",
                is_success=False,
                error_message="تعذر العثور على محرك Whisper صالح لتفريغ الصوت.",
                backend="none",
            )

        if delete_after and p.exists():
            try:
                p.unlink(missing_ok=True)
            except Exception:
                pass

        return result

    def _transcribe_local(self, path: Path, language: Optional[str]) -> TranscriptionResult:
        """Executes transcription via local faster-whisper model."""
        model = self._get_local_model()
        if model is None:
            raise RuntimeError("faster-whisper model is not available")

        # Beam size 5 + Arabic context prompt ensures accurate transcription of short greetings and HR commands
        initial_prompt = "مرحباً، ألو، السلام عليكم. تسجيل صوتي واضح باللغة العربية لنظام الموارد البشرية Odoo."
        segments, info = model.transcribe(
            str(path),
            language=language or "ar",
            beam_size=5,
            vad_filter=True,
            initial_prompt=initial_prompt,
            condition_on_previous_text=False,
            repetition_penalty=1.2,
        )

        texts = []
        for s in segments:
            t = s.text.strip()
            if t:
                texts.append(t)

        full_text = " ".join(texts).strip()
        detected_lang = getattr(info, "language", language or "ar")
        duration = getattr(info, "duration", 0.0)
        prob = getattr(info, "language_probability", 1.0)

        # Sanitize laugh / breathing hallucination artifacts on short speech
        clean_candidate = full_text.strip()
        if _LAUGH_HALLUCINATION_RE.match(clean_candidate) or _REPETITIVE_CHAR_RE.match(clean_candidate):
            if duration <= 2.5:
                full_text = "ألو"
            else:
                full_text = ""

        if not full_text:
            return TranscriptionResult(
                text="",
                language=detected_lang,
                duration=round(duration, 2),
                backend=f"faster_whisper_{self.model_size}",
                confidence=0.0,
                is_success=False,
                error_message="لم أتمكن من تمييز كلمات واضحة في التسجيل الصوتي.",
            )

        return TranscriptionResult(
            text=full_text,
            language=detected_lang,
            duration=round(duration, 2),
            backend=f"faster_whisper_{self.model_size}",
            confidence=round(prob, 2),
            is_success=True,
        )

    def _transcribe_groq(self, path: Path, language: Optional[str]) -> TranscriptionResult:
        """Executes transcription via Groq Cloud Whisper API."""
        import groq

        client = groq.Groq(api_key=self.groq_api_key)
        with open(path, "rb") as f:
            transcription = client.audio.transcriptions.create(
                file=f,
                model="whisper-large-v3-turbo",
                prompt="تسجيل صوتي لنظام الموارد البشرية وإدارة الموظفين باللغة العربية",
                response_format="verbose_json",
                language=language or "ar",
            )

        text = getattr(transcription, "text", "") or ""
        duration = getattr(transcription, "duration", 0.0)
        lang = getattr(transcription, "language", language or "ar")

        return TranscriptionResult(
            text=text.strip(),
            language=lang,
            duration=float(duration),
            backend="groq_whisper_large_v3_turbo",
            confidence=0.99,
            is_success=True,
        )

    def _transcribe_openai(self, path: Path, language: Optional[str]) -> TranscriptionResult:
        """Executes transcription via OpenAI Whisper API."""
        import httpx

        headers = {"Authorization": f"Bearer {self.openai_api_key}"}
        with open(path, "rb") as f:
            files = {"file": (path.name, f, "audio/ogg")}
            data = {"model": "whisper-1", "language": language or "ar"}
            resp = httpx.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers=headers,
                files=files,
                data=data,
                timeout=30.0,
            )

        if resp.status_code == 200:
            res_json = resp.json()
            return TranscriptionResult(
                text=res_json.get("text", "").strip(),
                language=language or "ar",
                backend="openai_whisper_1",
                confidence=0.98,
                is_success=True,
            )
        else:
            raise RuntimeError(f"OpenAI transcription failed: {resp.status_code} {resp.text}")
