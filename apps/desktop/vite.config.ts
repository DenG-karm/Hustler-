/// <reference types="vitest" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react()],
  build: {
    target: 'es2022',
    minify: 'terser',
    terserOptions: {
      ecma: 2020,
      module: true,
      toplevel: true,
      compress: {
        drop_console: true,
        drop_debugger: true,
        passes: 2,
        unsafe_comps: true,
        pure_getters: true,
        unsafe: true,
        unsafe_arrows: true,
        unsafe_methods: true,
        unsafe_math: true,
        unsafe_undefined: true,
        unsafe_proto: true,
        dead_code: true,
        booleans_as_integers: true,
        keep_fargs: false,
        toplevel: true,
        inline: false,
      },
      mangle: {
        toplevel: true,
        properties: false,
      },
      format: {
        comments: false,
      },
    },
    rollupOptions: {
      treeshake: true,
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    fileParallelism: false,
    pool: 'forks',
    isolate: true,
    testTimeout: 30000,
  },
})
