/** @type {import('next').NextConfig} */
const defaultDevOrigins = ['127.0.0.1', 'localhost', '*.preview.emergentagent.com', '**.preview.emergentcf.cloud'];
const envDevOrigins = (process.env.ORCA_DEV_ORIGINS || '')
  .split(',')
  .map((value) => value.trim())
  .filter(Boolean);

const nextConfig = {
  reactStrictMode: true,
  devIndicators: false,
  allowedDevOrigins: Array.from(new Set([...defaultDevOrigins, ...envDevOrigins])),
  poweredByHeader: false,
  env: {
    NEXT_PUBLIC_GOOGLE_MAPS_API_KEY:
      process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY ||
      process.env.VITE_GOOGLE_MAPS_API_KEY ||
      '',
  },
  async headers() {
    return [
      {
        source: '/:path*',
        headers: [
          { key: 'X-Content-Type-Options', value: 'nosniff' },
          { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
          { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
          { key: 'Strict-Transport-Security', value: 'max-age=31536000; includeSubDomains' },
          { key: 'Permissions-Policy', value: 'camera=(), geolocation=(self), microphone=(self)' },
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://maps.googleapis.com https://static.cloudflareinsights.com",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' data: https://fonts.gstatic.com",
              "img-src 'self' data: blob: https:",
              "media-src 'self' data: blob: https:",
              "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 ws://localhost:8000 https: wss:",
              "frame-ancestors 'self'",
              "object-src 'none'",
              "base-uri 'self'"
            ].join('; ')
          }
        ]
      }
    ];
  },
  async redirects() {
    return [
      {
        source: '/marine-explorer',
        destination: '/marine-map',
        permanent: true,
      },
      {
        source: '/mobile-view',
        destination: '/mobile',
        permanent: true,
      },
      {
        source: '/route-planner',
        destination: '/routes',
        permanent: true,
      },
      {
        source: '/scenario-lab',
        destination: '/scenarios',
        permanent: true,
      },
      {
        source: '/knowledge-center',
        destination: '/knowledge',
        permanent: true,
      },
    ];
  },
  async rewrites() {
    const backendUrl = process.env.ORCA_API_UPSTREAM || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/v1/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
