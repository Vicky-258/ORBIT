import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import orbitApiPlugin from './vite-plugin-orbit-api.js';

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    orbitApiPlugin(),
  ],
  server: {
    port: 3000,
    host: '0.0.0.0',
  },
});
