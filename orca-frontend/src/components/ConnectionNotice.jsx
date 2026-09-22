'use client';

import Link from 'next/link';
import { Radio, ArrowUpRight, LoaderCircle } from 'lucide-react';
import { useBackend } from '../context/BackendContext';

export const ConnectionNotice = () => {
  const { isBackendLive, isChecking } = useBackend();
  return (
    <div className={`ocean-connection ${isBackendLive ? 'is-connected' : ''}`} role="status" data-testid="connection-notice">
      {isChecking ? <LoaderCircle size={13} className="ocean-spin" /> : <Radio size={13} />}
      <span data-testid="connection-notice-text">{isChecking ? 'Checking data connection…' : isBackendLive ? 'API connected. Check individual source freshness before making decisions.' : 'Preview mode · Live services unavailable. Sample data is not for navigation.'}</span>
      <Link href="/system-health" data-testid="connection-details-link">Data status <ArrowUpRight size={12} /></Link>
    </div>
  );
};