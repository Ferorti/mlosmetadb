/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        ink:       '#16181C',
        ink2:      '#4A4E55',
        ink3:      '#4E5762',
        muted:     '#5F6874',
        navy:      '#0E2136',
        brand:     '#1560A8',
        surface:   '#FFFFFF',
        page:      '#F7F9FC',
        border: {
          strong:  '#D2D9E3',
          DEFAULT: '#DFE4EC',
          soft:    '#E9EDF4',
        },
        track:     '#E8ECF3',
        feature: {
          idr:     '#B8362B',
          domain:  '#2C7A6B',
          lcd:     '#98A2B3',
          morf:    '#6B4E8F',
        },
        // Kept as-is from the pre-redesign palette (RoleBadge.vue), not
        // part of the document's 4-color feature encoding -- a distinct
        // axis (protein role), already AA-verified against its own
        // #F6EFE4 background. See spec §1.3.
        regulator: '#854F0B',
      },
      fontFamily: {
        sans:    ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono:    ['"IBM Plex Mono"', 'ui-monospace', 'monospace'],
        display: ['Archivo', '"IBM Plex Sans"', 'ui-sans-serif', 'sans-serif'],
      },
    }
  },
  plugins: []
}
