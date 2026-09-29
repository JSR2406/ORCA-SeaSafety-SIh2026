'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Radio, ArrowUpRight, LoaderCircle } from 'lucide-react';
import { useBackend } from '../context/BackendContext';

export const ConnectionNotice = () => {
  const { isBackendLive, isChecking } = useBackend();
  const pathname = usePathname();

  // Never show the preview/offline notice on the dashboard —
  // the dashboard showcases IMD + INCOIS prototype integrations inline instead.
  if (pathname === '/dashboard' || pathname?.startsWith('/dashboard')) {
    return null;
  }

  return (
    <div className={`ocean-connection ${isBackendLive ? 'is-connected' : ''}`} role="status" data-testid="connection-notice">
      {isChecking ? <LoaderCircle size={13} className="ocean-spin" /> : <Radio size={13} />}
      <span data-testid="connection-notice-text">{isChecking ? 'Checking data connection…' : isBackendLive ? 'API connected · IMD + INCOIS feeds live. Check individual source freshness before making decisions.' : 'OFFLINE FALLBACK active · live-direct telemetry where reachable, climatology otherwise. Full fusion resumes on reconnect.'}</span>
      <Link href="/system-health" data-testid="connection-details-link">Data status <ArrowUpRight size={12} /></Link>
    </div>
  );
};