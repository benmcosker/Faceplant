/// <reference types="cypress" />

// Exercises the two-tier API-failure treatment (see the README): a blocking
// load failure renders a retryable inline error; a non-blocking action failure
// surfaces a toast while leaving the view intact.

describe('API failures', () => {
  it('shows a retryable error when the feed fails, and recovers on "Try again"', () => {
    cy.intercept('GET', '/api/posts*', { statusCode: 500, body: { error: 'feed exploded' } }).as('feedFail')

    cy.visitAs('maya')
    cy.wait('@feedFail')

    cy.contains("Couldn't load the feed")
    cy.contains('feed exploded')

    // The retry re-runs the request; stub it to succeed this time.
    cy.intercept('GET', '/api/posts*', { fixture: 'feed.json' }).as('feedOk')
    cy.contains('button', 'Try again').click()
    cy.wait('@feedOk')

    cy.contains('switched to oat milk')
    cy.contains('Try again').should('not.exist')
  })

  it('recovers from an unreachable server (network error) on retry', () => {
    cy.intercept('GET', '/api/posts*', { forceNetworkError: true }).as('feedDown')

    cy.visitAs('maya')
    cy.wait('@feedDown')
    cy.contains("Can't reach the server.")

    cy.intercept('GET', '/api/posts*', { fixture: 'feed.json' }).as('feedOk')
    cy.contains('button', 'Try again').click()
    cy.wait('@feedOk')
    cy.contains('switched to oat milk')
  })

  it('surfaces a failed like as a toast without tearing down the feed', () => {
    cy.intercept('GET', '/api/posts*', { fixture: 'feed.json' }).as('feed')
    cy.intercept('POST', '/api/posts/*/like', { statusCode: 500, body: { error: 'like failed' } }).as('like')

    cy.visitAs('maya')
    cy.wait('@feed')

    cy.contains('.MuiCard-root', 'switched to oat milk').within(() => {
      cy.contains('button', '5').click()
    })

    cy.wait('@like')
    cy.contains('like failed') // the toast
    cy.contains('switched to oat milk') // feed is still there
  })
})

export {}
