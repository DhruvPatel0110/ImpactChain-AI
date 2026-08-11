/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        globe: {
          bg: '#050814',
          accent: '#3b82f6',
        }
      }
    },
  },
  plugins: [],
}
