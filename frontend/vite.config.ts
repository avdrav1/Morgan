import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: true,
    port: 5173,
    watch: {
      usePolling: true,
    },
  },
  build: {
    // Production build optimizations
    minify: 'esbuild',
    target: 'es2015',
    cssMinify: true,
    
    // Code splitting for better caching
    rollupOptions: {
      output: {
        manualChunks: {
          // Vendor chunk for React and related libraries
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          // Separate chunk for UI libraries
          'ui-vendor': ['lucide-react', 'date-fns'],
          // Separate chunk for data fetching
          'data-vendor': ['axios', '@tanstack/react-query'],
        },
        // Use content hash for better caching
        chunkFileNames: 'assets/[name]-[hash].js',
        entryFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash].[ext]',
      },
    },
    
    // Optimize chunk size
    chunkSizeWarningLimit: 1000,
    
    // Source maps for production debugging (optional, can be disabled)
    sourcemap: false,
    
    // Report compressed size
    reportCompressedSize: true,
  },
})
