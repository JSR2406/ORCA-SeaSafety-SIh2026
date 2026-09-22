'use client';

import React, { useState } from 'react';
import AppShell from '../components/AppShell';
import Card from '../components/Card';
import SectionHeader from '../components/SectionHeader';
import Badge from '../components/Badge';
import Icon from '../components/Icon';
import { getGoogleMapsApiKey, setGoogleMapsApiKey, maskApiKey, isEnvApiKey } from '../utils/googleMaps';
import { useLanguage } from '../context/LanguageContext';

export default function ProfileSettingsPage() {
  const { language, setLanguage, t, languages } = useLanguage();
  const [activeTab, setActiveTab] = useState('profile');
  const [saved, setSaved] = useState(false);
  const [copiedToken, setCopiedToken] = useState(false);
  const [gmapsKey, setGmapsKey] = useState(() => getGoogleMapsApiKey());
  const [isEditingGmapsKey, setIsEditingGmapsKey] = useState(false);
  const [newGmapsKey, setNewGmapsKey] = useState('');

  const [form, setForm] = useState({
    name: 'Dr. Ananya Kumar',
    org: 'National Institute of Oceanic Studies (NIOS)',
    role: 'Principal Marine Biologist & Coastal Researcher',
    location: 'Kochi Base, Kerala, India',
    lang: 'English (EN)',
    units: 'Metric (°C, m, km/h)',
    radioChannel: 'VHF Channel 16 (International Distress)',
    smsEmergency: true,
    whatsappFleet: true,
    vesselType: '14.2m Mechanized Trawler (380 HP)',
    depthBuffer: 5.0,
    waveRiskThreshold: 2.0,
    autoAvoidNavalZones: true,
    mmsiNumber: '419001248',
    emergencyPhone: '+91 94470 12345',
    navtexFrequency: '518 kHz (English Standard)',
    apiKey: 'inc_live_983a7f20e4bc11e98d71',
    satelliteSecret: 'sat_sec_••••••••••••••••'
  });

  const handleSave = () => {
    if (isEditingGmapsKey && newGmapsKey.trim()) {
      setGoogleMapsApiKey(newGmapsKey.trim());
      setGmapsKey(newGmapsKey.trim());
      setIsEditingGmapsKey(false);
      setNewGmapsKey('');
    }
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  };

  const handleRemoveGmapsKey = () => {
    setGoogleMapsApiKey('');
    setGmapsKey('');
    setIsEditingGmapsKey(false);
    setNewGmapsKey('');
  };


  return (
    <AppShell
      title={t('nav.profileSettings', 'User Profile & Maritime Settings')}
      subtitle="Institutional Credentials, Operational Units & Emergency Alert Routing"
      actions={
        <div className="profile-header-actions">
          <Badge tone="blue">RESEARCHER ACCESS</Badge>
        </div>
      }
    >
      <div className="profile-layout">
        {/* Profile Card Header */}
        <Card className="profile-id-card">
          <div className="profile-id-flex">
            <div className="avatar large profile-avatar-lg">
              <span>AK</span>
              <span className="profile-verified-badge" title="Verified Govt Scientist">✓</span>
            </div>
            <div className="profile-id-text">
              <div className="profile-name-row">
                <h2>{form.name}</h2>
                <Badge tone="green">ACTIVE TELEMETRY LICENSE</Badge>
              </div>
              <span className="profile-role">{form.role}</span>
              <span className="profile-org">{form.org} • {form.location}</span>
            </div>
          </div>
        </Card>

        {/* Settings Navigation Tabs */}
        <div className="tabs-modern" style={{ margin: '14px 0' }}>
          {[
            { key: 'profile', label: 'Researcher Profile', icon: 'User' },
            { key: 'preferences', label: 'Navigational Preferences', icon: 'Sliders' },
            { key: 'notifications', label: 'Emergency Alerts Routing', icon: 'Bell' },
            { key: 'security', label: 'Security & API Keys', icon: 'Shield' }
          ].map((t) => (
            <button
              key={t.key}
              data-testid={`settings-tab-${t.key}`}
              className={`tab-btn ${activeTab === t.key ? 'active' : ''}`}
              onClick={() => setActiveTab(t.key)}
            >
              <Icon name={t.icon} size={13} />
              <span>{t.label}</span>
            </button>
          ))}
        </div>

        {/* Tab 1: Profile Form */}
        {activeTab === 'profile' && (
          <Card className="settings-form-card">
            <SectionHeader
              title="Operational Parameters &amp; Credentials"
              badge="INCOIS CERTIFIED USER"
              icon="Settings"
            />

            <div className="form-grid-modern">
              <label className="settings-field">
                <span className="field-label">FULL LEGAL NAME</span>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                />
              </label>

              <label className="settings-field">
                <span className="field-label">INSTITUTIONAL AFFILIATION</span>
                <input
                  type="text"
                  value={form.org}
                  onChange={(e) => setForm({ ...form, org: e.target.value })}
                />
              </label>

              <label className="settings-field">
                <span className="field-label">COASTAL HOME PORT</span>
                <input
                  type="text"
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                />
              </label>

              <label className="settings-field">
                <span className="field-label">PREFERRED INTERFACE LANGUAGE</span>
                <select
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                >
                  {languages.map((l) => (
                    <option key={l.code} value={l.code}>
                      {l.native} — {l.name} ({l.code.toUpperCase()})
                    </option>
                  ))}
                </select>
              </label>

              <label className="settings-field">
                <span className="field-label">MEASUREMENT UNITS CONVENTION</span>
                <select
                  value={form.units}
                  onChange={(e) => setForm({ ...form, units: e.target.value })}
                >
                  <option value="Metric (°C, m, km/h)">Metric (°C, Wave in Meters, Wind in km/h)</option>
                  <option value="Nautical (°C, m, knots)">Nautical Standard (°C, Wave in Meters, Wind in Knots)</option>
                  <option value="Imperial (°F, ft, mph)">Imperial (°F, Wave in Feet, Wind in mph)</option>
                </select>
              </label>

              <label className="settings-field">
                <span className="field-label">PRIMARY VHF MARITIME CHANNEL</span>
                <input
                  type="text"
                  value={form.radioChannel}
                  onChange={(e) => setForm({ ...form, radioChannel: e.target.value })}
                />
              </label>
            </div>

            <div className="settings-actions-footer">
              <button className="btn primary" onClick={handleSave}>
                <Icon name="Save" size={14} />
                <span>Save Profile Configuration</span>
              </button>
              {saved && (
                <span className="save-success-indicator">
                  <Icon name="CheckCircle" size={14} />
                  <span>Configuration successfully synchronized with central INCOIS profile.</span>
                </span>
              )}
            </div>
          </Card>
        )}

        {/* Tab 2: Navigational Preferences */}
        {activeTab === 'preferences' && (
          <Card className="settings-form-card">
            <SectionHeader
              title="Vessel Hydrodynamics &amp; Routing Guardrails"
              badge="ECDIS POLICIES"
              icon="Compass"
            />

            <div className="form-grid-modern">
              <label className="settings-field">
                <span className="field-label">DEFAULT OPERATIONAL VESSEL</span>
                <select
                  value={form.vesselType}
                  onChange={(e) => setForm({ ...form, vesselType: e.target.value })}
                >
                  <option value="14.2m Mechanized Trawler (380 HP)">14.2m Mechanized Trawler (380 HP • Draft 2.4m)</option>
                  <option value="9.5m Fiber-Reinforced Gillnetter">9.5m Fiber-Reinforced Gillnetter (60 HP • Draft 1.1m)</option>
                  <option value="7.2m Traditional Motorized Canoe">7.2m Traditional Motorized Canoe (9.9 HP • Draft 0.6m)</option>
                  <option value="28.0m Deep-Sea Tuna Longliner">28.0m Deep-Sea Tuna Longliner (750 HP • Draft 3.8m)</option>
                </select>
              </label>

              <label className="settings-field">
                <span className="field-label">MINIMUM SOUNDING DEPTH BUFFER (METERS)</span>
                <input
                  type="number"
                  step="0.5"
                  value={form.depthBuffer}
                  onChange={(e) => setForm({ ...form, depthBuffer: Number(e.target.value) })}
                />
              </label>

              <label className="settings-field">
                <span className="field-label">MAX WAVE HEIGHT CEILING (Hs METERS)</span>
                <input
                  type="number"
                  step="0.1"
                  value={form.waveRiskThreshold}
                  onChange={(e) => setForm({ ...form, waveRiskThreshold: Number(e.target.value) })}
                />
              </label>

              <label className="settings-field checkbox-field">
                <input
                  type="checkbox"
                  checked={form.autoAvoidNavalZones}
                  onChange={(e) => setForm({ ...form, autoAvoidNavalZones: e.target.checked })}
                />
                <div>
                  <b>STRICT GEOFENCE AVOIDANCE</b>
                  <p>Automatically reroute any proposed trajectory around NAVAREA VIII Sector Bravo exercises.</p>
                </div>
              </label>
            </div>

            <div className="settings-actions-footer">
              <button className="btn primary" onClick={handleSave}>
                <Icon name="Save" size={14} />
                <span>Save Routing Parameters</span>
              </button>
              {saved && (
                <span className="save-success-indicator">
                  <Icon name="CheckCircle" size={14} />
                  <span>Navigational rules saved and propagated to Route Planner solver.</span>
                </span>
              )}
            </div>
          </Card>
        )}

        {/* Tab 3: Emergency Alerts Routing */}
        {activeTab === 'notifications' && (
          <Card className="settings-form-card">
            <SectionHeader
              title="Emergency Dispatch &amp; Shore-to-Ship Relays"
              badge="COAST GUARD DISPATCH"
              icon="Bell"
            />

            <div className="form-grid-modern">
              <label className="settings-field">
                <span className="field-label">EMERGENCY SMS DISPATCH NUMBER</span>
                <input
                  type="tel"
                  value={form.emergencyPhone}
                  onChange={(e) => setForm({ ...form, emergencyPhone: e.target.value })}
                />
              </label>

              <label className="settings-field">
                <span className="field-label">VESSEL DIGITAL SELECTIVE CALLING (MMSI)</span>
                <input
                  type="text"
                  value={form.mmsiNumber}
                  onChange={(e) => setForm({ ...form, mmsiNumber: e.target.value })}
                />
              </label>

              <label className="settings-field">
                <span className="field-label">NAVTEX RECEIVER FREQUENCY CHANNEL</span>
                <select
                  value={form.navtexFrequency}
                  onChange={(e) => setForm({ ...form, navtexFrequency: e.target.value })}
                >
                  <option value="518 kHz (English Standard)">518 kHz (International Standard English)</option>
                  <option value="490 kHz (Vernacular Malayalam)">490 kHz (National Vernacular Malayalam)</option>
                  <option value="4209.5 kHz (High Frequency Marine)">4209.5 kHz (High Frequency Long-Range Marine)</option>
                </select>
              </label>

              <label className="settings-field checkbox-field">
                <input
                  type="checkbox"
                  checked={form.smsEmergency}
                  onChange={(e) => setForm({ ...form, smsEmergency: e.target.checked })}
                />
                <div>
                  <b>INSTANT HIGH SWELL &amp; TSUNAMI SMS DISPATCH</b>
                  <p>Receive immediate automated SMS whenever swell Hs exceeds 2.2m within 30 NM of home port.</p>
                </div>
              </label>

              <label className="settings-field checkbox-field">
                <input
                  type="checkbox"
                  checked={form.whatsappFleet}
                  onChange={(e) => setForm({ ...form, whatsappFleet: e.target.checked })}
                />
                <div>
                  <b>KOCHI HARBOUR FLEET WHATSAPP BROADCAST</b>
                  <p>Forward INCOIS verified PFZ daily coordinates to registered coastal skippers group.</p>
                </div>
              </label>
            </div>

            <div className="settings-actions-footer">
              <button className="btn primary" onClick={handleSave}>
                <Icon name="Save" size={14} />
                <span>Save Notification Rules</span>
              </button>
              {saved && (
                <span className="save-success-indicator">
                  <Icon name="CheckCircle" size={14} />
                  <span>Distress routing credentials updated with Coast Guard MRCC Kochi.</span>
                </span>
              )}
            </div>
          </Card>
        )}

        {/* Tab 4: Security & API Keys */}
        {activeTab === 'security' && (
          <Card className="settings-form-card">
            <SectionHeader
              title="API Authentication &amp; Telemetry Feed Keys"
              badge="RBAC LEVEL 4"
              icon="Shield"
            />

            <div className="form-grid-modern">
              <label className="settings-field">
                <span className="field-label">INCOIS SECURE REST API BEARER TOKEN</span>
                <div className="api-key-input-row">
                  <input type="text" readOnly value={form.apiKey} />
                  <button
                    type="button"
                    className="btn secondary btn-sm"
                    onClick={() => {
                      navigator.clipboard?.writeText(form.apiKey);
                      setCopiedToken(true);
                      setTimeout(() => setCopiedToken(false), 2000);
                    }}
                  >
                    {copiedToken ? '✓ Copied' : 'Copy'}
                  </button>
                </div>
              </label>

              <label className="settings-field">
                <span className="field-label">ISRO MOSDAC SATELLITE INGESTION SECRET</span>
                <input type="password" readOnly value={form.satelliteSecret} />
              </label>

              <div className="settings-field">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                  <span className="field-label">GOOGLE MAPS PLATFORM API KEY</span>
                  <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                    {gmapsKey.trim() && (
                      <Badge tone="cyan">{isEnvApiKey() ? '🔒 ENV MANAGED' : '🔒 PROTECTED'}</Badge>
                    )}
                    <Badge tone={gmapsKey.trim() ? 'green' : 'amber'}>
                      {gmapsKey.trim() ? 'HIGH-RES SATELLITE ACTIVE' : 'OPEN MARITIME FALLBACK'}
                    </Badge>
                  </div>
                </div>

                {gmapsKey.trim() && !isEditingGmapsKey ? (
                  <div className="gmaps-protected-key-card settings-card-style">
                    <div className="protected-key-header">
                      <div className="protected-key-title-row">
                        <Icon name="ShieldCheck" size={15} className="protected-key-shield-icon" />
                        <code className="protected-key-code">{maskApiKey(gmapsKey)}</code>
                      </div>
                      {!isEnvApiKey() && (
                        <div style={{ display: 'flex', gap: '6px' }}>
                          <button
                            type="button"
                            className="btn secondary btn-xs"
                            onClick={() => {
                              setIsEditingGmapsKey(true);
                              setNewGmapsKey('');
                            }}
                          >
                            <Icon name="Edit3" size={12} />
                            <span>Replace</span>
                          </button>
                          <button
                            type="button"
                            className="btn danger subtle btn-xs"
                            onClick={handleRemoveGmapsKey}
                            title="Remove API Key"
                          >
                            <Icon name="Trash2" size={12} />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="api-key-input-row">
                    <input
                      type="password"
                      placeholder={gmapsKey.trim() ? "Enter new AIzaSy... API key" : "Paste your AIzaSy... Google Maps API key"}
                      value={newGmapsKey}
                      onChange={(e) => setNewGmapsKey(e.target.value)}
                      autoComplete="off"
                      spellCheck="false"
                    />
                    {gmapsKey.trim() && (
                      <button
                        type="button"
                        className="btn secondary btn-sm"
                        onClick={() => {
                          setIsEditingGmapsKey(false);
                          setNewGmapsKey('');
                        }}
                      >
                        Cancel
                      </button>
                    )}
                  </div>
                )}
                <p style={{ fontSize: '11px', color: 'var(--c-text-muted)', marginTop: '4px' }}>
                  {isEnvApiKey()
                    ? 'Injected securely via environment variables. Plaintext extraction is blocked.'
                    : 'Unlocks Google Satellite Hybrid, Roadmap & Coastal Places. Plaintext key is never exposed.'}
                </p>
              </div>

              <div className="security-sessions-box">
                <span className="sec-sessions-title">AUTHORIZED ACTIVE SESSIONS:</span>
                <div className="sec-session-item">
                  <div className="session-icon">💻</div>
                  <div className="session-info">
                    <b>Kochi Marine Ops Workstation (Linux 6.8 • 192.168.10.42)</b>
                    <span>Active Now • Authenticated via Kerberos Institutional SSO</span>
                  </div>
                  <Badge tone="green">CURRENT</Badge>
                </div>
                <div className="sec-session-item">
                  <div className="session-icon">📱</div>
                  <div className="session-info">
                    <b>Skipper Handheld PWA (Chrome on Android 14)</b>
                    <span>Last heartbeat 18m ago • Token expires in 14 days</span>
                  </div>
                  <Badge tone="blue">OFFLINE CAPABLE</Badge>
                </div>
              </div>
            </div>

            <div className="settings-actions-footer">
              <button className="btn primary" onClick={handleSave}>
                <Icon name="Save" size={14} />
                <span>Synchronize Security Credentials</span>
              </button>
              {saved && (
                <span className="save-success-indicator">
                  <Icon name="CheckCircle" size={14} />
                  <span>Security access tokens rotated and validated.</span>
                </span>
              )}
            </div>
          </Card>
        )}
      </div>
    </AppShell>
  );
}
