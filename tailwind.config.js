/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        surface: "var(--surface)",
        primary: "var(--primary)",
        "action-blue": "var(--action-blue)",
        "pure-white": "var(--pure-white)",
        "pure-black": "var(--pure-black)",
        "near-black": "var(--near-black)",
        parchment: "var(--parchment)",
        main: "var(--text-main)",
        dim: "var(--text-dim)",
        "vns-border": "var(--border)",
        divider: "var(--divider)",
      },
    },
  },
  plugins: [],
}
