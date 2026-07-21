/// <reference types="cypress" />

// Visit the app already "logged in" as `username`. Identity is a magic-link
// session cookie the app checks via GET /api/auth/me on load — stubbing that
// to succeed drops us straight onto the feed instead of the email gate.
Cypress.Commands.add('visitAs', (username: string, path = '/') => {
  cy.intercept('GET', '/api/auth/me', {
    statusCode: 200,
    body: { id: 999, username, avatar_url: `/media/avatars/${username}.png`, is_bot: false },
  }).as('me')
  cy.visit(path)
  cy.wait('@me')
})

declare global {
  namespace Cypress {
    interface Chainable {
      visitAs(username: string, path?: string): Chainable<void>
    }
  }
}

export {}
