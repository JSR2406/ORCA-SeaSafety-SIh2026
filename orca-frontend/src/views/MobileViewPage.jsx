'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import Icon from '../components/Icon';
import Badge from '../components/Badge';
import { transcribeAudioWithSarvam, synthesizeAudioWithSarvam } from '../services/apiClient';

export default function MobileViewPage() {
  const router = useRouter();
  const SAMPLE_QUERIES = [
    {
      q: 'നാളെ രാവിലെ മീൻപിടിക്കാൻ പോകാമോ?',
      a: 'നാളെ രാവിലെ കൊച്ചി തീരത്ത് കടൽസ്ഥിതി മിതമായ അപകടസാധ്യതയാണ്. തിരമാല ഉയരം 1.6–1.8 മീറ്റർ. Route B വഴി പോവുക.',
      tone: 'orange',
      badge: 'മിതമായ അപകടസാധ്യത'
    },
    {
      q: 'കൊച്ചി തീരത്ത് ഇന്നത്തെ തിരമാല എത്രയാണ്?',
      a: 'കൊച്ചി തീരത്ത് തിരമാല ഉയരം 1.4 മീറ്റർ ആണ്. ഉപരിതല കാറ്റ് 18 km/h ENE ദിശയിൽ വീശുന്നു.',
      tone: 'green',
      badge: 'സുരക്ഷിതമായ അവസ്ഥ'
    },
    {
      q: 'ഏറ്റവും അടുത്തുള്ള PFZ സോൺ എവിടെയാണ്?',
      a: 'ഏറ്റവും അടുത്തുള്ള PFZ-01 സോൺ കൊച്ചിയിൽ നിന്ന് 14.2 km തെക്കുപടിഞ്ഞാറ് സ്ഥിതിചെയ്യുന്നു. ചൂര, അയല ലഭ്യത പ്രതീക്ഷിക്കുന്നു.',
      tone: 'green',
      badge: 'PFZ-01 സജീവമാണ്'
    }
  ];

  const [activeVoice, setActiveVoice] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [showSosModal, setShowSosModal] = useState(false);
  const [sosCountdown, setSosCountdown] = useState(5);
  const [selectedPromptIndex, setSelectedPromptIndex] = useState(0);
  const [userSpokenText, setUserSpokenText] = useState(SAMPLE_QUERIES[0].q);

  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioPlayerRef = useRef(null);

  const activeAdvisory = SAMPLE_QUERIES[selectedPromptIndex] || SAMPLE_QUERIES[0];
  const malayalamAdvisory = activeAdvisory.a;

  // Browser Speech Synthesis fallback helper
  const fallbackSpeechSynthesis = (customText) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(customText || malayalamAdvisory);
    utterance.lang = 'ml-IN';
    utterance.rate = 0.9;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const malayalamVoice = voices.find((v) => v.lang.startsWith('ml') || v.name.toLowerCase().includes('india'));
    if (malayalamVoice) utterance.voice = malayalamVoice;

    utterance.onstart = () => setIsPlayingAudio(true);
    utterance.onend = () => setIsPlayingAudio(false);
    utterance.onerror = () => setIsPlayingAudio(false);

    window.speechSynthesis.speak(utterance);
  };

  // Sarvam AI Text-to-Speech (bulbul:v3) with Web Speech fallback
  const handlePlayMalayalamAudio = async (customText) => {
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

    setIsPlayingAudio(true);

    try {
      const textToSynthesize = customText || malayalamAdvisory;
      const ttsData = await synthesizeAudioWithSarvam(textToSynthesize, 'ml-IN', 'kavitha');
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
          fallbackSpeechSynthesis(customText);
        };
        await audio.play();
        return;
      }
    } catch (err) {
      console.warn('Sarvam TTS failed, falling back to Web Speech Synthesis:', err);
    }

    fallbackSpeechSynthesis(customText);
  };

  const handleSelectPrompt = (idx) => {
    setSelectedPromptIndex(idx);
    setUserSpokenText(SAMPLE_QUERIES[idx].q);
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    setIsPlayingAudio(false);
  };

  // Browser SpeechRecognition fallback helper
  const fallbackBrowserRecognition = () => {
    const SpeechRecognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);
    if (!SpeechRecognition) {
      setActiveVoice(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = 'ml-IN';
      recognition.continuous = false;
      recognition.interimResults = true;

      recognition.onstart = () => setActiveVoice(true);
      recognition.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map((r) => r[0].transcript)
          .join('');
        if (transcript) setUserSpokenText(transcript);
      };
      recognition.onend = () => setActiveVoice(false);
      recognition.onerror = () => setActiveVoice(false);

      recognition.start();
    } catch {
      setActiveVoice(false);
    }
  };

  // Sarvam AI Speech-to-Text (saaras:v3) with MediaRecorder
  const handleToggleMic = async () => {
    if (activeVoice && mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        setActiveVoice(false);
      }
      return;
    }

    if (activeVoice) {
      setActiveVoice(false);
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
          setActiveVoice(false);
          return;
        }

        setActiveVoice(false);
        setIsTranscribing(true);

        try {
          const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
          const res = await transcribeAudioWithSarvam(audioBlob, 'ml-IN');
          if (res?.transcript && res.transcript.trim()) {
            setUserSpokenText(res.transcript.trim());
          }
        } catch (err) {
          console.warn('Sarvam STT failed, falling back:', err);
          fallbackBrowserRecognition();
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start(200);
      setActiveVoice(true);
    } catch (err) {
      console.warn('Microphone permission denied, falling back:', err);
      fallbackBrowserRecognition();
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
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
    };
  }, []);

  const handleTriggerSos = () => {
    setShowSosModal(true);
    setSosCountdown(5);
  };

  return (
    <div className="mobile-demo-page">
      {/* Header Bar */}
      <header className="mobile-demo-header">
        <div className="demo-header-left">
          <button className="btn ghost btn-sm" onClick={() => router.push('/dashboard')}>
            <Icon name="ArrowLeft" size={14} />
            <span>Back to Dashboard</span>
          </button>
          <div className="demo-title-group">
            <span className="demo-eyebrow">SCREEN 16 • FIELD-HARDENED MOBILE EXPERIENCE</span>
            <h1>ORCA Fishermen Mobile PWA &amp; Offline Field Mode</h1>
          </div>
        </div>

        <div className="demo-header-right">
          <Badge tone="green" dot>PWA OFFLINE CAPABLE</Badge>
          <span className="demo-tag">Optimized for low-bandwidth 2G/3G &amp; high-glare sunlight</span>
        </div>
      </header>

      {/* 3 Smartphone Mockups Showcase */}
      <div className="phones-showcase-container">
        {/* Phone 1: High-Contrast Tactical Marine Dashboard */}
        <div className="phone-device-frame">
          <div className="phone-speaker-notch" />
          <div className="phone-screen-content">
            {/* Phone Top Status */}
            <div className="phone-status-bar">
              <span>09:41</span>
              <div className="phone-status-icons">
                <Icon name="Wifi" size={12} />
                <Icon name="Battery" size={12} />
              </div>
            </div>

            {/* Mobile App Bar */}
            <div className="phone-app-bar">
              <div className="phone-brand-mark">
                <b>ORCA</b>
                <span>KOCHI HARBOUR</span>
              </div>
              <Badge tone="green">LIVE GPS</Badge>
            </div>

            {/* High-Contrast Risk Alert Card */}
            <div className="phone-risk-hero-card">
              <span className="risk-eyebrow">SURFACE SAFETY INDEX</span>
              <div className="risk-large-headline text-caution">MODERATE</div>
              <p className="risk-brief">Sea conditions manageable with caution for vessels &lt; 15m.</p>
              <div className="phone-telemetry-mini-row">
                <div><span>SST:</span> <b>28.7°C</b></div>
                <div><span>Wave:</span> <b>1.4m</b></div>
                <div><span>Wind:</span> <b>18 km/h</b></div>
              </div>
            </div>

            {/* Mobile Tactical Mini-Map */}
            <div className="phone-mini-map-box">
              <div className="mini-map-overlay-pin">
                <span className="live-pulse" />
                <b>YOU (14km to Port)</b>
              </div>
            </div>

            {/* Harbor Return Direct CTA */}
            <button className="phone-action-btn primary" onClick={() => router.push('/routes')}>
              <Icon name="Navigation" size={14} />
              <span>Navigate Safe Return (Route B)</span>
            </button>

            {/* Phone Bottom Nav */}
            <div className="phone-bottom-nav">
              <button className="nav-tab-active" onClick={() => router.push('/dashboard')} title="Home"><Icon name="Home" size={16} /><span>Home</span></button>
              <button onClick={() => router.push('/marine-map')} title="Marine Map"><Icon name="Map" size={16} /><span>Map</span></button>
              <button onClick={() => router.push('/fishing')} title="Fishing PFZ"><Icon name="Fish" size={16} /><span>PFZ</span></button>
              <button onClick={() => router.push('/alerts')} title="Alerts"><Icon name="Bell" size={16} /><span>Alerts</span></button>
              <button onClick={() => router.push('/settings')} title="Settings"><Icon name="Menu" size={16} /><span>More</span></button>
            </div>
          </div>
        </div>

        {/* Phone 2: Voice-First AI Assistant (Vernacular) */}
        <div className="phone-device-frame">
          <div className="phone-speaker-notch" />
          <div className="phone-screen-content">
            <div className="phone-status-bar">
              <span>09:41</span>
              <div className="phone-status-icons">
                <Icon name="Wifi" size={12} />
                <Icon name="Battery" size={12} />
              </div>
            </div>

            <div className="phone-app-bar">
              <div className="phone-brand-mark">
                <b>Ask ORCA</b>
                <span>SARVAM AI VOICE</span>
              </div>
              <span className="lang-mini-badge">മലയാളം (saaras:v3)</span>
            </div>

            {/* Voice Wave Hero Box */}
            <div className="phone-voice-stage">
              <div
                className={`voice-mic-circle ${activeVoice ? 'pulsing' : ''} ${isTranscribing ? 'transcribing' : ''}`}
                onClick={handleToggleMic}
                title={isTranscribing ? "Transcribing with Sarvam AI (saaras:v3)..." : activeVoice ? "Tap to Stop & Transcribe" : "Tap Mic to Speak in Malayalam (Sarvam AI STT)"}
              >
                <Icon name={isTranscribing ? 'Sparkles' : 'Mic'} size={32} />
              </div>
              <span className="voice-prompt-state">
                {isTranscribing ? '⚡ Transcribing with Sarvam AI (saaras:v3)...' : activeVoice ? '🎙️ Recording coastal audio... Tap to stop' : 'Tap Mic to Speak in Malayalam'}
              </span>

              {/* Sample Quick Questions Selector */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', margin: '4px 0 8px 0', width: '100%' }}>
                <span style={{ fontSize: '10px', color: 'var(--c-text-muted, #94a3b8)', fontWeight: 600, textTransform: 'uppercase' }}>Quick Questions:</span>
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {SAMPLE_QUERIES.map((sq, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={() => handleSelectPrompt(i)}
                      style={{
                        fontSize: '11px',
                        padding: '3px 8px',
                        borderRadius: '12px',
                        background: selectedPromptIndex === i ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.05)',
                        border: selectedPromptIndex === i ? '1px solid var(--th-accent-cyan, #38bdf8)' : '1px solid rgba(255, 255, 255, 0.1)',
                        color: selectedPromptIndex === i ? 'var(--th-accent-cyan, #38bdf8)' : 'var(--c-text-primary, #fff)',
                        cursor: 'pointer',
                        textAlign: 'left'
                      }}
                    >
                      {i === 0 ? 'മീൻപിടുത്തം' : i === 1 ? 'തിരമാല' : 'PFZ സോൺ'}
                    </button>
                  ))}
                </div>
              </div>

              {/* Sample User Query Pill */}
              <div className="voice-user-bubble">
                <span>"{userSpokenText}"</span>
                <small>(Sarvam AI Transcribed Malayalam Input)</small>
              </div>

              {/* Voice Synthesized Output */}
              <div className="voice-response-card">
                <div className="voice-response-top">
                  <Badge tone={activeAdvisory.tone}>{activeAdvisory.badge}</Badge>
                  <button
                    className={`btn-audio-play ${isPlayingAudio ? 'active-playing' : ''}`}
                    onClick={() => handlePlayMalayalamAudio(malayalamAdvisory)}
                  >
                    <Icon name={isPlayingAudio ? 'Square' : 'Volume2'} size={14} />
                    <span>{isPlayingAudio ? 'Stop Audio' : '🔊 Play Audio (Sarvam AI bulbul:v3)'}</span>
                  </button>
                </div>
                <p className="voice-response-text">
                  {malayalamAdvisory}
                </p>
              </div>
            </div>

            <div className="phone-bottom-nav">
              <button onClick={() => router.push('/dashboard')} title="Home"><Icon name="Home" size={16} /><span>Home</span></button>
              <button onClick={() => router.push('/marine-map')} title="Marine Map"><Icon name="Map" size={16} /><span>Map</span></button>
              <button className="nav-tab-active"><Icon name="Mic" size={16} /><span>Voice</span></button>
              <button onClick={() => router.push('/alerts')} title="Alerts"><Icon name="Bell" size={16} /><span>Alerts</span></button>
              <button onClick={() => router.push('/settings')} title="Settings"><Icon name="Menu" size={16} /><span>More</span></button>
            </div>
          </div>
        </div>

        {/* Phone 3: Offline Emergency & Swell Alerts */}
        <div className="phone-device-frame">
          <div className="phone-speaker-notch" />
          <div className="phone-screen-content">
            <div className="phone-status-bar">
              <span>09:41</span>
              <div className="phone-status-icons">
                <Icon name="WifiOff" size={12} className="text-caution" />
                <Icon name="Battery" size={12} />
              </div>
            </div>

            <div className="phone-app-bar">
              <div className="phone-brand-mark">
                <b>Emergency Alerts</b>
                <span className="text-hazard">3 ACTIVE NOTICES</span>
              </div>
              <Badge tone="red">HIGH SWELL</Badge>
            </div>

            <div className="phone-alerts-feed">
              <div className="phone-alert-card border-red">
                <div className="alert-card-header">
                  <Icon name="AlertTriangle" size={15} className="text-hazard" />
                  <b>High Swell &amp; Wave Warning</b>
                </div>
                <p>Lakshadweep Sea • Waves 2.4m - 2.8m expected.</p>
                <div className="alert-card-meta">
                  <span>Valid until: 06 Sep 06:00 IST</span>
                  <b className="text-hazard">AVOID VOYAGE</b>
                </div>
              </div>

              <div className="phone-alert-card border-orange">
                <div className="alert-card-header">
                  <Icon name="Ban" size={15} className="text-caution" />
                  <b>Restricted Naval Exercise Box</b>
                </div>
                <p>12 km east of Kochi • Active until 18:00 IST.</p>
              </div>

              {/* Emergency SOS Dialer */}
              <div className="phone-sos-card">
                <Icon name="LifeBuoy" size={24} className="text-hazard" />
                <b>Coast Guard Emergency SOS</b>
                <span>Direct Distress Relay on VHF Ch 16</span>
                <button
                  className="phone-sos-btn"
                  onClick={handleTriggerSos}
                >
                  <Icon name="PhoneCall" size={16} />
                  <span>Broadcast Mayday / SOS</span>
                </button>
              </div>
            </div>

            <div className="phone-bottom-nav">
              <button onClick={() => router.push('/dashboard')} title="Home"><Icon name="Home" size={16} /><span>Home</span></button>
              <button onClick={() => router.push('/marine-map')} title="Marine Map"><Icon name="Map" size={16} /><span>Map</span></button>
              <button onClick={() => router.push('/fishing')} title="Fishing PFZ"><Icon name="Fish" size={16} /><span>PFZ</span></button>
              <button className="nav-tab-active" onClick={() => router.push('/alerts')} title="Alerts"><Icon name="Bell" size={16} /><span>Alerts</span></button>
              <button onClick={() => router.push('/settings')} title="Settings"><Icon name="Menu" size={16} /><span>More</span></button>
            </div>
          </div>
        </div>
      </div>

      {/* Real Emergency SOS Beacon Overlay Modal */}
      {showSosModal && (
        <div className="maritime-modal-overlay" onClick={() => setShowSosModal(false)}>
          <div className="maritime-modal-window sos-danger-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header-bar bg-danger-bar">
              <div className="modal-header-title">
                <Icon name="AlertTriangle" size={20} className="text-white" />
                <span>COAST GUARD MARITIME RESCUE COORDINATION (MRCC KOCHI)</span>
              </div>
              <button className="modal-close-btn" onClick={() => setShowSosModal(false)}>
                <Icon name="X" size={16} />
              </button>
            </div>

            <div className="modal-body-content">
              <div className="sos-emergency-box">
                <div className="sos-pulse-beacon">🚨</div>
                <h3>DISTRESS CALL BEACON ACTIVATED</h3>
                <p>Transmitting DSC Digital Selective Calling burst on <b>156.525 MHz (VHF Ch 70)</b> and <b>406 MHz COSPAS-SARSAT</b> satellite relay.</p>

                <div className="sos-coordinates-card">
                  <div className="sos-coord-row">
                    <span>VESSEL IDENTITY:</span>
                    <b>F/V Matsya-04 (MMSI: 419001248)</b>
                  </div>
                  <div className="sos-coord-row">
                    <span>GPS FIX:</span>
                    <code>09°58'24" N, 076°14'30" E</code>
                  </div>
                  <div className="sos-coord-row">
                    <span>DISTANCE TO KOCHI MRCC:</span>
                    <b>14.2 km (7.7 Nautical Miles)</b>
                  </div>
                  <div className="sos-coord-row">
                    <span>EMERGENCY FREQUENCIES:</span>
                    <b>VHF Ch 16 (Distress) • Toll-Free: 1554</b>
                  </div>
                </div>

                <div className="sos-contact-action-box">
                  <a href="tel:1554" className="btn btn-emergency-call">
                    <Icon name="PhoneCall" size={18} />
                    <span>Dial Coast Guard MRCC 1554 Now</span>
                  </a>
                  <button className="btn secondary" onClick={() => setShowSosModal(false)}>
                    Cancel Distress Broadcast
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
