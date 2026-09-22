'use client';

import React from 'react';
import dynamic from 'next/dynamic';

const MarineMapInternal = dynamic(() => import('./MarineMap'), {
  ssr: false,
  loading: () => (
    <div
      className="leaflet-map-canvas"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'var(--c-surface, #0a131f)',
        color: 'var(--c-text-muted, #8397a7)',
        fontFamily: 'var(--font-mono, monospace)',
        fontSize: '12px',
        minHeight: '350px'
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <span
          style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: 'var(--th-accent-cyan, #48cae4)',
            boxShadow: '0 0 8px var(--th-accent-cyan, #48cae4)',
            animation: 'pulse 1.5s infinite ease-in-out'
          }}
        />
        <span>Initializing Navigational Hydrographic Engine...</span>
      </div>
    </div>
  )
});

export default function DynamicMarineMap(props) {
  return <MarineMapInternal {...props} />;
}
