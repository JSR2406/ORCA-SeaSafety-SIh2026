'use client';

import React, { createContext, useContext, useState, useEffect } from 'react';

export const THEMES = [
  { id: 'modern-minimalist', name: 'Modern Minimalist', iconName: 'Sun', desc: 'Crisp Slate & Clean White (Light)', primary: '#0284c7', accent: '#334155' },
  { id: 'ocean-daylight', name: 'Ocean Daylight', iconName: 'SunMedium', desc: 'Sunlit Coastal Teal & Pure White (Light)', primary: '#2d8b8b', accent: '#274156' },
  { id: 'ocean-depths', name: 'Ocean Depths', iconName: 'Waves', desc: 'Deep ocean, luminous seafoam', primary: '#00d9cf', accent: '#a8dadc' },
  { id: 'tech-innovation', name: 'Tech Innovation', iconName: 'Cpu', desc: 'Electric Blue & Neon Cyan (Dark)', primary: '#0066ff', accent: '#00ffff' },
  { id: 'arctic-frost', name: 'Arctic Frost', iconName: 'Snowflake', desc: 'Steel Blue & Ice Silver (Dark)', primary: '#4a6fa5', accent: '#d4e4f7' },
  { id: 'midnight-galaxy', name: 'Midnight Galaxy', iconName: 'Sparkles', desc: 'Cosmic Purple & Lavender (Dark)', primary: '#4a4e8f', accent: '#a490c2' },
];

const ThemeContext = createContext({
  theme: 'ocean-depths',
  setTheme: () => {},
  themes: THEMES,
  activeThemeMeta: THEMES[0]
});

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState('ocean-depths');

  useEffect(() => {
    try {
      const savedTheme = localStorage.getItem('orca-app-theme') || localStorage.getItem('orca-landing-theme');
      if (savedTheme && THEMES.some(t => t.id === savedTheme)) {
        setThemeState(savedTheme);
        document.documentElement.setAttribute('data-theme', savedTheme);
      } else {
        document.documentElement.setAttribute('data-theme', 'ocean-depths');
      }
    } catch (e) {
      console.warn('Theme initialization error:', e);
    }
  }, []);

  const setTheme = (newTheme) => {
    setThemeState(newTheme);
    try {
      localStorage.setItem('orca-app-theme', newTheme);
      localStorage.setItem('orca-landing-theme', newTheme);
      document.documentElement.setAttribute('data-theme', newTheme);
    } catch (e) {
      console.warn('Theme save error:', e);
    }
  };

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.setAttribute('data-theme', theme);
    }
  }, [theme]);

  const activeThemeMeta = THEMES.find(t => t.id === theme) || THEMES[0];

  return (
    <ThemeContext.Provider value={{ theme, setTheme, themes: THEMES, activeThemeMeta }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
