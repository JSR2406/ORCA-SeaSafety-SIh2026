'use client';

import React from 'react';
import { motion } from 'framer-motion';

export default function PageWrapper({ children, className = '' }) {
  return (
    <motion.div
      initial={false}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      className={`page-transition-wrapper ${className}`}
      data-testid="page-content"
      style={{ width: '100%' }}
    >
      {children}
    </motion.div>
  );
}
