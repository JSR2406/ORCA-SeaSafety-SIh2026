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
    const backendUrl = process.env.ORCA_API_UPSTREAM || process.env.NEXT_PUBLIC_API_URL;
    if (!backendUrl) return [];
    return [
      {
        source: '/api/v1/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
