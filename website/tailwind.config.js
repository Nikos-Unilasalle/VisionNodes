/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-main':    'var(--bg-main)',
        'bg-alt':     'var(--bg-alt)',
        'bg-card':    'var(--bg-card)',
        'bg-dark':    'var(--bg-dark)',
        main:         'var(--text-main)',
        dim:          'var(--text-dim)',
        xdim:         'var(--text-xdim)',
        accent:       'var(--accent)',
        'accent-dark':'var(--accent-dark)',
        'accent-light':'var(--accent-light)',
        border:       'var(--border)',

        // Node / Wire colors
        'port-image':   'var(--port-image)',
        'port-scalar':  'var(--port-scalar)',
        'port-vector':  'var(--port-vector)',
        'port-boolean': 'var(--port-boolean)',
        'port-string':  'var(--port-string)',
        'port-dict':    'var(--port-dict)',
        'port-any':     'var(--port-any)',

        // Category colors
        'cat-src':      'var(--cat-src)',
        'cat-cv':       'var(--cat-cv)',
        'cat-math':     'var(--cat-math)',
        'cat-logic':    'var(--cat-logic)',
        'cat-util':     'var(--cat-util)',
        'cat-track':    'var(--cat-track)',
        'cat-features': 'var(--cat-features)',
        'cat-analysis': 'var(--cat-analysis)',
        'cat-draw':     'var(--cat-draw)',
        'cat-out':      'var(--cat-out)',
        'cat-mask':     'var(--cat-mask)',
        'cat-geom':     'var(--cat-geom)',
        'cat-blend':    'var(--cat-blend)',
        'cat-strings':  'var(--cat-strings)',
        'cat-noise':    'var(--cat-noise)',
        'cat-ocr':      'var(--cat-ocr)',
        'cat-data':     'var(--cat-data)',
        'cat-visualize':'var(--cat-visualize)',
        'cat-canvas':   'var(--cat-canvas)',
      },
      fontFamily: {
        sans:     ['"Nunito Sans"', 'sans-serif'],
        headings: ['Rubik', 'sans-serif'],
        mono:     ['"JetBrains Mono"', '"Fira Code"', 'monospace'],
      },
    },
  },
  plugins: [],
}
