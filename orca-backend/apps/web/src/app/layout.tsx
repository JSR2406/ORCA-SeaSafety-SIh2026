import type { Metadata, Viewport } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Providers } from './providers';

const inter = Inter({ subsets: ['latin'], variable: '--font-inter' });

export const metadata: Metadata = {
  title: 'FloatChat — Ask the Ocean, in Your Language',
  description: 'Voice-first, multilingual, explainable AI interface for ARGO ocean data',
  keywords: ['ARGO', 'ocean data', 'oceanography', 'marine science', 'voice AI', 'multilingual'],
  authors: [{ name: 'FloatChat Team' }],
  creator: 'FloatChat',
  publisher: 'FloatChat',
  robots: 'index, follow',
  openGraph: {
    type: 'website',
    locale: 'en_IN',
    url: 'https://floatchat.example.com',
    title: 'FloatChat — Ask the Ocean, in Your Language',
    description: 'Voice-first, multilingual, explainable AI interface for ARGO ocean data',
    siteName: 'FloatChat',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'FloatChat — Ask the Ocean, in Your Language',
    description: 'Voice-first, multilingual, explainable AI interface for ARGO ocean data',
  },
  viewport: 'width=device-width, initial-scale=1',
};

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#0c4a6e' },
  ],
  width: 'device-width',
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} antialiased`}>
      <head>
        <link rel="preconnect" href="https://api.maptiler.com" />
        <link rel="preconnect" href="https://tiles.maptiler.com" />
      </head>
      <body className="min-h-screen bg-background font-sans">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}