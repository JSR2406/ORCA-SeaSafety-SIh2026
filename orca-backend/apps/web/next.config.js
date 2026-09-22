/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ['@floatchat/shared-types'],
  experimental: {
    optimizePackageImports: ['lucide-react', 'recharts'],
  },
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '*.supabase.co' },
      { protocol: 'https', hostname: '*.vercel-storage.com' },
    ],
  },
  async rewrites() {
    return [
      { source: '/api/backend/:path*', destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/:path*` },
    ];
  },
};

module.exports = nextConfig;