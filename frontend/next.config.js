/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // No rewrites needed - frontend connects directly to backend via NEXT_PUBLIC_BACKEND_URL env var
};

module.exports = nextConfig;
