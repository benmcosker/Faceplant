import { defineConfig } from 'cypress'

export default defineConfig({
  e2e: {
    // The Vite dev server (see `npm run dev`). The `e2e` script boots it first.
    baseUrl: 'http://localhost:5174',
    specPattern: 'cypress/e2e/**/*.cy.ts',
    supportFile: 'cypress/support/e2e.ts',
    fixturesFolder: 'cypress/fixtures',
    // The suite stubs the backend with cy.intercept(), so no artifacts are
    // needed to debug real network calls.
    video: false,
    screenshotOnRunFailure: false,
  },
})
