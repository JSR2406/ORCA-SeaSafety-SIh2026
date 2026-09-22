/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
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
    const backendUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/v1/:path*',
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
