# Voice Services Package
# Provider interfaces for STT, TTS, Translation

from abc import ABC, abstractmethod
from typing import Optional
from dataclasses import dataclass


@dataclass
class TranscriptResult:
    text: str
    language: str
    confidence: float
    duration_seconds: float


@dataclass
class NormalizedText:
    text: str
    source_language: str
    target_language: str
    intent: Optional[str] = None
    entities: Optional[dict] = None


@dataclass
class AudioResult:
    audio_bytes: bytes
    format: str
    duration_seconds: float
    sample_rate: int = 16000


class SpeechToTextProvider(ABC):
    """Interface for speech-to-text providers."""
    
    @abstractmethod
    async def transcribe(
        self, 
        audio_bytes: bytes, 
        language_hint: Optional[str] = None
    ) -> TranscriptResult:
        """Transcribe audio to text."""
        pass
    
    @abstractmethod
    async def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes."""
        pass


class TranslationProvider(ABC):
    """Interface for translation/normalization providers."""
    
    @abstractmethod
    async def normalize(
        self, 
        text: str, 
        source_language: str, 
        target_language: str = "en-IN"
    ) -> NormalizedText:
        """Normalize text to canonical intent."""
        pass


class TextToSpeechProvider(ABC):
    """Interface for text-to-speech providers."""
    
    @abstractmethod
    async def synthesize(
        self, 
        text: str, 
        language: str, 
        voice: Optional[str] = None
    ) -> AudioResult:
        """Synthesize text to audio."""
        pass
    
    @abstractmethod
    async def get_supported_voices(self, language: str) -> list[str]:
        """Get available voices for a language."""
        pass


# Provider registry
_providers = {
    "stt": {},
    "tts": {},
    "translation": {},
}


def register_stt_provider(name: str, provider: SpeechToTextProvider):
    _providers["stt"][name] = provider


def register_tts_provider(name: str, provider: TextToSpeechProvider):
    _providers["tts"][name] = provider


def register_translation_provider(name: str, provider: TranslationProvider):
    _providers["translation"][name] = provider


def get_stt_provider(name: str) -> SpeechToTextProvider:
    if name not in _providers["stt"]:
        raise ValueError(f"STT provider '{name}' not registered")
    return _providers["stt"][name]


def get_tts_provider(name: str) -> TextToSpeechProvider:
    if name not in _providers["tts"]:
        raise ValueError(f"TTS provider '{name}' not registered")
    return _providers["tts"][name]


def get_translation_provider(name: str) -> TranslationProvider:
    if name not in _providers["translation"]:
        raise ValueError(f"Translation provider '{name}' not registered")
    return _providers["translation"][name]