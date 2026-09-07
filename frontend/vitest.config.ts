import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    // Playwright specs live in e2e/ and are driven by Playwright, not Vitest.
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
  },
})
