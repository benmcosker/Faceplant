/// <reference types="cypress" />

describe('feed', () => {
  it('renders the posts returned by the API', () => {
    cy.intercept('GET', '/api/posts*', { fixture: 'feed.json' }).as('feed')

    cy.visitAs('maya')
    cy.wait('@feed')

    cy.contains('switched to oat milk')
    cy.contains('anyone else think the new update is broken?')
    cy.contains('jordan')
  })

  it('shows skeleton placeholders while the feed is loading', () => {
    cy.intercept('GET', '/api/posts*', { fixture: 'feed.json', delay: 500 }).as('feed')

    cy.visitAs('maya')
    cy.get('[role="status"][aria-label="Loading posts"]').should('exist')

    cy.wait('@feed')
    cy.contains('switched to oat milk')
    cy.get('[aria-label="Loading posts"]').should('not.exist')
  })

  it('shows an empty state when there are no posts', () => {
    cy.intercept('GET', '/api/posts*', { statusCode: 200, body: [] }).as('feed')

    cy.visitAs('maya')
    cy.wait('@feed')
    cy.contains('No posts yet. Be the first.')
  })
})

export {}
