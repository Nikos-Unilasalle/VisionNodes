/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#181818",
        surface: "#242424",
        primary: "#3a3a3a",
        accent: "#3b82f6",
      },
    },
  },
  plugins: [],
}
