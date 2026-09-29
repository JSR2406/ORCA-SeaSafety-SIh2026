'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import Logo from '../components/Logo';
import Icon from '../components/Icon';
import Badge from '../components/Badge';
import { useTheme } from '../context/ThemeContext';
import { useUserRole } from '../context/UserRoleContext';

export default function LoginPage() {
  const router = useRouter();
  const { theme, setTheme, themes, activeThemeMeta } = useTheme();
  const { setActiveRole } = useUserRole();

  const [role, setRole] = useState('researcher');
  const [email, setEmail] = useState('ananya.kumar@nios.res.in');
  const [password, setPassword] = useState('••••••••••••');
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [themeDropdownOpen, setThemeDropdownOpen] = useState(false);

  const ROLE_CONFIGS = {
    researcher: {
      title: 'Marine Scientist',
      email: 'ananya.kumar@nios.res.in',
      org: 'National Institute of Oceanic Studies (NIOS)',
      badge: 'SCIENTIFIC GIS ACCESS',
      icon: 'FlaskConical',
      redirect: '/dashboard'
    },
    fisherman: {
      title: 'Vessel Skipper',
      email: 'skipper.rajesh@coastal.kerala.gov.in',
      org: 'Kochi Harbour Trawler Association',
      badge: 'TACTICAL SKIPPER PWA',
      icon: 'Anchor',
      redirect: '/mobile'
    },
    coastguard: {
      title: 'Port Authority',
      email: 'officer.menon@indiancoastguard.nic.in',
      org: 'MRCC Kochi • Western Naval Command',
      badge: 'SAR & DISPATCH CLEARANCE',
      icon: 'Shield',
      redirect: '/safety'
    }
  };

  const handleRoleSelect = (selectedRole) => {
    setRole(selectedRole);
    setEmail(ROLE_CONFIGS[selectedRole].email);
  };

  // Login tabs → dashboard role keys (Port Authority signs in as government).
  const LOGIN_TO_APP_ROLE = { researcher: 'researcher', fisherman: 'fisherman', coastguard: 'government' };

  const signInAs = (loginRole) => {
    const appRole = LOGIN_TO_APP_ROLE[loginRole] || 'fisherman';
    try { setActiveRole(appRole); } catch {}
    try { localStorage.setItem('orca_active_role', appRole); } catch {}
    router.push(ROLE_CONFIGS[loginRole].redirect);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setTimeout(() => {
      signInAs(role);
    }, 450);
  };

  return (
    <div className="login-page-modern">
      {/* Top Floating Utilities: Back to Landing & Live Theme Selector */}
      <div className="login-top-floating-bar">
        <Link href="/" className="login-back-home-btn" title="Return to Portal Landing">
          <Icon name="ArrowLeft" size={14} />
          <span>Return to Portal</span>
        </Link>

        <div className="login-theme-selector-wrap">
          <button
            type="button"
            className="login-theme-toggle-btn"
            onClick={() => setThemeDropdownOpen(!themeDropdownOpen)}
            title={`Active Theme: ${activeThemeMeta.name}`}
          >
            <span className="theme-toggle-dot" style={{ background: activeThemeMeta.primary }} />
            <span className="theme-toggle-label">{activeThemeMeta.name}</span>
            <Icon name="Palette" size={13} />
          </button>

          <AnimatePresence>
            {themeDropdownOpen && (
              <motion.div
                className="login-theme-dropdown"
                initial={{ opacity: 0, y: 6, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 4, scale: 0.95 }}
                transition={{ duration: 0.15 }}
              >
                <div className="theme-dropdown-header">APPLICATION PALETTE</div>
                {themes.map((t) => (
                  <button
                    key={t.id}
                    type="button"
                    className={`theme-dropdown-opt ${theme === t.id ? 'active' : ''}`}
                    onClick={() => {
                      setTheme(t.id);
                      setThemeDropdownOpen(false);
                    }}
                  >
                    <span className="opt-dot" style={{ background: t.primary }} />
                    <span className="opt-name">{t.name}</span>
                    {theme === t.id && <Icon name="Check" size={12} className="opt-check" />}
                  </button>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Left Column: Maritime Ocean Hologram & Mission Briefing */}
      <motion.div
        className="login-brand-side"
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="brand-side-top">
          <Link href="/" className="brand-logo-link">
            <Logo />
          </Link>
          <div className="telemetry-live-badge">
            <span className="live-dot" />
            <span>Kochi Coastal Radar AD04 • INCOIS Synced</span>
          </div>
        </div>

        {/* Animated Cyber-Oceanic Radar Hologram */}
        <div className="login-hologram-stage">
          <div className="radar-compass-ring" />
          <div className="radar-grid-ring r3" />
          <div className="radar-grid-ring r2" />
          <div className="radar-grid-ring r1" />
          <div className="radar-crosshair-h" />
          <div className="radar-crosshair-v" />
          <div className="radar-sweep-beam" />

          {/* Tactical Radar Blips */}
          <div className="radar-blip blip-hq" title="Kochi Harbour Base HQ">
            <span className="blip-pulse" />
            <span className="blip-core" />
            <span className="blip-tag">HQ KOCHI</span>
          </div>

          <div className="radar-blip blip-pfz" title="PFZ-01 High Potential Front">
            <span className="blip-pulse pfz-pulse" />
            <span className="blip-core pfz-core" />
            <span className="blip-tag">PFZ-01 FRONT</span>
          </div>

          <div className="radar-blip blip-vessel" title="F/V Matsya-04 (MMSI: 419001248)">
            <span className="blip-pulse vessel-pulse" />
            <span className="blip-core vessel-core" />
            <span className="blip-tag">MATSYA-04 • 9.8 kts</span>
          </div>

          <div className="radar-blip blip-buoy" title="Cochin Fairway Buoy">
            <span className="blip-core buoy-core" />
            <span className="blip-tag">FAIRWAY BUOY</span>
          </div>

          {/* Real-time Telemetry Floating HUD Strip */}
          <div className="hologram-telemetry-hud">
            <div className="hud-metric">
              <span className="hud-lbl">SST ANALYZED</span>
              <span className="hud-val">28.4 °C</span>
            </div>
            <div className="hud-metric-sep" />
            <div className="hud-metric">
              <span className="hud-lbl">CHLOROPHYLL</span>
              <span className="hud-val">0.88 mg/m³</span>
            </div>
            <div className="hud-metric-sep" />
            <div className="hud-metric">
              <span className="hud-lbl">SIGNIFICANT WAVE</span>
              <span className="hud-val safe">1.4 m Hs</span>
            </div>
            <div className="hud-metric-sep" />
            <div className="hud-metric">
              <span className="hud-lbl">COASTAL WIND</span>
              <span className="hud-val">14 kts NW</span>
            </div>
          </div>
        </div>

        {/* Mission Statement */}
        <div className="brand-side-bottom">
          <div className="brand-eyebrow-tag">
            <Icon name="Radio" size={12} />
            <span>NATIONAL MARITIME DECISION SUPPORT SYSTEM</span>
          </div>
          <h2>Precision Intelligence for Indian Coastal Waters.</h2>
          <p>
            Bridging oceanic telemetry from satellites, wave rider buoys, and HF radar directly to coastal skippers and scientists — delivering verified Potential Fishing Zones, emergency safety advisories, and weather routing.
          </p>
          <div className="brand-partners-tag">
            <span>INCOIS Hyderabad • IMD Mausam Bhavan • National Hydrographic Office • Coast Guard MRCC</span>
          </div>
        </div>
      </motion.div>

      {/* Right Column: High-End Authentication Card */}
      <motion.div
        className="login-form-side"
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="login-card-modern">
          {/* Card Header */}
          <div className="login-card-header">
            <div className="login-auth-badge">
              <Icon name="ShieldCheck" size={13} />
              <span>SECURE ACCESS • GOV.IN CAS</span>
            </div>
            <h1>Sign In to ORCA</h1>
            <p>Select your operational maritime role to load institutional clearance.</p>
          </div>

          {/* Interactive Role Switcher Tabs */}
          <div className="login-role-tabs">
            {Object.entries(ROLE_CONFIGS).map(([key, config]) => {
              const isSelected = role === key;
              return (
                <button
                  key={key}
                  type="button"
                  className={`role-tab-btn ${isSelected ? 'active' : ''}`}
                  onClick={() => handleRoleSelect(key)}
                >
                  <div className="role-tab-icon-wrap">
                    <Icon name={config.icon} size={16} />
                  </div>
                  <div className="role-tab-text">
                    <span className="role-tab-title">{config.title}</span>
                    <span className="role-tab-desc">{key === 'researcher' ? 'Full GIS' : key === 'fisherman' ? 'Mobile PWA' : 'SAR / Port'}</span>
                  </div>
                  {isSelected && <span className="role-active-dot" />}
                </button>
              );
            })}
          </div>

          {/* Active Role Meta Card */}
          <div className="active-role-pill-banner">
            <div className="banner-left">
              <span className="banner-org">{ROLE_CONFIGS[role].org}</span>
              <span className="banner-title">{ROLE_CONFIGS[role].badge}</span>
            </div>
            <Badge tone={role === 'coastguard' ? 'amber' : 'blue'}>
              {role.toUpperCase()}
            </Badge>
          </div>

          {/* Credentials Form */}
          <form onSubmit={handleSubmit} className="login-actual-form">
            <label className="login-input-label">
              <span className="field-title">OFFICIAL EMAIL ADDRESS</span>
              <div className="login-input-wrap">
                <Icon name="Mail" size={15} className="input-glyph" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@institution.res.in"
                  required
                  autoComplete="username"
                />
              </div>
            </label>

            <label className="login-input-label">
              <div className="pwd-label-row">
                <span className="field-title">ACCOUNT PASSWORD</span>
                <a href="#forgot" onClick={(e) => { e.preventDefault(); alert('Demo environment: Simply click "Sign In to Dashboard" to enter.'); }} className="forgot-link">
                  Forgot credentials?
                </a>
              </div>
              <div className="login-input-wrap">
                <Icon name="Lock" size={15} className="input-glyph" />
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="pwd-toggle-btn"
                  onClick={() => setShowPassword(!showPassword)}
                  title={showPassword ? 'Hide password' : 'Show password'}
                >
                  <Icon name={showPassword ? 'EyeOff' : 'Eye'} size={15} />
                </button>
              </div>
            </label>

            {/* Remember & Institutional Session Options */}
            <div className="login-options-row">
              <label className="remember-checkbox-label">
                <input
                  type="checkbox"
                  checked={rememberMe}
                  onChange={(e) => setRememberMe(e.target.checked)}
                />
                <span>Persist 30-day clearance</span>
              </label>
              <span className="clearance-tag">FIPS 140-3 Compliant</span>
            </div>

            {/* Main Submit Action Button */}
            <button
              type="submit"
              className="btn primary wide btn-lg login-submit-btn"
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <>
                  <Icon name="RefreshCw" size={15} className="spin-icon" />
                  <span>Authenticating Credentials...</span>
                </>
              ) : (
                <>
                  <span>Sign In as {ROLE_CONFIGS[role].title}</span>
                  <Icon name="ArrowRight" size={15} />
                </>
              )}
            </button>
          </form>

          {/* Quick Demo Access Bar for SIH Evaluation Judges */}
          <div className="quick-demo-access-box">
            <div className="demo-box-header">
              <Icon name="Zap" size={12} />
              <span className="demo-box-label">QUICK DEMO ACCESS (FOR SIH EVALUATION):</span>
            </div>
            <div className="demo-buttons-row">
              <button
                type="button"
                className="demo-quick-btn skipper"
                onClick={() => signInAs('fisherman')}
              >
                <Icon name="Smartphone" size={13} />
                <span><b>Skipper Rajesh</b> (Vessel Skipper)</span>
              </button>
              <button
                type="button"
                className="demo-quick-btn scientist"
                onClick={() => signInAs('researcher')}
              >
                <Icon name="LayoutDashboard" size={13} />
                <span><b>Dr. Ananya</b> (Oceanographer)</span>
              </button>
              <button
                type="button"
                className="demo-quick-btn authority"
                onClick={() => {
                  try { setActiveRole('government'); } catch {}
                  try { localStorage.setItem('orca_active_role', 'government'); } catch {}
                  router.push('/safety');
                }}
              >
                <Icon name="Shield" size={13} />
                <span><b>Officer Menon</b> (Port Authority)</span>
              </button>
              <button
                type="button"
                className="demo-quick-btn fleet"
                onClick={() => {
                  try { setActiveRole('maritime'); } catch {}
                  try { localStorage.setItem('orca_active_role', 'maritime'); } catch {}
                  router.push('/dashboard');
                }}
              >
                <Icon name="Navigation" size={13} />
                <span><b>Capt. Rao</b> (Fleet Ops)</span>
              </button>
              <button
                type="button"
                className="demo-quick-btn admin"
                onClick={() => {
                  try { setActiveRole('admin'); } catch {}
                  try { localStorage.setItem('orca_active_role', 'admin'); } catch {}
                  router.push('/dashboard');
                }}
              >
                <Icon name="Settings" size={13} />
                <span><b>Aditya</b> (Platform Admin)</span>
              </button>
            </div>
          </div>

          {/* Footer Guest Link */}
          <div className="login-footer-text">
            <span>Need institutional clearance? </span>
            <Link href="/dashboard" className="guest-link">
              <b>Continue as Public Maritime Observer</b>
              <Icon name="ChevronRight" size={13} />
            </Link>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
