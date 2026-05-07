/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        brand: {
          blue:  '#185FA5',
          green: '#3B6D11',
          amber: '#854F0B',
          teal:  '#0F6E56',
        }
      }
    }
  },
  plugins: []
}
