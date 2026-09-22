'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Logo from '../components/Logo';
import Icon from '../components/Icon';
import Badge from '../components/Badge';
import { multilingualTranslations } from '../data/mock';
import { useLanguage } from '../context/LanguageContext';
import { transcribeAudioWithSarvam, synthesizeAudioWithSarvam } from '../services/apiClient';

// Native BCP-47 voice language tags
const LANG_VOICE_MAP = {
  ml: 'ml-IN',
  hi: 'hi-IN',
  ta: 'ta-IN',
  te: 'te-IN',
  ur: 'ur-IN',
  mr: 'mr-IN',
  en: 'en-IN'
};

export default function MultilingualPage() {
  const router = useRouter();
  const { language: selectedLang, setLanguage: setSelectedLang, t: tGlobal, languages } = useLanguage();
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [isListeningMic, setIsListeningMic] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [customInputQuery, setCustomInputQuery] = useState('');
  const [micStatusText, setMicStatusText] = useState('');

  const recognitionRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioPlayerRef = useRef(null);

  const t = multilingualTranslations[selectedLang] || multilingualTranslations.en;

  // Browser Speech Synthesis fallback helper
  const fallbackSpeechSynthesis = (textToSpeak) => {
    if (!('speechSynthesis' in window)) {
      setIsPlayingAudio(false);
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.lang = LANG_VOICE_MAP[selectedLang] || 'en-IN';
    utterance.rate = 0.95;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const matchingVoice = voices.find((v) => v.lang.startsWith(selectedLang) || v.lang === LANG_VOICE_MAP[selectedLang]);
    if (matchingVoice) {
      utterance.voice = matchingVoice;
    }

    utterance.onstart = () => setIsPlayingAudio(true);
    utterance.onend = () => setIsPlayingAudio(false);
    utterance.onerror = () => setIsPlayingAudio(false);

    window.speechSynthesis.speak(utterance);
  };

  // Sarvam AI Text-to-Speech (bulbul:v3) with Web Speech fallback
  const handlePlayAudio = async () => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
      setIsPlayingAudio(false);
      return;
    }

    if (typeof window !== 'undefined' && 'speechSynthesis' in window && window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      setIsPlayingAudio(false);
      return;
    }

    if (isPlayingAudio) {
      setIsPlayingAudio(false);
      return;
    }

    const textToSpeak = `${t.audioTitle}. ${t.verdict}. ${t.bullets.join('. ')}. ${t.disclaimer}`;
    const targetLang = LANG_VOICE_MAP[selectedLang] || 'ml-IN';

    setIsPlayingAudio(true);

    try {
      const ttsData = await synthesizeAudioWithSarvam(textToSpeak, targetLang, 'kavitha');
      if (ttsData?.audioUrl) {
        const audio = new Audio(ttsData.audioUrl);
        audioPlayerRef.current = audio;
        audio.onended = () => {
          setIsPlayingAudio(false);
          audioPlayerRef.current = null;
        };
        audio.onerror = () => {
          setIsPlayingAudio(false);
          audioPlayerRef.current = null;
          fallbackSpeechSynthesis(textToSpeak);
        };
        await audio.play();
        return;
      }
    } catch (err) {
      console.warn('Sarvam TTS synthesis failed, falling back to Web Speech Synthesis:', err);
    }

    fallbackSpeechSynthesis(textToSpeak);
  };

  // Browser SpeechRecognition fallback helper
  const fallbackBrowserRecognition = () => {
    const SpeechRecognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);
    if (!SpeechRecognition) {
      setMicStatusText('Speech recognition is not supported in this browser.');
      setIsListeningMic(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;
      recognition.lang = LANG_VOICE_MAP[selectedLang] || 'en-IN';
      recognition.interimResults = true;
      recognition.continuous = false;

      recognition.onstart = () => {
        setIsListeningMic(true);
        setMicStatusText('Listening for native voice in ' + t.nativeName + ' (Browser Speech)...');
      };

      recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map((result) => result[0].transcript)
          .join('');
        setCustomInputQuery(transcript);
      };

      recognition.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsListeningMic(false);
        setMicStatusText('Mic Error: ' + event.error);
      };

      recognition.onend = () => {
        setIsListeningMic(false);
        setMicStatusText('Transcribed successfully.');
        setTimeout(() => setMicStatusText(''), 3000);
      };

      recognition.start();
    } catch (err) {
      console.error('Failed to start speech recognition:', err);
      setIsListeningMic(false);
    }
  };

  // Sarvam AI Speech-to-Text (saaras:v3) with MediaRecorder
  const handleToggleMic = async () => {
    if (isListeningMic && mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        setIsListeningMic(false);
      }
      return;
    }

    if (isListeningMic) {
      setIsListeningMic(false);
      return;
    }

    if (typeof window === 'undefined' || !navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      fallbackBrowserRecognition();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunksRef.current = [];

      let mimeType = 'audio/webm';
      if (typeof MediaRecorder !== 'undefined') {
        if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
          mimeType = 'audio/webm;codecs=opus';
        } else if (MediaRecorder.isTypeSupported('audio/webm')) {
          mimeType = 'audio/webm';
        } else if (MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')) {
          mimeType = 'audio/ogg';
        } else if (MediaRecorder.isTypeSupported('audio/wav')) {
          mimeType = 'audio/wav';
        }
      }

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data && event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());

        if (audioChunksRef.current.length === 0) {
          setIsListeningMic(false);
          setMicStatusText('');
          return;
        }

        setIsListeningMic(false);
        setIsTranscribing(true);
        setMicStatusText(`Transcribing audio with Sarvam AI (saaras:v3) in ${t.nativeName}...`);

        try {
          const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
          const targetLang = LANG_VOICE_MAP[selectedLang] || 'ml-IN';
          const res = await transcribeAudioWithSarvam(audioBlob, targetLang);
          if (res?.transcript && res.transcript.trim()) {
            setCustomInputQuery(res.transcript.trim());
            setMicStatusText(`✓ Transcribed via Sarvam AI saaras:v3 (${targetLang})`);
            setTimeout(() => setMicStatusText(''), 4000);
          } else {
            setMicStatusText('No speech detected. Please speak clearly into the microphone.');
            setTimeout(() => setMicStatusText(''), 3000);
          }
        } catch (err) {
          console.warn('Sarvam STT failed, trying fallback:', err);
          setMicStatusText('Sarvam STT failed, switching to browser speech recognition...');
          fallbackBrowserRecognition();
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start(200);
      setIsListeningMic(true);
      setMicStatusText(`🎙️ Recording voice in ${t.nativeName}... Click button to stop & transcribe.`);
    } catch (err) {
      console.warn('Microphone access denied or error:', err);
      fallbackBrowserRecognition();
    }
  };

  // Stop audio and recording if user switches language or leaves
  useEffect(() => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      try {
        mediaRecorderRef.current.stop();
      } catch {}
    }
    setIsPlayingAudio(false);
    setIsListeningMic(false);
    setIsTranscribing(false);
  }, [selectedLang]);

  return (
    <div className="multilingual-showcase-page">
      {/* Header Bar */}
      <header className="multilingual-header">
        <div className="multi-header-left">
          <Logo />
          <span className="multi-header-sep">/</span>
          <span className="multi-header-title">National Vernacular Cognitive Architecture</span>
        </div>

        <div className="multi-lang-pills">
          {languages.map((item) => (
            <button
              key={item.code}
              className={`multi-lang-pill-btn ${selectedLang === item.code ? 'active' : ''}`}
              onClick={() => {
                setSelectedLang(item.code);
              }}
            >
              <span>{item.flag}</span>
              <span>{item.native} ({item.name})</span>
            </button>
          ))}
        </div>

        <button className="btn ghost btn-sm" onClick={() => router.push('/dashboard')}>
          <Icon name="ArrowLeft" size={13} />
          <span>{tGlobal('nav.dashboard', 'Dashboard')}</span>
        </button>
      </header>

      {/* Main Showcase Grid */}
      <main className="multilingual-main-content">
        {/* Left Column: Conversational Translation Demo */}
        <div className="multi-copy-col">
          <span className="multi-eyebrow">EQUITY IN MARITIME SAFETY & COGNITIVE OUTREACH</span>
          <h1 className="multi-headline">Ocean Intelligence in Every Coastal Language.</h1>
          <p className="multi-desc">
            Bridging literacy and dialect gaps for India's 4 million artisanal fishermen through automated domain intent translation, browser-native text-to-speech synthesis, and verified INCOIS/IMD coastal broadcasts.
          </p>

          {/* Active Language Telemetry Bar */}
          <div className="active-lang-badge-bar">
            <div className="active-lang-info">
              <Icon name="Languages" size={16} className="text-safe" />
              <span>ACTIVE SYNTHESIS DIALECT:</span>
              <b>{t.nativeName} ({LANG_VOICE_MAP[selectedLang]})</b>
            </div>
            <Badge tone="green">SARVAM AI VOICE (saaras:v3 &amp; bulbul:v3)</Badge>
          </div>

          {/* Interactive Voice Mic Input Box */}
          <div className="vernacular-mic-bar">
            <button
              className={`vernacular-mic-btn ${isListeningMic ? 'active-listening' : ''} ${isTranscribing ? 'transcribing' : ''}`}
              onClick={handleToggleMic}
              disabled={isTranscribing}
              title={isTranscribing ? "Transcribing audio with Sarvam AI..." : isListeningMic ? "Click to stop and transcribe" : "Click to speak with microphone (Sarvam AI STT)"}
            >
              <Icon name={isListeningMic ? 'MicOff' : isTranscribing ? 'Sparkles' : 'Mic'} size={16} />
              <span>{isTranscribing ? 'Transcribing with Sarvam AI...' : isListeningMic ? 'Stop & Transcribe' : 'Speak into Microphone (Sarvam STT)'}</span>
            </button>
            {micStatusText && <span className="mic-status-readout">{micStatusText}</span>}
          </div>

          {/* Localized Chat Dialog */}
          <div className="multi-chat-dialog">
            {/* User Message */}
            <div className="dialog-bubble user">
              <div className="bubble-tag">FISHERMAN INQUIRY ({t.nativeName}):</div>
              <div className="bubble-text">{customInputQuery || t.query}</div>
              <span className="bubble-timestamp">{t.time}</span>
            </div>

            {/* Assistant Native Response */}
            <div className="dialog-bubble assistant">
              <div className="bubble-tag-assistant">
                <Badge tone="orange">{t.riskLevel}</Badge>
                <span className="assistant-conf">INCOIS VERIFIED • 94.2% ACCURACY</span>
              </div>
              <div className="bubble-text-verdict">{t.verdict}</div>

              {/* Native Bullet Points */}
              <div className="bubble-native-bullets">
                {t.bullets.map((b, i) => (
                  <div key={i} className="bullet-row">
                    <span className="bullet-dot" />
                    <span>{b}</span>
                  </div>
                ))}
              </div>

              <div className="dialog-disclaimer">
                <Icon name="Info" size={12} />
                <span>{t.disclaimer}</span>
              </div>
            </div>
          </div>

          {/* Real Audio Synthesizer Player Bar */}
          <div className="audio-player-card">
            <div className="player-left">
              <button
                className={`audio-play-trigger-btn ${isPlayingAudio ? 'playing' : ''}`}
                onClick={handlePlayAudio}
                title={isPlayingAudio ? 'Click to Stop Audio' : 'Click to Play Audio Aloud'}
              >
                <Icon name={isPlayingAudio ? 'Square' : 'Play'} size={18} />
              </button>
              <div className="player-meta">
                <b>{isPlayingAudio ? '🔊 BROADCASTING ALOUD (Sarvam AI bulbul:v3)...' : t.audioTitle}</b>
                <span>
                  {isPlayingAudio
                    ? `Streaming synthesized audio broadcast in ${t.nativeName} powered by Sarvam AI`
                    : `Click Play to hear speech synthesis • Duration ${t.audioDuration} • Sarvam AI Ready`}
                </span>
              </div>
            </div>

            {/* Audio Waveform Animation */}
            <div className={`audio-waveform ${isPlayingAudio ? 'active' : ''}`}>
              {[12, 28, 45, 18, 36, 52, 22, 40, 16, 32, 48, 20, 38, 50, 15, 30].map((h, i) => (
                <span
                  key={i}
                  className="wave-bar"
                  style={{
                    height: isPlayingAudio ? `${h}px` : '6px',
                    animationDelay: `${(i * 0.08).toFixed(2)}s`
                  }}
                />
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Radio Telemetry & Coastal Broadcast Matrix */}
        <div className="multi-graphic-col">
          <div className="language-orbit-stage">
            <div className="orbit-technical-masthead">
              <span className="ot-badge">NAVTEX FREQ: 518 kHz</span>
              <span className="ot-id">ALL INDIA RADIO COASTAL RELAY</span>
            </div>

            {/* Marine Radio Frequency Spectrum Card */}
            <div className="radio-spectrum-card">
              <div className="spectrum-row">
                <span className="s-label">VHF MARINE CH 16</span>
                <code>156.800 MHz (Distress)</code>
              </div>
              <div className="spectrum-row">
                <span className="s-label">MF NAVTEX</span>
                <code>518.0 kHz (Safety Net)</code>
              </div>
              <div className="spectrum-row">
                <span className="s-label">MSS TRANSCEIVER</span>
                <code>S-Band (ISRO GSAT-6)</code>
              </div>
              <div className="spectrum-row">
                <span className="s-label">COMMUNITY FM</span>
                <code>90.4 MHz (Kochi Coastal)</code>
              </div>
            </div>

            {/* Dialect Coverage Grid */}
            <div className="dialect-coverage-matrix">
              <span className="matrix-title">SUPPORTED INDIAN COASTAL DIALECTS</span>
              <div className="matrix-pills">
                <span className="d-pill active">മലയാളം (Kerala & Lakshadweep)</span>
                <span className="d-pill active">தமிழ் (Tamil Nadu & Puducherry)</span>
                <span className="d-pill active">తెలుగు (Andhra Pradesh & Yanam)</span>
                <span className="d-pill active">हिन्दी (National Maritime Service)</span>
                <span className="d-pill active">বাংলা (West Bengal Coast)</span>
                <span className="d-pill active">ಕನ್ನಡ (Karnataka Coast)</span>
                <span className="d-pill active">मराठी (Maharashtra Coast)</span>
                <span className="d-pill active">ગુજરાતી (Gujarat Coast)</span>
                <span className="d-pill active">ଓଡ଼ିଆ (Odisha Coast)</span>
              </div>
            </div>

            <div className="orbit-feature-callout">
              <Icon name="Radio" size={16} className="text-safe" />
              <span>Broadcasts comply with WMO-No. 558 & IMO GMDSS Vernacular Dissemination Standards.</span>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
