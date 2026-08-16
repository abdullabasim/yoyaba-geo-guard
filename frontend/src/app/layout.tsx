import type { Metadata } from 'next';

import './globals.css';

export const metadata: Metadata = {
  title: {
    default: 'YOYABA GEO & IntentShift Guard',
    template: '%s | YOYABA GEO'
  },
  description:
    'Automated Generative Engine Optimization (GEO) & Search Intent-Shift Detection Engine built for YOYABA B2B Growth Engineering.',
  keywords: ['SEO', 'GEO', 'Generative Engine Optimization', 'Intent Shift', 'Search Intent', 'YOYABA', 'B2B Growth', 'Rank Tracking'],
  authors: [{ name: 'YOYABA Growth Engineering', url: 'https://yoyaba.com' }],
  creator: 'YOYABA',
  publisher: 'YOYABA',
  formatDetection: {
    email: false,
    address: false,
    telephone: false,
  },
  metadataBase: new URL('https://yoyaba.com'),
  alternates: {
    canonical: '/',
  },
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: {
      index: false,
      follow: false,
      noimageindex: true,
      'max-video-preview': -1,
      'max-image-preview': 'large',
      'max-snippet': -1,
    },
  },
  openGraph: {
    title: 'YOYABA GEO & IntentShift Guard',
    description: 'Automated Generative Engine Optimization (GEO) & Search Intent-Shift Detection Engine.',
    url: 'https://yoyaba.com',
    siteName: 'YOYABA GEO Guard',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'YOYABA GEO & IntentShift Guard',
      },
    ],
    locale: 'en_US',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'YOYABA GEO & IntentShift Guard',
    description: 'Automated Generative Engine Optimization & Search Intent-Shift Detection Engine.',
    creator: '@yoyaba',
    images: ['/og-image.png'],
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=Mulish:wght@400;500;600;700;800;900&family=Bebas+Neue&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
