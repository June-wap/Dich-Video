import { defineConfig } from 'vitest/config'

// Kept separate from vite.config.ts: vitest@3.2.7's config typing resolves
// against Vite 7's Plugin type, while this app's own Vite is 8.3.0, so
// importing defineConfig from 'vitest/config' inside the application's own
// vite.config.ts (which needs the real @vitejs/plugin-react Plugin from
// Vite 8) produced a Plugin-type conflict at `plugins: [react()]`. A
// dedicated vitest.config.ts avoids the conflict entirely: Vitest picks
// this file up automatically (before falling back to vite.config.ts), and
// it doesn't need the React/Vite plugin - esbuild's default JSX transform
// (per tsconfig's "jsx": "react-jsx") is enough for the test files.
export default defineConfig({
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: false,
  },
})
