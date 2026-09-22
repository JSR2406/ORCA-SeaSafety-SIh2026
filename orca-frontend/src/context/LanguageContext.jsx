'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { translations, SUPPORTED_LANGUAGES } from '../data/translations';

const LanguageContext = createContext({
  language: 'en',
  setLanguage: () => {},
  t: (key, fallback) => fallback || key,
  languages: SUPPORTED_LANGUAGES,
  currentLangMeta: SUPPORTED_LANGUAGES[0],
});

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState('en');
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    try {
      const saved = localStorage.getItem('orca-app-lang');
      if (saved && translations[saved.toLowerCase()]) {
        setLanguageState(saved.toLowerCase());
        document.documentElement.lang = saved.toLowerCase();
      }
    } catch (e) {
      console.warn('Unable to retrieve stored language:', e);
    }
  }, []);

  const setLanguage = useCallback((code) => {
    const normalized = (code || 'en').toLowerCase();
    if (translations[normalized]) {
      setLanguageState(normalized);
      try {
        localStorage.setItem('orca-app-lang', normalized);
        document.documentElement.lang = normalized;
      } catch (e) {
        console.warn('Unable to persist language:', e);
      }
    }
  }, []);

  // Safe dot-notation lookup resolver
  const t = useCallback((path, fallback = '') => {
    if (!path) return fallback;

    const resolveKey = (dict, keyPath) => {
      if (!dict) return undefined;
      const parts = keyPath.split('.');
      let current = dict;
      for (const part of parts) {
        if (current && typeof current === 'object' && part in current) {
          current = current[part];
        } else {
          return undefined;
        }
      }
      return current;
    };

    // 1. Try active language
    const val = resolveKey(translations[language], path);
    if (val !== undefined && typeof val === 'string') {
      return val;
    }

    // 2. Fallback to English
    const enVal = resolveKey(translations.en, path);
    if (enVal !== undefined && typeof enVal === 'string') {
      return enVal;
    }

    // 3. Fallback to user fallback or key
    return fallback || path;
  }, [language]);

  const currentLangMeta = SUPPORTED_LANGUAGES.find((l) => l.code === language) || SUPPORTED_LANGUAGES[0];

  return (
    <LanguageContext.Provider
      value={{
        language,
        setLanguage,
        t,
        languages: SUPPORTED_LANGUAGES,
        currentLangMeta,
        mounted,
      }}
    >
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error('useLanguage must be used within a LanguageProvider');
  }
  return context;
}
