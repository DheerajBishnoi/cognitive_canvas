/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Google Sans"', 'Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        surface: '#f8f9fa',
        surfaceCard: '#ffffff',
        accent: '#1a73e8',
        accentHover: '#1765cc',
        accentLight: '#e8f0fe',
        accentText: '#1967d2',
        textPrimary: '#202124',
        textSecondary: '#5f6368',
        textTertiary: '#80868b',
        borderLight: '#dadce0',
        borderFocus: '#1a73e8',
        tagBg: '#e8eaed',
        tagText: '#3c4043',
        successBg: '#e6f4ea',
        successText: '#137333',
        warningBg: '#fef7e0',
        warningText: '#b06000',
        dangerBg: '#fce8e6',
        dangerText: '#c5221f',
      },
      boxShadow: {
        card: '0 1px 2px 0 rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15)',
        cardHover: '0 1px 3px 0 rgba(60,64,67,0.3), 0 4px 8px 3px rgba(60,64,67,0.15)',
        sidebar: '-2px 0 8px rgba(60,64,67,0.15)',
      },
      borderRadius: {
        card: '12px',
      },
    },
  },
  plugins: [],
}
