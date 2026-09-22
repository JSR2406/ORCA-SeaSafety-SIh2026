import React from 'react';

export default function Badge({ children, tone = 'blue', color, dot = true }) {
  const finalTone = color || tone;
  return (
    <span className={`badge badge-${finalTone}`}>
      {dot && <span className={`badge-dot dot-${finalTone}`} />}
      {children}
    </span>
  );
}
