import React from 'react';
import 'leaflet/dist/leaflet.css';
import '../styles.css';
import '../ocean-system.css';
import '../landing.css';
import '../simple-dashboard.css';
import { ThemeProvider } from '../context/ThemeContext';
import { LanguageProvider } from '../context/LanguageContext';
import { BackendProvider } from '../context/BackendContext';
import { UserRoleProvider } from '../context/UserRoleContext';

export const metadata = {
  title: 'ORCA — Ocean Reasoning with Collaborative Agent',
  description: 'National Maritime Operational Decision Support System for Oceanographic Analysis, Navigational Safety, and Potential Fishing Zones (INCOIS, IMD, NAVAREA VIII).',
  icons: {
    icon: '/logo.png',
    shortcut: '/logo.png',
    apple: '/logo.png',
  },
};

export const viewport = {
  width: 'device-width',
  initialScale: 1.0,
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" data-theme="ocean-depths" data-scroll-behavior="smooth" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var t = localStorage.getItem('orca-app-theme') || localStorage.getItem('orca-landing-theme') || 'ocean-depths';
                  document.documentElement.setAttribute('data-theme', t);
                  var l = localStorage.getItem('orca-app-lang') || 'en';
                  document.documentElement.setAttribute('lang', l);
                } catch (e) {}
              })();
            `,
          }}
        />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;450;500;550;600;650;700&family=Outfit:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <LanguageProvider>
          <ThemeProvider>
            <BackendProvider>
              <UserRoleProvider>
                {children}
              </UserRoleProvider>
            </BackendProvider>
          </ThemeProvider>
        </LanguageProvider>
      </body>
    </html>
  );
}
