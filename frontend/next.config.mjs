/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: ["picsum.photos", "source.unsplash.com"], // Add any other domains here
  },
  async rewrites() {
    return [
      {
        source: '/api/auth/:path*',
        destination: 'http://127.0.0.1:5328/auth/:path*', // Proxy to Flask backend
      },
    ];
  },
};

export default nextConfig;
