import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: ['class'],
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // shadcn semantic tokens — hex so opacity modifiers work
        background:  '#000000',
        foreground:  '#F5F5F5',
        card:        { DEFAULT: '#0D0D0D', foreground: '#F5F5F5' },
        popover:     { DEFAULT: '#0D0D0D', foreground: '#F5F5F5' },
        primary:     { DEFAULT: '#C9922A', foreground: '#000000' },
        secondary:   { DEFAULT: '#1A1A1A', foreground: '#F5F5F5' },
        muted:       { DEFAULT: '#1A1A1A', foreground: '#888888' },
        accent:      { DEFAULT: '#1A1A1A', foreground: '#C9922A' },
        destructive: { DEFAULT: '#E05252', foreground: '#F5F5F5' },
        border:      '#2A2A2A',
        input:       '#1A1A1A',
        ring:        '#C9922A',

        // stoX design tokens
        golden:  { DEFAULT: '#C9922A', muted: '#8A6420' },
        jade:    { DEFAULT: '#3DAA6E', muted: '#2A7A4E' },
        surface: { DEFAULT: '#0D0D0D', 2: '#1A1A1A' },
        danger:  '#E05252',
      },
      borderRadius: {
        lg: '0.5rem',
        md: 'calc(0.5rem - 2px)',
        sm: 'calc(0.5rem - 4px)',
      },
      fontFamily: {
        sans: ['var(--font-geist-sans)', 'sans-serif'],
        mono: ['var(--font-geist-mono)', 'monospace'],
      },
    },
  },
  plugins: [],
};

export default config;
