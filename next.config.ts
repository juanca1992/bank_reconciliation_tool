import type {NextConfig} from 'next';

const nextConfig: NextConfig = {
  /* config options here */
  typescript: {
    ignoreBuildErrors: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'picsum.photos',
        port: '',
        pathname: '/**',
      },
    ],
  },
  allowedDevOrigins: [
    "localhost:8000",
    "9000-idx-studio-1746226524199.cluster-ux5mmlia3zhhask7riihruxydo.cloudworkstations.dev",
  ],
  // Make environment variables available to the client-side bundle
  // Only variables prefixed with NEXT_PUBLIC_ are exposed
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },
};

export default nextConfig;
