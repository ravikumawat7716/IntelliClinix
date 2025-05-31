'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    // Check if user is authenticated (has token in localStorage)
    const token = localStorage.getItem('token');
    const username = localStorage.getItem('username');

    if (token && username) {
      // If authenticated, redirect to dashboard
      router.push('/dashboard');
    } else {
      // If not authenticated, redirect to login
      router.push('/login');
    }
  }, [router]);

  // Return null or loading state while redirecting
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
    </div>
  );
}