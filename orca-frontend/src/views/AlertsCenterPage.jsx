'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import AppShell from '../components/AppShell';
import Card from '../components/Card';
import Badge from '../components/Badge';
import Icon from '../components/Icon';
import { alerts as mockAlerts } from '../data/mock';
import { useLanguage } from '../context/LanguageContext';
import { useBackend } from '../context/BackendContext';
import {
  getHazards,
  getBackendAlerts,
  createBackendAlert,
  acknowledgeBackendAlert,
  synthesizeAudioWithSarvam
} from '../services/apiClient';

export default function AlertsCenterPage() {
  const router = useRouter();
  const { t, language } = useLanguage();
  const { isBackendLive } = useBackend();

  // Primary State
  const [alertsList, setAlertsList] = useState(mockAlerts);
  const [readAlerts, setReadAlerts] = useState({});
  const [liveHazardsLoaded, setLiveHazardsLoaded] = useState(false);
  const [realCount, setRealCount] = useState(0);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastSyncTime, setLastSyncTime] = useState('Just now');

  // Search & Filter State
  const [searchQuery, setSearchQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState('All');
  const [activeSeverity, setActiveSeverity] = useState('ALL');
  const [activeStatus, setActiveStatus] = useState('ALL'); // 'ALL' | 'UNREAD' | 'ACKNOWLEDGED'

  // Audio / Speech State
  const [currentlySpeakingId, setCurrentlySpeakingId] = useState(null);
  const audioElementRef = useRef(null);

  // Toast Notifications State
  const [toasts, setToasts] = useState([]);

  // Modals State
  const [isBroadcastModalOpen, setIsBroadcastModalOpen] = useState(false);
  const [broadcastProgress, setBroadcastProgress] = useState(0);
  const [broadcastStep, setBroadcastStep] = useState('idle'); // 'idle' | 'transmitting' | 'success'
  const [broadcastChannel, setBroadcastChannel] = useState('ALL');
  const [broadcastSeverity, setBroadcastSeverity] = useState('HIGH');
  const [broadcastSector, setBroadcastSector] = useState('Sector 4 (Kochi to Alappuzha 50 NM Offshore)');
  const [customNotice, setCustomNotice] = useState('URGENT: Squall warning in Central Arabian Sea. Vessels advised to alter course to Fairway Route B.');

  // Create Notice Modal State
  const [isCreateNoticeModalOpen, setIsCreateNoticeModalOpen] = useState(false);
  const [newNoticeTitle, setNewNoticeTitle] = useState('');
  const [newNoticeDesc, setNewNoticeDesc] = useState('');
  const [newNoticeCategory, setNewNoticeCategory] = useState('Safety');
  const [newNoticeSeverity, setNewNoticeSeverity] = useState('MEDIUM');
  const [newNoticeSector, setNewNoticeSector] = useState('Kochi Fairway & Approaches');
  const [newNoticeDirective, setNewNoticeDirective] = useState('');

  // Audio Tone Generator (Web Audio API)
  const playMarineTone = useCallback((type = 'beep') => {
    if (typeof window === 'undefined') return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();

      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'broadcast') {
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(880, ctx.currentTime);
        osc.frequency.setValueAtTime(440, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.12, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
      } else {
        osc.type = 'sine';
        osc.frequency.setValueAtTime(520, ctx.currentTime);
        osc.frequency.setValueAtTime(780, ctx.currentTime + 0.08);
        gain.gain.setValueAtTime(0.08, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.2);
        osc.start();
        osc.stop(ctx.currentTime + 0.2);
      }
    } catch (_) {}
  }, []);

  // Helper to show floating toasts
  const showToast = useCallback((message, type = 'success') => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }, []);

  // Fetch Live Alerts from Backend
  const loadAlerts = useCallback(async (manual = false) => {
    if (manual) setIsRefreshing(true);
    try {
      const res = await getHazards();
      if (res && res.hazards && res.hazards.length > 0) {
        setAlertsList(res.hazards);
        setLiveHazardsLoaded(res.isLive);
        setRealCount(res.realCount || res.hazards.length);

        const nextRead = {};
        res.hazards.forEach((h) => {
          if (h.status === 'acknowledged') {
            nextRead[h.id] = true;
          }
        });
        setReadAlerts((prev) => ({ ...prev, ...nextRead }));
        setLastSyncTime(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
        if (manual) showToast(t('alerts.refreshedMsg', 'Live alerts synchronized with Coast Guard & INCOIS network'), 'success');
      }
    } catch (err) {
      if (manual) showToast(t('alerts.refreshOfflineMsg', 'Offline mode: loaded edge-cached notices'), 'warning');
    } finally {
      if (manual) setIsRefreshing(false);
    }
  }, [showToast, t]);

  useEffect(() => {
    loadAlerts();
  }, [loadAlerts]);

  // Extract Coordinates helper
  const parseCoordinates = (item) => {
    if (item.lat && (item.lon || item.lng)) {
      return { lat: item.lat, lon: item.lon || item.lng };
    }
    if (item.coordinates) {
      const match = item.coordinates.match(/([0-9]+\.?[0-9]*)[°\s]*([0-9]+\.?[0-9]*)?'?[NSns]?[\s,]+([0-9]+\.?[0-9]*)[°\s]*([0-9]+\.?[0-9]*)?'?[EWew]?/);
      if (match) {
        const lat = parseFloat(match[1]) + (parseFloat(match[2] || 0) / 60);
        const lon = parseFloat(match[3]) + (parseFloat(match[4] || 0) / 60);
        return { lat, lon };
      }
    }
    return { lat: 9.9667, lon: 76.1650 };
  };

  // Plot Alert on Marine Map
  const handlePlotOnMap = (item) => {
    const coords = parseCoordinates(item);
    router.push(`/marine-map?lat=${coords.lat.toFixed(4)}&lng=${coords.lon.toFixed(4)}&zoom=13&name=${encodeURIComponent(item.title)}`);
  };

  // Acknowledge Single Bulletin
  const toggleAcknowledge = async (item) => {
    const isCurrentlyRead = !!readAlerts[item.id];
    const nextReadState = !isCurrentlyRead;

    setReadAlerts((prev) => ({ ...prev, [item.id]: nextReadState }));
    playMarineTone('beep');

    if (nextReadState) {
      showToast(`${t('alerts.acknowledgedTag', 'Acknowledged')} notice ${item.id}`, 'success');
      try {
        await acknowledgeBackendAlert(item.id);
      } catch (_) {}
    } else {
      showToast(`${t('alerts.reopenedTag', 'Reopened active')} notice ${item.id}`, 'warning');
    }
  };

  // Mark All Read
  const markAllRead = () => {
    const next = {};
    alertsList.forEach((a) => { next[a.id] = true; });
    setReadAlerts(next);
    playMarineTone('beep');
    showToast(t('alerts.allMarkedAck', 'All bulletins marked as acknowledged'), 'success');
  };

  // Voice Readout
  const handleSpeakAlert = (item) => {
    if (currentlySpeakingId === item.id) {
      if (audioElementRef.current) {
        audioElementRef.current.pause();
        audioElementRef.current = null;
      }
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
      setCurrentlySpeakingId(null);
      return;
    }

    if (audioElementRef.current) {
      audioElementRef.current.pause();
      audioElementRef.current = null;
    }
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    setCurrentlySpeakingId(item.id);
    const speechText = `${item.title}. Directive: ${item.actionRequired}. Sector: ${item.place}. Valid until ${item.validTill}.`;

    const langMap = {
      ml: 'ml-IN',
      ta: 'ta-IN',
      hi: 'hi-IN',
      mr: 'mr-IN',
      te: 'te-IN',
      bn: 'bn-IN',
      en: 'en-IN'
    };
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
      .then((res) => {
        if (res && res.audioUrl) {
          const audio = new Audio(res.audioUrl);
          audioElementRef.current = audio;
          audio.onended = () => setCurrentlySpeakingId(null);
          audio.onerror = () => fallbackBrowserSpeech();
          audio.play().catch(() => fallbackBrowserSpeech());
        } else {
          fallbackBrowserSpeech();
        }
      })
      .catch(() => {
        fallbackBrowserSpeech();
      });
  };

  // Copy NAVTEX
  const handleCopyNavtex = (item) => {
    const coords = parseCoordinates(item);
    const navtexText = [
      'ZCZC MA01',
      `COASTAL WARNING / ${item.source?.toUpperCase() || 'MARITIME RESCUE'}`,
      `NOTICE ID: ${item.id}`,
      `SECTOR: ${item.place?.toUpperCase()}`,
      `POSITION: ${coords.lat.toFixed(2)}N ${coords.lon.toFixed(2)}E`,
      `SEVERITY: ${item.level} PRIORITY`,
      `DIRECTIVE: ${item.actionRequired}`,
      `DETAILS: ${item.desc}`,
      `VALIDITY: UNTIL ${item.validTill}`,
      'NNNN'
    ].join('\n');

    if (navigator.clipboard) {
      navigator.clipboard.writeText(navtexText);
      playMarineTone('beep');
      showToast(`NAVTEX dispatch telex for ${item.id} copied to clipboard`, 'success');
    }
  };

  // Execute Live Fleet Broadcast
  const handleStartBroadcast = async () => {
    setBroadcastStep('transmitting');
    setBroadcastProgress(20);
    playMarineTone('broadcast');

    setTimeout(() => setBroadcastProgress(55), 500);
    setTimeout(() => setBroadcastProgress(85), 1100);

    setTimeout(async () => {
      setBroadcastProgress(100);
      setBroadcastStep('success');
      playMarineTone('broadcast');

      const sectorCoords = broadcastSector.includes('Sector 4')
        ? { lat: 9.75, lon: 76.12, text: "09°45'N, 076°07'E" }
        : broadcastSector.includes('Munambam')
        ? { lat: 10.18, lon: 76.15, text: "10°11'N, 076°09'E" }
        : { lat: 9.97, lon: 76.16, text: "09°58'N, 076°10'E" };

      const newAlert = {
        id: `ALT-DISPATCH-${Date.now().toString().slice(-4)}`,
        title: `EMERGENCY FLEET BROADCAST: ${broadcastChannel}`,
        place: broadcastSector,
        time: 'Just now',
        level: broadcastSeverity,
        category: 'Safety',
        source: `Coast Guard MRCC • ${broadcastChannel}`,
        validTill: '24 Hours IST',
        desc: customNotice,
        coordinates: sectorCoords.text,
        lat: sectorCoords.lat,
        lon: sectorCoords.lon,
        actionRequired: customNotice,
        isLive: true,
        status: 'active'
      };

      setAlertsList((prev) => [newAlert, ...prev]);
      showToast(`Fleet broadcast transmitted to 2,480 registered craft via ${broadcastChannel}`, 'success');

      try {
        await createBackendAlert(newAlert);
      } catch (_) {}
    }, 1700);
  };

  const handleCloseBroadcast = () => {
    setIsBroadcastModalOpen(false);
    setBroadcastStep('idle');
    setBroadcastProgress(0);
  };

  // Create Notice
  const handleCreateNoticeSubmit = async (e) => {
    e.preventDefault();
    if (!newNoticeTitle.trim()) return;

    const noticeItem = {
      id: `ALT-NOTICE-${Date.now().toString().slice(-4)}`,
      title: newNoticeTitle.trim(),
      place: newNoticeSector.trim() || 'Coastal Operating Basin',
      time: 'Just now',
      level: newNoticeSeverity,
      category: newNoticeCategory,
      source: 'Port Authority Harbor Master',
      validTill: '48 Hours IST',
      desc: newNoticeDesc.trim() || 'General navigational advisory issued for commercial and artisanal vessels.',
      coordinates: "09°58'N, 076°16'E",
      lat: 9.9667,
      lon: 76.1650,
      actionRequired: newNoticeDirective.trim() || 'Exercise enhanced navigational caution and maintain radio watch.',
      isLive: true,
      status: 'active'
    };

    setAlertsList((prev) => [noticeItem, ...prev]);
    setIsCreateNoticeModalOpen(false);
    setNewNoticeTitle('');
    setNewNoticeDesc('');
    setNewNoticeDirective('');
    playMarineTone('beep');
    showToast(`Notice ${noticeItem.id} posted successfully to active bulletins`, 'success');

    try {
      await createBackendAlert(noticeItem);
    } catch (_) {}
  };

  // Filter Pipeline
  const filteredAlerts = alertsList.filter((item) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchText = (
        (item.title || '') +
        (item.desc || '') +
        (item.place || '') +
        (item.coordinates || '') +
        (item.actionRequired || '') +
        (item.source || '') +
        (item.id || '')
      ).toLowerCase();
      if (!matchText.includes(q)) return false;
    }

    if (activeCategory !== 'All') {
      if (item.category?.toLowerCase() !== activeCategory.toLowerCase()) {
        return false;
      }
    }

    if (activeSeverity !== 'ALL') {
      if (activeSeverity === 'HIGH' && item.level !== 'HIGH') return false;
      if (activeSeverity === 'MEDIUM' && item.level !== 'MEDIUM') return false;
      if (activeSeverity === 'LOW' && item.level !== 'LOW' && item.level !== 'INFO') return false;
    }

    if (activeStatus === 'UNREAD' && readAlerts[item.id]) return false;
    if (activeStatus === 'ACKNOWLEDGED' && !readAlerts[item.id]) return false;

    return true;
  });

  // KPI Calculations
  const totalCount = alertsList.length;
  const highSeverityCount = alertsList.filter((a) => a.level === 'HIGH').length;
  const pendingAckCount = alertsList.filter((a) => !readAlerts[a.id]).length;
  const acknowledgedCount = totalCount - pendingAckCount;

  return (
    <AppShell
      title={t('alerts.title', 'Maritime Alerts & Warning Center')}
      subtitle={t('alerts.subtitle', 'Multi-Agency Coastal Hazard Warning Network (INCOIS • IMD • NAVAREA VIII)')}
      actions={
        <div className="alerts-header-actions">
          <span className="terminal-status-tag" style={{ display: 'inline-flex', alignItems: 'center', gap: '6px' }}>
            <span className={liveHazardsLoaded ? "enc-pulse-dot" : "enc-pulse-dot-amber"} />
            {liveHazardsLoaded ? `GDACS & INCOIS REAL-TIME (${realCount} ACTIVE)` : 'EDGE BUFFER (OFFLINE)'}
          </span>
          <button
            className="btn secondary btn-sm"
            onClick={() => loadAlerts(true)}
            disabled={isRefreshing}
            title="Re-sync latest advisories from Coast Guard & INCOIS"
          >
            <Icon name="RefreshCw" size={13} className={isRefreshing ? "spin-icon" : ""} />
            <span>{isRefreshing ? t('alerts.syncing', 'Syncing...') : t('alerts.refresh', 'Refresh Feed')}</span>
          </button>
          <button className="btn secondary btn-sm" onClick={markAllRead} title="Acknowledge all current notices">
            <Icon name="CheckCheck" size={13} />
            <span>{t('alerts.markAllRead', 'Mark All Read')}</span>
          </button>
          <button
            className="btn secondary btn-sm"
            onClick={() => setIsCreateNoticeModalOpen(true)}
            title="Create and issue a local maritime notice"
          >
            <Icon name="PlusCircle" size={13} />
            <span>{t('alerts.newNotice', 'New Notice')}</span>
          </button>
          <button
            className="btn primary btn-sm"
            onClick={() => setIsBroadcastModalOpen(true)}
            title="Transmit urgent voice/digital broadcast to fleet"
          >
            <Icon name="Radio" size={13} />
            <span>{t('alerts.fleetBroadcast', 'Fleet Emergency Broadcast')}</span>
          </button>
        </div>
      }
    >
      {/* Operational KPI Summary Strip */}
      <div className="alerts-stats-grid">
        <div className="alert-stat-card">
          <div className="alert-stat-icon blue">
            <Icon name="Bell" size={18} />
          </div>
          <div className="alert-stat-content">
            <span className="alert-stat-value">{totalCount}</span>
            <span className="alert-stat-label">{t('alerts.totalBulletins', 'Active Bulletins')}</span>
          </div>
        </div>

        <div className="alert-stat-card">
          <div className="alert-stat-icon red">
            <Icon name="ShieldAlert" size={18} />
          </div>
          <div className="alert-stat-content">
            <span className="alert-stat-value">{highSeverityCount}</span>
            <span className="alert-stat-label">{t('alerts.highHazards', 'High Severity Warnings')}</span>
          </div>
        </div>

        <div className="alert-stat-card">
          <div className="alert-stat-icon orange">
            <Icon name="Clock" size={18} />
          </div>
          <div className="alert-stat-content">
            <span className="alert-stat-value">{pendingAckCount}</span>
            <span className="alert-stat-label">{t('alerts.pendingAck', 'Pending Acknowledgment')}</span>
          </div>
        </div>

        <div className="alert-stat-card">
          <div className="alert-stat-icon green">
            <Icon name="Radio" size={18} />
          </div>
          <div className="alert-stat-content">
            <span className="alert-stat-value">156.800</span>
            <span className="alert-stat-label">{t('alerts.radioWatch', 'VHF Ch 16 / NAVTEX 518kHz')}</span>
          </div>
        </div>
      </div>

      {/* Modern Filter & Search Controls */}
      <div className="alerts-controls-row">
        <div className="alerts-search-wrap">
          <div className="alerts-search-box">
            <Icon name="Search" size={14} className="alerts-search-icon" />
            <input
              type="text"
              className="alerts-search-input"
              placeholder={t('alerts.searchPlaceholder', 'Search notices by keyword, sector, coordinates, or source (e.g. Swell, Kochi, NAVAREA)...')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button className="alerts-search-clear" onClick={() => setSearchQuery('')} title="Clear search">
                <Icon name="X" size={13} />
              </button>
            )}
          </div>
        </div>

        {/* Category Tabs */}
        <div className="alerts-tabs-group">
          {[
            { key: 'All', label: t('alerts.allNotices', 'All Notices'), count: alertsList.length },
            { key: 'Safety', label: t('alerts.safetyHarbor', 'Safety & Harbor'), count: alertsList.filter(a => a.category?.toLowerCase() === 'safety').length },
            { key: 'Weather', label: t('alerts.weatherSwell', 'Weather & Swell'), count: alertsList.filter(a => a.category?.toLowerCase() === 'weather').length },
            { key: 'Geofence', label: t('alerts.geofencesNaval', 'Geofences & Naval'), count: alertsList.filter(a => a.category?.toLowerCase() === 'geofence').length },
            { key: 'Fishing', label: t('alerts.pfzAdvisories', 'PFZ Advisories'), count: alertsList.filter(a => a.category?.toLowerCase() === 'fishing').length },
            { key: 'System', label: t('alerts.telemetryHealth', 'Telemetry Health'), count: alertsList.filter(a => a.category?.toLowerCase() === 'system').length }
          ].map((tab) => (
            <button
              key={tab.key}
              className={`alerts-tab-btn ${activeCategory === tab.key ? 'active' : ''}`}
              onClick={() => setActiveCategory(tab.key)}
            >
              <span>{tab.label}</span>
              <span className="alerts-tab-count">({tab.count})</span>
            </button>
          ))}
        </div>

        {/* Secondary Severity and Status Filter Pills */}
        <div className="alerts-secondary-filters">
          <div className="filter-group-pills">
            <span className="filter-pill-label">{t('alerts.severityFilter', 'Severity:')}</span>
            <button
              className={`filter-pill-btn ${activeSeverity === 'ALL' ? 'active' : ''}`}
              onClick={() => setActiveSeverity('ALL')}
            >
              {t('alerts.allSeverity', 'All')}
            </button>
            <button
              className={`filter-pill-btn ${activeSeverity === 'HIGH' ? 'active-red' : ''}`}
              onClick={() => setActiveSeverity('HIGH')}
            >
              🔴 {t('alerts.criticalHigh', 'Critical / High')} ({alertsList.filter(a => a.level === 'HIGH').length})
            </button>
            <button
              className={`filter-pill-btn ${activeSeverity === 'MEDIUM' ? 'active-orange' : ''}`}
              onClick={() => setActiveSeverity('MEDIUM')}
            >
              🟠 {t('alerts.medium', 'Medium')} ({alertsList.filter(a => a.level === 'MEDIUM').length})
            </button>
            <button
              className={`filter-pill-btn ${activeSeverity === 'LOW' ? 'active-blue' : ''}`}
              onClick={() => setActiveSeverity('LOW')}
            >
              🔵 {t('alerts.lowInfo', 'Low / Info')} ({alertsList.filter(a => a.level === 'LOW' || a.level === 'INFO').length})
            </button>
          </div>

          <div className="filter-group-pills">
            <span className="filter-pill-label">{t('alerts.statusFilter', 'Status:')}</span>
            <button
              className={`filter-pill-btn ${activeStatus === 'ALL' ? 'active' : ''}`}
              onClick={() => setActiveStatus('ALL')}
            >
              {t('alerts.allStatus', 'All Status')}
            </button>
            <button
              className={`filter-pill-btn ${activeStatus === 'UNREAD' ? 'active-orange' : ''}`}
              onClick={() => setActiveStatus('UNREAD')}
            >
              ⚡ {t('alerts.pendingAction', 'Pending Action')} ({pendingAckCount})
            </button>
            <button
              className={`filter-pill-btn ${activeStatus === 'ACKNOWLEDGED' ? 'active-green' : ''}`}
              onClick={() => setActiveStatus('ACKNOWLEDGED')}
            >
              ✅ {t('alerts.acknowledgedTag', 'Acknowledged')} ({acknowledgedCount})
            </button>
          </div>
        </div>
      </div>

      {/* Main Alerts Feed Card */}
      <Card className="alerts-main-card">
        <div className="alerts-feed-header">
          <div className="feed-header-left">
            <Icon name="ShieldAlert" size={18} className="text-caution" />
            <h3>
              {t('alerts.activeBulletins', 'Active Regional Bulletins')} ({filteredAlerts.length}
              {filteredAlerts.length !== alertsList.length && ` of ${alertsList.length}`})
            </h3>
          </div>
          <span className="feed-header-meta">
            Synchronized at {lastSyncTime} • Marine Inmarsat-C & Coastal VHF
          </span>
        </div>

        {filteredAlerts.length === 0 ? (
          <div className="empty-alerts-state">
            <Icon name="CheckCircle" size={36} className="text-safe" />
            <h4>{t('alerts.noMatchingBulletins', 'No Bulletins Match Selected Filters')}</h4>
            <p style={{ fontSize: '12px' }}>
              {t('alerts.noMatchingSub', 'Adjust search terms, severity, or clear active category filters.')}
            </p>
            <button
              className="btn secondary btn-sm"
              onClick={() => {
                setSearchQuery('');
                setActiveCategory('All');
                setActiveSeverity('ALL');
                setActiveStatus('ALL');
              }}
            >
              <Icon name="RotateCcw" size={12} />
              <span>{t('alerts.resetFilters', 'Reset All Filters')}</span>
            </button>
          </div>
        ) : (
          <div className="alerts-full-list">
            {filteredAlerts.map((item) => {
              const isAcknowledged = !!readAlerts[item.id];
              const isSpeaking = currentlySpeakingId === item.id;

              return (
                <div
                  key={item.id}
                  className={`alert-bulletin-card border-${item.level.toLowerCase()} ${isAcknowledged ? 'read' : ''}`}
                >
                  <div className="bulletin-card-top">
                    <div className="bulletin-title-group">
                      <div className={`bulletin-icon-box bg-${item.level.toLowerCase()}`}>
                        <Icon
                          name={
                            item.category === 'Weather'
                              ? 'Waves'
                              : item.category === 'Geofence'
                              ? 'ShieldAlert'
                              : item.category === 'Safety'
                              ? 'LifeBuoy'
                              : item.category === 'Fishing'
                              ? 'Fish'
                              : 'Activity'
                          }
                          size={18}
                        />
                      </div>
                      <div>
                        <div className="bulletin-headline">
                          <b>{item.title}</b>
                          <span className="bulletin-place">• {item.place}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
                          <span className="bulletin-id-tag">{item.id} • {item.source}</span>
                          {isAcknowledged && (
                            <span className="alerts-ack-status-tag">
                              <Icon name="Check" size={10} />
                              <span>{t('alerts.acknowledgedTag', 'ACKNOWLEDGED')}</span>
                            </span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="bulletin-badges-group">
                      <Badge tone={item.level === 'HIGH' ? 'red' : item.level === 'MEDIUM' ? 'orange' : 'blue'}>
                        {item.level} SEVERITY
                      </Badge>
                      <span className="bulletin-time">{item.time}</span>
                    </div>
                  </div>

                  <p className="bulletin-desc-p">{item.desc}</p>

                  <div className="bulletin-details-row">
                    <div className="detail-chip" title="Click to copy sector fix" onClick={() => {
                      if (navigator.clipboard) {
                        navigator.clipboard.writeText(item.coordinates || '');
                        showToast(`Sector coordinates ${item.coordinates} copied`, 'success');
                      }
                    }} style={{ cursor: 'pointer' }}>
                      <Icon name="MapPin" size={12} />
                      <span>Sector: <code>{item.coordinates}</code></span>
                    </div>
                    <div className="detail-chip">
                      <Icon name="Clock" size={12} />
                      <span>{t('alerts.validUntil', 'Valid Until:')} <b>{item.validTill}</b></span>
                    </div>
                    <div className="detail-chip">
                      <Icon name="AlertCircle" size={12} className="text-hazard" />
                      <span>{t('alerts.directive', 'Directive:')} <b className="text-hazard">{item.actionRequired}</b></span>
                    </div>
                  </div>

                  <div className="bulletin-card-footer">
                    <div className="bulletin-actions-left" style={{ flexWrap: 'wrap' }}>
                      <button
                        className="btn secondary btn-sm"
                        onClick={() => handlePlotOnMap(item)}
                        title="Jump to this hazard on the 16-layer Marine GIS Map"
                      >
                        <Icon name="Map" size={12} />
                        <span>{t('alerts.plotOnMap', 'Plot on Marine Map')}</span>
                      </button>

                      <button
                        className="btn secondary btn-sm"
                        onClick={() => router.push(`/ai-copilot?q=${encodeURIComponent(`Analyze the navigational impact and safety directives of ${item.id} (${item.title}) for craft operating near ${item.place}.`)}`)}
                        title="Query AI Copilot for autonomous route hazard breakdown"
                      >
                        <Icon name="Bot" size={12} />
                        <span>{t('alerts.copilotAssessment', 'Copilot Assessment')}</span>
                      </button>

                      <button
                        className={`btn secondary btn-sm ${isSpeaking ? 'active' : ''}`}
                        onClick={() => handleSpeakAlert(item)}
                        title="Listen to advisory spoken aloud in active language"
                      >
                        {isSpeaking ? (
                          <>
                            <div className="audio-equalizer">
                              <span className="audio-bar" />
                              <span className="audio-bar" />
                              <span className="audio-bar" />
                            </div>
                            <span style={{ color: '#38bdf8' }}>{t('alerts.stopAudio', 'Stop Audio')}</span>
                          </>
                        ) : (
                          <>
                            <Icon name="Volume2" size={12} />
                            <span>{t('alerts.readAdvisory', 'Listen Advisory')}</span>
                          </>
                        )}
                      </button>

                      <button
                        className="btn secondary btn-sm"
                        onClick={() => handleCopyNavtex(item)}
                        title="Copy official NAVTEX telex dispatch message"
                      >
                        <Icon name="Copy" size={12} />
                        <span>{t('alerts.copyNavtex', 'Copy NAVTEX')}</span>
                      </button>
                    </div>

                    <button
                      className="btn-text-subtle"
                      onClick={() => toggleAcknowledge(item)}
                    >
                      {isAcknowledged ? t('alerts.reopenNotice', 'Mark as Unacknowledged') : t('alerts.acknowledge', 'Acknowledge Bulletin')}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Real Emergency Fleet Broadcast Modal */}
      {isBroadcastModalOpen && (
        <div className="maritime-modal-overlay" onClick={handleCloseBroadcast}>
          <div className="maritime-modal-window" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header-bar">
              <div className="modal-header-title">
                <Icon name="Radio" size={18} className="text-hazard" />
                <span>COASTAL EMERGENCY BROADCAST CONSOLE</span>
              </div>
              <button className="modal-close-btn" onClick={handleCloseBroadcast}>
                <Icon name="X" size={16} />
              </button>
            </div>

            <div className="modal-body-content">
              <div className="broadcast-status-banner">
                <span className="live-radar-dot" />
                <span>GATEWAY LINK: INDIAN COAST GUARD MRCC KOCHI • SATELLITE MSS ACTIVE</span>
              </div>

              <div className="broadcast-form-grid">
                <div className="b-field">
                  <label>TRANSMISSION CHANNELS:</label>
                  <div className="b-channel-pills">
                    {['ALL', 'VHF DSC Ch 70', 'NAVTEX 518 kHz', 'MSS S-Band', 'Coastal SMS Gateway'].map((ch) => (
                      <button
                        key={ch}
                        type="button"
                        className={`b-pill ${broadcastChannel === ch ? 'active' : ''}`}
                        onClick={() => setBroadcastChannel(ch)}
                        disabled={broadcastStep === 'transmitting'}
                      >
                        {ch}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="b-field">
                  <label>ALERT SEVERITY LEVEL:</label>
                  <div className="b-channel-pills">
                    {[
                      { id: 'HIGH', label: '🔴 CRITICAL EMERGENCY (Immediate Divert)' },
                      { id: 'MEDIUM', label: '🟠 WARNING (Moderate Hazard)' },
                      { id: 'LOW', label: '🔵 ADVISORY (Informational)' }
                    ].map((lvl) => (
                      <button
                        key={lvl.id}
                        type="button"
                        className={`b-pill ${broadcastSeverity === lvl.id ? 'active' : ''}`}
                        onClick={() => setBroadcastSeverity(lvl.id)}
                        disabled={broadcastStep === 'transmitting'}
                      >
                        {lvl.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="b-field">
                  <label>TARGET COVERAGE SECTOR:</label>
                  <select
                    value={broadcastSector}
                    onChange={(e) => setBroadcastSector(e.target.value)}
                    disabled={broadcastStep === 'transmitting'}
                  >
                    <option value="Sector 4 (Kochi to Alappuzha 50 NM Offshore)">Sector 4 (Kochi to Alappuzha 50 NM Offshore)</option>
                    <option value="Munambam Coastal Basin (30 NM Inshore)">Munambam Coastal Basin (30 NM Inshore)</option>
                    <option value="Lakshadweep Sea Transit Corridor">Lakshadweep Sea Transit Corridor</option>
                    <option value="All Southern Arabian Sea Craft (100 NM)">All Southern Arabian Sea Craft (100 NM)</option>
                  </select>
                </div>

                <div className="b-field">
                  <label>EMERGENCY DISPATCH DIRECTIVE:</label>
                  <textarea
                    rows={3}
                    value={customNotice}
                    onChange={(e) => setCustomNotice(e.target.value)}
                    disabled={broadcastStep === 'transmitting'}
                  />
                </div>

                <div className="b-meta-summary">
                  <div className="meta-box">
                    <span>REGISTERED CRAFT:</span>
                    <b>2,480 Vessels</b>
                  </div>
                  <div className="meta-box">
                    <span>FREQUENCY:</span>
                    <b>156.525 MHz / S-Band</b>
                  </div>
                  <div className="meta-box">
                    <span>SECURITY HASH:</span>
                    <code>SHA256: 9b8f..41c</code>
                  </div>
                </div>

                {broadcastStep !== 'idle' && (
                  <div className="b-progress-zone">
                    <div className="b-progress-header">
                      <span>{broadcastStep === 'transmitting' ? 'Uplinking to Coastal Transponders...' : '✅ BROADCAST CONFIRMED'}</span>
                      <b>{broadcastProgress}%</b>
                    </div>
                    <div className="b-progress-track">
                      <div className="b-progress-fill" style={{ width: `${broadcastProgress}%` }} />
                    </div>
                    {broadcastStep === 'success' && (
                      <div className="b-success-alert">
                        <Icon name="CheckCircle" size={16} className="text-safe" />
                        <span>Emergency transmission acknowledged by 2,480 marine transponders and Coast Guard MRCC. Bulletin added to live feed.</span>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>

            <div className="modal-footer-bar">
              <button className="btn secondary" onClick={handleCloseBroadcast}>
                Close
              </button>
              {broadcastStep !== 'success' ? (
                <button
                  className="btn primary"
                  onClick={handleStartBroadcast}
                  disabled={broadcastStep === 'transmitting'}
                >
                  <Icon name="Send" size={14} />
                  <span>{broadcastStep === 'transmitting' ? 'Transmitting Fleet Burst...' : 'Transmit Live Fleet Broadcast'}</span>
                </button>
              ) : (
                <button className="btn primary" onClick={handleCloseBroadcast}>
                  Done
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Create New Maritime Notice Modal */}
      {isCreateNoticeModalOpen && (
        <div className="maritime-modal-overlay" onClick={() => setIsCreateNoticeModalOpen(false)}>
          <div className="maritime-modal-window" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header-bar">
              <div className="modal-header-title">
                <Icon name="PlusCircle" size={18} className="text-safe" />
                <span>ISSUE NEW MARITIME NOTICE</span>
              </div>
              <button className="modal-close-btn" onClick={() => setIsCreateNoticeModalOpen(false)}>
                <Icon name="X" size={16} />
              </button>
            </div>

            <form onSubmit={handleCreateNoticeSubmit}>
              <div className="modal-body-content">
                <div className="broadcast-form-grid">
                  <div className="b-field">
                    <label>NOTICE HEADLINE / TITLE:</label>
                    <input
                      type="text"
                      className="alerts-search-input"
                      required
                      placeholder="e.g. Fairway Buoy Fl(2) 10s Extinguished"
                      value={newNoticeTitle}
                      onChange={(e) => setNewNoticeTitle(e.target.value)}
                    />
                  </div>

                  <div className="b-field" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                    <div>
                      <label>CATEGORY:</label>
                      <select value={newNoticeCategory} onChange={(e) => setNewNoticeCategory(e.target.value)}>
                        <option value="Safety">Safety & Harbor</option>
                        <option value="Weather">Weather & Swell</option>
                        <option value="Geofence">Geofences & Naval</option>
                        <option value="Fishing">PFZ Advisories</option>
                        <option value="System">Telemetry Health</option>
                      </select>
                    </div>
                    <div>
                      <label>SEVERITY LEVEL:</label>
                      <select value={newNoticeSeverity} onChange={(e) => setNewNoticeSeverity(e.target.value)}>
                        <option value="HIGH">HIGH (Critical)</option>
                        <option value="MEDIUM">MEDIUM (Caution)</option>
                        <option value="LOW">LOW (Informational)</option>
                      </select>
                    </div>
                  </div>

                  <div className="b-field">
                    <label>OPERATING SECTOR / LOCATION:</label>
                    <input
                      type="text"
                      className="alerts-search-input"
                      placeholder="e.g. Cochin Channel Bar Mouth (09°58'N, 076°14'E)"
                      value={newNoticeSector}
                      onChange={(e) => setNewNoticeSector(e.target.value)}
                    />
                  </div>

                  <div className="b-field">
                    <label>DIRECTIVE / REQUIRED MARINER ACTION:</label>
                    <input
                      type="text"
                      className="alerts-search-input"
                      placeholder="e.g. Maintain 0.5 NM clearance, transit with lookout"
                      value={newNoticeDirective}
                      onChange={(e) => setNewNoticeDirective(e.target.value)}
                    />
                  </div>

                  <div className="b-field">
                    <label>FULL BULLETIN DESCRIPTION:</label>
                    <textarea
                      rows={3}
                      placeholder="Describe the navigational condition or temporary hazard in detail..."
                      value={newNoticeDesc}
                      onChange={(e) => setNewNoticeDesc(e.target.value)}
                    />
                  </div>
                </div>
              </div>

              <div className="modal-footer-bar">
                <button type="button" className="btn secondary" onClick={() => setIsCreateNoticeModalOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn primary">
                  <Icon name="Check" size={14} />
                  <span>Publish Notice</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Floating Toast Feedback Notifications */}
      {toasts.length > 0 && (
        <div className="alert-toast-container">
          {toasts.map((t) => (
            <div key={t.id} className={`alert-toast ${t.type}`}>
              <Icon
                name={t.type === 'success' ? 'CheckCircle' : t.type === 'warning' ? 'AlertTriangle' : 'Info'}
                size={16}
              />
              <span>{t.message}</span>
            </div>
          ))}
        </div>
      )}
    </AppShell>
  );
}
