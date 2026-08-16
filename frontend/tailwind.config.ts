import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: ['./src/**/*.{js,ts,jsx,tsx,mdx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#f0f3ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#93a4ff',
          400: '#6b7dff',
          500: '#4d65ff',
          600: '#4d65ff',
          700: '#3b4bf2',
          800: '#2d39d5',
          900: '#1c2282',
        },
        yoyaba: {
          indigo: '#4d65ff',
          yellow: '#FFD600',
          cyan: '#00FFFF',
          dark: '#0d0e12',
          glow: '#0f2a36',
          border: '#303E44',
        },
        status: {
          pending: '#f59e0b',
          success: '#10b981',
          failed: '#ef4444',
          skipped: '#6b7280',
        },
      },
      fontFamily: {
        sans: ['Mulish', 'ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        display: ['Bebas Neue', 'ui-sans-serif', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      fontSize: {
        'xs': '0.85rem',
        'sm': '0.95rem',
        'base': '1.1rem',
        'lg': '1.25rem',
        'xl': '1.4rem',
      },
      fontWeight: {
        normal: '600',
        medium: '700',
        semibold: '800',
        bold: '900',
      },
    },
  },
  plugins: [],
};

export default config;
