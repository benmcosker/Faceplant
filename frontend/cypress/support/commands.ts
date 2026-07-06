/// <reference types="cypress" />

// Visit the app already "logged in" as `username`. Identity is just a value in
// localStorage (there is no real auth — see the README), so seeding it before
// the app script runs drops us straight onto the feed instead of the gate.
Cypress.Commands.add('visitAs', (username: string, path = '/') => {
  cy.visit(path, {
    onBeforeLoad(win) {
      win.localStorage.setItem('faceplant:username', username)
    },
  })
})

declare global {
  namespace Cypress {
    interface Chainable {
      visitAs(username: string, path?: string): Chainable<void>
    }
  }
}

export {}
