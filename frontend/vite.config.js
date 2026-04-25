import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:5000',
      '/register': 'http://127.0.0.1:5000',
      '/login': 'http://127.0.0.1:5000',
      '/predict': 'http://127.0.0.1:5000',
      '/chat': 'http://127.0.0.1:5000',
      '/history': 'http://127.0.0.1:5000',
      '/user-loans': 'http://127.0.0.1:5000',
      '/admin-data': 'http://127.0.0.1:5000',
    },
  },
});
