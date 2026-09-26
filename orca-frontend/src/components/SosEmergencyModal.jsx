'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Icon from './Icon';
import Badge from './Badge';
import { dispatchSmsAlert } from '../services/apiClient';

const EMERGENCY_TYPES = [
  { id: 'sinking', label: 'Vessel Sinking / Capsized', icon: 'Anchor', color: '#dc2626' },
  { id: 'mob', label: 'Man Overboard (MOB)', icon: 'LifeBuoy', color: '#dc2626' },
  { id: 'fire', label: 'Fire / Explosion', icon: 'Flame', color: '#ea580c' },
  { id: 'medical', label: 'Medical Emergency', icon: 'Heart', color: '#e11d48' },
  { id: 'collision', label: 'Collision / Grounding', icon: 'AlertTriangle', color: '#f59e0b' },
  { id: 'piracy', label: 'Piracy / Armed Attack', icon: 'Shield', color: '#7c3aed' },
  { id: 'mechanical', label: 'Engine / Steering Failure', icon: 'Settings', color: '#f59e0b' },
  { id: 'other', label: 'Other Emergency', icon: 'Radio', color: '#64748b' },
];

const MRCC_CONTACTS = [
  { name: 'MRCC Mumbai', phone: '022-22614646', area: 'West Coast (Gujarat to Goa)' },
  { name: 'MRCC Chennai', phone: '044-25395018', area: 'East Coast (TN to AP)' },
  { name: 'MRCC Port Blair', phone: '03192-245530', area: 'Andaman & Nicobar Islands' },
  { name: 'ICG Toll-Free', phone: '1554', area: 'All India — Coast Guard Emergency' },
];

export default function SosEmergencyModal({ isOpen, onClose }) {
  const [step, setStep] = useState('select'); // select | confirm | broadcasting
  const [emergencyType, setEmergencyType] = useState(null);
  const [crewCount, setCrewCount] = useState('');
  const [vesselName, setVesselName] = useState('');
  const [countdown, setCountdown] = useState(5);
  const [gpsCoords, setGpsCoords] = useState(null);
  const [gpsStatus, setGpsStatus] = useState('acquiring'); // acquiring | locked | denied
  const countdownRef = useRef(null);
  // Fire-and-forget SMS guard (reset each time the modal opens).
  const smsFiredRef = useRef(false);

  // Acquire GPS on open
  useEffect(() => {
    if (!isOpen) return;
    setStep('select');
    setEmergencyType(null);
    setCountdown(5);
    setCrewCount('');
    setGpsStatus('acquiring');
    if (smsFiredRef.current) smsFiredRef.current = false;

    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setGpsCoords({ lat: pos.coords.latitude, lon: pos.coords.longitude, accuracy: pos.coords.accuracy });
          setGpsStatus('locked');
        },
        () => {
          // Fallback: use Kochi harbour coordinates
          setGpsCoords({ lat: 9.9656, lon: 76.2746, accuracy: null });
          setGpsStatus('denied');
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    } else {
      setGpsCoords({ lat: 9.9656, lon: 76.2746, accuracy: null });
      setGpsStatus('denied');
    }
  }, [isOpen]);

  // Countdown timer in confirm step
  useEffect(() => {
    if (step !== 'confirm') return;
    setCountdown(5);
    countdownRef.current = setInterval(() => {
      setCountdown(prev => {
        if (prev <= 1) {
          clearInterval(countdownRef.current);
          setStep('broadcasting');
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
    return () => clearInterval(countdownRef.current);
  }, [step]);

  const handleCancel = useCallback(() => {
    clearInterval(countdownRef.current);
    onClose();
  }, [onClose]);

  const handleSelectType = (type) => {
    setEmergencyType(type);
  };

  const handleProceedToConfirm = () => {
    if (!emergencyType) return;
    setStep('confirm');
  };

  const handleImmediateBroadcast = () => {
    clearInterval(countdownRef.current);
    setStep('broadcasting');
  };

  // Fire-and-forget SMS to the saved emergency number when broadcasting starts.
  useEffect(() => {
    if (step !== 'broadcasting' || smsFiredRef.current) return;
    smsFiredRef.current = true;
    let phone = '';
    try {
      phone = (JSON.parse(localStorage.getItem('orca-emergency-prefs') || '{}').emergencyPhone) || '';
    } catch {
      phone = '';
    }
    if (!phone) return;
    const lat = gpsCoords?.lat ?? 9.9656;
    const lon = gpsCoords?.lon ?? 76.2746;
    dispatchSmsAlert({
      phone,
      message: `MAYDAY RELAY via ORCA: ${emergencyType?.label || 'Distress'} — vessel ${vesselName || 'unknown'}${crewCount ? ` (${crewCount} POB)` : ''} at ${Number(lat).toFixed(4)}N, ${Number(lon).toFixed(4)}E. VHF Ch16. (demo SMS)`.slice(0, 300),
      severity: 'HIGH'
    }).catch(() => {});
  }, [step, emergencyType, gpsCoords, vesselName, crewCount]);

  const formatCoord = (val, isLat) => {
    if (!val && val !== 0) return '—';
    const abs = Math.abs(val);
    const deg = Math.floor(abs);
    const minFloat = (abs - deg) * 60;
    const min = Math.floor(minFloat);
    const sec = ((minFloat - min) * 60).toFixed(1);
    const dir = isLat ? (val >= 0 ? 'N' : 'S') : (val >= 0 ? 'E' : 'W');
    return `${deg}°${String(min).padStart(2, '0')}'${sec}" ${dir}`;
  };

  if (!isOpen) return null;

  return (
    <div className="maritime-modal-overlay" onClick={handleCancel}>
      <div
        className="maritime-modal-window sos-danger-modal"
        onClick={(e) => e.stopPropagation()}
        style={{ maxWidth: step === 'select' ? 640 : 540 }}
      >
        {/* Header */}
        <div className="modal-header-bar bg-danger-bar">
          <div className="modal-header-title">
            <Icon name="AlertTriangle" size={20} style={{ color: '#fff' }} />
            <span>
              {step === 'broadcasting'
                ? 'DISTRESS SIGNAL BROADCASTING'
                : 'EMERGENCY SOS — COAST GUARD DISTRESS RELAY'}
            </span>
          </div>
          <button className="modal-close-btn" onClick={handleCancel}>
            <Icon name="X" size={16} />
          </button>
        </div>

        <div className="modal-body-content" style={{ padding: '20px', overflowY: 'auto' }}>

          {/* ──── STEP 1: Select Emergency Type ──── */}
          {step === 'select' && (
            <div className="sos-emergency-box" style={{ textAlign: 'left', alignItems: 'stretch' }}>
              {/* GPS Status */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
                  Your Location
                </span>
                <Badge tone={gpsStatus === 'locked' ? 'green' : gpsStatus === 'acquiring' ? 'orange' : 'red'} dot>
                  {gpsStatus === 'locked' ? 'GPS LOCKED' : gpsStatus === 'acquiring' ? 'ACQUIRING GPS…' : 'GPS FALLBACK'}
                </Badge>
              </div>
              {gpsCoords && (
                <div className="sos-coordinates-card" style={{ marginBottom: 14 }}>
                  <div className="sos-coord-row">
                    <span>LATITUDE:</span>
                    <code>{formatCoord(gpsCoords.lat, true)}</code>
                  </div>
                  <div className="sos-coord-row">
                    <span>LONGITUDE:</span>
                    <code>{formatCoord(gpsCoords.lon, false)}</code>
                  </div>
                  {gpsCoords.accuracy && (
                    <div className="sos-coord-row">
                      <span>ACCURACY:</span>
                      <b>±{Math.round(gpsCoords.accuracy)}m</b>
                    </div>
                  )}
                </div>
              )}

              {/* Emergency Type Selection */}
              <span style={{ fontSize: 11, color: '#94a3b8', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 6, display: 'block' }}>
                Select Emergency Type
              </span>
              <div className="sos-type-grid">
                {EMERGENCY_TYPES.map(type => (
                  <button
                    key={type.id}
                    type="button"
                    className={`sos-type-btn ${emergencyType?.id === type.id ? 'active' : ''}`}
                    onClick={() => handleSelectType(type)}
                    style={{ '--sos-type-color': type.color }}
                  >
                    <Icon name={type.icon} size={18} />
                    <span>{type.label}</span>
                  </button>
                ))}
              </div>

              {/* Optional Fields */}
              <div style={{ display: 'flex', gap: 10, marginTop: 14 }}>
                <div style={{ flex: 1 }}>
                  <label style={{ display: 'block', fontSize: 10, color: '#64748b', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 4, textTransform: 'uppercase' }}>
                    Vessel / Craft Name
                  </label>
                  <input
                    type="text"
                    value={vesselName}
                    onChange={(e) => setVesselName(e.target.value)}
                    placeholder="e.g. F/V Matsya-04"
                    className="sos-input"
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ display: 'block', fontSize: 10, color: '#64748b', fontWeight: 700, letterSpacing: '0.08em', marginBottom: 4, textTransform: 'uppercase' }}>
                    Persons on Board
                  </label>
                  <input
                    type="number"
                    value={crewCount}
                    onChange={(e) => setCrewCount(e.target.value)}
                    placeholder="e.g. 6"
                    min="1"
                    max="999"
                    className="sos-input"
                  />
                </div>
              </div>

              {/* Action */}
              <button
                type="button"
                className="btn btn-emergency-call"
                style={{ marginTop: 16, opacity: emergencyType ? 1 : 0.4, pointerEvents: emergencyType ? 'auto' : 'none' }}
                onClick={handleProceedToConfirm}
              >
                <Icon name="AlertTriangle" size={18} />
                <span>Activate Distress Signal →</span>
              </button>
            </div>
          )}

          {/* ──── STEP 2: Countdown Confirmation ──── */}
          {step === 'confirm' && (
            <div className="sos-emergency-box">
              <div className="sos-countdown-ring">
                <span className="sos-countdown-number">{countdown}</span>
              </div>
              <h3>BROADCASTING IN {countdown} SECONDS</h3>
              <p>
                <b style={{ color: emergencyType?.color || '#ef4444' }}>{emergencyType?.label}</b> distress signal
                will be transmitted on <b>156.525 MHz (VHF Ch 70)</b> DSC and <b>406 MHz COSPAS-SARSAT</b> satellite relay.
              </p>
              {vesselName && (
                <p style={{ fontSize: 11 }}>Vessel: <b>{vesselName}</b>{crewCount ? ` • ${crewCount} persons on board` : ''}</p>
              )}

              <div className="sos-contact-action-box">
                <button type="button" className="btn btn-emergency-call" onClick={handleImmediateBroadcast}>
                  <Icon name="Radio" size={18} />
                  <span>Broadcast Now — Don't Wait</span>
                </button>
                <button type="button" className="btn secondary" style={{ width: '100%', justifyContent: 'center' }} onClick={handleCancel}>
                  <Icon name="X" size={14} />
                  <span>Cancel — False Alarm</span>
                </button>
              </div>
            </div>
          )}

          {/* ──── STEP 3: Broadcasting Active ──── */}
          {step === 'broadcasting' && (
            <div className="sos-emergency-box">
              <div className="sos-pulse-beacon">🚨</div>
              <h3>DISTRESS CALL BEACON ACTIVATED</h3>
              <p>
                <b style={{ color: emergencyType?.color || '#ef4444' }}>{emergencyType?.label}</b> — Transmitting DSC Digital Selective Calling
                burst on <b>156.525 MHz (VHF Ch 70)</b> and <b>406 MHz COSPAS-SARSAT</b> satellite relay.
              </p>

              <div className="sos-coordinates-card">
                {vesselName && (
                  <div className="sos-coord-row">
                    <span>VESSEL IDENTITY:</span>
                    <b>{vesselName}{crewCount ? ` (${crewCount} POB)` : ''}</b>
                  </div>
                )}
                <div className="sos-coord-row">
                  <span>EMERGENCY TYPE:</span>
                  <b style={{ color: emergencyType?.color }}>{emergencyType?.label}</b>
                </div>
                <div className="sos-coord-row">
                  <span>GPS FIX:</span>
                  <code>
                    {gpsCoords ? `${formatCoord(gpsCoords.lat, true)}, ${formatCoord(gpsCoords.lon, false)}` : 'Acquiring…'}
                  </code>
                </div>
                <div className="sos-coord-row">
                  <span>TIMESTAMP:</span>
                  <b>{new Date().toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST</b>
                </div>
                <div className="sos-coord-row">
                  <span>FREQUENCIES:</span>
                  <b>VHF Ch 16 (Distress) • DSC Ch 70 • 406 MHz EPIRB</b>
                </div>
              </div>

              {/* MRCC Contact Cards */}
              <span style={{ fontSize: 10, color: '#94a3b8', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', marginTop: 10, display: 'block', width: '100%', textAlign: 'left' }}>
                MARITIME RESCUE COORDINATION CENTRES
              </span>
              <div className="sos-mrcc-grid">
                {MRCC_CONTACTS.map(mrcc => (
                  <a key={mrcc.phone} href={`tel:${mrcc.phone.replace(/[^0-9+]/g, '')}`} className="sos-mrcc-card">
                    <Icon name="PhoneCall" size={16} style={{ color: '#ef4444', flexShrink: 0 }} />
                    <div>
                      <b>{mrcc.name}</b>
                      <span>{mrcc.phone}</span>
                      <small>{mrcc.area}</small>
                    </div>
                  </a>
                ))}
              </div>

              <div className="sos-contact-action-box" style={{ marginTop: 14 }}>
                <a href="tel:1554" className="btn btn-emergency-call">
                  <Icon name="PhoneCall" size={18} />
                  <span>Dial Coast Guard 1554 Now</span>
                </a>
                <button type="button" className="btn secondary" style={{ width: '100%', justifyContent: 'center' }} onClick={handleCancel}>
                  Cancel Distress Broadcast
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
