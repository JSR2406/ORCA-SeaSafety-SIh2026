'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { checkBackendHealth } from '../services/apiClient';

const BackendContext = createContext({
  isBackendLive: false,
  latencyMs: 0,
  backendInfo: { status: 'offline', database: 'disconnected', version: '0.1.0' },
  isChecking: false,
  recheckBackend: async () => {},
});

export function BackendProvider({ children }) {
  const [isBackendLive, setIsBackendLive] = useState(false);
  const [latencyMs, setLatencyMs] = useState(0);
  const [backendInfo, setBackendInfo] = useState({
    status: 'offline',
    database: 'disconnected',
    version: '0.1.0'
  });
  const [isChecking, setIsChecking] = useState(true);

  const recheckBackend = useCallback(async () => {
    setIsChecking(true);
    try {
      const res = await checkBackendHealth();
      setIsBackendLive(res.isLive);
      setLatencyMs(res.latencyMs);
      setBackendInfo({
        status: res.status,
        database: res.database,
        version: res.version,
        timestamp: res.timestamp
      });
    } catch (e) {
      setIsBackendLive(false);
      setLatencyMs(0);
      setBackendInfo({
        status: 'offline',
        database: 'disconnected',
        version: '0.1.0'
      });
    } finally {
      setIsChecking(false);
    }
  }, []);

  useEffect(() => {
    recheckBackend();
    // Poll backend health every 30 seconds
    const interval = setInterval(recheckBackend, 30000);
    return () => clearInterval(interval);
  }, [recheckBackend]);

  return (
    <BackendContext.Provider
      value={{
        isBackendLive,
        latencyMs,
        backendInfo,
        isChecking,
        recheckBackend
      }}
    >
      {children}
    </BackendContext.Provider>
  );
}

export function useBackend() {
  return useContext(BackendContext);
}
