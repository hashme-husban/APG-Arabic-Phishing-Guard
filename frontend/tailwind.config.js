/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        apg: {
          bg: '#07111C',
          sidebar: '#08131F',
          panel: '#0D1724',
          card: '#111827',
          cardSoft: '#101B2A',
          elevated: '#151F2E',
          border: 'rgba(148, 163, 184, 0.14)',
          borderStrong: 'rgba(148, 163, 184, 0.24)',
          muted: '#94A3B8',
          cyan: '#22D3EE',
          blue: '#38BDF8',
          purple: '#8B5CF6',
          green: '#22C55E',
          yellow: '#FACC15',
          red: '#FB7185'
        }
      },
      boxShadow: {
        glow: '0 0 18px rgba(34, 211, 238, 0.10)'
      }
    }
  },
  plugins: []
};
