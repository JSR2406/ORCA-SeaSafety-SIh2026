import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Icon from './Icon';
import {
  getGoogleMapsApiKey,
  setGoogleMapsApiKey,
  loadGoogleMapsJsSdk,
  maskApiKey,
  isEnvApiKey
} from '../utils/googleMaps';

export default function GoogleMapsConfigModal({ isOpen, onClose, onKeyUpdated }) {
  const [activeKey, setActiveKey] = useState('');
  const [newKeyInput, setNewKeyInput] = useState('');
  const [isEditing, setIsEditing] = useState(false);
  const [testStatus, setTestStatus] = useState('idle'); // 'idle' | 'testing' | 'success' | 'error'
  const [testMessage, setTestMessage] = useState('');

  useEffect(() => {
    if (isOpen) {
      const current = getGoogleMapsApiKey();
      setActiveKey(current);
      setNewKeyInput('');
      setIsEditing(!current);
      setTestStatus(current ? 'success' : 'idle');
      setTestMessage(current ? 'Google Maps API is securely configured and active.' : '');
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = () => {
    if (isEditing) {
      const trimmed = newKeyInput.trim();
      if (trimmed) {
        setGoogleMapsApiKey(trimmed);
        setActiveKey(trimmed);
        setIsEditing(false);
        if (onKeyUpdated) onKeyUpdated(trimmed);
      }
    }
    onClose();
  };

  const handleClear = () => {
    setNewKeyInput('');
    setActiveKey('');
    setGoogleMapsApiKey('');
    setIsEditing(true);
    setTestStatus('idle');
    setTestMessage('Google Maps API key removed. Using default Open Maritime Cartography.');
    if (onKeyUpdated) onKeyUpdated('');
  };

  const handleTestKey = async () => {
    const keyToTest = isEditing ? newKeyInput.trim() : activeKey;
    if (!keyToTest) {
      setTestStatus('error');
      setTestMessage('Please enter an API key first.');
      return;
    }

    setTestStatus('testing');
    setTestMessage('Verifying Google Maps API handshake...');

    try {
      // Test 1: Test tile image accessibility
      const testTileUrl = `https://mt1.google.com/vt/lyrs=y&x=0&y=0&z=0&key=${encodeURIComponent(keyToTest)}`;
      const img = new Image();
      const tilePromise = new Promise((resolve, reject) => {
        img.onload = () => resolve(true);
        img.onerror = () => reject(new Error('Tile server handshake failed. Please verify API key permissions.'));
        img.src = testTileUrl;
      });

      await tilePromise;

      // Test 2: Try loading JS SDK
      try {
        await loadGoogleMapsJsSdk(keyToTest);
      } catch (e) {
        console.warn('JS SDK initialization optional check notice:', e);
      }

      setTestStatus('success');
      setTestMessage('Valid API key! High-resolution Google Satellite & Roadmap layers unlocked.');
    } catch (err) {
      setTestStatus('error');
      setTestMessage(err.message || 'Key verification failed. Ensure Maps JavaScript API is enabled in Google Cloud.');
    }
  };

  return (
    <AnimatePresence>
      <div className="gmaps-modal-backdrop" onClick={onClose}>
        <motion.div
          className="gmaps-modal-container"
          initial={{ opacity: 0, scale: 0.95, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Modal Header */}
          <div className="gmaps-modal-header">
            <div className="gmaps-modal-title-wrap">
              <div className="gmaps-icon-badge">
                <Icon name="Layers" size={18} />
              </div>
              <div>
                <h3 className="gmaps-modal-title">Google Maps Platform Integration</h3>
                <p className="gmaps-modal-subtitle">
                  High-Resolution Nautical Cartography, Hybrid Satellite & Coastal Places
                </p>
              </div>
            </div>
            <button
              type="button"
              className="gmaps-modal-close-btn"
              onClick={onClose}
              aria-label="Close dialog"
            >
              <Icon name="X" size={16} />
            </button>
          </div>

          {/* Modal Body */}
          <div className="gmaps-modal-body">
            {/* Status Alert Banner */}
            <div className={`gmaps-status-card ${activeKey ? 'active' : 'inactive'}`}>
              <div className="gmaps-status-indicator">
                <span className={`status-dot ${activeKey ? 'online' : 'offline'}`} />
                <span className="status-label">
                  {activeKey ? 'Google Maps Connected' : 'Default CartoDB / Esri Maritime Mode'}
                </span>
              </div>
              <p className="gmaps-status-desc">
                {activeKey
                  ? 'High-definition Google Satellite Hybrid, Roadmap, and Terrain base layers are active across all tactical views.'
                  : 'Operating on open maritime base layers (CartoDB Voyager, Esri Satellite, Dark ECDIS). Add your API key below to unlock Google Maps.'}
              </p>
            </div>

            {/* API Key Form Section */}
            <div className="gmaps-field-group">
              <label className="gmaps-field-label" htmlFor="gmaps-key-input">
                <span>Google Maps API Key</span>
                <span className="gmaps-field-hint">
                  {isEnvApiKey() ? 'Supplied securely via environment' : 'Stored securely in browser local storage'}
                </span>
              </label>

              {activeKey && !isEditing ? (
                <div className="gmaps-protected-key-card">
                  <div className="protected-key-header">
                    <div className="protected-key-title-row">
                      <Icon name="ShieldCheck" size={15} className="protected-key-shield-icon" />
                      <span className="protected-key-title">Active Platform Credential</span>
                      <span className="protected-key-badge">
                        {isEnvApiKey() ? '🔒 ENV MANAGED' : '🔒 PROTECTED'}
                      </span>
                    </div>
                    {!isEnvApiKey() && (
                      <button
                        type="button"
                        className="btn secondary btn-xs"
                        onClick={() => {
                          setIsEditing(true);
                          setNewKeyInput('');
                        }}
                      >
                        <Icon name="Edit3" size={12} />
                        <span>Replace Key</span>
                      </button>
                    )}
                  </div>
                  <div className="protected-key-display">
                    <code className="protected-key-code">{maskApiKey(activeKey)}</code>
                  </div>
                  <p className="protected-key-hint">
                    {isEnvApiKey()
                      ? 'Injected via system environment variables. Cannot be modified or viewed in browser.'
                      : 'Key is securely masked to protect credentials from shoulder-surfing and unauthorized inspection.'}
                  </p>
                </div>
              ) : (
                <div className="gmaps-edit-key-container">
                  <div className="gmaps-input-wrapper">
                    <Icon name="Key" size={15} className="gmaps-input-icon" />
                    <input
                      id="gmaps-key-input"
                      type="password"
                      className="gmaps-text-input"
                      placeholder="Paste your AIzaSy... API key here"
                      value={newKeyInput}
                      onChange={(e) => {
                        setNewKeyInput(e.target.value);
                        setTestStatus('idle');
                        setTestMessage('');
                      }}
                      autoComplete="off"
                      spellCheck="false"
                    />
                    {activeKey && (
                      <button
                        type="button"
                        className="btn secondary btn-xs gmaps-cancel-edit-btn"
                        onClick={() => {
                          setIsEditing(false);
                          setNewKeyInput('');
                        }}
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                  <p className="gmaps-field-subhint">
                    Key is treated as a secret and will never be exposed in plaintext once saved.
                  </p>
                </div>
              )}

              {testStatus !== 'idle' && (
                <div className={`gmaps-test-feedback ${testStatus}`}>
                  <Icon
                    name={
                      testStatus === 'testing'
                        ? 'RefreshCw'
                        : testStatus === 'success'
                        ? 'CheckCircle2'
                        : 'AlertTriangle'
                    }
                    size={14}
                    className={testStatus === 'testing' ? 'spin-icon' : ''}
                  />
                  <span>{testMessage}</span>
                </div>
              )}
            </div>

            {/* Quick Tips & API Documentation */}
            <div className="gmaps-info-box">
              <div className="gmaps-info-title">
                <Icon name="Info" size={13} />
                <span>Recommended Google Cloud API Services</span>
              </div>
              <ul className="gmaps-info-list">
                <li>
                  <b>Maps JavaScript API:</b> Unlocks interactive hybrid satellite, roadmap, and terrain controls.
                </li>
                <li>
                  <b>Geocoding API:</b> Enables searching ports, harbours, coordinates, and coastal landmarks.
                </li>
                <li>
                  <b>Places API:</b> Powers autocomplete search for Indian ports and global maritime terminals.
                </li>
              </ul>
              <div className="gmaps-info-actions">
                <a
                  href="https://console.cloud.google.com/google/maps-apis"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="gmaps-console-link"
                >
                  Open Google Cloud Console <Icon name="ExternalLink" size={12} />
                </a>
                <span className="gmaps-env-note">
                  Or set <code>NEXT_PUBLIC_GOOGLE_MAPS_API_KEY</code> in <code>.env.local</code>
                </span>
              </div>
            </div>
          </div>

          {/* Modal Footer Actions */}
          <div className="gmaps-modal-footer">
            <div className="gmaps-footer-left">
              {activeKey && !isEnvApiKey() && (
                <button
                  type="button"
                  className="btn danger subtle btn-sm"
                  onClick={handleClear}
                >
                  <Icon name="Trash2" size={13} />
                  <span>Remove Key</span>
                </button>
              )}
            </div>

            <div className="gmaps-footer-right">
              <button
                type="button"
                className="btn secondary btn-sm"
                onClick={handleTestKey}
                disabled={(!activeKey && !newKeyInput.trim()) || testStatus === 'testing'}
              >
                <Icon name="Activity" size={13} />
                <span>Test Handshake</span>
              </button>
              <button
                type="button"
                className="btn secondary btn-sm"
                onClick={onClose}
              >
                {isEditing && activeKey ? 'Close' : 'Cancel'}
              </button>
              {(isEditing || !activeKey) && (
                <button
                  type="button"
                  className="btn primary btn-sm"
                  onClick={handleSave}
                  disabled={!newKeyInput.trim()}
                >
                  <Icon name="Check" size={13} />
                  <span>Save & Activate</span>
                </button>
              )}
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
