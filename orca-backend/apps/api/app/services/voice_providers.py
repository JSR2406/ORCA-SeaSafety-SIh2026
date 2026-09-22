# Voice Providers
# STT/TTS interfaces with Sarvam and ElevenLabs support

import asyncio
import base64
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Coastal Indian languages (10 languages)
COASTAL_LANGUAGES = [
    "en-IN",  # English (common)
    "hi-IN",  # Hindi (common across India)
    "ml-IN",  # Malayalam (Kerala coast)
    "ta-IN",  # Tamil (Tamil Nadu coast)
    "te-IN",  # Telugu (Andhra Pradesh coast)
    "bn-IN",  # Bengali (West Bengal coast)
    "gu-IN",  # Gujarati (Gujarat coast)
    "mr-IN",  # Marathi (Maharashtra coast)
    "or-IN",  # Odia (Odisha coast)
    "kn-IN",  # Kannada (Karnataka coast)
]

COASTAL_LANGUAGE_CODES = ["en", "hi", "ml", "ta", "te", "bn", "gu", "mr", "or", "kn"]

COASTAL_LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi",
    "ml": "Malayalam",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "gu": "Gujarati",
    "mr": "Marathi",
    "or": "Odia",
    "kn": "Kannada",
}


class STTProvider(ABC):
    """Abstract base class for Speech-to-Text providers."""

    @abstractmethod
    async def transcribe(
        self,
        audio_data: bytes,
        language: str,
        format: str = "wav",
    ) -> Dict[str, Any]:
        """Transcribe audio to text."""
        pass

    @abstractmethod
    async def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        pass

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Get provider health status."""
        pass


class TTSProvider(ABC):
    """Abstract base class for Text-to-Speech providers."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        language: str,
        voice: Optional[str] = None,
        format: str = "mp3",
    ) -> bytes:
        """Synthesize text to speech audio."""
        pass

    @abstractmethod
    async def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        pass

    @abstractmethod
    async def get_available_voices(self, language: str) -> List[Dict[str, Any]]:
        """Get available voices for a language."""
        pass

    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """Get provider health status."""
        pass


class TranslationProvider(ABC):
    """Abstract base class for translation providers."""

    @abstractmethod
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> str:
        """Translate text from source to target language."""
        pass

    @abstractmethod
    async def detect_language(self, text: str) -> str:
        """Detect language of text."""
        pass

    @abstractmethod
    async def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes."""
        pass


# --- Sarvam AI Provider ---

class SarvamSTTProvider(STTProvider):
    """Sarvam AI Speech-to-Text provider for Indian coastal languages."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.sarvam.ai"
        self._supported_languages = COASTAL_LANGUAGES

    async def transcribe(
        self,
        audio_data: bytes,
        language: str,
        format: str = "wav",
    ) -> Dict[str, Any]:
        """Transcribe audio using Sarvam AI speech-to-text."""
        url = f"{self.base_url}/speech-to-text"
        ext = "wav"
        if format in ("mp3", "mpeg"):
            ext = "mp3"
        elif format in ("webm",):
            ext = "webm"
        elif format in ("ogg",):
            ext = "ogg"

        files = {"file": (f"audio.{ext}", audio_data, self._mime(format))}
        lang_code = language if "-" in language else f"{language}-IN"
        data = {
            "model": "saaras:v3",
            "language_code": lang_code,
            "with_timestamps": "false",
        }
        headers = {"api-subscription-key": self.api_key}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, data=data, files=files)
        if resp.status_code >= 400:
            raise RuntimeError(f"Sarvam STT failed (HTTP {resp.status_code}): {resp.text[:300]}")
        payload = resp.json()
        transcript = payload.get("transcript")
        # Sarvam returns transcript as a string (newer) or a list of {text, timestamps}.
        if isinstance(transcript, str):
            text = transcript.strip()
        elif isinstance(transcript, list):
            text = " ".join(
                t.get("text", "").strip() for t in transcript
                if isinstance(t, dict) and t.get("text")
            ).strip()
        else:
            text = ""
        return {
            "text": text,
            "language": payload.get("language_code", language),
            "confidence": 0.95,
            "duration_ms": 0,
        }

    @staticmethod
    def _mime(fmt: str) -> str:
        return {
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "webm": "audio/webm",
            "ogg": "audio/ogg",
        }.get(fmt, "audio/wav")

    async def get_supported_languages(self) -> List[str]:
        return self._supported_languages

    async def get_status(self) -> Dict[str, Any]:
        return {
            "provider": "sarvam",
            "status": "configured" if self.api_key else "not_configured",
            "supported_languages": len(self._supported_languages),
            "latency_ms": 50,
        }


class SarvamTTSProvider(TTSProvider):
    """Sarvam AI Text-to-Speech provider for Indian coastal languages."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.sarvam.ai"
        self._supported_languages = COASTAL_LANGUAGES

    async def synthesize(
        self,
        text: str,
        language: str,
        voice: Optional[str] = None,
        format: str = "mp3",
    ) -> bytes:
        """Synthesize speech using Sarvam AI text-to-speech."""
        url = f"{self.base_url}/text-to-speech"
        lang_code = language if "-" in language else f"{language}-IN"
        body = {
            "inputs": [text],
            "target_language_code": lang_code,
            "speaker": voice or "kavitha",
            "pitch": 0,
            "pace": 1.0,
            "loudness": 1.5,
            "speech_sample_rate": 8000,
            "enable_preprocessing": True,
            "model": "bulbul:v3",
        }
        headers = {
            "api-subscription-key": self.api_key,
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"Sarvam TTS failed (HTTP {resp.status_code}): {resp.text[:300]}")
        payload = resp.json()
        audios = payload.get("audios")
        if not audios or not isinstance(audios, list) or len(audios) == 0:
            raise RuntimeError(f"Sarvam TTS returned no audio: {payload}")
        return base64.b64decode(audios[0])

    async def get_supported_languages(self) -> List[str]:
        return self._supported_languages

    async def get_available_voices(self, language: str) -> List[Dict[str, Any]]:
        return [{"id": f"{language}_default", "name": f"{COASTAL_LANGUAGE_NAMES.get(language.split('-')[0], language)} Default", "gender": "female"}]

    async def get_status(self) -> Dict[str, Any]:
        return {
            "provider": "sarvam",
            "status": "configured" if self.api_key else "not_configured",
            "supported_languages": len(self._supported_languages),
            "latency_ms": 80,
        }


# --- ElevenLabs Provider ---

class ElevenLabsTTSProvider(TTSProvider):
    """ElevenLabs Text-to-Speech provider for high-quality voices."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        self._supported_languages = COASTAL_LANGUAGES

    async def synthesize(
        self,
        text: str,
        language: str,
        voice: Optional[str] = None,
        format: str = "mp3",
    ) -> bytes:
        """Synthesize speech using ElevenLabs."""
        # ElevenLabs: POST /v1/text-to-speech/{voice_id} returns raw audio bytes.
        voice_id = voice or "21m00Tcm4TlvDq8ikWAM"  # Rachel - multi-language default
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        body = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.6},
            "output_format": format if format in ("mp3", "pcm", "ulaw") else "mp3",
        }
        headers = {"xi-api-key": self.api_key, "Accept": "audio/mpeg"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"ElevenLabs TTS failed (HTTP {resp.status_code}): {resp.text[:300]}")
        return resp.content

    async def get_supported_languages(self) -> List[str]:
        return self._supported_languages

    async def get_available_voices(self, language: str) -> List[Dict[str, Any]]:
        return [{"id": f"{language}_default", "name": f"{COASTAL_LANGUAGE_NAMES.get(language.split('-')[0], language)} Premium", "gender": "neutral"}]

    async def get_status(self) -> Dict[str, Any]:
        return {
            "provider": "elevenlabs",
            "status": "configured" if self.api_key else "not_configured",
            "supported_languages": len(self._supported_languages),
            "latency_ms": 120,
        }


# --- Google Translation Provider ---

class GoogleTranslationProvider(TranslationProvider):
    """Google Cloud Translation provider for multilingual support."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://translation.googleapis.com/language/translate/v2"
        self._supported_languages = COASTAL_LANGUAGE_CODES

    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> str:
        """Translate text using Google Cloud Translation (v2)."""
        url = f"{self.base_url}?key={self.api_key}"
        body = {"q": text, "source": source_lang.split("-")[0], "target": target_lang.split("-")[0]}
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=body)
        if resp.status_code >= 400:
            raise RuntimeError(f"Google Translation failed (HTTP {resp.status_code}): {resp.text[:300]}")
        payload = resp.json()
        try:
            return payload["data"]["translations"][0]["translatedText"]
        except (KeyError, IndexError, TypeError):
            raise RuntimeError(f"Google Translation returned unexpected payload: {payload}")

    async def detect_language(self, text: str) -> str:
        """Detect language of text using script detection."""
        for char in text:
            if "\u0900" <= char <= "\u097F":  # Devanagari (Hindi, Marathi)
                return "hi-IN"
            elif "\u0D00" <= char <= "\u0D7F":  # Malayalam
                return "ml-IN"
            elif "\u0B80" <= char <= "\u0BFF":  # Tamil
                return "ta-IN"
            elif "\u0C00" <= char <= "\u0C7F":  # Telugu
                return "te-IN"
            elif "\u0980" <= char <= "\u09FF":  # Bengali
                return "bn-IN"
            elif "\u0A80" <= char <= "\u0AFF":  # Gujarati
                return "gu-IN"
            elif "\u0B00" <= char <= "\u0B7F":  # Odia
                return "or-IN"
            elif "\u0C80" <= char <= "\u0CFF":  # Kannada
                return "kn-IN"
        return "en-IN"

    async def get_supported_languages(self) -> List[str]:
        return self._supported_languages

    async def get_status(self) -> Dict[str, Any]:
        return {
            "provider": "google_translate",
            "status": "configured" if self.api_key else "not_configured",
            "supported_languages": len(self._supported_languages),
            "latency_ms": 30,
        }


# --- Provider Factory ---

class VoiceProviderFactory:
    """Factory for creating voice provider instances."""

    def __init__(self):
        self._stt_providers: Dict[str, STTProvider] = {}
        self._tts_providers: Dict[str, TTSProvider] = {}
        self._translation_providers: Dict[str, TranslationProvider] = {}

    def register_stt(self, name: str, provider: STTProvider):
        self._stt_providers[name] = provider

    def register_tts(self, name: str, provider: TTSProvider):
        self._tts_providers[name] = provider

    def register_translation(self, name: str, provider: TranslationProvider):
        self._translation_providers[name] = provider

    def get_stt(self, name: str = "sarvam") -> STTProvider:
        return self._stt_providers.get(name, self._stt_providers.get("sarvam"))

    def get_tts(self, name: str = "elevenlabs") -> TTSProvider:
        return self._tts_providers.get(name, self._tts_providers.get("elevenlabs"))

    def get_translation(self, name: str = "google") -> TranslationProvider:
        return self._translation_providers.get(name, self._translation_providers.get("google"))

    async def get_all_status(self) -> Dict[str, Any]:
        return {
            "stt": {name: await p.get_status() for name, p in self._stt_providers.items()},
            "tts": {name: await p.get_status() for name, p in self._tts_providers.items()},
            "translation": {name: await p.get_status() for name, p in self._translation_providers.items()},
        }


# Global factory instance
_voice_factory: Optional[VoiceProviderFactory] = None


async def get_voice_factory() -> VoiceProviderFactory:
    global _voice_factory
    if _voice_factory is None:
        _voice_factory = VoiceProviderFactory()
        from app.config import settings
        _voice_factory.register_stt("sarvam", SarvamSTTProvider(settings.stt_api_key))
        _voice_factory.register_tts("elevenlabs", ElevenLabsTTSProvider(settings.tts_api_key))
        _voice_factory.register_tts("sarvam", SarvamTTSProvider(settings.stt_api_key))
        _voice_factory.register_translation("google", GoogleTranslationProvider(settings.translation_api_key))
    return _voice_factory