 /** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        base:     'var(--color-base)',
        surface:  'var(--color-surface)',
        elevated: 'var(--color-elevated)',

        accent: {
          DEFAULT: 'var(--color-accent)',
          hover:   'var(--color-accent-hover)',
          subtle:  'var(--color-accent-subtle)',
        },

        success: 'var(--color-success)',
        warning: 'var(--color-warning)',
        danger:  'var(--color-danger)',
        'danger-surface': 'var(--color-danger-surface)',
        'danger-border':  'var(--color-danger-border)',

        ink: {
          primary:   'var(--color-ink-primary)',
          secondary: 'var(--color-ink-secondary)',
          muted:     'var(--color-ink-muted)',
          faint:     'var(--color-ink-faint)',
        },

        line: {
          DEFAULT: 'var(--color-line)',
          strong:  'var(--color-line-strong)',
        },
      },
    },
  },
  plugins: [],
}