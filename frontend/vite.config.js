import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:5001',
      '/register': 'http://127.0.0.1:5001',
      '/login': 'http://127.0.0.1:5001',
      '/predict': 'http://127.0.0.1:5001',
      '/chat': 'http://127.0.0.1:5001',
      '/history': 'http://127.0.0.1:5001',
      '/user-loans': 'http://127.0.0.1:5001',
      '/admin-data': 'http://127.0.0.1:5001',
    },
  },
});
