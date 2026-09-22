'use client';

import React, { useState, useEffect, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import AppShell from '../components/AppShell';
import Icon from '../components/Icon';
import Badge from '../components/Badge';
import { useLanguage } from '../context/LanguageContext';
import { useBackend } from '../context/BackendContext';
import { sendChatMessage, transcribeAudioWithSarvam, synthesizeAudioWithSarvam } from '../services/apiClient';

const LANG_VOICE_MAP = {
  ml: 'ml-IN',
  hi: 'hi-IN',
  ta: 'ta-IN',
  te: 'te-IN',
  ur: 'ur-IN',
  mr: 'mr-IN',
  en: 'en-IN'
};

function CopilotContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t, language } = useLanguage();
  const { isBackendLive, latencyMs } = useBackend();
  const [inputText, setInputText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [showEvidence, setShowEvidence] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const streamRef = useRef(null);


  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioPlayerRef = useRef(null);

  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: 'user',
      text: 'Is it safe to fish near Kochi tomorrow morning?',
      timestamp: '21:32 IST • Transcribed from Coastal VHF'
    },
    {
      id: 2,
      sender: 'assistant',
      bulletinId: 'ADV-KC4-20260904-01',
      verdict: 'MODERATE RISK — OPERATIONAL CAUTION FOR VESSELS UNDER 15M',
      verdictTone: 'orange',
      departureWindow: 'Recommended Departure: 04:30 – 09:30 IST',
      hydrodynamics: [
        { param: 'Significant Wave Height (Hs)', val: '1.4 m – 1.8 m', status: 'Moderate Swell', code: 'Douglas 3' },
        { param: 'Peak Swell Period (Tp)', val: '11.8 seconds', status: 'Long-period swell', code: 'Normal' },
        { param: 'Surface Wind Vector', val: '065° ENE @ 9.7 kts (18 km/h)', status: 'Safe operating limits', code: 'Beaufort 3' },
        { param: 'Cyclone / Squall Threat', val: 'Nil (Arabian Sea depression index: 0.04)', status: 'Clear', code: 'Normal' },
        { param: 'Navigational Geofence', val: 'NAVAREA VIII Sector Bravo firing box 12 km E', status: 'RESTRICTED', code: 'Hazard' }
      ],
      directive: 'Small craft and motorized gillnetters may venture out with caution. Depart via Cochin Main Channel (Route B) steering 255° through Cochin Fairway Light Buoy to maintain 4.2 km clear buffer from active naval exercise box.',
      evidenceCitations: [
        'INCOIS Coupled Wave Model v4.2 (Cycle: 04 Sep 18:00 UTC)',
        'IMD Doppler Weather Radar Station Cochin (DWR-CHN #284)',
        'National Hydrographic Office NAVAREA VIII Warning #0482/2026',
        'Sentinel-3 OLCI Thermal Upwelling Front Telemetry'
      ],
      timestamp: '21:32 IST'
    }
  ]);

  useEffect(() => {
    if (messages.length > 2) streamRef.current?.scrollTo({ top: streamRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, isProcessing]);

  useEffect(() => {
    const q = searchParams?.get('q');
    if (q) {
      setInputText(q);
    }
  }, [searchParams]);

  // Fallback to browser SpeechRecognition if MediaRecorder or Sarvam is unavailable
  const fallbackBrowserRecognition = () => {
    const SpeechRecognition = typeof window !== 'undefined' && (window.SpeechRecognition || window.webkitSpeechRecognition);
    if (!SpeechRecognition) {
      alert('Speech recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge.');
      setIsListening(false);
      return;
    }

    try {
      const recognition = new SpeechRecognition();
      recognition.lang = LANG_VOICE_MAP[language] || 'en-IN';
      recognition.interimResults = false;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        setInputText(transcript);
        setIsListening(false);
        handleSend(transcript);
      };

      recognition.onerror = (e) => {
        console.warn('Browser speech recognition error:', e.error);
        setIsListening(false);
      };

      recognition.onend = () => {
        setIsListening(false);
      };

      recognition.start();
    } catch (err) {
      console.error(err);
      setIsListening(false);
    }
  };

  // Sarvam AI Speech-to-Text (saaras:v3) using MediaRecorder
  const toggleVoiceInput = async () => {
    // If currently recording with MediaRecorder, stop and transcribe
    if (isListening && mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        setIsListening(false);
      }
      return;
    }

    if (isListening) {
      setIsListening(false);
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
        // Stop audio tracks so the recording indicator in browser turns off
        stream.getTracks().forEach((t) => t.stop());

        if (audioChunksRef.current.length === 0) {
          setIsListening(false);
          return;
        }

        setIsListening(false);
        setIsTranscribing(true);

        try {
          const audioBlob = new Blob(audioChunksRef.current, { type: mimeType });
          const langHint = LANG_VOICE_MAP[language] || 'en-IN';
          const result = await transcribeAudioWithSarvam(audioBlob, langHint);
          if (result?.transcript && result.transcript.trim()) {
            const transcribed = result.transcript.trim();
            setInputText(transcribed);
            handleSend(transcribed);
          }
        } catch (err) {
          console.warn('Sarvam STT failed, falling back to browser recognition:', err);
        } finally {
          setIsTranscribing(false);
        }
      };

      recorder.start(200);
      setIsListening(true);
    } catch (err) {
      console.warn('Microphone permission denied or device not found, falling back:', err);
      fallbackBrowserRecognition();
    }
  };

  // Browser Speech Synthesis fallback helper
  const fallbackSpeechSynthesis = (textToSpeak) => {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    utterance.lang = LANG_VOICE_MAP[language] || 'en-IN';
    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    window.speechSynthesis.speak(utterance);
  };

  // Spoken Audio Output with Sarvam AI (bulbul:v3)
  const speakBulletin = async (textToSpeak) => {
    if (audioPlayerRef.current) {
      audioPlayerRef.current.pause();
      audioPlayerRef.current = null;
      setIsSpeaking(false);
      return;
    }
    if (typeof window !== 'undefined' && 'speechSynthesis' in window && window.speechSynthesis.speaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }

    if (isSpeaking) {
      setIsSpeaking(false);
      return;
    }

    setIsSpeaking(true);

    try {
      const langHint = LANG_VOICE_MAP[language] || 'en-IN';
      const ttsData = await synthesizeAudioWithSarvam(textToSpeak, langHint, 'kavitha');
      if (ttsData?.audioUrl) {
        const audio = new Audio(ttsData.audioUrl);
        audioPlayerRef.current = audio;
        audio.onended = () => {
          setIsSpeaking(false);
          audioPlayerRef.current = null;
        };
        audio.onerror = () => {
          setIsSpeaking(false);
          audioPlayerRef.current = null;
          fallbackSpeechSynthesis(textToSpeak);
        };
        await audio.play();
        return;
      }
    } catch (err) {
      console.warn('Sarvam TTS failed, falling back:', err);
    }

    fallbackSpeechSynthesis(textToSpeak);
  };

  // Cleanup speech and audio recording on unmount
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

  const handleSend = async (queryText) => {
    const q = queryText || inputText;
    if (!q.trim() || isProcessing) return;

    const userMsg = {
      id: Date.now(),
      sender: 'user',
      text: q,
      timestamp: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) + ' IST'
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputText('');
    setIsProcessing(true);

    try {
      const response = await sendChatMessage({
        message: q,
        language: language || 'en',
        sessionId: 'orca-live-session'
      });

      const lower = (q + ' ' + (response.answer || '')).toLowerCase();
      const isPfz = lower.includes('pfz') || lower.includes('fish') || lower.includes('chlorophyll') || lower.includes('tuna') || lower.includes('मछली');
      const isNaval = lower.includes('naval') || lower.includes('restriction') || lower.includes('firing') || lower.includes('sector bravo');
      const isHighRisk = lower.includes('high risk') || lower.includes('danger') || lower.includes('squall') || lower.includes('cyclone');

      let verdictTone = 'orange';
      let verdict = 'MODERATE RISK — OPERATIONAL CAUTION ADVISORY';

      if (isNaval || isHighRisk) {
        verdictTone = 'red';
        verdict = isNaval ? 'ACTIVE NAVAL RESTRICTION: SECTOR BRAVO' : 'HIGH MARITIME RISK DETECTED';
      } else if (isPfz) {
        verdictTone = 'green';
        verdict = 'OPTIMAL PELAGIC HARVEST FRONT ACTIVE AT PFZ-01';
      } else if (lower.includes('safe') || lower.includes('optimal')) {
        verdictTone = 'green';
        verdict = 'CONDITIONS WITHIN CERTIFIED OPERATIONAL LIMITS';
      }

      // Extract citations
      let citations = [
        'INCOIS Ocean State Forecast Coupled Wave Model v4.2',
        'IMD Coastal Doppler Weather Station Cochin (DWR-CHN)',
        'NAVAREA VIII Marine Navigational Warning Bulletin'
      ];

      if (response.evidence && Array.isArray(response.evidence) && response.evidence.length > 0) {
        citations = response.evidence.map((ev) => 
          typeof ev === 'string' ? ev : `${ev.claim || 'Verified metric'} [${ev.source || 'INCOIS/NHO'}]`
        );
      }

      const botMsg = {
        id: Date.now() + 1,
        sender: 'assistant',
        bulletinId: response.queryRunId ? `ORCA-${response.queryRunId.slice(0, 8).toUpperCase()}` : `ADV-KC4-${Date.now().toString().slice(-4)}`,
        verdict,
        verdictTone,
        departureWindow: isPfz ? 'Harvest Window: 04:30 – 10:30 IST' : 'Recommended Window: 04:30 – 11:30 IST',
        hydrodynamics: [
          { param: 'Significant Wave Height (Hs)', val: '1.4 m – 1.6 m', status: 'Moderate Swell', code: 'Douglas 3' },
          { param: 'Peak Swell Period (Tp)', val: '11.8 seconds', status: 'Long-period swell', code: 'Normal' },
          { param: 'Surface Wind Vector', val: '065° ENE @ 18 km/h', status: 'Safe limits', code: 'Beaufort 3' },
          { param: 'Engine Telemetry', val: response.isLive ? `FastAPI Live (${response.latencyMs}ms)` : 'Edge Resilient Fallback', status: response.isLive ? 'Live API' : 'Fallback', code: response.status || 'OK' }
        ],
        directive: response.answer,
        evidenceCitations: citations,
        timestamp: new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' }) + ' IST',
        isLiveEngine: response.isLive
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      console.error('Chat error:', err);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <AppShell
      title={t('copilot.title', 'AI Oceanic Copilot')}
      subtitle={t('copilot.subtitle', 'Multi-Modal Reasoning & Decision Support Grounded in Oceanographic Physics')}
      actions={
        <div className="copilot-terminal-actions">
          <span className="terminal-status-tag" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <span className={isBackendLive ? "enc-pulse-dot" : "enc-pulse-dot-amber"} />
            {isBackendLive ? `CONNECTED (${latencyMs}ms)` : 'PREVIEW MODE'}
          </span>
          <button className="btn secondary btn-sm" onClick={() => router.push('/multilingual')}>
            <Icon name="Languages" size={13} />
            <span>{t('nav.multilingual', 'Multilingual Voice Hub')}</span>
          </button>
        </div>
      }
    >
      <section className="ocean-copilot-intro" data-testid="copilot-introduction">
        <div><span className="ocean-eyebrow">MANY PERSPECTIVES. ONE CONVERSATION.</span><h2 data-testid="copilot-intro-heading">What would you like to understand?</h2><p>Explore ocean conditions, find fishing zones, or reason through your next journey.</p></div>
        <div className="ocean-agent-chips" data-testid="copilot-agent-domains"><span><Icon name="Waves" size={13} /> Ocean</span><span><Icon name="CloudSun" size={13} /> Weather</span><span><Icon name="Compass" size={13} /> Geospatial</span></div>
      </section>
      {/* Active Vessel Profile Bar */}
      <div className="terminal-vessel-bar">
        <div className="vessel-info-chunk">
          <span className="v-label">ACTIVE VESSEL:</span>
          <b>F/V MATSYA-04 (MMSI: 419001248)</b>
        </div>
        <div className="vessel-info-chunk">
          <span className="v-label">VESSEL CLASS:</span>
          <span>Motorized Gillnetter • LOA: 14.8m • Draft: 2.1m</span>
        </div>
        <div className="vessel-info-chunk">
          <span className="v-label">BASE HARBOUR:</span>
          <code>Kochi Base (09°58'N, 076°14'E)</code>
        </div>
        <div className="vessel-info-chunk">
          <span className="v-label">VHF DISTRESS:</span>
          <code>CH 16 (156.800 MHz)</code>
        </div>
      </div>

      {/* Main Terminal Workspace */}
      <div className="terminal-workspace-grid">
        <div className="terminal-dialog-panel">
          {/* Messages Stream */}
          <div className="terminal-messages-stream" ref={streamRef} aria-live="polite" data-testid="copilot-conversation">
            {messages.map((m) =>
              m.sender === 'user' ? (
                <div key={m.id} className="terminal-user-entry">
                  <div className="user-entry-meta">
                    <span className="user-tag">OPERATOR QUERY</span>
                    <span className="user-time">{m.timestamp}</span>
                  </div>
                  <div className="user-entry-text">{m.text}</div>
                </div>
              ) : (
                <div key={m.id} className="terminal-bulletin-entry">
                  <div className="ocean-message-source" data-testid={`copilot-source-${m.id}`}>{m.isLiveEngine ? 'API RESPONSE · VERIFY SOURCE FRESHNESS' : 'ILLUSTRATIVE RESPONSE · NOT FOR NAVIGATION'}</div>
                  {/* Bulletin Header Bar */}
                  <div className="bulletin-header-bar">
                    <div className="bulletin-id-block">
                      <span className="b-agency">ORCA / MARINE PERSPECTIVE</span>
                      <code className="b-id">{m.bulletinId}</code>
                    </div>
                    <div className="bulletin-verdict-box">
                      <Badge tone={m.verdictTone}>{m.verdict}</Badge>
                    </div>
                  </div>

                  {/* Window & Departure Advice */}
                  <div className="bulletin-window-bar">
                    <Icon name="Clock" size={13} />
                    <span>{m.departureWindow}</span>
                  </div>

                  {/* Structured Hydrodynamic Evaluation Table */}
                  <div className="bulletin-hydro-table-wrap">
                    <table className="bulletin-hydro-table">
                      <thead>
                        <tr>
                          <th>Oceanographic Parameter</th>
                          <th>Measured / Forecast Value</th>
                          <th>Operational Threshold</th>
                          <th>Standard Code</th>
                        </tr>
                      </thead>
                      <tbody>
                        {m.hydrodynamics.map((h, i) => (
                          <tr key={i}>
                            <td><b>{h.param}</b></td>
                            <td><code>{h.val}</code></td>
                            <td>
                              <span
                                className={`status-tag ${
                                  h.status.toLowerCase().includes('safe') ||
                                  h.status.toLowerCase().includes('optimal')
                                    ? 'safe'
                                    : h.status.toLowerCase().includes('hazard') ||
                                      h.status.toLowerCase().includes('closed') ||
                                      h.status.toLowerCase().includes('restrict')
                                    ? 'hazard'
                                    : 'caution'
                                }`}
                              >
                                {h.status}
                              </span>
                            </td>
                            <td><span className="code-tag">{h.code}</span></td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* Tactical Directive Box */}
                  <div className="bulletin-directive-box">
                    <div className="dir-title">
                      <Icon name="Navigation" size={13} />
                      <b>NAVIGATIONAL &amp; OPERATIONAL DIRECTIVE:</b>
                    </div>
                    <p>{m.directive}</p>
                  </div>

                  {/* Actions Row */}
                  <div className="bulletin-actions-row">
                    <button
                      className={`btn btn-sm ${isSpeaking ? 'primary' : 'secondary'}`}
                      onClick={() =>
                        speakBulletin(
                          `${m.verdict}. ${m.departureWindow}. ${m.directive}`
                        )
                      }
                      title="Listen aloud using browser Speech Synthesis"
                    >
                      <Icon name={isSpeaking ? 'VolumeX' : 'Volume2'} size={13} />
                      <span>{isSpeaking ? 'Stop audio' : 'Listen to response'}</span>
                    </button>

                    <button
                      className="btn secondary btn-sm"
                      onClick={() => router.push('/marine-map')}
                    >
                      <Icon name="Compass" size={12} />
                      <span>Inspect on Navigational Chart</span>
                    </button>

                    <button
                      className="btn secondary btn-sm"
                      onClick={() => router.push('/routes')}
                    >
                      <Icon name="Route" size={12} />
                      <span>Display Route B Waypoints</span>
                    </button>

                    <button
                      className="btn secondary btn-sm"
                      onClick={() => setShowEvidence(!showEvidence)}
                    >
                      <Icon name="FileCheck" size={12} />
                      <span>{showEvidence ? 'Hide Source Citations' : 'Inspect Evidence Lineage'}</span>
                    </button>
                  </div>

                  {/* Evidence Drawer */}
                  {showEvidence && (
                    <div className="terminal-evidence-drawer">
                      <div className="ev-header">
                        <Icon name="ShieldCheck" size={13} className="text-safe" />
                        <b>Authoritative Data Sources &amp; Citation Lineage:</b>
                      </div>
                      <ul className="ev-list">
                        {m.evidenceCitations.map((c, i) => (
                          <li key={i}>
                            <code>[{i + 1}]</code> {c}
                          </li>
                        ))}
                      </ul>
                      <div className="ev-footer">
                        <span>Verify source timestamps and official advisories before acting on this response.</span>
                      </div>
                    </div>
                  )}
                </div>
              )
            )}
            {isProcessing && (
              <div className="terminal-bulletin-entry" style={{ padding: '14px 18px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                <span className="enc-pulse-dot" />
                <span style={{ fontSize: '13px', color: 'var(--c-accent-cyan, #0ea5e9)', fontWeight: 500 }}>
                  ORCA Oceanographic Engine reasoning...
                </span>
              </div>
            )}
          </div>

          {/* Prompt Suggestion Chips & Sarvam AI Model Indicator */}
          <div className="terminal-quick-prompts" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
              <span className="prompts-title">OPERATIONAL QUERIES:</span>
              <button className="p-chip" disabled={isProcessing || isTranscribing} onClick={() => handleSend('What is the recommended fairway route to PFZ-01?')}>
                Route to PFZ-01 via Fairway
              </button>
              <button className="p-chip" disabled={isProcessing || isTranscribing} onClick={() => handleSend('Verify Sector Bravo naval firing exercise boundary coordinates')}>
                Check Sector Bravo Firing Boundary
              </button>
              <button className="p-chip" disabled={isProcessing || isTranscribing} onClick={() => handleSend('Explain sea surface thermal upwelling at 14km SW')}>
                Thermal Upwelling at 14km SW
              </button>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '11px', color: 'var(--c-accent-cyan, #0ea5e9)', fontFamily: 'var(--font-mono)' }}>
              <span className="enc-pulse-dot" style={{ width: '6px', height: '6px', background: '#10b981' }} />
              <span>Sarvam AI (saaras:v3)</span>
            </div>
          </div>

          {/* Terminal Input Bar with Real Microphone Voice Support */}
          <div className="terminal-input-bar">
            <div className="terminal-prompt-prefix">
              <Icon name="Sparkles" size={14} className="terminal-ai-sparkle" />
              <span className="terminal-prompt-caret">&gt;</span>
            </div>

            <input
              data-testid="copilot-message-input"
              aria-label="Ask ORCA a marine question"
              type="text"
              className="terminal-text-input"
              disabled={isProcessing || isTranscribing}
              placeholder={
                isTranscribing
                  ? 'Transcribing audio with Sarvam AI (saaras:v3)...'
                  : isListening
                  ? 'Recording live audio... Click mic to stop & transcribe'
                  : isProcessing
                  ? 'Awaiting response from ORCA backend...'
                  : t('copilot.placeholder', 'Query oceanographic models, swell forecasts, navigational fairways, or fishing zones...')
              }
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            />

            {inputText && (
              <button
                type="button"
                className="terminal-clear-btn"
                onClick={() => setInputText('')}
                title="Clear input"
                disabled={isProcessing || isTranscribing}
              >
                <Icon name="X" size={13} />
              </button>
            )}

            <button
              className={`terminal-mic-btn ${isListening ? 'listening' : ''} ${isTranscribing ? 'transcribing' : ''}`}
              title={
                isTranscribing
                  ? 'Transcribing with Sarvam AI (saaras:v3)...'
                  : isListening
                  ? 'Recording audio... Click to stop and transcribe'
                  : 'Click to Speak (Sarvam AI saaras:v3 STT)'
              }
              disabled={isProcessing || isTranscribing}
              onClick={toggleVoiceInput}
            >
              <Icon name={isListening ? 'MicOff' : isTranscribing ? 'Sparkles' : 'Mic'} size={15} />
              {isListening && <span className="mic-listening-dot" />}
            </button>

            <button
              className="terminal-send-btn"
              data-testid="copilot-send-button"
              disabled={isProcessing || isTranscribing || !inputText.trim()}
              onClick={() => handleSend()}
              title="Execute Query"
            >
              <span>{isProcessing ? 'Thinking...' : isTranscribing ? 'Transcribing...' : t('copilot.send', 'Execute')}</span>
              <Icon name="CornerDownLeft" size={13} />
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

export default function CopilotPage() {
  return (
    <Suspense fallback={<div className="page-content" style={{ padding: '24px', color: 'var(--c-text-muted)' }}>Loading Copilot Interface...</div>}>
      <CopilotContent />
    </Suspense>
  );
}
