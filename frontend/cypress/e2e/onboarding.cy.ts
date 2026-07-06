/// <reference types="cypress" />

// The identity gate: claim/look up a username, then post. There is no real
// auth — a known username just means "post as that person again".

const maya = { id: 1, username: 'maya', avatar_url: '/media/avatars/maya.png', is_bot: false }

function stubCreatePost(author: typeof maya) {
  cy.intercept('POST', '/api/posts', {
    statusCode: 200,
    body: {
      id: 99,
      body: 'hello there',
      created_at: '2026-07-06T12:00:00Z',
      author,
      like_count: 0,
      comment_count: 0,
    },
  }).as('createPost')
  // The feed the app loads immediately after identity resolves.
  cy.intercept('GET', '/api/posts*', { statusCode: 200, body: [] }).as('feed')
}

describe('onboarding', () => {
  it('sends a returning username straight to posting, then lands on the feed', () => {
    cy.intercept('GET', '/api/users/*', { statusCode: 200, body: maya }).as('lookup')
    stubCreatePost(maya)

    cy.visit('/')
    cy.get('input').type('maya')
    cy.contains('button', 'Continue').click()

    cy.wait('@lookup')
    cy.contains('Welcome back')
    cy.get('textarea').first().type('hello there')
    cy.contains('button', 'Post').click()

    cy.wait('@createPost')
    // AppShell only shows "Switch user" once an identity is set — i.e. on the feed.
    cy.contains('Switch user').should('be.visible')
  })

  it('claims a brand-new username with an avatar and a first post', () => {
    cy.intercept('GET', '/api/users/*', { statusCode: 404, body: { error: 'not found' } }).as('lookup')
    cy.intercept('POST', '/api/users', {
      statusCode: 200,
      body: { id: 2, username: 'newbie', avatar_url: '/media/avatars/newbie.png', is_bot: false },
    }).as('claim')
    stubCreatePost({ id: 2, username: 'newbie', avatar_url: '/media/avatars/newbie.png', is_bot: false })

    cy.visit('/')
    cy.get('input').type('newbie')
    cy.contains('button', 'Continue').click()

    cy.wait('@lookup')
    cy.contains('is new')
    cy.get('input[type="file"]').selectFile(
      { contents: Cypress.Buffer.from('not-a-real-png'), fileName: 'avatar.png', mimeType: 'image/png' },
      { force: true },
    )
    cy.get('textarea').first().type('hello there')
    cy.contains('button', 'Post').click()

    cy.wait('@claim')
    cy.wait('@createPost')
    cy.contains('Switch user').should('be.visible')
  })

  it('surfaces a lookup failure inline without leaving the gate', () => {
    cy.intercept('GET', '/api/users/*', { statusCode: 500, body: { error: 'lookup exploded' } }).as('lookup')

    cy.visit('/')
    cy.get('input').type('maya')
    cy.contains('button', 'Continue').click()

    cy.wait('@lookup')
    cy.contains('lookup exploded')
    // Still on the gate — the username field is present.
    cy.contains('button', 'Continue').should('be.visible')
  })
})

export {}
