'use client';

import React, { useState, useEffect, useMemo, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import Icon from '../components/Icon';
import { alerts as mockAlerts } from '../data/mock';
import { useLanguage } from '../context/LanguageContext';
import {
  getHazards,
  createBackendAlert,
  acknowledgeBackendAlert,
  synthesizeAudioWithSarvam
} from '../services/apiClient';

const LEVEL_WORDS = {
  HIGH: { word: 'Serious', tone: 'avoid', icon: 'AlertOctagon' },
  MEDIUM: { word: 'Be careful', tone: 'caution', icon: 'AlertTriangle' },
  LOW: { word: 'For information', tone: 'good', icon: 'Info' },
  INFO: { word: 'For information', tone: 'good', icon: 'Info' }
};

// "15 min ago" / "3 hours ago" / "Just now" / date string -> minutes old, for newest-first sorting.
function minutesOld(time) {
  if (!time) return 1e9;
  const value = String(time).toLowerCase().trim();
  if (value === 'just now' || value === 'active') return 0;
  const match = value.match(/^(\d+)\s*(min|minute|hour|hr|day)/);
  if (match) {
    const amount = parseInt(match[1], 10);
    if (match[2].startsWith('min')) return amount;
    if (match[2].startsWith('h')) return amount * 60;
    return amount * 1440;
  }
  const parsed = Date.parse(time);
  if (!Number.isNaN(parsed)) return Math.max(0, (Date.now() - parsed) / 60000);
  return 1e9;
}

export default function AlertsCenterPage() {
  const router = useRouter();
  const { t, language } = useLanguage();

  const [alertsList, setAlertsList] = useState(mockAlerts);
  const [readAlerts, setReadAlerts] = useState({});
  const [isLive, setIsLive] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastSyncTime, setLastSyncTime] = useState('Just now');

  const [searchQuery, setSearchQuery] = useState('');
  const [filter, setFilter] = useState('ALL'); // 'ALL' | 'SERIOUS' | 'UNREAD'
  const [expandedId, setExpandedId] = useState(null);
  const [showTools, setShowTools] = useState(false);

  const [currentlySpeakingId, setCurrentlySpeakingId] = useState(null);
  const audioElementRef = useRef(null);
  const [toasts, setToasts] = useState([]);

  // Notice composer (kept for harbour authorities, tucked away under tools)
  const [isCreateNoticeModalOpen, setIsCreateNoticeModalOpen] = useState(false);
  const [newNoticeTitle, setNewNoticeTitle] = useState('');
  const [newNoticeDesc, setNewNoticeDesc] = useState('');
  const [newNoticeSeverity, setNewNoticeSeverity] = useState('MEDIUM');
  const [newNoticeSector, setNewNoticeSector] = useState('Kochi fairway and approaches');
  const [newNoticeDirective, setNewNoticeDirective] = useState('');

  const showToast = useCallback((message, type = 'success') => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(item => item.id !== id)), 4000);
  }, []);

  const loadAlerts = useCallback(async (manual = false) => {
    if (manual) setIsRefreshing(true);
    try {
      const res = await getHazards();
      if (res?.hazards?.length) {
        setAlertsList(res.hazards);
        setIsLive(Boolean(res.isLive));
        const nextRead = {};
        res.hazards.forEach(h => { if (h.status === 'acknowledged') nextRead[h.id] = true; });
        setReadAlerts(prev => ({ ...prev, ...nextRead }));
        setLastSyncTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
        if (manual) showToast(t('plain.alertsUpdated', 'Warnings updated'), 'success');
      }
    } catch {
      if (manual) showToast(t('plain.alertsOffline', 'You are offline · showing saved warnings'), 'warning');
    } finally {
      if (manual) setIsRefreshing(false);
    }
  }, [showToast, t]);

  useEffect(() => { loadAlerts(); }, [loadAlerts]);

  const parseCoordinates = (item) => {
    if (item.lat && (item.lon || item.lng)) return { lat: item.lat, lon: item.lon || item.lng };
    if (item.coordinates) {
      const match = item.coordinates.match(/([0-9]+\.?[0-9]*)[°\s]*([0-9]+\.?[0-9]*)?'?[NSns]?[\s,]+([0-9]+\.?[0-9]*)[°\s]*([0-9]+\.?[0-9]*)?'?[EWew]?/);
      if (match) {
        return {
          lat: parseFloat(match[1]) + (parseFloat(match[2] || 0) / 60),
          lon: parseFloat(match[3]) + (parseFloat(match[4] || 0) / 60)
        };
      }
    }
    return { lat: 9.9667, lon: 76.165 };
  };

  const handlePlotOnMap = (item) => {
    const coords = parseCoordinates(item);
    router.push(`/marine-map?lat=${coords.lat.toFixed(4)}&lng=${coords.lon.toFixed(4)}&zoom=13&name=${encodeURIComponent(item.title)}`);
  };

  const toggleAcknowledge = async (item) => {
    const next = !readAlerts[item.id];
    setReadAlerts(prev => ({ ...prev, [item.id]: next }));
    showToast(next ? 'Marked as read' : 'Moved back to unread', next ? 'success' : 'warning');
    if (next) {
      try { await acknowledgeBackendAlert(item.id); } catch {}
    }
  };

  const markAllRead = () => {
    const next = {};
    alertsList.forEach(a => { next[a.id] = true; });
    setReadAlerts(next);
    showToast('All warnings marked as read', 'success');
  };

  const handleSpeakAlert = (item) => {
    const stop = () => {
      if (audioElementRef.current) { audioElementRef.current.pause(); audioElementRef.current = null; }
      if (typeof window !== 'undefined' && window.speechSynthesis) window.speechSynthesis.cancel();
    };

    if (currentlySpeakingId === item.id) { stop(); setCurrentlySpeakingId(null); return; }
    stop();
    setCurrentlySpeakingId(item.id);

    const speechText = `${item.title}. What to do: ${item.actionRequired}. Area: ${item.place}. Valid until ${item.validTill}.`;
    const langMap = { ml: 'ml-IN', ta: 'ta-IN', hi: 'hi-IN', mr: 'mr-IN', te: 'te-IN', bn: 'bn-IN', en: 'en-IN' };
    const speechLang = langMap[language] || 'en-IN';

    const fallbackBrowserSpeech = () => {
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        const utterance = new SpeechSynthesisUtterance(speechText);
        utterance.lang = speechLang;
        utterance.rate = 0.95;
        utterance.onend = () => setCurrentlySpeakingId(null);
        utterance.onerror = () => setCurrentlySpeakingId(null);
        window.speechSynthesis.speak(utterance);
      } else {
        setCurrentlySpeakingId(null);
      }
    };

    synthesizeAudioWithSarvam(speechText, speechLang)
      .then(res => {
        if (res?.audioUrl) {
          const audio = new Audio(res.audioUrl);
          audioElementRef.current = audio;
          audio.onended = () => setCurrentlySpeakingId(null);
          audio.onerror = fallbackBrowserSpeech;
          audio.play().catch(fallbackBrowserSpeech);
        } else {
          fallbackBrowserSpeech();
        }
      })
      .catch(fallbackBrowserSpeech);
  };

  const handleCreateNoticeSubmit = async (e) => {
    e.preventDefault();
    if (!newNoticeTitle.trim()) return;

    const noticeItem = {
      id: `ALT-NOTICE-${Date.now().toString().slice(-4)}`,
      title: newNoticeTitle.trim(),
      place: newNoticeSector.trim() || 'Coastal operating area',
      time: 'Just now',
      level: newNoticeSeverity,
      category: 'Safety',
      source: 'Port authority harbour master',
      validTill: '48 hours',
      desc: newNoticeDesc.trim() || 'General advisory issued for vessels in this area.',
      coordinates: "09°58'N, 076°16'E",
      lat: 9.9667,
      lon: 76.165,
      actionRequired: newNoticeDirective.trim() || 'Take extra care and keep your radio on.',
      isLive: true,
      status: 'active'
    };

    setAlertsList(prev => [noticeItem, ...prev]);
    setIsCreateNoticeModalOpen(false);
    setNewNoticeTitle('');
    setNewNoticeDesc('');
    setNewNoticeDirective('');
    showToast('Notice published to the warning list', 'success');
    try { await createBackendAlert(noticeItem); } catch {}
  };

  const sortedAlerts = useMemo(
    () => [...alertsList].sort((a, b) => minutesOld(a.time) - minutesOld(b.time)),
    [alertsList]
  );

  const visibleAlerts = useMemo(() => sortedAlerts.filter(item => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const haystack = `${item.title || ''} ${item.desc || ''} ${item.place || ''} ${item.actionRequired || ''} ${item.id || ''}`.toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    if (filter === 'SERIOUS' && item.level !== 'HIGH') return false;
    if (filter === 'UNREAD' && readAlerts[item.id]) return false;
    return true;
  }), [sortedAlerts, searchQuery, filter, readAlerts]);

  const unreadCount = sortedAlerts.filter(a => !readAlerts[a.id]).length;
  const seriousUnread = sortedAlerts.filter(a => a.level === 'HIGH' && !readAlerts[a.id]).length;
  const newest = sortedAlerts[0];

  const summary = seriousUnread > 0
    ? {
        tone: 'avoid',
        icon: 'AlertOctagon',
        headline: `${seriousUnread} serious warning${seriousUnread > 1 ? 's' : ''} right now`,
        line: newest ? `${newest.title} — ${newest.actionRequired}` : 'Read the warnings below before you leave the shore.'
      }
    : unreadCount > 0
      ? {
          tone: 'caution',
          icon: 'AlertTriangle',
          headline: `${unreadCount} warning${unreadCount > 1 ? 's' : ''} to read`,
          line: newest ? `${newest.title} — ${newest.actionRequired}` : 'Nothing serious, but read the notices below.'
        }
      : {
          tone: 'good',
          icon: 'CheckCircle2',
          headline: 'Nothing urgent for your area',
          line: 'You have read every warning currently in force. We will tell you when a new one arrives.'
        };

  return (
    <AppShell>
      <div className="simple-dash" data-testid="alerts-simple">
        <div className="simple-head">
          <div>
            <span className="ocean-eyebrow" data-testid="alerts-eyebrow">MARINE WARNINGS</span>
            <h1 data-testid="alerts-heading">{t('plain.alertsTitle', 'What to watch out for')}</h1>
            <p>
              {isLive ? `Newest first · updated ${lastSyncTime}` : 'Newest first · sample warnings, not for navigation'}
            </p>
          </div>
          <div className="simple-head-actions">
            <button
              type="button"
              className="pill-badge-btn"
              onClick={() => loadAlerts(true)}
              disabled={isRefreshing}
              data-testid="alerts-refresh-button"
            >
              <Icon name="RefreshCw" size={13} className={isRefreshing ? 'spin-icon' : ''} />
              <span>{isRefreshing ? t('plain.alertsUpdating', 'Updating…') : t('plain.alertsUpdate', 'Update')}</span>
            </button>
            <button
              type="button"
              className="pill-badge-btn"
              onClick={markAllRead}
              data-testid="alerts-mark-all-button"
            >
              <Icon name="CheckCheck" size={13} />
              <span>{t('plain.alertsMarkAll', 'Mark all read')}</span>
            </button>
          </div>
        </div>

        <section className="simple-verdict" data-tone={summary.tone} data-testid="alerts-summary">
          <div className="verdict-mark"><Icon name={summary.icon} size={26} strokeWidth={1.8} /></div>
          <div className="verdict-body">
            <span className="verdict-kicker">Right now</span>
            <h2 data-testid="alerts-summary-headline">{summary.headline}</h2>
            <p data-testid="alerts-summary-line">{summary.line}</p>
          </div>
        </section>

        <div className="simple-card" data-testid="alerts-list-panel">
          <div className="simple-card-head">
            <div>
              <h3>Warnings for your coast</h3>
              <p>{visibleAlerts.length} shown{visibleAlerts.length !== sortedAlerts.length ? ` of ${sortedAlerts.length}` : ''}</p>
            </div>
            <div className="simple-chips">
              {[
                { key: 'ALL', label: 'All' },
                { key: 'SERIOUS', label: 'Serious only' },
                { key: 'UNREAD', label: `Unread (${unreadCount})` }
              ].map(chip => (
                <button
                  key={chip.key}
                  type="button"
                  className={`simple-chip ${filter === chip.key ? 'active' : ''}`}
                  onClick={() => setFilter(chip.key)}
                  aria-pressed={filter === chip.key}
                  data-testid={`alerts-filter-${chip.key.toLowerCase()}`}
                >
                  {chip.label}
                </button>
              ))}
            </div>
          </div>

          <div className="simple-ask" style={{ marginBottom: '16px' }}>
            <Icon name="Search" size={15} style={{ color: 'var(--c-text-muted)' }} />
            <input
              type="text"
              data-testid="alerts-search-input"
              aria-label="Search warnings"
              placeholder={t('plain.alertsSearch', 'Search by place or keyword…')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button type="button" className="pill-badge-btn" onClick={() => setSearchQuery('')} data-testid="alerts-search-clear">
                <Icon name="X" size={13} />
              </button>
            )}
          </div>

          {visibleAlerts.length === 0 ? (
            <div className="alert-empty" data-testid="alerts-empty-state">
              <Icon name="CheckCircle2" size={30} style={{ color: 'var(--c-safe, #10b981)' }} />
              <b>Nothing to show here</b>
              <p>Try another search, or go back to all warnings.</p>
              <button
                type="button"
                className="btn secondary"
                onClick={() => { setSearchQuery(''); setFilter('ALL'); }}
                data-testid="alerts-reset-button"
              >
                <Icon name="RotateCcw" size={13} /> <span>Show all warnings</span>
              </button>
            </div>
          ) : (
            <div className="alert-feed">
              {visibleAlerts.map((item, idx) => {
                const level = LEVEL_WORDS[item.level] || LEVEL_WORDS.LOW;
                const isRead = !!readAlerts[item.id];
                const isSpeaking = currentlySpeakingId === item.id;
                const isOpen = expandedId === item.id;

                return (
                  <article
                    key={item.id}
                    className="alert-item"
                    data-tone={level.tone}
                    data-read={isRead ? 'true' : 'false'}
                    data-testid={`alert-item-${idx}`}
                  >
                    <div className="alert-item-top">
                      <span className="alert-level-tag" data-tone={level.tone}>
                        <Icon name={level.icon} size={12} />
                        <span>{level.word}</span>
                      </span>
                      <span className="alert-time">{idx === 0 ? `Newest · ${item.time}` : item.time}</span>
                    </div>

                    <h4 data-testid={`alert-title-${idx}`}>{item.title}</h4>
                    <p className="alert-place"><Icon name="MapPin" size={12} /> {item.place}</p>
                    <p className="alert-desc">{item.desc}</p>

                    <div className="alert-todo" data-tone={level.tone}>
                      <span>What to do</span>
                      <b>{item.actionRequired}</b>
                    </div>

                    <div className="alert-actions">
                      <button
                        type="button"
                        className="btn secondary btn-sm"
                        onClick={() => handleSpeakAlert(item)}
                        data-testid={`alert-listen-${idx}`}
                      >
                        <Icon name={isSpeaking ? 'Square' : 'Volume2'} size={12} />
                        <span>{isSpeaking ? t('plain.alertsStop', 'Stop') : t('plain.alertsListen', 'Listen')}</span>
                      </button>
                      <button
                        type="button"
                        className="btn secondary btn-sm"
                        onClick={() => handlePlotOnMap(item)}
                        data-testid={`alert-map-${idx}`}
                      >
                        <Icon name="Map" size={12} />
                        <span>{t('plain.alertsOnMap', 'Show on map')}</span>
                      </button>
                      <button
                        type="button"
                        className="btn secondary btn-sm"
                        onClick={() => router.push(`/ai-copilot?q=${encodeURIComponent(`What does ${item.title} near ${item.place} mean for a small boat today?`)}`)}
                        data-testid={`alert-ask-${idx}`}
                      >
                        <Icon name="Bot" size={12} />
                        <span>Ask ORCA</span>
                      </button>
                      <button
                        type="button"
                        className="btn secondary btn-sm"
                        onClick={() => toggleAcknowledge(item)}
                        data-testid={`alert-ack-${idx}`}
                      >
                        <Icon name={isRead ? 'RotateCcw' : 'Check'} size={12} />
                        <span>{isRead ? 'Unread' : 'Mark read'}</span>
                      </button>
                      <button
                        type="button"
                        className="btn ghost btn-sm"
                        onClick={() => setExpandedId(isOpen ? null : item.id)}
                        aria-expanded={isOpen}
                        data-testid={`alert-details-${idx}`}
                      >
                        <Icon name={isOpen ? 'ChevronUp' : 'ChevronDown'} size={12} />
                        <span>{isOpen ? 'Hide details' : 'Details'}</span>
                      </button>
                    </div>

                    {isOpen && (
                      <div className="alert-meta" data-testid={`alert-meta-${idx}`}>
                        <div><span>Notice</span><b>{item.id}</b></div>
                        <div><span>Issued by</span><b>{item.source}</b></div>
                        <div><span>Position</span><b>{item.coordinates}</b></div>
                        <div><span>Valid until</span><b>{item.validTill}</b></div>
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </div>

        <div className="simple-card" data-testid="alerts-tools-panel">
          <div className="simple-card-head">
            <div>
              <h3>Harbour tools</h3>
              <p>For authorities who need to publish a notice.</p>
            </div>
            <button
              type="button"
              className="pill-badge-btn"
              onClick={() => setShowTools(prev => !prev)}
              aria-expanded={showTools}
              data-testid="alerts-tools-toggle"
            >
              <Icon name={showTools ? 'ChevronUp' : 'Sliders'} size={13} />
              <span>{showTools ? 'Hide' : 'Open'}</span>
            </button>
          </div>
          {showTools && (
            <div className="alert-actions" data-testid="alerts-tools-section">
              <button
                type="button"
                className="btn secondary btn-sm"
                onClick={() => setIsCreateNoticeModalOpen(true)}
                data-testid="alerts-new-notice-button"
              >
                <Icon name="PlusCircle" size={13} />
                <span>{t('plain.alertsNewNotice', 'Publish a notice')}</span>
              </button>
              <span className="simple-note">Published notices appear at the top of the list for everyone.</span>
            </div>
          )}
        </div>
      </div>

      {isCreateNoticeModalOpen && (
        <div className="maritime-modal-overlay" onClick={() => setIsCreateNoticeModalOpen(false)}>
          <div className="maritime-modal-window" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header-bar">
              <div className="modal-header-title">
                <Icon name="PlusCircle" size={18} />
                <span>Publish a notice</span>
              </div>
              <button className="modal-close-btn" onClick={() => setIsCreateNoticeModalOpen(false)} data-testid="alerts-notice-close">
                <Icon name="X" size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateNoticeSubmit}>
              <div className="modal-body-content">
                <div className="broadcast-form-grid">
                  <div className="b-field">
                    <label>What is happening?</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. Fairway buoy light not working"
                      value={newNoticeTitle}
                      onChange={(e) => setNewNoticeTitle(e.target.value)}
                      data-testid="alerts-notice-title"
                    />
                  </div>
                  <div className="b-field">
                    <label>How serious is it?</label>
                    <select value={newNoticeSeverity} onChange={(e) => setNewNoticeSeverity(e.target.value)} data-testid="alerts-notice-severity">
                      <option value="HIGH">Serious</option>
                      <option value="MEDIUM">Be careful</option>
                      <option value="LOW">For information</option>
                    </select>
                  </div>
                  <div className="b-field">
                    <label>Where?</label>
                    <input
                      type="text"
                      placeholder="e.g. Cochin channel bar mouth"
                      value={newNoticeSector}
                      onChange={(e) => setNewNoticeSector(e.target.value)}
                      data-testid="alerts-notice-place"
                    />
                  </div>
                  <div className="b-field">
                    <label>What should people do?</label>
                    <input
                      type="text"
                      placeholder="e.g. Keep half a mile clear and post a lookout"
                      value={newNoticeDirective}
                      onChange={(e) => setNewNoticeDirective(e.target.value)}
                      data-testid="alerts-notice-directive"
                    />
                  </div>
                  <div className="b-field">
                    <label>Anything else to add?</label>
                    <textarea
                      rows={3}
                      placeholder="Describe the situation in plain words…"
                      value={newNoticeDesc}
                      onChange={(e) => setNewNoticeDesc(e.target.value)}
                      data-testid="alerts-notice-desc"
                    />
                  </div>
                </div>
              </div>

              <div className="modal-footer-bar">
                <button type="button" className="btn secondary" onClick={() => setIsCreateNoticeModalOpen(false)}>Cancel</button>
                <button type="submit" className="btn primary" data-testid="alerts-notice-submit">
                  <Icon name="Check" size={14} />
                  <span>Publish</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {toasts.length > 0 && (
        <div className="alert-toast-container">
          {toasts.map(toast => (
            <div key={toast.id} className={`alert-toast ${toast.type}`}>
              <Icon name={toast.type === 'success' ? 'CheckCircle' : 'AlertTriangle'} size={16} />
              <span>{toast.message}</span>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
