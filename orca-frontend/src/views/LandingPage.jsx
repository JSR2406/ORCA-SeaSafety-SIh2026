'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowRight,
  Compass,
  Waves,
  ShieldCheck,
  Activity,
  Radio,
  Globe,
  Sparkles,
  Smartphone,
  GitBranch,
  FlaskConical,
  Zap,
  Snowflake,
  Moon,
  Sun,
  SunMedium,
  Menu,
  X,
  Palette,
  Check
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useLanguage } from '../context/LanguageContext';
import Logo from '../components/Logo';
import MarineMap from '../components/DynamicMarineMap';

const THEMES = [
  { id: 'modern-minimalist', name: 'Modern Minimalist', icon: Sun, desc: 'Crisp Slate & Clean White (Light)' },
  { id: 'ocean-daylight', name: 'Ocean Daylight', icon: SunMedium, desc: 'Sunlit Coastal Teal & Pure White (Light)' },
  { id: 'ocean-depths', name: 'Ocean Depths', icon: Waves, desc: 'Deep Navy & Seafoam (Dark)' },
  { id: 'tech-innovation', name: 'Tech Innovation', icon: Zap, desc: 'Electric Blue & Neon Cyan (Dark)' },
  { id: 'arctic-frost', name: 'Arctic Frost', icon: Snowflake, desc: 'Steel Blue & Ice Silver (Dark)' },
  { id: 'midnight-galaxy', name: 'Midnight Galaxy', icon: Moon, desc: 'Deep Purple & Cosmic Blue (Dark)' }
];

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.08,
      delayChildren: 0.04
    }
  }
};

const fadeUpVariants = {
  hidden: { opacity: 0, y: 16 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1] }
  }
};

export default function LandingPage() {
  const { theme: currentTheme, setTheme: setCurrentTheme } = useTheme();
  const { language, setLanguage, t, languages } = useLanguage();
  const [themeDropdownOpen, setThemeDropdownOpen] = useState(false);
  const [langDropdownOpen, setLangDropdownOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const activeThemeObj = THEMES.find((t) => t.id === currentTheme) || THEMES[0];
  const ThemeIcon = activeThemeObj.icon;

  return (
    <div className="gov-landing-root" data-theme={currentTheme}>
      {/* Ambient Animated Glowing Canvas */}
      <div className="landing-ambient-canvas" aria-hidden="true">
        <motion.div
          className="ambient-orb orb-1"
          animate={{
            x: [0, 45, -30, 0],
            y: [0, -35, 25, 0],
            scale: [1, 1.12, 0.92, 1]
          }}
          transition={{
            duration: 18,
            repeat: Infinity,
            ease: 'easeInOut'
          }}
        />
        <motion.div
          className="ambient-orb orb-2"
          animate={{
            x: [0, -40, 30, 0],
            y: [0, 40, -30, 0],
            scale: [1, 0.9, 1.1, 1]
          }}
          transition={{
            duration: 22,
            repeat: Infinity,
            ease: 'easeInOut'
          }}
        />
        <motion.div
          className="ambient-orb orb-3"
          animate={{
            x: [0, 30, -30, 0],
            y: [0, -25, 30, 0],
            scale: [1, 1.1, 0.95, 1]
          }}
          transition={{
            duration: 25,
            repeat: Infinity,
            ease: 'easeInOut'
          }}
        />
        <div className="ambient-grid-overlay" />
      </div>

      {/* Top Institutional Telemetry Ribbon */}
      <div className="gov-masthead">
        <div className="masthead-inner">
          <div className="masthead-agency">
            <span className="live-status-dot" />
            <span className="masthead-agency-text">
              MINISTRY OF EARTH SCIENCES • INCOIS TELEMETRY PARTNER
            </span>
          </div>
          <div className="masthead-status">
            <span>ARABIAN SEA SECTOR 4</span>
            <span className="spec-sep">•</span>
            <span>FEED SYNCHRONIZED 10Hz</span>
          </div>
        </div>
      </div>

      {/* Main Glass Navigation Bar */}
      <motion.header
        className="gov-nav-bar"
        initial={{ opacity: 0, y: -8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35 }}
      >
        <div className="nav-bar-inner">
          <Logo />

          {/* Desktop Nav Links */}
          <nav className="nav-links-clean desktop-only">
            <a href="#capabilities">{t('nav.capabilities', 'Capabilities')}</a>
            <Link href="/marine-map">{t('nav.marineMap', 'Nautical Chart')}</Link>
            <Link href="/ai-copilot">{t('nav.copilot', 'AI Copilot')}</Link>
            <Link href="/safety">{t('nav.safety', 'Safety Alerts')}</Link>
            <Link href="/fishing">{t('nav.fishing', 'Fishing Zones')}</Link>
          </nav>

          {/* Nav Actions & Theme / Language Switcher */}
          <div className="nav-actions-clean">
            {/* Language Switcher Dropdown */}
            <div className="theme-switcher-wrap">
              <button
                type="button"
                className="theme-switcher-btn"
                onClick={() => {
                  setLangDropdownOpen((prev) => !prev);
                  setThemeDropdownOpen(false);
                }}
                aria-label="Select interface language"
                title="Select Language"
              >
                <Globe size={14} className="theme-btn-icon" />
                <span className="theme-btn-label">{languages.find((l) => l.code === language)?.native || 'EN'}</span>
              </button>

              <AnimatePresence>
                {langDropdownOpen && (
                  <motion.div
                    className="theme-dropdown-menu"
                    initial={{ opacity: 0, y: 8, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 6, scale: 0.96 }}
                    transition={{ duration: 0.18 }}
                  >
                    <div className="theme-dropdown-title">SELECT LANGUAGE / भाषा</div>
                    {languages.map((l) => {
                      const isSelected = language === l.code;
                      return (
                        <button
                          key={l.code}
                          type="button"
                          className={`theme-option-row ${isSelected ? 'selected' : ''}`}
                          onClick={() => {
                            setLanguage(l.code);
                            setLangDropdownOpen(false);
                          }}
                        >
                          <div className="theme-row-left">
                            <span style={{ fontSize: '15px', lineHeight: 1 }}>{l.flag}</span>
                            <div className="theme-row-info">
                              <span className="theme-row-name">{l.native}</span>
                              <span className="theme-row-desc">{l.name} ({l.code.toUpperCase()})</span>
                            </div>
                          </div>
                          {isSelected && <Check size={14} className="theme-check-icon" />}
                        </button>
                      );
                    })}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Theme Switcher Dropdown */}
            <div className="theme-switcher-wrap">
              <button
                type="button"
                className="theme-switcher-btn"
                onClick={() => {
                  setThemeDropdownOpen((prev) => !prev);
                  setLangDropdownOpen(false);
                }}
                aria-label="Select visual theme"
                title={`Current Theme: ${activeThemeObj.name}`}
              >
                <ThemeIcon size={14} className="theme-btn-icon" />
                <span className="theme-btn-label">{activeThemeObj.name}</span>
                <Palette size={12} className="theme-palette-icon" />
              </button>

              <AnimatePresence>
                {themeDropdownOpen && (
                  <motion.div
                    className="theme-dropdown-menu"
                    initial={{ opacity: 0, y: 8, scale: 0.96 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: 6, scale: 0.96 }}
                    transition={{ duration: 0.18 }}
                  >
                    <div className="theme-dropdown-title">THEME FACTORY PALETTES</div>
                    {THEMES.map((theme) => {
                      const IconC = theme.icon;
                      const isSelected = currentTheme === theme.id;
                      return (
                        <button
                          key={theme.id}
                          type="button"
                          className={`theme-option-row ${isSelected ? 'selected' : ''}`}
                          onClick={() => {
                            setCurrentTheme(theme.id);
                            setThemeDropdownOpen(false);
                          }}
                        >
                          <div className="theme-row-left">
                            <div className="theme-row-info">
                              <span className="theme-row-name">{theme.name}</span>
                              <span className="theme-row-desc">{theme.desc}</span>
                            </div>
                          </div>
                          {isSelected && <Check size={14} className="theme-check-icon" />}
                        </button>
                      );
                    })}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Desktop Actions */}
            <Link href="/login" className="btn-clean-ghost desktop-only">
              {t('common.login', 'Sign In')}
            </Link>
            <Link href="/dashboard" className="btn-clean-primary desktop-only">
              {t('dashboard.headerTitle', 'Launch Console')}
            </Link>

            {/* Mobile Hamburger Button */}
            <button
              type="button"
              className="mobile-hamburger-btn mobile-only"
              onClick={() => setMobileMenuOpen((prev) => !prev)}
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>

        {/* Mobile Dropdown Drawer */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              className="mobile-nav-drawer"
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.25 }}
            >
              <div className="mobile-drawer-inner">
                <nav className="mobile-drawer-links">
                  <a href="#capabilities" onClick={() => setMobileMenuOpen(false)}>
                    Capabilities
                  </a>
                  <Link href="/marine-map" onClick={() => setMobileMenuOpen(false)}>
                    Nautical Chart
                  </Link>
                  <Link href="/ai-copilot" onClick={() => setMobileMenuOpen(false)}>
                    AI Copilot
                  </Link>
                  <Link href="/safety" onClick={() => setMobileMenuOpen(false)}>
                    Safety Alerts
                  </Link>
                  <Link href="/fishing" onClick={() => setMobileMenuOpen(false)}>
                    Fishing Zones
                  </Link>
                </nav>

                <div className="mobile-drawer-actions">
                  <Link
                    to="/dashboard"
                    className="btn-command-primary w-full"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <span>Launch Tactical Console</span>
                    <ArrowRight size={15} />
                  </Link>
                  <Link
                    to="/login"
                    className="btn-command-secondary w-full"
                    onClick={() => setMobileMenuOpen(false)}
                  >
                    <span>Institutional Sign In</span>
                  </Link>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.header>

      {/* Hero Section */}
      <section className="gov-hero-section">
        <div className="gov-hero-container">
          {/* Hero Left Content */}
          <motion.div
            className="hero-technical-copy"
            variants={containerVariants}
            initial="hidden"
            animate="visible"
          >
            <motion.div variants={fadeUpVariants} className="hero-spec-tag">
              <Sparkles size={13} className="hero-sparkle" />
              <span>ORCA COGNITIVE ENGINE • v2.6</span>
              <span className="spec-sep">/</span>
              <span>{activeThemeObj.name.toUpperCase()}</span>
            </motion.div>

            <motion.h1 variants={fadeUpVariants} className="hero-command-heading">
              Autonomous Maritime Intelligence &amp; Voyage Safety.
            </motion.h1>

            <motion.p variants={fadeUpVariants} className="hero-lead-text">
              Real-time hydrodynamic fusion, deterministic hazard verification, and vernacular voice guidance built for coastal mariners and fleet operations.
            </motion.p>

            <motion.div variants={fadeUpVariants} className="hero-action-buttons">
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="hero-btn-wrap">
                <Link href="/dashboard" className="btn-command-primary">
                  <span>Enter Tactical Console</span>
                  <ArrowRight size={15} />
                </Link>
              </motion.div>
              <motion.div whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }} className="hero-btn-wrap">
                <Link href="/marine-map" className="btn-command-secondary">
                  <Compass size={15} />
                  <span>Open Nautical Chart</span>
                </Link>
              </motion.div>
            </motion.div>

            {/* Institutional Trust Indicator */}
            <motion.div variants={fadeUpVariants} className="hero-trust-indicator">
              <span className="live-status-dot" />
              <span>Data Governance: INCOIS Hyderabad &amp; IMD Mausam Bhavan</span>
            </motion.div>
          </motion.div>

          {/* Hero Right Tactical Monitor Display */}
          <motion.div
            className="hero-tactical-display"
            initial={{ opacity: 0, scale: 0.97, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.55, delay: 0.15, ease: [0.22, 1, 0.36, 1] }}
          >
            <div className="display-window-chrome">
              <span className="window-title">Kochi Coastal Sector 4 • Real-Time Operations</span>
              <span className="window-telemetry-badge">10Hz LIVE</span>
            </div>

            <div className="display-window-content">
              {/* Operational Verdict Strip */}
              <div className="display-status-bar">
                <div className="status-metric-col">
                  <span className="ds-label">OPERATIONAL VERDICT:</span>
                  <strong className="ds-val text-caution">MODERATE RISK (0.61)</strong>
                </div>
                <div className="status-metric-col">
                  <span className="ds-label">RECOMMENDED ROUTE:</span>
                  <strong className="ds-val text-safe">ROUTE B (FAIRWAY VIA BUOY RW)</strong>
                </div>
              </div>

              {/* Interactive Cartography Preview */}
              <div className="display-chart-preview-real">
                <MarineMap showControls={false} />
              </div>

              {/* Bottom Summary Strip */}
              <div className="display-summary-strip">
                <span><b>Wind:</b> 18 km/h @ 065° ENE</span>
                <span className="spec-sep">•</span>
                <span><b>Swell:</b> 1.4m @ 11.8s</span>
                <span className="spec-sep">•</span>
                <span><b>Route B:</b> Clear of NAVAREA VIII</span>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Engineering Capabilities / Pillars Section */}
      <section id="capabilities" className="gov-pillars-section">
        <div className="pillars-container">
          <motion.div
            className="section-head-clean"
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true, margin: '-40px' }}
            transition={{ duration: 0.45 }}
          >
            <span className="section-kicker">CORE CAPABILITIES</span>
            <h2>Deterministic Maritime Intelligence</h2>
            <p>
              Physical hydrodynamic modeling and hard-rule maritime guardrails replace probabilistic guesswork with verified nautical decisions.
            </p>
          </motion.div>

          <div className="pillars-grid">
            {[
              {
                icon: Waves,
                num: '01',
                title: 'Hydrodynamic Fusion',
                desc: 'Coupled wave, swell, and surface temperature telemetry continuously ingested from MoES moored buoys, SAR satellites, and Doppler radar.',
                badge: 'Physical Hydrodynamics'
              },
              {
                icon: ShieldCheck,
                num: '02',
                title: 'Deterministic Safety & Routing',
                desc: 'Hard-rule maritime guardrails cross-reference trajectories against active NAVAREA VIII military zones and bathymetric shoals with zero hallucination.',
                badge: 'Certified Safe Corridors'
              },
              {
                icon: Radio,
                num: '03',
                title: 'Vernacular Outreach',
                desc: 'Automated native voice synthesizers deliver time-critical sea state advisories across 14 coastal Indian languages over VHF marine radio and mobile PWA.',
                badge: '14 Coastal Indian Languages'
              }
            ].map((pillar, idx) => {
              const IconComp = pillar.icon;
              return (
                <motion.div
                  key={pillar.num}
                  className="pillar-item"
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, margin: '-30px' }}
                  transition={{ duration: 0.4, delay: idx * 0.08 }}
                  whileHover={{ y: -5, transition: { duration: 0.2 } }}
                >
                  <div className="pillar-top-row">
                    <div className="pillar-icon-box">
                      <IconComp size={18} />
                    </div>
                    <span className="pillar-num">{pillar.num}</span>
                  </div>
                  <h3>{pillar.title}</h3>
                  <p>{pillar.desc}</p>
                  <div className="pillar-footer">
                    <code>{pillar.badge}</code>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Streamlined Tactical CTA Strip */}
      <section className="gov-cta-section">
        <motion.div
          className="gov-cta-card"
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.45 }}
          whileHover={{ y: -3, transition: { duration: 0.2 } }}
        >
          <div className="gov-cta-content">
            <h3>Ready for Mission-Critical Coastal Operations?</h3>
            <p>Access the tactical command console, electronic nautical cartography, and real-time telemetry.</p>
          </div>
          <Link href="/dashboard" className="btn-command-primary">
            <span>Enter Tactical Console</span>
            <ArrowRight size={15} />
          </Link>
        </motion.div>
      </section>

      {/* Minimal Footer */}
      <footer className="gov-footer">
        <div className="gov-footer-inner">
          <div className="footer-agency-col">
            <Logo />
            <p className="footer-agency-desc">
              National Oceanic &amp; Regional Cognitive Assistant (ORCA). High-reliability maritime decision support for Indian coastal waters.
            </p>
            <div className="footer-gov-credits">
              <span>Data Governance: INCOIS Hyderabad • IMD Mausam Bhavan • National Hydrographic Office Dehradun</span>
            </div>
          </div>

          <div className="footer-links-col">
            <div className="footer-link-group">
              <b>OPERATIONAL SUITE</b>
              <Link href="/marine-map">Nautical Chart (ENC)</Link>
              <Link href="/dashboard">Tactical Operations HQ</Link>
              <Link href="/ai-copilot">Cognitive Decision Copilot</Link>
              <Link href="/fishing">PFZ Fishery Intelligence</Link>
            </div>

            <div className="footer-link-group">
              <b>SAFETY &amp; POLICY</b>
              <Link href="/safety">NAVAREA VIII Center</Link>
              <Link href="/routes">Navigational Fairways</Link>
              <Link href="/scenarios">Hazard Simulator</Link>
              <Link href="/system-health">Infrastructure Telemetry</Link>
            </div>
          </div>
        </div>

        <div className="footer-legal-bar">
          <span>© 2026 ORCA Marine Intelligence Initiative. All rights reserved.</span>
          <span>Deterministic Decision Support System • Built for SIH 2026</span>
        </div>
      </footer>
    </div>
  );
}
