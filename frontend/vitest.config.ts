import { defineConfig } from 'vitest/config'

export default defineConfig({
  // Use the automatic JSX runtime (no `import React` needed).
  esbuild: { jsx: 'automatic', jsxImportSource: 'react' },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    css: false,
    // Inline these so jsdom can resolve MUI's ESM transition imports.
    server: {
      deps: {
        inline: [/@mui\//, /react-transition-group/],
      },
    },
  },
})
